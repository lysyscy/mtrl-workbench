"""TAIL-400 manual-only i8 flow against a real disposable PostgreSQL backend."""
from datetime import datetime, timedelta
from urllib.parse import urlsplit
import httpx
import json
import shutil
import socket
import subprocess
import time
import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from test_preview import ROOT, server, browser_page, login
from tools.audit.workspace_paths import output, output_dir


@pytest.fixture(scope='module')
def preview_factory():
    return 'apps.frontend.tests.fixtures.i8_backend:create_app'


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        from app.mod01_projects.models import Project
        from app.mod15_user.models import UserAccount
        from app.mod14_config.models import AppSetting
        from app.mod02_i8.models import RunRecord
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as session:
                assert session.execute(text("select current_database(), current_schema(), current_setting('search_path')")).one() == ('mtrl_workbench_test', env['PGOPTIONS'].split('search_path=')[1], env['PGOPTIONS'].split('search_path=')[1])
                admin = session.scalar(select(UserAccount).where(UserAccount.account == 'preview-admin'))
                admin.i8_user, admin.i8_password = 'synthetic-admin', 'synthetic-password'
                session.add(AppSetting(key='i8_base_url', value='http://i8.invalid'))
                session.add(Project(project_type='shell', name_full='合成待归属壳', disp='合成壳', ord=5))
                start = datetime(2026, 8, 1, 9)
                for kind, target, status in [('fetch', 'inv 2026-08（1 个项目）', 'failed'), ('sync', '仓库列表', 'success'), ('print', '付款通知书 2099-01', 'partial')]:
                    session.add(RunRecord(run_type=kind, target=target, status=status, triggered_by='合成操作人', success_count=1, fail_count=1 if status == 'partial' else 0, error_message='fixed diagnostic <script>unsafe()</script>' if status == 'failed' else '', started_at=start, finished_at=start + timedelta(seconds=4.25)))
                session.commit()
        finally:
            engine.dispose()
    return seed


def open_i8(page, server, month='2026-01', account='preview-admin'):
    login(page, server, account)
    page.get_by_role('link', name='MOD-02 i8 接入层', exact=True).click()
    expect(page.get_by_role('heading', name='i8 接入层', exact=True)).to_be_visible()
    page.get_by_label('抓取月份', exact=True).fill(month)
    expect(page.get_by_text(f'单据日期 {month}-01', exact=False)).to_be_visible()


def snapshot(page, month=None):
    origin = urlsplit(page.url)
    value = page.request.get(f'{origin.scheme}://{origin.netloc}/__test__/i8').json()
    if month:
        return [call for call in value['calls'] if call['month'] == month]
    return value


def confirm(page, kick=False):
    page.get_by_role('button', name='准备抓取', exact=True).click()
    dialog = page.get_by_role('dialog')
    expect(dialog).to_be_visible()
    checkbox = dialog.get_by_role('checkbox')
    expect(checkbox).not_to_be_checked()
    if kick:
        checkbox.check()
    dialog.get_by_role('button', name='确认强踢并执行' if kick else '确认执行', exact=True).click()


def test_safe_mount_scope_and_read_retry_never_execute(server, browser_page):
    page, _ = browser_page
    before = httpx.get(server + '/__test__/i8').json()['calls']
    page.route('**/api/m02/fetch/records?**', lambda route: route.fulfill(status=503, json={'message': '记录暂时不可用'}))
    open_i8(page, server)
    expect(page.get_by_text('记录暂时不可用', exact=True)).to_be_visible()
    page.unroute('**/api/m02/fetch/records?**')
    page.get_by_role('button', name='重读记录', exact=True).click()
    expect(page.get_by_role('region', name='执行记录列表')).to_be_visible()
    page.get_by_label('抓取月份', exact=True).fill('2026-02')
    expect(page.get_by_text('单据日期 2026-02-01 至 2026-02-28（含首尾）', exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role('region', name='各来源最近结果')).to_be_visible()
    assert snapshot(page)['calls'] == before
    expect(page.get_by_role('region', name='各来源最近结果').get_by_role('row').filter(has_text='付款通知书').get_by_text('2099-01', exact=False)).to_have_count(0)
    expect(page.get_by_text('http://i8.invalid', exact=False)).to_be_visible()
    page.get_by_role('region', name='执行记录列表').get_by_role('row').filter(has_text='inv 2026-08').get_by_text('查看原因', exact=True).click()
    expect(page.get_by_text('fixed diagnostic <script>unsafe()</script>', exact=True)).to_be_visible()
    assert page.locator('.i8-page script').count() == 0
    page.screenshot(path=str(output('i8-default.png', kind='screenshots')), full_page=True)


def test_success_duplicate_click_navigation_late_month_and_real_duration(server, browser_page):
    page, _ = browser_page
    open_i8(page, server)
    page.get_by_role('button', name='准备抓取', exact=True).click()
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()
    assert snapshot(page, '2026-01') == []
    page.get_by_role('button', name='准备抓取', exact=True).click()
    button = page.get_by_role('dialog').get_by_role('button', name='确认执行', exact=True)
    button.evaluate('(button) => { button.click(); button.click(); }')
    expect(page.get_by_text('正在执行，等待 i8 回执…', exact=False).first).to_be_visible()
    page.get_by_label('抓取月份', exact=True).fill('2026-02')
    page.get_by_role('link', name='MOD-01 项目档案', exact=True).click()
    expect(page.locator('.i8-progress')).to_contain_text('2026-01')
    page.get_by_role('link', name='MOD-02 i8 接入层', exact=True).click()
    expect(page.locator('.i8-receipt')).to_contain_text('成功', timeout=15000)
    expect(page.locator('.i8-receipt')).to_contain_text('2026-01')
    local_hour = page.evaluate("() => { const key = Object.keys(sessionStorage).find(key => key.startsWith('mtrl-i8:') && key.endsWith(':preview-admin')); return String(new Date(JSON.parse(sessionStorage.getItem(key)).startedAt).getHours()).padStart(2, '0'); }")
    assert ' ' + local_hour + ':' in page.locator('.i8-receipt .muted').inner_text()
    page.screenshot(path=str(output('i8-success-local-time.png', kind='screenshots')), full_page=True)
    assert len(snapshot(page, '2026-01')) == 1
    data = snapshot(page)
    row = next(row for row in data['notices'] if row['ph_id'] == 'TAIL400-2026-01')
    assert row['owner'] is not None and row['amount'] == '100.25'
    run = next(row for row in data['runs'] if row['target'] == '2026-01')
    assert run['operator'] == '预览管理员' and run['duration'] >= 2 and run['status'] == 'success'
    expect(page.get_by_role('region', name='执行记录列表').get_by_text('2026-01', exact=True)).to_be_visible()
    expect(page.get_by_text('正在更新记录…', exact=True)).to_have_count(0)
    page.route('**/api/m02/fetch/records?**', lambda route: route.fulfill(status=503, json={'message': '写入后记录读取失败'}))
    page.get_by_label('读取范围', exact=True).select_option('100')
    expect(page.get_by_text('写入后记录读取失败', exact=True)).to_be_visible()
    expect(page.locator('.i8-receipt')).to_contain_text('成功')
    page.unroute('**/api/m02/fetch/records?**')
    page.get_by_role('button', name='重读记录', exact=True).click()
    expect(page.get_by_role('region', name='执行记录列表')).to_be_visible()
    assert len(snapshot(page, '2026-01')) == 1


def test_conflict_requires_new_explicit_kick_confirmation(server, browser_page):
    page, _ = browser_page
    open_i8(page, server, '2026-02')
    confirm(page)
    expect(page.locator('.i8-receipt')).to_contain_text('本次未强踢')
    assert [call['allow_kick'] for call in snapshot(page, '2026-02')] == [False]
    page.get_by_role('button', name='准备抓取', exact=True).click()
    dialog = page.get_by_role('dialog')
    expect(dialog.get_by_role('checkbox')).not_to_be_checked()
    page.screenshot(path=str(output('i8-conflict-confirm.png', kind='screenshots')), full_page=True)
    dialog.get_by_role('checkbox').check()
    dialog.get_by_role('button', name='确认强踢并执行', exact=True).click()
    expect(page.locator('.i8-receipt')).to_contain_text('成功')
    assert [call['allow_kick'] for call in snapshot(page, '2026-02')] == [False, True]


def test_failure_has_no_automatic_retry_or_retired_import(server, browser_page):
    page, _ = browser_page
    open_i8(page, server, '2026-03')
    confirm(page)
    expect(page.locator('.i8-receipt')).to_contain_text('未完成')
    expect(page.locator('.i8-receipt')).to_contain_text('请查看执行记录')
    page.get_by_label('动作', exact=True).select_option('fetch')
    expect(page.get_by_role('region', name='执行记录列表')).to_contain_text('失败')
    assert len(snapshot(page, '2026-03')) == 1
    assert '数据导入' not in page.locator('.i8-page').inner_text()
    confirm(page)
    expect(page.locator('.i8-receipt')).to_contain_text('未完成')
    assert len(snapshot(page, '2026-03')) == 2


def test_lost_receipt_reload_blocks_repeat_until_record_review(server, browser_page):
    page, _ = browser_page
    open_i8(page, server, '2026-04')
    def lose_response(route):
        response = route.fetch()
        assert response.ok
        route.abort('failed')
    page.route('**/api/m03/notices/fetch', lose_response)
    confirm(page)
    expect(page.locator('.i8-receipt')).to_contain_text('结果待核实', timeout=15000)
    expect(page.get_by_role('button', name='准备抓取', exact=True)).to_be_disabled()
    assert len(snapshot(page, '2026-04')) == 1
    page.reload()
    expect(page.locator('.i8-receipt')).to_contain_text('结果待核实')
    expect(page.get_by_role('button', name='准备抓取', exact=True)).to_be_disabled()
    page.get_by_role('button', name='核对执行记录', exact=True).click()
    expect(page.get_by_role('region', name='执行记录列表')).to_contain_text('2026-04')
    page.get_by_role('checkbox', name='已核对记录，并确认没有仍在执行的任务', exact=True).check()
    page.get_by_role('button', name='结束核对，允许重新准备', exact=True).click()
    expect(page.get_by_role('button', name='准备抓取', exact=True)).to_be_enabled()
    assert len(snapshot(page, '2026-04')) == 1
    page.get_by_role('button', name='准备抓取', exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('checkbox')).not_to_be_checked()
    page.get_by_role('dialog').get_by_role('button', name='取消', exact=True).click()


def test_partial_is_not_success_and_scope_remains_explicit(server, browser_page):
    page, _ = browser_page
    open_i8(page, server, '2026-05')
    confirm(page)
    expect(page.locator('.i8-receipt')).to_contain_text('部分成功')
    expect(page.locator('.i8-receipt')).to_contain_text('1 条归属未确定')
    data = snapshot(page)
    assert not any(row['ph_id'] == 'TAIL400-UNRESOLVED' for row in data['notices'])
    assert next(row for row in data['runs'] if row['target'] == '2026-05')['status'] == 'partial'
    page.get_by_label('抓取月份', exact=True).fill('2026-06')
    expect(page.locator('.i8-receipt')).to_contain_text('2026-05')
    assert snapshot(page, '2026-06') == []


def test_account_switch_rejects_stale_actor_and_drops_late_receipt(server, browser_page):
    page, context = browser_page
    open_i8(page, server, '2026-06')
    pending = []
    page.route('**/api/m03/notices/fetch', lambda route: pending.append(route))
    with page.expect_request('**/api/m03/notices/fetch'):
        confirm(page)
    expect(page.locator('.i8-progress')).to_contain_text('正在执行，等待 i8 回执…')
    assert pending
    with httpx.Client(base_url=server) as client:
        assert client.post('/m15/login', data={'account': 'preview-user', 'password': ''}).status_code == 303
        context.add_cookies([{'name': 'mw_preview_397', 'value': client.cookies['mw_preview_397'], 'url': server}])
        for url, body in [('/api/m03/notices/fetch', {'year_month': '2026-06', 'expected_account': 'preview-admin'}), ('/api/m02/sync/warehouses?expected_account=preview-admin', {}), ('/api/m02/sync/common-projects?expected_account=preview-admin', {})]:
            rejected = client.post(url, json=body)
            assert rejected.status_code == 409 and rejected.json()['code'] == 'data_conflict'
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('预览同事 · 普通用户', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='准备抓取', exact=True)).to_be_disabled()
    expect(page.get_by_text('未绑定', exact=True)).to_be_visible()
    route = pending.pop()
    route.fulfill(response=route.fetch())
    expect(page.locator('.i8-receipt')).to_have_count(0)
    expect(page.locator('.i8-progress')).to_have_count(0)
    assert len(snapshot(page, '2026-06')) == 1
    page.set_viewport_size({'width': 800, 'height': 900})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    action_column = page.get_by_role('region', name='执行记录列表').get_by_role('columnheader', name='动作', exact=True)
    assert action_column.bounding_box()['width'] >= 140
    page.screenshot(path=str(output('i8-unbound-narrow-dark-large.png', kind='screenshots')), full_page=True)


def test_invalid_address_disables_execution_and_safe_reads_never_login(server, browser_page):
    page, _ = browser_page
    open_i8(page, server, '2026-07')
    before = len(snapshot(page)['calls'])
    saved = page.request.post(server + '/api/m14/settings', data={'i8_base_url': ''})
    assert saved.ok and saved.json()['ok']
    try:
        page.reload()
        expect(page.get_by_text('i8 服务地址未配置或格式不正确，请联系维护人员核对。', exact=True).first).to_be_visible()
        expect(page.get_by_role('button', name='准备抓取', exact=True)).to_be_disabled()
        assert len(snapshot(page)['calls']) == before
    finally:
        assert page.request.post(server + '/api/m14/settings', data={'i8_base_url': 'http://i8.invalid'}).json()['ok']


@pytest.fixture(scope='module')
def i8_dev_server(server):
    # Exercise React's actual development StrictMode with only a loopback proxy.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    work = output_dir('work') / 'i8-vite'
    work.mkdir(exist_ok=True)
    script = work / 'server.mjs'
    script.write_text("const {createServer} = await import(" + json.dumps((ROOT / 'apps/frontend/node_modules/vite/dist/node/index.js').as_uri()) + ");\n"
        + "const server = await createServer(" + json.dumps({'configFile': str(ROOT / 'apps/frontend/vite.config.ts'), 'root': str(ROOT / 'apps/frontend'), 'cacheDir': str(work / 'cache'), 'server': {'host': '127.0.0.1', 'port': port, 'strictPort': True, 'proxy': {path: server for path in ['/api', '/static', '/login', '/m15', '/__test__']}}}) + ");\nawait server.listen();\n", encoding='utf-8')
    with output('i8-development.log', kind='logs').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([shutil.which('node'), str(script)], cwd=ROOT / 'apps/frontend', stdout=log, stderr=log)
        base = f'http://127.0.0.1:{port}'
        print(f'I8-DEV owned pid={process.pid} port={port}', flush=True)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail('Vite exited before readiness; inspect i8-development.log')
                try:
                    if httpx.get(base + '/preview/').status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            else:
                pytest.fail('Vite readiness timeout')
            yield base
        finally:
            process.terminate()
            process.wait(timeout=15)
            print(f'I8-DEV closed pid={process.pid} port={port} exit={process.returncode}', flush=True)


def test_real_development_strict_remount_never_executes(i8_dev_server, browser_page):
    page, _ = browser_page
    reads = []
    page.on('request', lambda request: reads.append(request.url) if '/api/m15/users' in request.url else None)
    open_i8(page, i8_dev_server)
    assert len(reads) >= 2
    source = page.request.get(i8_dev_server + '/preview/src/main.tsx').text()
    assert 'import.meta.hot' in source and 'StrictMode' in source
    before = snapshot(page)['calls']
    page.reload()
    expect(page.get_by_role('region', name='执行记录列表')).to_be_visible()
    page.get_by_label('抓取月份', exact=True).fill('2026-08')
    expect(page.get_by_text('单据日期 2026-08-01 至 2026-08-31（含首尾）', exact=True)).to_be_visible()
    assert snapshot(page)['calls'] == before
