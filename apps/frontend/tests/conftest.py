"""Shared preview seed seam; each server owns its schema before seeding."""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope='module')
def preview_browser():
    # Keep Playwright's sync event loop inside its test module.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture(scope='module')
def preview_seed():
    return lambda env: None


@pytest.fixture(scope='module')
def preview_factory():
    return 'tools.dev.frontend_preview:create_preview_app'
