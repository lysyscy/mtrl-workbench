"""Closing animation must not swallow the next intent or resurrect discarded input."""
from playwright.sync_api import expect
from test_preview import browser_page, login, server  # noqa: F401


def test_closing_dialog_allows_immediate_fresh_reopen(server, browser_page):
    page, _ = browser_page
    login(page, server)
    trigger = page.get_by_role('button', name='＋ 手工建档', exact=True)
    trigger.click()
    page.get_by_role('textbox', name='项目全名', exact=True).fill('已放弃的动效验证草稿')
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    page.get_by_role('button', name='放弃并关闭', exact=True).click()
    # Deliberately do not let Playwright wait for the leaving overlay to disappear.
    trigger.click(force=True)
    field = page.get_by_role('textbox', name='项目全名', exact=True)
    expect(field).to_be_visible()
    expect(field).to_have_value('')
    field.fill('新的未保存草稿')
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    expect(page.get_by_role('heading', name='放弃未保存的修改？')).to_be_visible()
    page.get_by_role('button', name='继续编辑', exact=True).click()
    expect(field).to_have_value('新的未保存草稿')


def test_live_reduced_motion_keeps_dialog_draft_and_close_protocol(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('button', name='＋ 手工建档', exact=True).click()
    field = page.get_by_role('textbox', name='项目全名', exact=True)
    field.fill('切换动态设置时保留')
    page.emulate_media(reduced_motion='reduce')
    expect(field).to_have_value('切换动态设置时保留')
    expect(field).to_be_focused()
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    page.get_by_role('button', name='放弃并关闭', exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('link', name='付款通知书', exact=True).click()
    expect(page.locator('.page-view:not([hidden])')).to_be_visible()
    page.wait_for_function("[...document.querySelectorAll('.page-view')].every(e => getComputedStyle(e).transform === 'none')")


def test_leaving_dialog_releases_hit_target_and_mid_exit_reduction(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('button', name='＋ 手工建档', exact=True).click()
    dialog = page.get_by_role('dialog')
    box = dialog.bounding_box()
    assert box
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    page.locator('.business-dialog-motion-leave-active').wait_for(state='attached')
    hit = page.evaluate("""({x,y}) => {
      const node = document.elementFromPoint(x,y);
      return Boolean(node?.closest('.business-modal-root'));
    }""", {'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2})
    assert not hit, 'The leaving dialog must release its entire rectangle immediately'
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.emulate_media(reduced_motion='reduce')
    expect(page.locator('.business-modal-root')).to_have_count(0, timeout=1500)
    page.get_by_role('button', name='＋ 手工建档', exact=True).click()
    # AntD's reduced-motion path focuses its first control (the close button).
    assert page.get_by_role('dialog').evaluate('e => e.contains(document.activeElement)')
    field = page.get_by_role('textbox', name='项目全名', exact=True)
    field.fill('减少动效下可立即输入')
    expect(field).to_be_focused()
    expect(field).to_have_value('减少动效下可立即输入')


def test_appearance_close_keeps_the_next_input_and_one_layout_slot(server, browser_page):
    page, _ = browser_page
    login(page, server)
    width = page.locator('.main').evaluate('e => e.clientWidth')
    def open_panel():
        page.locator('.account-pill').click()
        page.get_by_role('menuitem', name='外观与字号', exact=True).click()
    open_panel()
    page.get_by_role('button', name='收起外观面板', exact=True).click()
    field = page.get_by_role('searchbox', name='项目搜索', exact=True)
    field.fill('下一步输入')
    page.wait_for_timeout(650)  # Observe after the old panel's actual exit lifecycle.
    expect(field).to_be_focused()
    expect(field).to_have_value('下一步输入')
    field.fill('')
    open_panel()
    page.get_by_role('button', name='收起外观面板', exact=True).click()
    open_panel()
    panel_width = page.locator('.appearance-panel:not([inert])').evaluate('e => e.getBoundingClientRect().width')
    assert page.locator('.main').evaluate('e => e.clientWidth') >= width - panel_width - 1


def test_controlled_modal_finishes_when_motion_preference_changes_during_exit(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='付款通知书', exact=True).click()
    page.get_by_role('button', name='导出 Excel', exact=True).click()
    expect(page.get_by_role('dialog', name='导出付款通知书台账', exact=True)).to_be_visible()
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    page.locator('.business-dialog-motion-leave-active').wait_for(state='attached')
    page.emulate_media(reduced_motion='reduce')
    expect(page.locator('.business-modal-root .ant-modal-wrap')).to_be_hidden(timeout=1500)
    page.get_by_role('button', name='导出 Excel', exact=True).click()
    expect(page.get_by_role('dialog', name='导出付款通知书台账', exact=True)).to_be_visible()
