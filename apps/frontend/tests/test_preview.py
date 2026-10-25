"""Public-browser and actual-backend checks against an owned, disposable schema."""
from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import expect
from preview_select import pick_option

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.audit.workspace_paths import output
from tools.dev.frontend_preview import isolated_database


@pytest.fixture(scope='module')
def server(preview_seed, preview_factory):
    source = os.environ.get('MTRL_PREVIEW_SOURCE_ENV')
    test_url = os.environ.get('MTRL_PREVIEW_TEST_DATABASE_URL', '')
    if not source and not test_url:
        pytest.fail('Explicit test DSN or approved source configuration is required')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with isolated_database(Path(source) if source else None, test_url=test_url) as env:
        preview_seed(env)
        log_path = output(env['PGAPPNAME'] + '.log', kind='logs')
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'uvicorn',
                preview_factory, '--factory', '--host', '127.0.0.1',
                '--port', str(port), '--log-level', 'warning'], cwd=ROOT, env=env, stdout=log, stderr=log)
            print(f'PREVIEW owned pid={process.pid} port={port} schema={env["PGAPPNAME"]}', flush=True)
            base = f'http://127.0.0.1:{port}'
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail('Preview exited before readiness; inspect ' + str(log_path))
                    try:
                        if httpx.get(base + '/healthz').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail('Preview readiness timed out')
                yield base
            finally:
                process.terminate()
                process.wait(timeout=15)
                print(f'PREVIEW closed pid={process.pid} port={port} exit={process.returncode}', flush=True)


@pytest.fixture
def browser_page(server, preview_browser):
    context = preview_browser.new_context(viewport={'width': 1920, 'height': 1080})
    try:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        yield page, context
        assert not errors, errors
    finally:
        context.close()


def login(page, server, account='preview-admin'):
    page.goto(server + '/login?next=%2Fpreview%2Fprojects')
    page.locator('[name=account]').fill(account)
    page.locator('[name=password]').fill('')
    page.locator('button[type=submit]').click()
    expect(page).to_have_url(server + '/preview/projects')
    expect(page.get_by_role('heading', name='项目档案')).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()


def test_fastapi_build_assets_cookie_and_read(server, browser_page):
    page, context = browser_page
    html = httpx.get(server + '/preview/projects')
    assert html.status_code == 200 and html.headers['cache-control'] == 'no-cache'
    assets = re.findall(r'(?:src|href)="(/preview/assets/[^" ]+)"', html.text)
    assert len(assets) == 2 and all(httpx.get(server + asset).status_code == 200 for asset in assets)
    assert httpx.get(server + '/preview/assets/missing.js').status_code == 404
    assert httpx.get(server + '/preview/missing.js').status_code == 404
    assert httpx.get(server + '/app').content == (ROOT / 'backend/app/web/index.html').read_bytes()
    page.goto(server + '/preview/projects')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    login(page, server)
    expect(page.get_by_text('预览管理员 · 管理员', exact=True)).to_be_visible()
    cookies = {c['name']: c for c in context.cookies()}
    assert cookies['mw_preview_397']['httpOnly'] and cookies['mw_preview_397']['sameSite'] == 'Lax'
    assert 'mw_session' not in cookies
    api = page.request.get(server + '/api/m01/projects').json()
    assert [p['disp'] for p in api] == ['隔离项目', '长项目名验收']
    page.reload()
    expect(page.get_by_text('预览管理员 · 管理员', exact=True)).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    page.evaluate('document.fonts.ready')
    assert page.evaluate("document.fonts.check('14px MiSans')")
    page.screenshot(path=str(output('projects-1080.png', kind='screenshots')), full_page=True)
    page.get_by_label('状态', exact=True).select_option('archived')
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
    page.get_by_label('项目', exact=True).fill('不存在的验收项目')
    expect(page.get_by_text('没有符合条件的项目。可调整状态或关键词。', exact=True)).to_be_visible()
    page.screenshot(path=str(output('projects-empty.png', kind='screenshots')), full_page=True)


def test_error_loading_forbidden_and_expiry(server, browser_page):
    page, context = browser_page
    page.route('**/api/m01/projects?status=all', lambda route: route.fulfill(status=403, json={'code':'forbidden'}))
    page.goto(server + '/login?next=%2Fpreview%2Fprojects')
    page.locator('[name=account]').fill('preview-admin')
    page.locator('button[type=submit]').click()
    expect(page.get_by_role('alert')).to_contain_text('核对权限或访问范围')
    page.unroute('**/api/m01/projects?status=all')
    page.route('**/api/m01/projects?status=all', lambda route: route.fulfill(status=500, json={'message':'项目读取失败，请稍后重试。'}))
    page.get_by_role('button', name='重读项目', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('项目读取失败，请稍后重试。')
    page.unroute('**/api/m01/projects?status=all')
    page.get_by_role('button', name='重读项目', exact=True).click()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    pick_option(page, '项目状态筛选', '归档')
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
    context.clear_cookies()
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('登录已失效')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 手工建档', exact=True)).to_be_disabled()


def test_switch_account_drops_old_scope_and_late_response(server, browser_page):
    page, context = browser_page
    login(page, server)
    page.get_by_label('项目搜索', exact=True).fill('older')
    page.get_by_role('link', name='MOD-02 i8 接入层', exact=True).click()
    pending = []
    def delay_old_account(route):
        if not pending:
            pending.append(route)
        else:
            route.continue_()
    page.route('**/api/m01/projects?status=all', delay_old_account)
    page.get_by_role('link', name='MOD-01 项目档案', exact=True).click()
    expect(page.get_by_text('共 0 个项目', exact=False)).to_be_visible()
    assert pending
    with httpx.Client() as client:
        response = client.post(server + '/m15/login', data={'account':'preview-user', 'password':''})
        assert response.status_code == 303
        context.add_cookies([{'name':'mw_preview_397','value':client.cookies['mw_preview_397'],'url':server}])
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('button', name='预览同事（普通用户）', exact=True)).to_be_visible()
    expect(page.get_by_label('项目搜索', exact=True)).to_have_value('')
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    pending.pop().fulfill(status=500, json={'message':'旧账号迟到错误'})
    expect(page.get_by_text('旧账号迟到错误', exact=True)).to_have_count(0)
    page.get_by_role('button', name='预览同事（普通用户）', exact=True).click()
    page.get_by_role('menuitem', name='退出登录', exact=True).click()
    expect(page).to_have_url(re.compile('/login'))
    assert not any(c['name']=='mw_preview_397' for c in context.cookies())


def test_actual_permission_rejection_and_invalid_cookie(server):
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login',data={'account':'preview-user','password':''}).status_code==303
        me=client.get('/api/m15/users').json()['me']
        assert me['account']=='preview-user'
        before=client.get('/api/m15/users').json()['counts']
        denied=client.post('/api/m15/actions/create',json={'account':'should-not-exist','name':'拒绝样例','role':'user'}).json()
        assert denied['ok'] is False
        assert client.get('/api/m15/users').json()['counts']==before
        client.cookies.set('mw_preview_397','invalid')
        assert client.get('/api/m15/users').json()['me'] is None
        assert client.post('/api/m01/projects',json={}).status_code==401


def test_preview_is_opt_in():
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.core.config import get_settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    assert not get_settings().frontend_preview_dir
    with TestClient(create_app()) as client:
        assert client.get('/preview/projects').status_code == 404
        assert client.get('/app').content == (ROOT / 'backend/app/web/index.html').read_bytes()


@pytest.mark.parametrize(('url', 'copy_source'), [
    ('postgresql+psycopg://synthetic@127.0.0.1:1/mtrl_workbench', False),
    ('postgresql+psycopg://synthetic@127.0.0.1:1/mtrl_workbench_test', True),
])
def test_explicit_test_dsn_rejects_other_database_and_source_copy(url, copy_source):
    with pytest.raises(RuntimeError, match='直接测试DSN'):
        with isolated_database(test_url=url, copy_source=copy_source):
            pytest.fail('Guard must reject before connecting or creating a schema')


def test_payment_preview_reads_only_selected_current_rows(server):
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login', data={'account':'preview-admin','password':''}).status_code == 303
        listed = client.get('/api/m03/notice-list?period=').json()
        selected = listed['items'][0]
        nid = selected['notice_id']
        endpoint = '/api/m03/payment-preview'
        assert client.get(endpoint).json()['items'] == []
        assert client.get(endpoint, params={'ids':99999999}).json()['items'] == []
        preview = client.get(endpoint, params=[('ids',nid),('ids',nid),('ids',99999999)]).json()
        assert preview == {'payment_methods':listed['payment_methods'], 'items':[selected]}
        changed = client.post('/api/m03/actions/category', json={'ids':[nid], 'category':'mechanical'}).json()
        assert changed['ok'] is True
        current = client.get('/api/m03/notice-list?period=').json()
        fresh = client.get(endpoint, params={'ids':nid}).json()['items']
        assert fresh == [next(row for row in current['items'] if row['notice_id'] == nid)]
        assert fresh[0]['category'] == 'mechanical'
        assert client.get('/api/m03/notice-list?period=').json() == current
