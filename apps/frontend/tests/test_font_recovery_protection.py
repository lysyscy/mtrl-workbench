"""Font recovery must preserve another retained page's unsaved inputs.

Only FontFace loading is failed. Business reads and writes are not replaced,
and the synthetic draft is never submitted.
"""
import pytest
from playwright.sync_api import expect

from test_async_layout_ownership import FRONTEND, bundle_browser_specimen
from test_preview import browser_page, login, server  # noqa: F401


def retained_mechanical_draft(page, address):
    login(page, address)
    page.get_by_role('link', name='机械费', exact=True).click()
    page.get_by_role('button', name='表2 零租明细', exact=True).click()
    page.get_by_role('button', name='车牌规则', exact=True).click()
    dialog = page.get_by_role('dialog', name='无需车牌设备关键词', exact=True)
    field = dialog.get_by_label('无需车牌设备关键词', exact=True)
    draft = field.input_value() + '\n字体恢复保护合成草稿'
    field.fill(draft)
    page.go_back()
    expect(page.locator('#page-title')).to_have_text('项目档案')
    return field, draft


@pytest.mark.parametrize('failure_scope', ['page', 'workspace'])
def test_font_retry_preserves_retained_draft(server, browser_page, disposable, failure_scope):
    page, _ = browser_page
    field, draft = retained_mechanical_draft(page, server)
    # A real browser FontFace fails to decode. The wrapper only selects where
    # that failure is awaited; it does not fabricate a business response.
    page.evaluate("""scope => {
      const nativeLoad = document.fonts.load.bind(document.fonts);
      window.__fontRecoveryDocument = 'original';
      window.__fontRecoveryFailure = null;
      window.__fontRecoveryBlocked = true;
      window.__fontRecoveryCalls = [];
      document.fonts.load = async (font, text) => {
        // loadTextFonts deduplicates characters across the whole load, so
        // phrases need not be contiguous even when each glyph is requested.
        const pageGlyphs = [...'剔除规则'].every(glyph => text?.includes(glyph));
        const shellGlyphs = [...'首页工作台撤销重做'].every(glyph => text?.includes(glyph));
        const selected = scope === 'page' ? pageGlyphs : shellGlyphs;
        if (window.__fontRecoveryCalls.length < 24) {
          window.__fontRecoveryCalls.push({font, length:text?.length ?? 0, pageGlyphs, shellGlyphs, selected});
        }
        if (selected && window.__fontRecoveryBlocked) {
          const face = window.__fontRecoveryFailure ??= new FontFace('RecoveryFailureProbe', new Uint8Array([0, 1, 2, 3]).buffer);
          try { await face.load(); }
          finally { window.__fontRecoveryFaceStatus = face.status; }
        }
        return nativeLoad(font, text);
      };
    }""", failure_scope)
    if failure_scope == 'page':
        page.get_by_role('link', name='规则配置', exact=True).click()
    else:
        page.evaluate("window.dispatchEvent(new Event('focus'))")
    retry = page.get_by_role('button', name='重试字体加载', exact=True)
    try:
        expect(retry).to_be_visible(timeout=6000)
    except AssertionError:
        pytest.fail(f'{failure_scope} font failure was not exposed: '
                    f'{page.evaluate("window.__fontRecoveryCalls")}', pytrace=False)
    assert page.evaluate('window.__fontRecoveryFaceStatus') == 'error'
    # Keep the controlled failure present until the user's actual retry click;
    # PageSurface can revisit the dependency after a query-cache notification.
    retry.evaluate("button => button.addEventListener('click', () => { window.__fontRecoveryBlocked = false; }, {once:true})")
    retry.click()
    page.wait_for_function("""window.__fontRecoveryDocument !== 'original' ||
      [...document.querySelectorAll('[role=alert] [role=status]')].some(node => node.textContent.includes('未保存'))""")
    assert page.evaluate("window.__fontRecoveryDocument === 'original'"), f'{failure_scope} font retry reloaded the document'
    expect(retry.locator('..').get_by_role('status')).to_contain_text('未保存')
    expect(page.locator('.workspace')).to_be_visible()
    expect(page.locator('.workspace')).not_to_have_attribute('inert', '')
    page.get_by_role('link', name='机械费', exact=True).click()
    # The retained modal itself must return; reopening a new modal would hide
    # the loss of the original editing context.
    expect(field).to_have_value(draft)
    dialog = page.get_by_role('dialog', name='无需车牌设备关键词', exact=True)
    dialog.get_by_role('button', name='取消', exact=True).click()
    page.get_by_role('button', name='放弃并关闭', exact=True).click()
    if failure_scope == 'workspace':
        # Resolving the guard makes the same recovery control usable again.
        retry.click()
        page.wait_for_function("window.__fontRecoveryDocument !== 'original'")
        expect(page.locator('.workspace')).not_to_have_attribute('inert', '')
        expect(page.locator('#page-title')).to_have_text('机械费')


def test_font_retry_respects_replay_in_flight_and_unknown(server, browser_page):
    """Exercise the real scoped reload guard with controlled replay state."""
    page, _ = browser_page
    source = """
import {createElement as h} from 'react';
import {createRoot} from 'react-dom/client';
import {HistoryScope, useHistoryState} from '__HISTORY__';
import {WorkspaceReloadButton} from '__PAGE_ERROR__';

window.specimenDocument = crypto.randomUUID();
function ReplayStateControls() {
  const {setBusy, setUncertain} = useHistoryState();
  return h('div', null, ['busy', 'uncertain', 'idle'].map(state => h('button', {
    key: state,
    onClick: () => {setBusy(state === 'busy'); setUncertain(state === 'uncertain');}
  }, state)), h(WorkspaceReloadButton, null, '重试字体加载'));
}
createRoot(document.getElementById('probe')).render(h(HistoryScope, null, h(ReplayStateControls)));
""".replace('__HISTORY__', (FRONTEND / 'src/history.tsx').as_posix()).replace(
        '__PAGE_ERROR__', (FRONTEND / 'src/page-error.tsx').as_posix())
    bundle = bundle_browser_specimen(source)
    # This page renders only the production guard and its context, with no
    # business requests. Reload still replaces the real browser document.
    document_url = str(server) + '/preview/__font_reload_guard_specimen__'
    script_url = document_url + '.js'
    page.route(script_url, lambda route: route.fulfill(content_type='application/javascript', body=bundle))
    page.route(document_url, lambda route: route.fulfill(content_type='text/html', body=
        '<!doctype html><meta charset="utf-8"><div id="probe"></div><script src="' + script_url + '"></script>'))
    page.goto(document_url, wait_until='domcontentloaded')
    original_document = page.evaluate('window.specimenDocument')
    assert original_document
    retry = page.get_by_role('button', name='重试字体加载', exact=True)
    for state, reason in [('busy', '操作历史正在处理'), ('uncertain', '操作历史结果待核实')]:
        page.get_by_role('button', name=state, exact=True).click()
        retry.click()
        expect(page.get_by_role('status')).to_contain_text(reason)
        assert page.evaluate('window.specimenDocument') == original_document

    page.get_by_role('button', name='idle', exact=True).click()
    retry.click()
    page.wait_for_function('original => window.specimenDocument && window.specimenDocument !== original',
                           arg=original_document)
