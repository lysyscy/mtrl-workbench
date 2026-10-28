"""UI opt-in reaches real i8 login; generic callers keep conservative defaults."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import json
import re

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from app.core.errors import AppError
from app.mod02_i8 import client as clients
from app.mod02_i8.login import LoginResult
from app.mod06_proc import workbench_i8
from app.mod11_jc import api


@pytest.fixture
def login(monkeypatch):
    calls = []
    monkeypatch.setattr(clients.I8Client, '_creds', lambda self: ('isolated', ''))
    monkeypatch.setattr(clients.cookie_store, 'save', lambda *a, **kw: None)

    def authenticate(**kw):
        calls.append(kw['allow_kick'])
        return LoginResult(ok=kw['allow_kick'], conflict=True, cookie='isolated-cookie')

    monkeypatch.setattr(clients, 'http_login', authenticate)
    return calls


@pytest.mark.parametrize('route', ['auto-link-preview', 'auto-link'])
@pytest.mark.parametrize('allow_kick', [False, True])
def test_auto_link_login_policy_and_failure_before_business(monkeypatch, login, route, allow_kick):
    from app.mod02_i8 import payable_source
    # Exercise the real client/login boundary without network or disk cookies.
    def fetch(client):
        client._login()
        return []
    monkeypatch.setattr(payable_source, 'fetch_payables', fetch)
    monkeypatch.setattr(api, 'session_scope', lambda: nullcontext(None))
    business = []
    def plan(*args):
        business.append(route)
        return {'ok': True}
    monkeypatch.setattr(api.SV, 'auto_link_plan', plan)
    monkeypatch.setattr(api.SV, 'act_auto_link', plan)
    app = FastAPI()
    @app.exception_handler(AppError)
    async def error(request, exc):
        return JSONResponse(status_code=exc.http_status, content=exc.to_payload())
    app.include_router(api.router)
    payload = {'notice_ids': [1], 'selections': [{'notice_id': 1, 'contract_id': 2,
               'amount': '1.00', 'payable_codes': ['P1']}]}
    if allow_kick:
        payload['allow_kick'] = True
    with TestClient(app) as client:
        result = client.post('/api/m11/' + route, json=payload)
    assert result.status_code == (200 if allow_kick else 409)
    assert login == [allow_kick]  # No login-failure loop.
    assert business == ([route] if allow_kick else [])


@pytest.mark.parametrize('allow_kick', [False, True])
def test_mechanical_reader_opt_in_and_default(monkeypatch, login, allow_kick):
    def lists(client):
        client._login()
        return {kind: {'total': 0, 'rows': []} for kind in workbench_i8.SOURCES}
    monkeypatch.setattr(workbench_i8, 'fetch_lists', lists)
    if allow_kick:
        assert workbench_i8.read_preview([], allow_kick=True)['counts'] == {
            'usage': 0, 'project': 0, 'team': 0}
    else:
        with pytest.raises(clients.I8OnlineConflictError):
            workbench_i8.read_preview([])
    assert login == [allow_kick]


@pytest.mark.parametrize('route', ['auto-link-preview', 'auto-link'])
def test_failed_ui_login_stops_without_retry_or_business_write(monkeypatch, login, route):
    from app.mod02_i8 import payable_source
    calls = []
    def rejected(**kw):
        calls.append(kw['allow_kick'])
        return LoginResult(ok=False, detail='isolated authentication failure')
    monkeypatch.setattr(clients, 'http_login', rejected)
    monkeypatch.setattr(payable_source, 'fetch_payables', lambda client: client._login())
    def forbidden():
        raise AssertionError('login failure reached business transaction')
    monkeypatch.setattr(api, 'session_scope', forbidden)
    payload = api.AutoLinkIn(notice_ids=[1], allow_kick=True, selections=[
        api.AutoLinkSelection(notice_id=1, contract_id=2, amount='1.00', payable_codes=['P1'])])
    with pytest.raises(AppError, match='isolated authentication failure'):
        (api.api_auto_link_preview if route.endswith('preview') else api.api_auto_link)(payload)
    assert calls == [True]


@pytest.mark.parametrize('path', ['projects.tsx', 'notice-auto-link.tsx',
    'mechanical-work.tsx', 'notice-maintenance.tsx', 'notice-fetch.tsx'])
def test_react_i8_request_wiring(path):
    # Stable opt-in contract only; backend tests cover login and business state.
    root = Path(__file__).resolve().parents[2] / 'apps/frontend/src'
    assert re.search(r'''allow_kick\s*:\s*(?:true\b|['"]true['"])''',
                     (root / path).read_text(encoding='utf-8'))


@pytest.mark.parametrize('allow_kick,authenticated', [(False, False), (True, True), (True, False)])
def test_http_online_conflict_kicks_only_when_opted_in_without_failure_loop(monkeypatch, allow_kick, authenticated):
    from app.mod02_i8 import login as http_login
    calls = []
    client_type = httpx.Client
    def respond(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(200, json={'success': False, 'msg': json.dumps(
                {'sessionID': 'isolated-session', 'userId': 'isolated'})})
        if request.url.path == http_login.KICK_PATH:
            return httpx.Response(200, json={'success': True})
        return httpx.Response(200, json={'accesstoken': 'isolated'} if authenticated else {'success': False})
    monkeypatch.setattr(http_login, 'get_settings', lambda: SimpleNamespace())
    monkeypatch.setattr(http_login, 'i8_base_of', lambda settings: 'https://i8.invalid')
    monkeypatch.setattr(http_login, 'sm2_encrypt', lambda plain: plain)
    monkeypatch.setattr(http_login.httpx, 'Client', lambda **kw:
                        client_type(**kw, transport=httpx.MockTransport(respond)))
    result = http_login.http_login(user='isolated', password='', **({'allow_kick': True} if allow_kick else {}))
    assert result.ok is authenticated
    assert result.conflict and result.kicked_online is allow_kick
    assert calls == ([http_login.LOGIN_PATH, http_login.KICK_PATH, http_login.LOGIN_PATH]
                     if allow_kick else [http_login.LOGIN_PATH])
