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
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.audit.workspace_paths import output
from tools.dev.frontend_preview import isolated_database


@pytest.fixture(scope='module')
def server():
    source = os.environ.get('MTRL_PREVIEW_SOURCE_ENV')
    if not source:
        pytest.fail('MTRL_PREVIEW_SOURCE_ENV must identify the approved database configuration')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with isolated_database(Path(source)) as env:
        log_path = output('preview-server.log', kind='logs')
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'uvicorn',
                'tools.dev.frontend_preview:create_preview_app', '--factory', '--host', '127.0.0.1',
                '--port', str(port), '--log-level', 'warning'], cwd=ROOT, env=env, stdout=log, stderr=log)
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


@pytest.fixture
def browser_page(server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        yield page, context
        assert not errors, errors
        context.close()
        browser.close()


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
    page.get_by_label('项目', exact=True).press('Tab')
    expect(page.get_by_role('button', name='查询', exact=True)).to_be_focused()
    page.get_by_role('button', name='查询', exact=True).press('Enter')
    expect(page.get_by_text('没有符合条件的项目。可调整状态或关键词。', exact=True)).to_be_visible()
    page.screenshot(path=str(output('projects-empty.png', kind='screenshots')), full_page=True)


def test_error_loading_forbidden_and_expiry(server, browser_page):
    page, context = browser_page
    login(page, server)
    pending = []
    page.route('**/api/m01/projects?**', lambda route: pending.append(route))
    page.get_by_label('状态', exact=True).select_option('archived')
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    assert pending
    pending.pop().fulfill(status=403, json={'code':'forbidden'})
    expect(page.get_by_role('alert')).to_contain_text('核对权限或访问范围')
    page.screenshot(path=str(output('projects-forbidden.png', kind='screenshots')), full_page=True)
    page.unroute('**/api/m01/projects?**')
    page.route('**/api/m01/projects?**', lambda route: route.fulfill(status=500, json={'message':'项目读取失败，请稍后重试。'}))
    page.get_by_role('button', name='重试', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('项目读取失败，请稍后重试。')
    page.unroute('**/api/m01/projects?**')
    page.get_by_role('button', name='重试', exact=True).click()
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
    context.clear_cookies()
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('登录已失效')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_label('状态', exact=True)).to_have_value('active')


def test_switch_account_drops_old_scope_and_late_response(server, browser_page):
    page, context = browser_page
    login(page, server)
    pending = []
    page.route('**/api/m01/projects?**keyword=older**', lambda route: pending.append(route))
    page.get_by_label('项目', exact=True).fill('older')
    page.get_by_role('button', name='查询', exact=True).click()
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    assert pending
    with httpx.Client() as client:
        response = client.post(server + '/m15/login', data={'account':'preview-user', 'password':'', 'next':'/preview/projects'})
        assert response.status_code == 303
        context.add_cookies([{'name':'mw_preview_397','value':client.cookies['mw_preview_397'],'url':server}])
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('预览同事 · 普通用户', exact=True)).to_be_visible()
    expect(page.get_by_label('项目', exact=True)).to_have_value('')
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    pending.pop().fulfill(status=500, json={'message':'旧账号迟到错误'})
    expect(page.get_by_text('旧账号迟到错误', exact=True)).to_have_count(0)
    assert page.locator('html').evaluate("e => e.style.getPropertyValue('--fscale')") == '1.12'
    page.set_viewport_size({'width':800,'height':900})
    expect(page.get_by_role('button',name='切换账号',exact=True)).to_be_in_viewport()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(output('projects-narrow-large.png',kind='screenshots')),full_page=True)
    page.get_by_role('button',name='切换账号',exact=True).click()
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
