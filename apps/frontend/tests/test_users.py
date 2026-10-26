"""Actual account counts, anonymous permissions and per-account appearance persistence."""
import httpx
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,open_page


def test_real_users_counts_and_anonymous_controls(server,browser_page,api):
    page,_=browser_page;data=get(api,'/api/m15/users');assert data['counts']['total']>=len(data['users'])
    open_page(page,server,'users','用户管理',authenticated=False)
    expect(page.get_by_role('button',name='＋ 新增账号',exact=True)).to_be_disabled()
    assert page.request.post(server+'/api/m15/actions/create',data={}).status==401
    expect(page.locator('.users-block')).to_be_visible()


def test_actual_appearance_persists_and_keeps_other_account(server,browser_page,api,disposable):
    page,_=browser_page;me=login(page,server);original=get(api,'/api/m15/theme',surface='react');target=next(p for p in original['palette'] if p['name']!=original['theme'])
    with httpx.Client(base_url=server) as other:
        assert other.post('/m15/login',data={'account':'preview-user','password':''}).status_code==303
        before=other.get('/api/m15/theme?surface=react').json()
        page.get_by_role('button',name=me['name']+'（管理员）',exact=True).click();page.get_by_role('menuitem',name='外观与字号',exact=True).click();dialog=page.locator('.appearance-dialog')
        expect(dialog.get_by_role('radio')).to_have_count(len(original['palette'])+len(original['scales']))
        dialog.get_by_role('radio',name=target['label']+'主题',exact=True).click();expect(dialog.get_by_role('radio',name=target['label']+'主题',exact=True)).to_have_attribute('aria-checked','true')
        page.reload();assert get(api,'/api/m15/theme',surface='react')['theme']==target['name']
        assert other.get('/api/m15/theme?surface=react').json()==before
    assert api.post('/api/m15/theme',json={'theme':original['theme']}).json()['ok']
