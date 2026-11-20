"""i8 login failure stops business work, and explicit generic client opt-in can kick."""
from types import SimpleNamespace
import json

import httpx
import pytest

from app.core.errors import AppError
from app.mod02_i8 import client as clients, session_policy
from app.mod02_i8.login import LoginResult
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
def test_failed_ui_login_stops_without_retry_or_business_write(monkeypatch, login, route):
    from app.core import app_settings
    from app.mod02_i8 import payable_source

    monkeypatch.setattr(api, "current_name", lambda: "isolated")
    monkeypatch.setattr(session_policy, "current_i8_credentials", lambda: ("isolated", ""))
    monkeypatch.setattr(app_settings, "effective", lambda key, default: "https://i8.example.test")
    calls = []
    def rejected(**kw):
        calls.append(kw['allow_kick'])
        return LoginResult(ok=False, detail='isolated authentication failure')
    monkeypatch.setattr(clients, 'http_login', rejected)
    monkeypatch.setattr(payable_source, 'fetch_payables', lambda client: client._login())
    def forbidden():
        raise AssertionError('login failure reached business transaction')
    monkeypatch.setattr(api, 'session_scope', forbidden)
    payload = api.AutoLinkIn(notice_ids=[1], session_mode="http", allow_kick=True, selections=[
        api.AutoLinkSelection(notice_id=1, contract_id=2, amount='1.00', payable_codes=['P1'])])
    with pytest.raises(AppError, match='isolated authentication failure'):
        (api.api_auto_link_preview if route.endswith('preview') else api.api_auto_link)(payload)
    assert calls == [False]


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
