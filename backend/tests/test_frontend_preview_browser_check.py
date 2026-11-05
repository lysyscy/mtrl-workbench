"""A live-check scope never enables HTTP login, printing or unrelated fetches."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dev.frontend_preview_browser_check import (BrowserNoticeCheck, approved_notice_context,
    browser_transport_allowed, enforce_browser_transport, load_check)
from tools.dev.frontend_preview_copy import restrict_copy_preview


SCOPE = BrowserNoticeCheck.parse({'year_month': '2026-11', 'origin': 'http://i8.example.test:30785', 'i8_user': 'fixture-user'})
PAYLOAD = {'year_month': '2026-11', 'session_mode': 'browser', 'device_id': 'fixture-device', 'expected_account': 'preview-admin'}


def client_for(scope=None):
    app = FastAPI()

    @app.post('/api/m03/notices/fetch')
    def notice(body: dict):
        # The real business endpoint is synchronous: prove context propagation to its worker too.
        return {'body': body, 'browser_transport_allowed': browser_transport_allowed()}

    @app.api_route('/{path:path}', methods=['GET', 'POST'])
    async def echo(request: Request, path: str):
        return {'body': await request.json() if request.method == 'POST' else None,
                'browser_transport_allowed': browser_transport_allowed()}

    restrict_copy_preview(app, full_app=True, browser_notice_check=scope, preview_account='preview-admin')
    return TestClient(app)


def test_default_preview_keeps_all_external_actions_blocked():
    with client_for() as client:
        assert client.get('/api/m02/browser/state?device_id=fixture').status_code == 200
        for path in ('/api/m03/notices/fetch', '/api/m03/batch', '/api/m11/fetch', '/api/m02/browser/connect',
                     '/api/m02/browser/complete', '/api/m02/sync/warehouses'):
            assert client.post(path, json=PAYLOAD).status_code == 403
        assert client.get('/api/m02/browser/pending?device_id=fixture').status_code == 403
        assert client.post('/api/m05/history/save', json={}).status_code == 200


def test_scoped_notice_keeps_the_original_body_for_the_business_route():
    with client_for(SCOPE) as client:
        response = client.post('/api/m03/notices/fetch', json=PAYLOAD)
        assert response.status_code == 200
        assert response.json()['body'] == PAYLOAD
        assert response.json()['browser_transport_allowed'] is True
        assert client.get('/api/m01/projects').json()['browser_transport_allowed'] is False
        for change in ({'year_month': '2026-10'}, {'session_mode': 'http'}, {'expected_account': 'someone-else'},
                       {'device_id': ''}, {'allow_kick': True}):
            assert client.post('/api/m03/notices/fetch', json={**PAYLOAD, **change}).status_code == 403
        assert client.post('/api/m03/notices/fetch', content='invalid-json').status_code == 403
        for path in ('/api/m03/batch', '/api/m11/fetch', '/api/m07/fetch', '/api/m08/fetch',
                     '/api/m06/workbench/i8-fetch', '/api/m03/notices/warehouse-check', '/api/m02/sync/warehouses',
                     '/api/m13/invoice-batches/1/run', '/api/m05/history/save'):
            assert client.post(path, json=PAYLOAD).status_code == 403
        assert client.post('/m15/login', json={}).status_code == 200


def test_connect_is_pinned_to_the_approved_site():
    connect = {'device_id': 'fixture-device', 'i8_origin': SCOPE.origin}
    with client_for(SCOPE) as client:
        assert client.post('/api/m02/browser/connect', json=connect).status_code == 200
        for change in ({'i8_origin': 'http://other.example.test'}, {'device_id': ''}):
            assert client.post('/api/m02/browser/connect', json={**connect, **change}).status_code == 403
        assert client.get('/api/m02/browser/pending?device_id=fixture-device').status_code == 200
        assert client.get('/api/m02/browser/pending').status_code == 403


def test_scope_cannot_be_applied_to_an_existing_or_non_disposable_database(tmp_path):
    for copy_source, disposable, existing in ((False, True, False), (True, False, False), (True, True, True)):
        args = SimpleNamespace(browser_notice_check=tmp_path / 'scope.json', copy_source=copy_source,
                               disposable=disposable, existing=existing)
        with pytest.raises(RuntimeError, match='新建的真实可丢弃副本'):
            load_check(args, tmp_path)
    with pytest.raises(ValueError):
        BrowserNoticeCheck.parse({'year_month': '2026-11', 'origin': SCOPE.origin, 'i8_user': SCOPE.i8_user, 'cookie': 'forbidden'})


def test_transport_guard_blocks_http_and_cookie_only_clients(monkeypatch):
    from app.core.errors import MustReportError
    from app.mod02_i8.client import I8Client
    from app.mod02_i8.browser_session import I8BrowserSessionClient, ReusedBrowserSession
    from app.mod02_i8.browser_relay import BrowserRelayTransport
    # Record originals in monkeypatch so this process-local preview policy cannot leak to other tests.
    monkeypatch.setattr(I8Client, '_ensure_session', I8Client._ensure_session)
    monkeypatch.setattr(I8Client, '_login', I8Client._login)
    sentinel = object()
    monkeypatch.setattr(I8BrowserSessionClient, '_ensure_session', lambda self: sentinel)
    enforce_browser_transport()
    with pytest.raises(MustReportError):
        I8Client()._ensure_session()
    with pytest.raises(MustReportError):
        I8Client()._login()
    with pytest.raises(MustReportError):
        I8BrowserSessionClient(ReusedBrowserSession(base_url=SCOPE.origin, cookie_header='fixture-cookie'))._ensure_session()
    transport = BrowserRelayTransport(owner='preview-admin', device='fixture-device', origin=SCOPE.origin)
    client = I8BrowserSessionClient(ReusedBrowserSession(base_url=SCOPE.origin, transport=transport))
    with pytest.raises(MustReportError):
        client._ensure_session()
    with approved_notice_context():
        assert client._ensure_session() is sentinel
    assert browser_transport_allowed() is False
