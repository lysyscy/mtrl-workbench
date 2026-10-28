"""Real DOM geometry tests for the collector, without an HTTP application or database."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dev import frontend_layout as layout


def grid(*, width=200, hidden=True, state='ready'):
    return f'''<section data-layout-state="{state}"><div class="ag-root-wrapper" style="width:400px;height:160px">
    <div class="ag-header-cell" col-id="amount" style="width:100px;height:20px">金额</div>
    <div class="ag-row" row-id="1"><div class="ag-cell" col-id="amount" style="width:100px;white-space:nowrap;overflow:hidden">100.00</div></div>
    <div class="ag-body-horizontal-scroll-viewport" style="width:200px;height:20px;overflow:hidden"><div style="width:{width}px;height:1px"></div></div>
    <div class="ag-body-horizontal-scroll" {'hidden' if hidden else ''} style="width:200px;height:12px"></div>
    </div></section>'''


def document(content):
    return '''<html style="--fscale:1.12"><body style="margin:0"><h1 id="page-title">测试页</h1>
    <div class="page-view" style="width:500px;min-height:20px">''' + content + '</div></body></html>'


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == 'win32':
            os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'C:/ProgramData/ms-playwright')
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.runtime.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':800,'height':600})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()

    def sample(self, content):
        self.page.set_content(document(content))
        return layout.measure_page(self.page, timeout=.15)

    def test_ready_grid_records_actual_viewport_scale_and_columns(self):
        result = self.sample(grid())
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['viewport'], [800,600])
        self.assertEqual(result['scale'], 1.12)
        self.assertEqual(result['grids'][0]['columns'][0]['id'], 'amount')

    def test_visible_scrollbar_and_real_width_overflow_fail(self):
        result = self.sample(grid(width=280, hidden=False))
        self.assertEqual((result['state'],result['reason']), ('failed','overflow'))
        self.assertTrue(result['grids'][0]['bars'][0]['visible'])

    def test_hiding_scrollbar_does_not_hide_actual_overflow(self):
        self.assertEqual(self.sample(grid(width=280))['state'], 'failed')

    def test_one_pixel_rounding_with_hidden_bar_is_not_reported_as_scrollbar(self):
        result = self.sample(grid(width=201))
        self.assertEqual(result['state'], 'ready')
        self.assertFalse(result['grids'][0]['bars'][0]['visible'])

    def test_missing_and_unprepared_grids_never_pass(self):
        for content in ['',grid(state='preparing')]:
            with self.subTest(content=bool(content)):
                result = self.sample(content)
                self.assertEqual((result['state'],result['reason']), ('failed','layout-timeout'))

    def test_waits_for_real_grid_instead_of_accepting_loading_as_empty(self):
        self.page.set_content(document('<p role="status">正在读取</p>'))
        self.page.evaluate("content=>setTimeout(()=>document.querySelector('.page-view').innerHTML=content,50)", grid())
        result = layout.measure_page(self.page, timeout=2)
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(len(result['grids']), 1)

    def test_explicit_empty_is_separate_from_verified_layout(self):
        self.assertEqual(self.sample('<p class="state">暂无明细</p>')['state'], 'empty')

    def test_ready_shell_with_no_rows_is_still_an_empty_sample(self):
        self.page.set_content(document(grid()))
        self.page.locator('.ag-row').evaluate("e=>e.remove()")
        self.page.locator('.ag-root-wrapper').evaluate("e=>e.insertAdjacentHTML('beforeend','<div class=ag-overlay-no-rows-center>暂无数据</div>')")
        self.assertEqual(layout.measure_page(self.page, timeout=.15)['state'], 'empty')

    def test_multiline_cell_clipped_by_row_height_fails(self):
        self.page.set_content(document(grid()))
        self.page.locator('.ag-cell').evaluate("e=>{e.style.height='10px';e.style.whiteSpace='normal';e.innerHTML='第一行<br>第二行';}")
        result = layout.measure_page(self.page, timeout=.15)
        self.assertEqual(result['state'], 'failed')
        self.assertGreater(result['grids'][0]['clipped'][0]['extraHeight'], 1)

    def test_closed_details_do_not_block_or_fail_visible_grid(self):
        result = self.sample(grid() + '<details><summary>关闭区</summary>' + grid(state='error') + '</details>')
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(len(result['grids']), 1)

    def test_layout_errors_fail_before_timeout(self):
        self.assertEqual(self.sample(grid(state='error'))['reason'], 'page-or-layout-error')

    def test_navigation_comes_from_dom_and_rejects_external_destinations(self):
        self.page.set_content('<aside class="sidebar"><nav><a href="http://127.0.0.1:8065/preview">首页</a><a href="http://127.0.0.1:8065/preview/new-page">新页面</a></nav></aside>')
        routes = layout.navigation(self.page, 'http://127.0.0.1:8065')
        self.assertEqual([item['route'] for item in routes], ['', '/new-page'])
        self.page.set_content('<aside class="sidebar"><nav><a href="https://example.com/preview">外站</a></nav></aside>')
        with self.assertRaisesRegex(ValueError, '非本预览'):
            layout.navigation(self.page, 'http://127.0.0.1:8065')

    def test_changed_preview_run_is_rejected_before_browser_login(self):
        with tempfile.TemporaryDirectory(prefix='layout-owner-',dir=os.environ.get('MTRL_TEST_WORK')) as temporary:
            root = Path(temporary)
            reports = root / 'reports'; reports.mkdir()
            claimed = root / 'claimed'
            actual = root / 'another/reports/real_owner.json'
            with patch.object(sys, 'argv', ['frontend_layout.py','--preview-run',str(claimed)]), \
                 patch.object(layout,'output_dir',return_value=reports), \
                 patch.object(layout,'close_runs'), \
                 patch.object(layout,'registered_preview',return_value=(actual,{},'http://127.0.0.1:8065')), \
                 patch('playwright.sync_api.sync_playwright') as browser:
                self.assertEqual(layout.main(), 2)
                browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
