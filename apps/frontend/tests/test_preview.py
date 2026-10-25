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
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')


def test_fastapi_build_assets_cookie_and_read(server, browser_page):
    page, context = browser_page
    html = httpx.get(server + '/preview/projects')
    assert html.status_code == 200 and html.headers['cache-control'] == 'no-cache'
    assets = re.findall(r'(?:src|href)="(/preview/assets/[^" ]+)"', html.text)
    assert assets and len(set(assets)) == len(assets)
    assert any(asset.endswith('.js') for asset in assets) and any(asset.endswith('.css') for asset in assets)
    assert all(httpx.get(server + asset).status_code == 200 for asset in assets)
    assert httpx.get(server + '/preview/assets/missing.js').status_code == 404
    assert httpx.get(server + '/preview/missing.js').status_code == 404
    assert httpx.get(server + '/app').content == (ROOT / 'backend/app/web/index.html').read_bytes()
    page.goto(server + '/preview/projects')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')
    login(page, server)
    expect(page.get_by_role('button', name='预览管理员（管理员）', exact=True)).to_be_visible()
    cookies = {c['name']: c for c in context.cookies()}
    assert cookies['mw_preview_397']['httpOnly'] and cookies['mw_preview_397']['sameSite'] == 'Lax'
    assert 'mw_session' not in cookies
    api = page.request.get(server + '/api/m01/projects').json()
    assert [p['disp'] for p in api] == ['隔离项目', '长项目名验收']
    page.reload()
    expect(page.get_by_role('button', name='预览管理员（管理员）', exact=True)).to_be_visible()
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')
    page.evaluate('document.fonts.ready')
    assert page.evaluate("document.fonts.check('14px MiSans')")
    page.screenshot(path=str(output('projects-1080.png', kind='screenshots')), full_page=True)
    pick_option(page, '项目状态筛选', '归档')
    expect(page.get_by_label('展示名：归档样例', exact=True)).to_have_value('归档样例')
    page.get_by_label('项目搜索', exact=True).fill('不存在的验收项目')
    expect(page.get_by_text('没有符合条件的项目。可调整筛选，或手工建档、同步名单。', exact=True)).to_be_visible()
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
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')
    pick_option(page, '项目状态筛选', '归档')
    expect(page.get_by_label('展示名：归档样例', exact=True)).to_have_value('归档样例')
    context.clear_cookies()
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('登录已失效')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')
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
    with page.expect_request('**/api/m01/projects?status=all'):
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
    expect(page.get_by_label('展示名：隔离项目', exact=True)).to_have_value('隔离项目')
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


def test_project_inline_save_keeps_next_draft_and_failed_input(server, browser_page):
    page, _ = browser_page
    login(page, server)
    projects = page.request.get(server + '/api/m01/projects?status=all').json()
    project = next(row for row in projects if row['disp'] == '隔离项目')
    saved_name = project['name_full']
    writes, delayed = [], []
    hold_reads = False
    fail_write = False

    def read(route):
        if hold_reads:
            delayed.append(route)
        else:
            route.fulfill(json=projects)

    def write(route):
        payload = route.request.post_data_json
        writes.append(payload)
        if fail_write:
            route.fulfill(status=409, json={'message': '此项未保存，请核对后重试。'})
        else:
            project.update(payload)
            route.fulfill(json=project)

    page.route('**/api/m01/projects?status=all', read)
    page.route(f'**/api/m01/projects/{project["id"]}', write)
    display = page.get_by_label('展示名：隔离项目', exact=True)
    hold_reads = True
    display.fill('行内展示名')
    with page.expect_request('**/api/m01/projects?status=all'):
        display.press('Tab')
    full = page.locator('.project-table tbody tr').filter(has=page.get_by_text(project['warehouse_name'], exact=True)).get_by_role('textbox').nth(1)
    # The next cell remains editable while the preceding save is being read back.
    full.fill('下一格尚未保存的草稿')
    hold_reads = False
    assert delayed
    delayed.pop().fulfill(json=projects)
    expect(full).to_have_value('下一格尚未保存的草稿')
    full.press('Escape')
    expect(full).to_have_value(saved_name)
    assert writes == [{'disp': '行内展示名'}]
    expect(page.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
    expect(page.get_by_title('纠正项目类型', exact=True)).to_have_count(0)
    fail_write = True
    display = page.get_by_label('展示名：行内展示名', exact=True)
    display.fill('失败后保留的输入')
    display.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='此项未保存')).to_contain_text('已保留输入')
    expect(display).to_have_value('失败后保留的输入')
    search = page.get_by_label('项目搜索', exact=True)
    search.fill('不存在的项目')
    expect(display).to_have_count(0)
    search.fill('')
    expect(display).to_have_value('失败后保留的输入')
    expect(page.get_by_role('alert').filter(has_text='此项未保存')).to_contain_text('已保留输入')
    display.press('Escape')
    expect(display).to_have_value('行内展示名')
    fail_write = False
    full.fill('行内修改项目全名')
    full.press('Enter')
    expect(full).to_have_value('行内修改项目全名')
    expect(page.get_by_role('status').filter(has_text='正在保存')).to_have_count(0)
    assert writes[-1] == {'name_full': '行内修改项目全名'}


@pytest.mark.parametrize('source, button', [('warehouses', '同步仓库名单'), ('common-projects', '同步常用项目列表')])
def test_project_sync_confirmation_never_forces_i8_login(server, browser_page, source, button):
    page, _ = browser_page
    login(page, server)
    writes = []
    page.route('**/api/m02/config', lambda route: route.fulfill(json={
        'account': 'preview-admin', 'i8_user': '验收绑定账号', 'ready': True, 'message': '',
    }))
    def sync(route):
        writes.append(route.request.url)
        route.fulfill(status=409, json={'message': 'i8 账号正在其他会话使用，请稍后重试。'})
    page.route(f'**/api/m02/sync/{source}?*', sync)
    page.get_by_role('button', name=button, exact=True).click()
    dialog = page.get_by_role('dialog')
    expect(dialog.get_by_text('验收绑定账号', exact=True)).to_be_visible()
    expect(dialog.get_by_role('checkbox')).to_have_count(0)
    dialog.get_by_role('button', name='确认同步', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('i8 账号正在其他会话使用')
    assert len(writes) == 1 and 'allow_kick=false' in writes[0] and 'expected_account=preview-admin' in writes[0]
    dialog.get_by_role('button', name='取消', exact=True).click()


def test_project_native_drag_reorders_rows_and_reads_back(server, browser_page):
    page, _ = browser_page
    login(page, server)
    before = page.request.get(server + '/api/m01/projects?status=all').json()
    active = [row for row in before if row['status'] == 'active']
    assert len(active) >= 2
    first, last = active[0], active[-1]
    source = page.get_by_role('button', name=f'拖动排序：{first["disp"]}', exact=True)
    target = page.locator('.project-table tbody tr').filter(has=page.get_by_label(f'展示名：{last["disp"]}', exact=True))
    page.evaluate("""() => {
      window.__projectDragSnapshots = [];
      const table = document.querySelector('.project-table tbody');
      const snapshot = () => {
        const rows = [...table.rows];
        const moving = table.querySelector('.project-dragging');
        if (moving) window.__projectDragSnapshots.push({
          order: rows.map(row => row.querySelector('[aria-label^="排序："]').getAttribute('aria-label')),
          draggedCells: moving.cells.length,
          movingRows: rows.filter(row => row.getAnimations().length > 0).length,
        });
      };
      const observer = new MutationObserver(snapshot);
      observer.observe(table, {childList:true, subtree:true, attributes:true, attributeFilter:['class']});
      window.__projectDragObserver = observer;
    }""")
    expected = [row['id'] for row in active[1:]] + [first['id']]
    with page.expect_response(lambda response: response.url.endswith(f'/api/m01/projects/{first["id"]}/ord') and response.request.method == 'PUT', timeout=10000) as saved:
        source.drag_to(target)
    assert saved.value.ok, saved.value.text()
    page.wait_for_function("""expected => [...document.querySelectorAll('.project-table tbody tr [aria-label^="拖动排序："]')].map(el => el.getAttribute('aria-label')).join('|') === expected.join('|')""",
        arg=[f'拖动排序：{row["disp"]}' for row in active[1:]] + [f'拖动排序：{first["disp"]}'])
    after = page.request.get(server + '/api/m01/projects?status=all').json()
    assert [row['id'] for row in after if row['status'] == 'active'] == expected
    assert [row['id'] for row in after if row['status'] == 'archived'] == [row['id'] for row in before if row['status'] == 'archived']
    previews = page.evaluate('window.__projectDragObserver.disconnect(); window.__projectDragSnapshots')
    assert any(item['draggedCells'] == 10 for item in previews), previews
    assert any(item['order'][0] != f'排序：{first["disp"]}' for item in previews), previews
    assert any(item['movingRows'] > 0 for item in previews), previews
    print(f'NATIVE DRAG saved order={expected}; preview snapshots={len(previews)}; animated rows={max(item["movingRows"] for item in previews)}')


@pytest.mark.parametrize('response_mode', ['lost_response', 'incomplete_receipt'])
def test_project_uncertain_save_survives_escape_and_filter_until_readback(server, browser_page, response_mode):
    page, _ = browser_page
    login(page, server)
    projects = page.request.get(server + '/api/m01/projects?status=all').json()
    project = next(row for row in projects if row['disp'] == '隔离项目')
    writes = []
    read_fails = True
    def read(route):
        if read_fails:
            route.fulfill(status=503, json={'message': '项目暂时读不回来'})
        else:
            route.fulfill(json=projects)
    def write(route):
        payload = route.request.post_data_json
        writes.append(payload)
        project.update(payload)
        if response_mode == 'lost_response':
            route.abort('failed')
        else:
            route.fulfill(json={'id': project['id']})
    page.route('**/api/m01/projects?status=all', read)
    page.route(f'**/api/m01/projects/{project["id"]}', write)
    name = page.get_by_label('项目全名：隔离项目', exact=True)
    name.fill('已写入但回执丢失的全名')
    name.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible()
    name.focus()
    name.press('Escape')
    expect(name).to_have_value('已写入但回执丢失的全名')
    expect(name).not_to_be_editable()
    search = page.get_by_label('项目搜索', exact=True)
    search.fill('不存在的项目')
    expect(name).to_have_count(0)
    search.fill('')
    expect(name).to_have_value('已写入但回执丢失的全名')
    expect(name).not_to_be_editable()
    page.get_by_role('button', name='重读核对：项目全名：隔离项目', exact=True).click()
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_contain_text('项目暂时读不回来')
    expect(name).not_to_be_editable()
    read_fails = False
    page.get_by_role('button', name='重读核对：项目全名：隔离项目', exact=True).click()
    expect(name).to_be_editable()
    expect(name).to_have_value(project['name_full'])
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_have_count(0)
    assert writes == [{'name_full': '已写入但回执丢失的全名'}]


def test_project_undelivered_write_readback_keeps_input_for_retry(server, browser_page):
    page, _ = browser_page
    login(page, server)
    projects = page.request.get(server + '/api/m01/projects?status=all').json()
    project = next(row for row in projects if row['disp'] == '隔离项目')
    previous = project['name_full']
    writes = []
    def write(route):
        payload = route.request.post_data_json
        writes.append(payload)
        if len(writes) == 1:
            route.abort('failed')
        else:
            project.update(payload)
            route.fulfill(json=project)
    page.route('**/api/m01/projects?status=all', lambda route: route.fulfill(json=projects))
    page.route(f'**/api/m01/projects/{project["id"]}', write)
    name = page.get_by_label('项目全名：隔离项目', exact=True)
    name.fill('首次断网未送达的全名')
    name.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible()
    page.get_by_role('button', name='重读核对：项目全名：隔离项目', exact=True).click()
    expect(name).to_be_editable()
    expect(name).to_have_value('首次断网未送达的全名')
    expect(page.get_by_role('alert').filter(has_text='已重读核对')).to_contain_text(previous)
    assert project['name_full'] == previous
    assert writes == [{'name_full': '首次断网未送达的全名'}]
    name.focus()
    name.press('Enter')
    expect(page.get_by_role('status').filter(has_text='正在保存')).to_have_count(0)
    expect(page.get_by_role('alert').filter(has_text='已重读核对')).to_have_count(0)
    expect(name).to_have_value('首次断网未送达的全名')
    assert project['name_full'] == '首次断网未送达的全名'
    assert writes == [{'name_full': '首次断网未送达的全名'}] * 2
