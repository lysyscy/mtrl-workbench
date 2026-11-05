"""Real-copy UI coverage for the restored report entry; never submit an i8 request."""
import re

from playwright.sync_api import expect
from test_preview import browser_page, login, server  # noqa: F401


def test_settlement_fetch_entry_and_shared_report_dialog(server, browser_page, api, disposable, preview_screenshot):
    page, _ = browser_page
    preferences = api.get('/api/m15/theme?surface=react').json()
    scale = next(item for item in preferences['scales'] if item['css'] == '1.12')
    assert api.post('/api/m15/ui-scale', json={'ui_scale': scale['key']}).is_success
    posts = []
    page.on('request', lambda req: posts.append(req.url) if req.method == 'POST' and '/fetch' in req.url else None)
    try:
        login(page, server)
        page.locator('a[href="/preview/settlement"]').click()
        page.get_by_label('收发结存核算月', exact=True).wait_for()
        month = page.get_by_label('收发结存核算月', exact=True).input_value()
        fetch = page.get_by_role('button', name='抓取 i8…', exact=True)
        expect(fetch).to_be_enabled()
        export = page.get_by_role('button', name='导出文件…', exact=True)
        assert fetch.bounding_box()['x'] < export.bounding_box()['x']
        preview_screenshot('settlement-fetch-desktop')
        fetch.click()
        dialog = page.get_by_role('dialog')
        expect(dialog.get_by_role('heading', name='按月抓取收发结存')).to_be_visible()
        expect(dialog.get_by_label('收发结存抓取月份', exact=True)).to_have_value(month)
        expect(dialog.locator('.i8-fetch-mode')).to_contain_text('工作台直连')
        expect(dialog.get_by_role('button', name=f'确认按 {month} 抓取', exact=True)).to_be_visible()
        preview_screenshot('settlement-fetch-dialog')
        page.set_viewport_size({'width': 720, 'height': 900})
        expect(dialog.get_by_role('button', name=f'确认按 {month} 抓取', exact=True)).to_be_in_viewport()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        preview_screenshot('settlement-fetch-narrow')
        dialog.get_by_role('button', name='取消', exact=True).click()
        page.set_viewport_size({'width': 1920, 'height': 1080})
        page.locator('a[href="/preview/inventory"]').click()
        page.get_by_role('button', name='按月抓取…', exact=True).click()
        expect(page.get_by_role('heading', name='按月抓取库存单据')).to_be_visible()
        expect(page.get_by_role('dialog').locator('.i8-fetch-mode')).to_contain_text('工作台直连')
        page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
        page.locator('a[href="/preview/contracts"]').click()
        page.get_by_role('button', name=re.compile('^抓取.*i8|^抓取采购合同')).click()
        expect(page.get_by_role('heading', name='抓取采购合同')).to_be_visible()
        expect(page.get_by_role('dialog').locator('.i8-fetch-mode')).to_contain_text('工作台直连')
        assert posts == []
    finally:
        assert api.post('/api/m15/ui-scale', json={'ui_scale': preferences['ui_scale']}).is_success
