"""Build, cookie, real read and permission wiring on the single registered preview."""
from pathlib import Path
import re
import httpx
import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[3]


class PreviewAddress(str):
    def __new__(cls,base,owner):
        value=super().__new__(cls,base);value.owner=owner;return value


@pytest.fixture(scope='session')
def server(real_preview):
    return PreviewAddress(real_preview[2],real_preview[1])


@pytest.fixture
def browser_page(server, preview_browser):
    from tools.dev.frontend_preview_runtime import registered_preview,assert_same_preview
    assert_same_preview(server.owner,registered_preview()[1])
    context = preview_browser.new_context(viewport={'width':1920, 'height':1080})
    page=None
    try:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        yield page, context
        assert not errors, errors
    finally:
        if page is not None and not page.is_closed():page.unroute_all(behavior='wait')
        context.close()


def login(page, server, account=None):
    from tools.dev.frontend_preview_runtime import registered_preview,assert_same_preview
    owner = registered_preview()[1]
    assert_same_preview(server.owner,owner)
    account = account or owner['preview_account']
    page.goto(server + '/login?next=%2Fpreview%2Fprojects')
    page.locator('[name=account]').fill(account)
    page.locator('[name=password]').fill('')
    page.locator('button[type=submit]').click()
    expect(page).to_have_url(server + '/preview/projects')
    expect(page.get_by_role('heading', name='项目档案', exact=True)).to_be_visible()
    me = page.request.get(server + '/api/m15/users').json()['me']
    assert me and me['account'] == account
    return me


def test_fastapi_build_assets_cookie_and_real_read(server, browser_page, real_preview, projects):
    page, context = browser_page
    html = httpx.get(server + '/preview/projects')
    assert html.status_code == 200 and html.headers['cache-control'] == 'no-cache'
    assets = re.findall(r'(?:src|href)="(/preview/assets/[^" ]+)"', html.text)
    assert assets and any(asset.endswith('.js') for asset in assets) and any(asset.endswith('.css') for asset in assets)
    assert all(httpx.get(server + asset).status_code == 200 for asset in assets)
    assert httpx.get(server + '/preview/assets/missing.js').status_code == 404
    assert httpx.get(server + '/app').content == (ROOT / 'backend/app/web/index.html').read_bytes()
    me = login(page, server)
    owner = real_preview[1]
    cookies = {c['name']:c for c in context.cookies()}
    assert cookies[owner['cookie_name']]['httpOnly'] and cookies[owner['cookie_name']]['sameSite'] == 'Lax'
    assert 'mw_session' not in cookies
    row = next(p for p in projects if p['status'] == 'active')
    expect(page.get_by_label('展示名：' + row['disp'], exact=True)).to_have_value(row['disp'])
    page.reload()
    assert page.request.get(server + '/api/m15/users').json()['me']['account'] == me['account']
    expect(page.locator('#page-title')).to_have_text('项目档案')
    page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    page.evaluate("document.fonts.load('14px MiSans',document.querySelector('#page-title').textContent)")
    page.wait_for_function("document.fonts.check('14px MiSans',document.querySelector('#page-title').textContent)")
    assert page.locator('#page-title').evaluate("e=>getComputedStyle(e).fontFamily.startsWith('MiSans')")


def test_real_read_failure_retry_and_session_expiry(server, browser_page, projects):
    page, context = browser_page
    login(page, server)
    page.route('**/api/m01/projects?status=all', lambda route: route.abort('failed'))
    page.reload()
    expect(page.get_by_role('alert')).to_be_visible()
    page.unroute('**/api/m01/projects?status=all')
    page.get_by_role('button', name='重读项目', exact=True).click()
    row = next(p for p in projects if p['status'] == 'active')
    expect(page.get_by_label('展示名：' + row['disp'], exact=True)).to_have_value(row['disp'])
    context.clear_cookies()
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 手工建档', exact=True)).to_be_disabled()


def test_actual_permission_rejection_and_invalid_cookie(server, real_preview):
    owner = real_preview[1]
    with httpx.Client(base_url=server) as client:
        assert client.post('/api/m01/projects', json={}).status_code == 401
        client.cookies.set(owner['cookie_name'], 'invalid')
        assert client.get('/api/m15/users').json()['me'] is None
        assert client.post('/api/m01/projects', json={}).status_code == 401


def test_project_inline_write_readback_and_unknown_result(server, browser_page, projects, disposable):
    page, _ = browser_page
    login(page, server)
    row = next(p for p in projects if p['status'] == 'active' and p['project_type'] == 'normal')
    value = row['name_full'] + '（校验）'
    writes = []
    def lose_receipt(route):
        response = route.fetch()
        assert response.ok
        writes.append(route.request.post_data_json)
        route.abort('failed')
    page.route(f'**/api/m01/projects/{row["id"]}', lose_receipt)
    field = page.get_by_label('项目全名：' + row['disp'], exact=True)
    field.fill(value)
    field.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible()
    expect(field).not_to_be_editable()
    field.press('Escape')
    expect(field).to_have_value(value)
    page.get_by_role('button', name='重读核对：项目全名：' + row['disp'], exact=True).click()
    expect(field).to_be_editable()
    expect(field).to_have_value(value)
    assert len(writes) == 1
    current = page.request.get(server + '/api/m01/projects?status=all').json()
    assert next(p for p in current if p['id'] == row['id'])['name_full'] == value
    expect(page.get_by_title('纠正项目类型', exact=True)).to_have_count(0)
    expect(page.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
