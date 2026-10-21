"""真实浏览器验证全局入口、键盘文字撤销和保存中的互斥。"""
from playwright.sync_api import expect

from app.mod03_notice.page import render_theme
from tests.ui_helpers import ui_page  # noqa: F401
from tools.audit.workspace_paths import output


def setup(p):
    server = {'applied': False, 'exists': False, 'blocked': False, 'undo': 0, 'redo': 0}
    def status():
        item = {'id': 7, 'label': '剔除付款通知书', 'count': 18}
        return {'undo': item if server['exists'] and server['applied'] else None,
                'redo': item if server['exists'] and not server['applied'] else None,
                'notice': '上一步暂不支持撤销／重做' if server['blocked'] else ''}
    def route(req):
        action = req.request.url.rsplit('/', 1)[-1]
        if action == 'status':
            body = status()
        else:
            assert req.request.post_data_json == {'operation_id': 7}
            server[action] += 1
            server['applied'] = action == 'redo'
            body = {'ok': True, 'message': '已完成历史操作'}
        req.fulfill(json=body)
    p.route('**/api/history/**', route)
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate("""() => {
      VIEW='m03';window.historyReloads=0;
      PAGE_LOAD.m03=['历史回归'];LOADERS['历史回归']=async()=>{historyReloads++;};
      reloadNotices=async()=>{};render();
    }""")
    p.evaluate('historyRefresh()')
    return server


def test_buttons_batch_undo_redo_keyboard_and_native_text_history(ui_page):
    p = ui_page
    server = setup(p)
    undo = p.get_by_role('button', name='撤销', exact=True)
    redo = p.get_by_role('button', name='重做', exact=True)
    expect(undo).to_be_disabled()
    expect(redo).to_be_disabled()
    def exclude(req):
        server.update(exists=True, applied=True)
        req.fulfill(json={'ok': True, 'marked': ['101'], 'message': '已剔除18条'},
                    headers={'X-Operation-History': 'recorded'})
    p.route('**/api/m03/actions/exclude', exclude)
    p.evaluate("pickSet.add('101');ACT.batchEx()")
    expect(undo).to_be_enabled()
    expect(undo).to_have_attribute('title', '撤销：剔除付款通知书（18条，Ctrl+Z）')
    assert p.locator('#historyControls').bounding_box()['x'] < p.locator('#who').bounding_box()['x']
    undo.click()
    expect(redo).to_be_enabled()
    expect(undo).to_be_disabled()
    assert server['undo'] == 1
    p.keyboard.press('Control+y')
    expect(undo).to_be_enabled()
    assert server['redo'] == 1
    assert p.evaluate('historyReloads') == 2
    p.evaluate("document.querySelector('#view').insertAdjacentHTML('afterbegin','<input id=historyText aria-label=文字草稿>')")
    text = p.get_by_label('文字草稿')
    text.press_sequentially('abcd')
    text.press('Control+z')
    assert text.input_value() != 'abcd'
    assert server['undo'] == 1
    p.get_by_role('heading', name='付款通知书', exact=True).click()
    p.keyboard.press('Control+z')
    expect(redo).to_be_enabled()
    p.keyboard.press('Control+Shift+z')
    expect(undo).to_be_enabled()
    p.screenshot(path=str(output('global-history-buttons.png', kind='screenshots')))
    p.evaluate("CUR.role='';historyRefresh()")
    expect(undo).to_be_disabled()
    assert p.evaluate('HISTORY.undo') is None


def test_pending_write_blocks_undo_and_unsupported_notice_persists(ui_page):
    p = ui_page
    server = setup(p)
    server.update(exists=True, applied=True)
    p.evaluate('historyRefresh()')
    pending = []
    p.route('**/api/m03/actions/exclude', lambda req: pending.append(req))
    p.evaluate("window.historySave=API.exclude(['101']);void 0")
    undo = p.get_by_role('button', name='撤销', exact=True)
    expect(undo).to_be_disabled()
    p.evaluate("historyApply('undo')")
    assert server['undo'] == 0
    assert len(pending) == 1
    pending[0].fulfill(json={'ok': True}, headers={'X-Operation-History': 'recorded'})
    p.evaluate('historySave')
    expect(undo).to_be_enabled()
    def unsupported(req):
        server.update(exists=False, blocked=True)
        req.fulfill(json={'ok': True}, headers={'X-Operation-History': 'unsupported'})
    p.route('**/unsupported', unsupported)
    p.evaluate("API.post('/unsupported',{})")
    expect(undo).to_be_disabled()
    expect(p.locator('#historyControls [role=status]')).to_have_text('上一步暂不支持撤销／重做')
    p.evaluate('historyRefresh()')
    expect(p.locator('#historyControls [role=status]')).to_have_text('上一步暂不支持撤销／重做')
    p.set_viewport_size({'width': 1120, 'height': 800})
    p.evaluate("document.documentElement.style.setProperty('--fscale','1.25');VIEW='m07';render()")
    geometry = p.locator('.tb').evaluate("""el=>{
      const title=el.querySelector('h1').getBoundingClientRect();
      const controls=el.querySelector('#historyControls').getBoundingClientRect();
      const who=el.querySelector('#who').getBoundingClientRect();
      return {titleRight:title.right,controlsLeft:controls.left,controlsRight:controls.right,
              whoLeft:who.left,whoRight:who.right,width:innerWidth};
    }""")
    assert geometry['titleRight'] <= geometry['controlsLeft'], geometry
    assert geometry['controlsRight'] <= geometry['whoLeft'] and geometry['whoRight'] <= geometry['width'], geometry
