"""TAIL-420/441: user management and appearance through the real isolated backend."""

import httpx
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login


def users_api(page, server):
    return page.request.get(server + '/api/m15/users').json()


def row_of(page, account):
    return page.get_by_role('region', name='账号列表').locator('tr').filter(has_text=account)


def test_admin_crud_guards_and_passwords(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-15 用户管理').click()
    block = page.locator('.users-block')
    expect(page.get_by_role('heading', name='用户管理')).to_be_visible()
    expect(block).to_contain_text('在用 2 · 停用 0 · 已删除 0')
    admin_row = row_of(page, 'preview-admin')
    expect(admin_row.get_by_text('管理员', exact=True)).to_be_visible()
    expect(admin_row).to_contain_text('（当前登录）')
    # Self delete is not offered and the last active admin cannot be disabled.
    expect(admin_row.get_by_role('button', name='删除', exact=True)).to_have_count(0)
    expect(admin_row.get_by_role('button', name='停用', exact=True)).to_be_disabled()
    # Create: client-side required fields, then a real account.
    page.get_by_role('button', name='＋ 新增账号', exact=True).click()
    dialog = page.locator('.users-dialog')
    dialog.get_by_role('button', name='创建', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('登录账号与姓名都要填')
    dialog.get_by_label('登录账号 ＊（非空、不重复即可）').fill('yanshou')
    dialog.get_by_label('姓名 ＊').fill('王验收')
    dialog.get_by_label('初始密码（可为空）').fill('pw1')
    dialog.get_by_role('button', name='创建', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(block.get_by_role('status')).to_contain_text('已创建普通用户')
    row = row_of(page, 'yanshou')
    expect(row.get_by_text('在用', exact=True)).to_be_visible()
    expect(row).to_contain_text('从未登录')
    # Duplicate accounts are rejected by the server and add no row.
    page.get_by_role('button', name='＋ 新增账号', exact=True).click()
    dialog.get_by_label('登录账号 ＊（非空、不重复即可）').fill('yanshou')
    dialog.get_by_label('姓名 ＊').fill('重复者')
    dialog.get_by_role('button', name='创建', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('已存在')
    dialog.get_by_role('button', name='取消', exact=True).click()
    dialog.get_by_role('button', name='放弃并关闭').click()
    # View password shows the plaintext password plus the unbound i8 warning.
    row.get_by_role('button', name='看密码', exact=True).click()
    expect(dialog.get_by_label('当前密码')).to_have_value('pw1')
    expect(dialog.get_by_label('i8 账号')).to_have_value('（未绑定）')
    expect(dialog).to_contain_text('还没绑 i8')
    dialog.get_by_role('button', name='关闭', exact=True).click()
    # Password and i8 binding save together; empty password clears on purpose.
    row.get_by_role('button', name='改密', exact=True).click()
    dialog.get_by_label('新密码（可为空）').fill('pw2')
    dialog.get_by_label('i8 账号（绑定到本系统账号、每人一份）').fill('i8wang')
    dialog.get_by_role('button', name='保存', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(block.get_by_role('status')).to_contain_text('密码已更新')
    expect(block.get_by_role('status')).to_contain_text('i8 绑定已保存')
    expect(row).to_contain_text('i8wang')
    row.get_by_role('button', name='看密码', exact=True).click()
    expect(dialog.get_by_label('当前密码')).to_have_value('pw2')
    expect(dialog.get_by_label('i8 账号')).to_have_value('i8wang')
    expect(dialog).to_contain_text('i8 密码为空')
    dialog.get_by_role('button', name='关闭', exact=True).click()
    row.get_by_role('button', name='改密', exact=True).click()
    dialog.get_by_label('i8 账号（绑定到本系统账号、每人一份）').fill('')
    dialog.get_by_role('button', name='保存', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已清空')
    expect(row.get_by_text('未绑定', exact=True)).to_be_visible()
    row.get_by_role('button', name='看密码', exact=True).click()
    expect(dialog.get_by_label('当前密码')).to_have_value('')
    expect(dialog).to_contain_text('没有设密码')
    dialog.get_by_role('button', name='关闭', exact=True).click()
    # Disable / enable round-trip.
    row.get_by_role('button', name='停用', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已停用')
    expect(row.get_by_text('已停用', exact=True)).to_be_visible()
    row.get_by_role('button', name='启用', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已启用')
    # Delete is soft, confirmed explicitly, and restorable.
    row.get_by_role('button', name='删除', exact=True).click()
    expect(dialog).to_contain_text('删除账号确认')
    expect(dialog).to_contain_text('必要时可恢复')
    dialog.get_by_role('button', name='确认删除', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已删除')
    expect(row.get_by_text('已删除', exact=True)).to_be_visible()
    row.get_by_role('button', name='恢复', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已恢复')
    expect(row.get_by_text('在用', exact=True)).to_be_visible()
    # The last-admin guard also holds when the write is forced straight at the API.
    admin_id = users_api(page, server)['me']['id']
    refused = page.request.post(server + '/api/m15/actions/status', data={'id': admin_id, 'status': '已停用'}).json()
    assert refused['ok'] is False and '最后一个在用管理员' in refused['message']


def test_non_admin_permissions_and_own_password(server, browser_page):
    page, _ = browser_page
    login(page, server, 'preview-user')
    page.goto(server + '/preview/users')
    block = page.locator('.users-block')
    expect(page.get_by_role('button', name='＋ 新增账号', exact=True)).to_be_disabled()
    expect(page.get_by_role('button', name='转让管理员', exact=True)).to_be_disabled()
    expect(block).to_contain_text('只有管理员可以新增、启停或删除账号')
    self_row = row_of(page, 'preview-user')
    admin_row = row_of(page, 'preview-admin')
    expect(self_row.get_by_role('button', name='改密', exact=True)).to_be_enabled()
    expect(admin_row.get_by_role('button', name='改密', exact=True)).to_be_disabled()
    expect(admin_row.get_by_role('button', name='看密码', exact=True)).to_be_disabled()
    expect(admin_row.get_by_role('button', name='停用', exact=True)).to_be_disabled()
    # Every admin-only write is refused server-side for a normal user, data unchanged.
    data = users_api(page, server)
    admin_id = next(user['id'] for user in data['users'] if user['account'] == 'preview-admin')
    for path, payload in [
        ('/api/m15/actions/create', {'account': 'hacker', 'name': '越权', 'password': ''}),
        ('/api/m15/actions/status', {'id': admin_id, 'status': '已停用'}),
        ('/api/m15/actions/delete', {'id': admin_id}),
        ('/api/m15/actions/transfer', {'id': admin_id}),
        ('/api/m15/actions/password', {'id': admin_id, 'password': 'x'}),
        ('/api/m15/actions/i8', {'id': admin_id, 'i8_user': 'x'}),
    ]:
        response = page.request.post(server + path, data=payload).json()
        assert response['ok'] is False, path
    refused = page.request.get(server + f'/api/m15/password?id={admin_id}').json()
    assert refused['ok'] is False
    assert users_api(page, server)['counts'] == data['counts']
    # A normal user can still change their own password; the session survives it.
    self_row.get_by_role('button', name='改密', exact=True).click()
    dialog = page.locator('.users-dialog')
    dialog.get_by_label('新密码（可为空）').fill('userpw')
    dialog.get_by_role('button', name='保存', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('密码已更新')
    assert users_api(page, server)['me']['account'] == 'preview-user'
    # Restore the empty password so later logins keep using the documented default.
    self_row.get_by_role('button', name='改密', exact=True).click()
    dialog.get_by_label('新密码（可为空）').fill('')
    dialog.get_by_role('button', name='保存', exact=True).click()
    expect(block.get_by_role('status')).to_contain_text('已清空')


def test_transfer_atomicity_and_disabled_sessions(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/users')
    block = page.locator('.users-block')
    page.get_by_role('button', name='转让管理员', exact=True).click()
    dialog = page.locator('.users-dialog')
    expect(dialog).to_contain_text('转让后对方为管理员，你转为普通用户')
    dialog.get_by_label('转让给（限在用账号）').select_option(label='预览同事（preview-user）')
    dialog.get_by_role('button', name='确认转让', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(block.get_by_role('status')).to_contain_text('管理员已转让给')
    expect(row_of(page, 'preview-user').get_by_text('管理员', exact=True)).to_be_visible()
    expect(row_of(page, 'preview-admin').get_by_text('普通用户', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 新增账号', exact=True)).to_be_disabled()
    # A failed transfer leaves both roles untouched (no partial transfer).
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login', data={'account': 'preview-user', 'password': ''}, follow_redirects=False).status_code == 303
        refused = client.post('/api/m15/actions/transfer', json={'id': 999999}).json()
        assert refused['ok'] is False
        roles = {user['account']: user['role'] for user in client.get('/api/m15/users').json()['users']}
        assert roles['preview-admin'] == 'user' and roles['preview-user'] == 'admin'
        admin_id = next(user['id'] for user in client.get('/api/m15/users').json()['users'] if user['account'] == 'preview-admin')
        assert client.post('/api/m15/actions/transfer', json={'id': admin_id}).json()['ok'] is True
        roles = {user['account']: user['role'] for user in client.get('/api/m15/users').json()['users']}
        assert roles['preview-admin'] == 'admin' and roles['preview-user'] == 'user'
    # Disabling keeps an existing session identified but refuses new logins.
    with httpx.Client(base_url=server) as user_client:
        assert user_client.post('/m15/login', data={'account': 'preview-user', 'password': ''}, follow_redirects=False).status_code == 303
        with httpx.Client(base_url=server) as admin_client:
            assert admin_client.post('/m15/login', data={'account': 'preview-admin', 'password': ''}, follow_redirects=False).status_code == 303
            user_id = next(user['id'] for user in admin_client.get('/api/m15/users').json()['users'] if user['account'] == 'preview-user')
            assert admin_client.post('/api/m15/actions/status', json={'id': user_id, 'status': '已停用'}).json()['ok'] is True
        me = user_client.get('/api/m15/users').json()['me']
        assert me['account'] == 'preview-user' and me['state'] == '已停用'
    refused_login = httpx.post(server + '/m15/login', data={'account': 'preview-user', 'password': ''})
    assert refused_login.status_code == 200 and '已停用' in refused_login.text
    with httpx.Client(base_url=server) as admin_client:
        assert admin_client.post('/m15/login', data={'account': 'preview-admin', 'password': ''}, follow_redirects=False).status_code == 303
        assert admin_client.post('/api/m15/actions/status', json={'id': user_id, 'status': '在用'}).json()['ok'] is True


def test_theme_and_scale_persist_per_account(server, browser_page):
    page, _ = browser_page
    login(page, server)
    original = page.request.get(server + '/api/m15/theme?surface=react').json()
    current, target = original['theme'], '玫瑰柔粉'
    page.get_by_role('button', name='预览管理员（管理员）').click()
    page.get_by_role('menuitem', name='外观与字号').click()
    dialog = page.locator('.appearance-dialog')
    expect(dialog.get_by_role('radio')).to_have_count(12)
    dialog.get_by_role('radio', name=target + '主题', exact=True).click()
    expect(dialog.get_by_role('radio', name=target + '主题', exact=True)).to_have_attribute('aria-checked', 'true')
    dialog.get_by_role('radio', name='大一点字号', exact=True).click()
    page.wait_for_function("document.documentElement.style.getPropertyValue('--fscale') === '1.12'")
    expect(dialog).to_contain_text('仅影响当前账号')
    page.reload()
    expect(page.get_by_role('button', name='预览管理员（管理员）')).to_be_visible()
    saved = page.request.get(server + '/api/m15/theme?surface=react').json()
    assert saved['theme'] == target
    page.wait_for_function("document.documentElement.style.getPropertyValue('--fscale') === '1.12'")
    page.wait_for_function("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() === '#f9edf2'")
    login(page, server, 'preview-user')
    other = page.request.get(server + '/api/m15/theme?surface=react').json()
    assert other['theme'] == '深色' and other['ui_scale'] == 'large'
    login(page, server)
    page.get_by_role('button', name='预览管理员（管理员）').click()
    page.get_by_role('menuitem', name='外观与字号').click()
    label = next(item['label'] for item in original['palette'] if item['name'] == current)
    dialog.get_by_role('radio', name=label + '主题', exact=True).click()
    expect(dialog.get_by_role('radio', name=label + '主题', exact=True)).to_have_attribute('aria-checked', 'true')
    dialog.get_by_role('radio', name='标准字号', exact=True).click()
    page.wait_for_function("document.documentElement.style.getPropertyValue('--fscale') === '1'")
    restored = page.request.get(server + '/api/m15/theme?surface=react').json()
    assert restored['theme'] == current and restored['ui_scale'] == original['ui_scale']



def test_appearance_unknown_save_requires_readback_before_another_choice(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('button', name='预览管理员（管理员）').click()
    page.get_by_role('menuitem', name='外观与字号').click()
    dialog = page.locator('.appearance-dialog')
    target = dialog.get_by_role('radio', name='丁香浅紫主题', exact=True)
    expect(target).to_be_visible()
    writes = []

    def lose_confirmation(route):
        writes.append(route.request.post_data_json)
        response = route.fetch()
        assert response.ok
        route.fulfill(status=200, content_type='application/json', body='{}')

    page.route('**/api/m15/theme', lose_confirmation)
    target.click()
    expect(dialog.get_by_role('alert')).to_contain_text('保存结果未确认')
    expect(dialog.get_by_role('radio', name='松绿主题', exact=True)).to_be_disabled()
    assert len(writes) == 1
    page.unroute('**/api/m15/theme', lose_confirmation)
    dialog.get_by_role('button', name='重新读取', exact=True).click()
    expect(target).to_have_attribute('aria-checked', 'true')
    expect(dialog).to_contain_text('已重新读取当前账号设置')
    page.wait_for_function("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() === '#f0edfa'")
    dialog.get_by_role('radio', name='松绿主题', exact=True).click()
    expect(dialog.get_by_role('radio', name='松绿主题', exact=True)).to_have_attribute('aria-checked', 'true')
    dialog.get_by_role('button', name='收起外观面板', exact=True).click()
    expect(page.get_by_role('button', name='预览管理员（管理员）')).to_be_focused()


def test_appearance_cards_geometry_keyboard_and_narrow(server, browser_page):
    page, _ = browser_page
    login(page, server)
    search = page.get_by_role('searchbox', name='项目搜索', exact=True)
    search.fill('隔离')
    page.get_by_role('button', name='预览管理员（管理员）').click()
    page.get_by_role('menuitem', name='外观与字号').click()
    panel = page.locator('.appearance-dialog')
    expect(panel.get_by_role('radio')).to_have_count(12)
    # All cards exercise the actual account endpoint and the matching full-page CSS.
    palettes = page.request.get(server + '/api/m15/theme?surface=react').json()['palette']
    for item in palettes:
        card = panel.get_by_role('radio', name=item['label'] + '主题', exact=True)
        card.click()
        expect(card).to_have_attribute('aria-checked', 'true')
        expect(panel).to_have_attribute('aria-busy', 'false')
        page.wait_for_function('(bg) => getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() === bg', arg=item['vars']['--bg'])
    for label, scale in [('标准', '1'), ('大一点', '1.12'), ('更大', '1.25'), ('最大', '1.4')]:
        card = panel.get_by_role('radio', name=label + '字号', exact=True)
        card.click()
        expect(card).to_have_attribute('aria-checked', 'true')
        expect(panel).to_have_attribute('aria-busy', 'false')
        page.wait_for_function('(scale) => document.documentElement.style.getPropertyValue("--fscale") === scale', arg=scale)
    expect(search).to_have_value('隔离')
    samples = panel.locator('.appearance-size-sample').evaluate_all('(items) => items.map(el => parseFloat(getComputedStyle(el).fontSize))')
    assert samples == [13.5, 15.12, 16.875, 18.9]
    current = panel.get_by_role('radio', name='丁香浅紫主题', exact=True)
    current.press('Home')
    expect(panel.get_by_role('radio', name='中性浅色主题', exact=True)).to_have_attribute('aria-checked', 'true')
    expect(panel).to_have_attribute('aria-busy', 'false')
    # Resizing while focus is in the page moves it into the compact dialog.
    search.focus()
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(panel).to_have_attribute('aria-modal', 'true')
    close = panel.get_by_role('button', name='收起外观面板', exact=True)
    expect(close).to_be_focused()
    assert page.locator('.main').evaluate('(el) => el.inert')
    assert panel.evaluate('(el) => el.getBoundingClientRect().left >= 0 && el.getBoundingClientRect().right <= innerWidth && el.scrollWidth <= el.clientWidth')
    for card in panel.locator('.appearance-choice').all():
        assert card.evaluate('(el) => el.scrollWidth <= el.clientWidth'), card.get_attribute('aria-label')
    close.press('Escape')
    expect(panel).not_to_be_visible()
    assert not page.locator('.main').evaluate('(el) => el.inert')
