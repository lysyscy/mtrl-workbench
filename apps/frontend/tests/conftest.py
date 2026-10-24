"""Shared preview seed seam; each server owns its schema before seeding."""
import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
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
def make_preview_seed():
    def make(seed=lambda env: None):
        def run(env):
            build = os.environ.get('MTRL_PREVIEW_TEST_BUILD')
            if build:
                env['FRONTEND_PREVIEW_DIR'] = build
            seed(env)
        return run
    return make


@pytest.fixture(scope='module')
def preview_seed(make_preview_seed):
    return make_preview_seed()


@pytest.fixture(scope='module')
def preview_session():
    @contextmanager
    def session(env):
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as current:
                assert current.execute(text('SELECT current_database(),current_schema()')).one() == (
                    'mtrl_workbench_test', env['PGOPTIONS'].split('search_path=')[1])
                yield current
        finally:
            engine.dispose()
    return session


@pytest.fixture(scope='module')
def preview_factory():
    return 'tools.dev.frontend_preview:create_preview_app'
