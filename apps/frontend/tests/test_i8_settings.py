"""TAIL-419 address-only settings against an owned real backend/schema."""
import httpx
from concurrent.futures import ThreadPoolExecutor
import pytest
from tools.audit.workspace_paths import output
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from test_i8 import open_i8, snapshot

LONG_ACCOUNT = 'synthetic-settings-' + 'a' * 92


@pytest.fixture(scope='module')
def preview_factory():
    return 'apps.frontend.tests.fixtures.i8_settings_backend:create_app'


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
        from app.mod14_config.models import AppSetting
        from app.mod15_user.models import UserAccount
        env['I8_BASE_URL'] = 'http://fallback-i8.invalid'
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as session:
                schema = env['PGOPTIONS'].split('search_path=')[1]
                assert session.execute(text("select current_database(), current_schema(), current_setting('search_path')")).one() == ('mtrl_workbench_test', schema, schema)
                session.add(UserAccount(account=LONG_ACCOUNT, name='', role='user', password=''))
                session.add_all([AppSetting(key=key, value=value) for key, value in {
                    'i8_base_url': 'http://initial-i8.invalid',
                    'i8_print_id_material': 'synthetic-material',
                    'i8_print_id_mechanical': 'synthetic-mechanical',
                }.items()])
                session.commit()
        finally:
            engine.dispose()
    return seed


def settings(client):
    response = client.get('/api/m14/settings')
    assert response.status_code == 200
    return response.json()


def test_real_address_partial_save_validation_fallback_logs_and_account(server):
    with httpx.Client(base_url=server) as client:
        before = settings(client)
        assert client.post('/api/m14/settings', json={'i8_base_url': 'http://denied.invalid'}).status_code == 401
        assert settings(client) == before
        assert client.post('/m15/login', data={'account': 'preview-admin', 'password': ''}).status_code == 303
        # The stale account is checked on the actual write, including after a cookie switch.
        stale = client.post('/api/m14/settings?expected_account=preview-user', json={'i8_base_url': 'http://stale.invalid'})
        assert stale.status_code == 409
        assert settings(client) == before
        for bad in ['missing-protocol', 'http://', 'https://host.invalid:99999', 'http://user:pass@host.invalid', 'http://host.invalid?query=x', 'http://bad host.invalid']:
            invalid = client.post('/api/m14/settings?expected_account=preview-admin', json={'i8_base_url': bad})
            assert invalid.status_code == 200 and invalid.json()['ok'] is False, bad
            assert invalid.json()['errors']
            assert settings(client) == before
        for address in ['https://changed-i8.invalid:8443', '']:
            saved = client.post('/api/m14/settings?expected_account=preview-admin', json={'i8_base_url': address})
            assert saved.status_code == 200 and saved.json()['ok'] is True
            reread = settings(client)
            items = {item['key']: item for item in reread['items']}
            assert items['i8_print_id_material']['stored'] == 'synthetic-material'
            assert items['i8_print_id_mechanical']['stored'] == 'synthetic-mechanical'
            assert items['i8_base_url']['stored'] == address
            effective = address or 'http://fallback-i8.invalid'
            assert items['i8_base_url']['effective'] == effective
            actual = client.get('/api/m02/config').json()
            assert actual['base_url'] == effective
            assert actual['source'] == ('page' if address else 'environment')
            log = reread['logs'][0]
            assert log['key'] == 'i8_base_url' and log['new'] == address
            assert log['operator'] == '预览管理员' and log['at']
            assert log['old'] == ('http://initial-i8.invalid' if address else 'https://changed-i8.invalid:8443')
            assert len(reread['logs']) == (1 if address else 2)
        # Same value is a no-op; no extra log or external request.
        assert client.post('/api/m14/settings', json={'i8_base_url': ''}).json()['ok'] is True
        noop = settings(client)
        assert noop['logs'] == reread['logs']
        assert {i['key']: i['stored'] for i in noop['items']} == {i['key']: i['stored'] for i in reread['items']}
        assert client.get('/__test__/i8').json()['calls'] == []



def open_settings(page, server, account='preview-admin'):
    open_i8(page, server, account=account)
    page.get_by_role('button', name='修改服务地址', exact=True).click()
    dialog = page.get_by_role('dialog', name='i8 连接设置')
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
    return dialog


def test_cancel_close_read_failure_and_no_external_actions(server, browser_page):
    page, _ = browser_page
    before = httpx.get(server + '/__test__/i8').json()
    writes = []
    page.on('request', lambda request: writes.append(request) if request.method == 'POST' and '/api/m14/settings' in request.url else None)
    dialog = open_settings(page, server)
    stored = dialog.get_by_label('服务地址', exact=True).input_value()
    dialog.get_by_label('服务地址', exact=True).fill('http://cancelled.invalid')
    dialog.get_by_role('button', name='取消', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button', name='修改服务地址', exact=True)).to_be_focused()
    page.get_by_role('button', name='修改服务地址', exact=True).click()
    expect(dialog.get_by_label('服务地址', exact=True)).to_have_value(stored)
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    page.route('**/api/m14/settings', lambda route: route.fulfill(status=503, json={'message': '配置暂时不可用'}))
    page.get_by_role('button', name='修改服务地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('配置暂时不可用')
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_disabled()
    page.unroute('**/api/m14/settings')
    dialog.get_by_role('button', name='重读配置', exact=True).click()
    expect(dialog.get_by_label('服务地址', exact=True)).to_have_value(stored)
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
    dialog.get_by_role('button', name='取消', exact=True).click()
    assert writes == []
    assert snapshot(page) == before


def test_invalid_valid_duplicate_save_reread_and_visuals(server, browser_page):
    page, _ = browser_page
    dialog = open_settings(page, server)
    field = dialog.get_by_label('服务地址', exact=True)
    field.fill('http://')
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('地址格式不完整')
    expect(field).to_have_value('http://')
    address = 'https://browser-i8.invalid:8443'
    field.fill(address)
    before = page.request.get(server + '/api/m14/settings').json()['logs']
    pending = []
    def hold(route):
        response = route.fetch()
        pending.append((route, response))
        page.evaluate('window.__addressSaved = true')
    page.route('**/api/m14/settings?expected_account=*', hold)
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('button', name='正在保存…', exact=True)).to_be_disabled()
    # Force two submit events too: the synchronous gate protects beyond the disabled button.
    dialog.locator('form').evaluate("f => { f.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true})); f.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true})); }")
    expect(dialog.get_by_role('button', name='取消', exact=True)).to_be_disabled()
    page.keyboard.press('Escape')
    expect(dialog).to_be_visible()
    page.wait_for_function('window.__addressSaved === true')
    assert len(pending) == 1
    route, response = pending.pop()
    assert route.request.post_data_json == {'i8_base_url': address}
    route.fulfill(response=response)
    expect(dialog.get_by_role('status')).to_contain_text('已保存并重读配置')
    expect(field).to_have_value(address)
    expect(dialog.locator('dd').first).to_have_text(address + '（界面所设）')
    after = page.request.get(server + '/api/m14/settings').json()
    assert len(after['logs']) == len(before) + 1
    assert after['logs'][0]['new'] == address
    assert page.request.get(server + '/api/m02/config').json()['base_url'] == address
    page.screenshot(path=str(output('i8-address-light.png', kind='screenshots')), full_page=True)
    dialog.get_by_role('button', name='取消', exact=True).click()
    expect(page.locator('.i8-config dd').first).to_contain_text(address)
    page.reload()
    expect(page.locator('.i8-config dd').first).to_contain_text(address)
    assert snapshot(page)['calls'] == []
    # Ordinary users retain the existing permission to edit connection settings.
    dialog = open_settings(page, server, account='preview-user')
    page.set_viewport_size({'width': 800, 'height': 900})
    expect(dialog).to_be_in_viewport()
    assert dialog.evaluate('e => e.scrollWidth <= e.clientWidth')
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_in_viewport()
    page.screenshot(path=str(output('i8-address-dark-large.png', kind='screenshots')), full_page=True)
    page.unroute('**/api/m14/settings?expected_account=*')
    dialog.get_by_label('服务地址', exact=True).fill('')
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('status')).to_contain_text('已保存并重读配置')
    expect(dialog.locator('dd').first).to_have_text('http://fallback-i8.invalid（环境配置）')
    expect(dialog.get_by_label('服务地址', exact=True)).to_have_value('')
    cleared = page.request.get(server + '/api/m14/settings').json()
    assert cleared['logs'][0]['old'] == address and cleared['logs'][0]['new'] == ''
    assert cleared['logs'][0]['operator'] == '预览同事'
    by_key = {item['key']: item['stored'] for item in cleared['items']}
    assert by_key['i8_print_id_material'] == 'synthetic-material'
    assert by_key['i8_print_id_mechanical'] == 'synthetic-mechanical'
    dialog.get_by_role('button', name='取消', exact=True).click()
    expect(page.locator('.i8-config dd').first).to_have_text('http://fallback-i8.invalid （环境配置）')
    assert snapshot(page)['calls'] == []


@pytest.mark.parametrize('lost_reply', ['network', 'missing-ok', 'truncated-json'])
def test_permission_failure_keeps_input_and_uncertain_write_survives_reopen(server, browser_page, lost_reply):
    page, _ = browser_page
    dialog = open_settings(page, server)
    field = dialog.get_by_label('服务地址', exact=True)
    address = 'http://uncertain-' + lost_reply + '-i8.invalid'
    field.fill(address)
    page.route('**/api/m14/settings?expected_account=*', lambda route: route.fulfill(status=403, json={'message': '拒绝保存'}))
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('核对权限或访问范围')
    expect(field).to_have_value(address)
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
    page.unroute('**/api/m14/settings?expected_account=*')
    writes = []
    def lost(route):
        response = route.fetch()
        assert response.ok
        writes.append(route.request.post_data_json)
        if lost_reply == 'network':
            route.abort('failed')
        elif lost_reply == 'truncated-json':
            route.fulfill(status=200, content_type='application/json', body='{"ok":')
        else:
            data = response.json()
            del data['ok']
            route.fulfill(status=200, json=data)
    page.route('**/api/m14/settings?expected_account=*', lost)
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('保存结果待核实')
    expect(dialog.locator('dt').first).to_have_text('上次读取')
    expect(field).to_have_value(address)
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_disabled()
    if lost_reply == 'truncated-json':
        page.screenshot(path=str(output('i8-address-uncertain.png', kind='screenshots')), full_page=True)
    after = page.request.get(server + '/api/m14/settings').json()
    assert after['logs'][0]['new'] == address
    dialog.get_by_role('button', name='关闭', exact=True).click()
    page.reload()
    expect(page.get_by_role('heading', name='i8 接入层', exact=True)).to_be_visible()
    page.get_by_role('button', name='修改服务地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('上次保存结果待核实')
    expect(field).to_have_value(address)
    dialog.get_by_role('button', name='重读配置', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('已重读当前配置')
    expect(dialog.locator('dd').first).to_have_text(address + '（界面所设）')
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
    assert writes == [{'i8_base_url': address}]
    assert page.request.get(server + '/api/m14/settings').json() == after
    assert snapshot(page)['calls'] == []


def test_saved_but_readback_failed_is_not_reported_as_failed_save(server, browser_page):
    page, _ = browser_page
    dialog = open_settings(page, server)
    address = 'http://saved-readback-i8.invalid'
    dialog.get_by_label('服务地址', exact=True).fill(address)
    page.route('**/api/m14/settings', lambda route: route.fulfill(status=503, json={'message': '重读暂时不可用'}))
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('已保存，重读配置失败')
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_disabled()
    expect(dialog.get_by_label('服务地址', exact=True)).to_have_value(address)
    page.unroute('**/api/m14/settings')
    dialog.get_by_role('button', name='重读配置', exact=True).click()
    expect(dialog.get_by_role('status')).to_contain_text('已保存并重读配置')
    assert page.request.get(server + '/api/m02/config').json()['base_url'] == address
    assert snapshot(page)['calls'] == []


def switch_cookie(context, server):
    with httpx.Client() as client:
        assert client.post(server + '/m15/login', data={'account': 'preview-user', 'password': ''}).status_code == 303
        context.add_cookies([{'name': 'mw_preview_397', 'value': client.cookies['mw_preview_397'], 'url': server}])


def test_account_switch_blocks_stale_save_and_drops_late_receipt(server, browser_page):
    page, context = browser_page
    dialog = open_settings(page, server)
    dialog.get_by_label('服务地址', exact=True).fill('http://wrong-actor.invalid')
    writes = []
    page.on('request', lambda request: writes.append(request) if request.method == 'POST' and '/api/m14/settings' in request.url else None)
    switch_cookie(context, server)
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('账号已变化')
    assert writes == []
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('预览同事 · 普通用户', exact=True)).to_be_visible()
    expect(dialog).not_to_be_visible()
    dialog = open_settings(page, server)
    address = 'http://late-address.invalid'
    dialog.get_by_label('服务地址', exact=True).fill(address)
    pending = []
    def hold(route):
        response = route.fetch()
        pending.append((route, response))
        page.evaluate('window.__addressSaved = true')
    page.route('**/api/m14/settings?expected_account=*', hold)
    dialog.get_by_role('button', name='保存地址', exact=True).click()
    expect(dialog.get_by_role('button', name='正在保存…', exact=True)).to_be_disabled()
    page.wait_for_function('window.__addressSaved === true')
    assert pending
    switch_cookie(context, server)
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('预览同事 · 普通用户', exact=True)).to_be_visible()
    expect(dialog).not_to_be_visible()
    page.get_by_role('button', name='修改服务地址', exact=True).click()
    expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
    route, response = pending.pop()
    route.fulfill(status=500, json={'message': '旧账号迟到错误'})
    expect(dialog.get_by_text('旧账号迟到错误', exact=True)).to_have_count(0)
    expect(dialog.get_by_label('服务地址', exact=True)).to_have_value(address)
    assert snapshot(page)['calls'] == []



def test_long_blank_name_account_is_preserved_in_settings_and_log(server):
    assert len(LONG_ACCOUNT) == 111
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login', data={'account': LONG_ACCOUNT, 'password': ''}).status_code == 303
        revision = next(item['version'] for item in settings(client)['items'] if item['key'] == 'i8_base_url')
        saved = client.post('/api/m14/settings', params={'expected_account': LONG_ACCOUNT, 'expected_version': revision}, json={'i8_base_url': 'http://long-identity.invalid'})
        assert saved.status_code == 200, saved.text
        assert saved.json()['ok'] is True
        reread = settings(client)
        assert reread['logs'][0]['operator'] == LONG_ACCOUNT
        persisted = client.get('/__test__/settings-state').json()
        assert persisted['updated_by'] == persisted['operator'] == LONG_ACCOUNT
        assert persisted['value'] == 'http://long-identity.invalid'



@pytest.mark.parametrize(('order', 'noop'), [('new-first', False), ('old-first', False), ('new-first', True)])
def test_late_inflight_write_cannot_overwrite_a_new_save(server, browser_page, order, noop):
    page, context = browser_page
    dialog = open_settings(page, server)
    original = dialog.get_by_label('服务地址', exact=True).input_value()
    assert page.request.post(server + '/__test__/address-reset').json()['ok']
    futures = []
    cookies = {item['name']: item['value'] for item in context.cookies()}
    with ThreadPoolExecutor(max_workers=1) as pool:
        def lose_while_pending(route):
            if route.request.post_data_json['i8_base_url'] != 'http://held-old-address.invalid':
                route.continue_()
                return
            futures.append(pool.submit(httpx.post, route.request.url, json=route.request.post_data_json,
                                       cookies=cookies, timeout=20))
            route.abort('failed')
        page.route('**/api/m14/settings?expected_account=*', lose_while_pending)
        try:
            dialog.get_by_label('服务地址', exact=True).fill('http://held-old-address.invalid')
            dialog.get_by_role('button', name='保存地址', exact=True).click()
            expect(dialog.get_by_role('alert')).to_contain_text('保存结果待核实')
            page.wait_for_function("async () => (await (await fetch('/__test__/address-flight')).json()).started")
            assert page.request.get(server + '/__test__/address-flight').json()['finished'] is False
            dialog.get_by_role('button', name='重读配置', exact=True).click()
            expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
            expect(dialog.get_by_role('checkbox')).to_have_count(0)
            desired = original if noop else 'http://new-address-' + order + '.invalid'
            dialog.get_by_label('服务地址', exact=True).fill(desired)
            if order == 'old-first':
                assert page.request.post(server + '/__test__/address-release').json()['ok']
                assert futures[0].result(timeout=20).status_code == 200
                dialog.get_by_role('button', name='保存地址', exact=True).click()
                expect(dialog.get_by_role('alert')).to_contain_text('服务地址已变化')
                expect(dialog.get_by_label('服务地址', exact=True)).to_have_value(desired)
                dialog.get_by_role('button', name='重读配置', exact=True).click()
                expect(dialog.get_by_role('button', name='保存地址', exact=True)).to_be_enabled()
            dialog.get_by_role('button', name='保存地址', exact=True).click()
            expect(dialog.get_by_role('status')).to_contain_text('已保存并重读配置')
            if order == 'new-first':
                # Include a same-value new save: its revision must also fence old writes.
                assert page.request.post(server + '/__test__/address-release').json()['ok']
                assert futures[0].result(timeout=20).status_code == 409
            final = page.request.get(server + '/api/m14/settings').json()
            assert next(item['stored'] for item in final['items'] if item['key'] == 'i8_base_url') == desired
            assert page.request.get(server + '/api/m02/config').json()['base_url'] == (desired or 'http://fallback-i8.invalid')
            assert snapshot(page)['calls'] == []
        finally:
            page.request.post(server + '/__test__/address-release')
            for future in futures:
                future.result(timeout=20)



def test_absent_address_same_value_save_fences_missing_revision(server):
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login', data={'account': 'preview-admin', 'password': ''}).status_code == 303
        assert client.post('/__test__/address-remove-row').json()['ok']
        item = next(item for item in settings(client)['items'] if item['key'] == 'i8_base_url')
        assert item['version'] == 'missing' and item['stored'] == ''
        before = settings(client)['logs']
        assert client.post('/api/m14/settings?expected_version=missing', json={'i8_base_url': ''}).json()['ok']
        current = settings(client)
        assert current['logs'] == before
        item = next(item for item in current['items'] if item['key'] == 'i8_base_url')
        assert item['stored'] == '' and item['version'] != 'missing'
        stale = client.post('/api/m14/settings?expected_version=missing', json={'i8_base_url': 'http://late-missing.invalid'})
        assert stale.status_code == 409
        assert settings(client) == current
