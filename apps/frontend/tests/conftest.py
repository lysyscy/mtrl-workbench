"""Browser tests attach to the registered real-copy preview; no seeding or server creation."""
from pathlib import Path
import sys
import httpx
import pytest
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope='session')
def real_preview():
    from tools.dev.frontend_preview_runtime import registered_preview
    return registered_preview()


@pytest.fixture(scope='session')
def preview_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture(scope='session')
def api(real_preview):
    _, owner, base = real_preview
    with httpx.Client(base_url=base, timeout=60) as client:
        assert client.post('/m15/login', data={'account':owner['preview_account'], 'password':''}).status_code == 303
        me = client.get('/api/m15/users').json()['me']
        assert me and me['account'] == owner['preview_account']
        yield client


@pytest.fixture
def disposable(real_preview):
    from tools.dev.frontend_preview_runtime import registered_preview,assert_same_preview
    _, current, _=registered_preview()
    assert_same_preview(real_preview[1],current,disposable=True)
    return current


@pytest.fixture
def projects(api):
    result=api.get('/api/m01/projects?status=all');result.raise_for_status();rows=result.json()
    assert rows,'真实副本没有项目，项目相关路径未覆盖'
    return rows
