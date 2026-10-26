"""Real rules displayed and a representative existing-rule edit."""
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,open_page


def test_actual_rules_and_anonymous_write_protection(server,browser_page,api):
    page,_=browser_page
    data=get(api,'/api/m14/rules')
    assert data['ok'] and data['rules']
    open_page(page,server,'rules','规则配置',authenticated=False)
    expect(page.locator('.rules-block').first).to_be_visible()
    expect(page.get_by_role('button',name='＋ 增加规则',exact=True)).to_be_disabled()
    assert page.request.post(server+'/api/m14/rules',data={}).status==401


def test_actual_rule_edit_preserves_notice_exclusion_flags(server,browser_page,api,disposable):
    page,_=browser_page
    before={r['notice_id']:r['is_excluded'] for r in get(api,'/api/m03/notice-list',period='')['items']}
    open_page(page,server,'rules','规则配置')
    block=page.locator('.rules-block').first
    block.get_by_role('button',name='编辑',exact=True).first.click()
    dialog=page.locator('.rules-dialog')
    meaning=dialog.get_by_label('剔除的业务含义')
    original=meaning.input_value()
    meaning.fill(original+'校验')
    dialog.get_by_role('button',name='保存修改',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(block.get_by_role('status')).to_contain_text('已更新')
    after={r['notice_id']:r['is_excluded'] for r in get(api,'/api/m03/notice-list',period='')['items']}
    assert before==after
