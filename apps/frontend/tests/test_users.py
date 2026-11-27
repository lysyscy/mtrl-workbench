"""Actual account counts, anonymous permissions and per-account appearance persistence."""
import httpx
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,open_page


def test_real_users_counts_and_anonymous_controls(server,browser_page,api):
    page,_=browser_page;data=get(api,'/api/m15/users');assert data['counts']['total']>=len(data['users'])
    open_page(page,server,'users','用户管理',authenticated=False)
    expect(page.get_by_role('button',name='+ 新增账号',exact=True)).to_be_disabled()
    assert page.request.post(server+'/api/m15/actions/create',data={}).status==401
    expect(page.locator('.users-block')).to_be_visible()


def test_actual_appearance_persists_and_keeps_other_account(server,browser_page,api,disposable):
    page,_=browser_page;me=login(page,server);original=get(api,'/api/m15/theme',surface='react')
    theme, = original['palette']
    target = next(scale for scale in original['scales'] if scale['key'] != original['ui_scale'])
    try:
        with httpx.Client(base_url=server) as other:
            assert other.post('/m15/login',data={'account':'preview-user','password':''}).status_code==303
            before=other.get('/api/m15/theme?surface=react').json()
            page.get_by_role('button',name=me['name']+'（管理员）',exact=True).click();page.get_by_role('menuitem',name='外观与字号',exact=True).click();dialog=page.locator('.appearance-dialog')
            expect(dialog.get_by_role('radio')).to_have_count(1+len(original['scales']))
            expect(dialog.get_by_role('radio',name=theme['label']+'主题',exact=True)).to_have_attribute('aria-checked','true')
            option = dialog.get_by_role('radio',name=target['label']+'字号',exact=True)
            option.click()
            expect(option).to_have_attribute('aria-checked','true')
            page.reload()
            result = get(api,'/api/m15/theme',surface='react')
            assert result['ui_scale'] == target['key'] and result['theme'] == theme['name']
            assert other.get('/api/m15/theme?surface=react').json()==before
    finally:
        assert api.post('/api/m15/ui-scale',json={'ui_scale':original['ui_scale']}).json()['ok']
