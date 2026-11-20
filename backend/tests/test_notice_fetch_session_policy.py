"""TAIL-504 contract at the notice route, using a fake i8 and the real session clients."""

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import app_settings
from app.core.config import I8_PATH_PAYMENT_NOTICE
from app.core.errors import MustReportError
from app.core.session import set_current_name
from app.main import _install_error_handlers
from app.mod02_i8 import browser_broker, cookie_store, login, session_policy
from app.mod03_notice.router import router

BASE = "https://i8.example.test"
DEVICE = "notice-test-device"
OWNER = "operator"
PAYLOAD = {"year_month": "2026-10", "session_mode": "http"}
SOURCE = {
    "Record": [{
        "PhId": "isolated-notice", "BillNo": "N-1", "BillDt": "2026-10-05",
        "PhidBusType_EXName": "付劳务公司款", "ApproveAmt": "8.50",
    }],
}


@pytest.fixture
def case(monkeypatch, rollback_db):
    state = SimpleNamespace(
        base=BASE, user="i8-operator", requests=[], cache_reads=[], cached="", expires=False, online=True,
        store=browser_broker.BrowserBroker(),
    )
    monkeypatch.setattr(browser_broker, "_BROKER", state.store)
    monkeypatch.setattr(app_settings, "effective", lambda key, default: state.base if key == "i8_base_url" else default)
    monkeypatch.setattr(session_policy, "current_i8_credentials", lambda: (state.user, ""))
    monkeypatch.setattr(session_policy, "_tokens", {})
    monkeypatch.setattr(login, "sm2_encrypt", lambda plain: plain)

    def load_cookie(user, origin):
        assert origin == session_policy._origin_of(state.base)
        state.cache_reads.append(user)
        return state.cached

    monkeypatch.setattr(cookie_store, "load", load_cookie)
    monkeypatch.setattr(cookie_store, "save", lambda *args, **kwargs: None)
    monkeypatch.setattr(cookie_store, "clear", lambda *args, **kwargs: None)

    def respond(request):
        assert request.url.host == httpx.URL(state.base).host
        state.requests.append(request)
        path = request.url.path
        if path == login.LOGIN_PATH:
            payload = json.loads(parse_qs(request.content.decode())["body"][0])
            if not state.online or payload.get("isOnlineCheck") == "1":
                return httpx.Response(200, json={"accesstoken": "isolated"}, headers={"set-cookie": "i8-test=new"})
            return httpx.Response(200, json={"msg": json.dumps({
                "sessionID": "existing-session", "userId": "test-i8-user", "ipAddress": "127.0.0.1",
            })})
        if path == login.KICK_PATH:
            return httpx.Response(200)
        assert path == I8_PATH_PAYMENT_NOTICE
        return httpx.Response(401) if state.expires else httpx.Response(200, json=SOURCE)

    client_type = httpx.Client

    def mock_http_client(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(respond))
        return client_type(**kwargs)

    monkeypatch.setattr(httpx, "Client", mock_http_client)
    app = FastAPI()
    _install_error_handlers(app)
    app.include_router(router)
    from app.mod02_i8.router import router as session_router
    app.include_router(session_router)

    @app.middleware("http")
    async def bind_identity(request: Request, call_next):
        set_current_name(request.headers.get("x-test-owner", OWNER))
        return await call_next(request)

    with TestClient(app) as client:
        def post(payload=None, *, owner=OWNER):
            return client.post("/api/m03/notices/fetch", json=PAYLOAD if payload is None else payload,
                               headers={"x-test-owner": owner})
        state.post = post
        state.cancel = lambda token, owner=OWNER: client.post(
            "/api/m02/session/kick-cancel", json={"kick_token": token}, headers={"x-test-owner": owner},
        )
        yield state


def paths(case):
    return [request.url.path for request in case.requests]


def conflict_token(response):
    assert response.status_code == 409, response.text
    error = response.json()
    assert error["code"] == "i8_online_conflict"
    assert "让现有会话下线" in error["message"]
    return error["detail"]["kick_token"]


def browser_request(case, *, status=200):
    def relay():
        pending = case.store.take_pending(OWNER, DEVICE, timeout=3)
        assert pending is not None
        response = json.dumps(SOURCE).encode()
        assert case.store.complete(OWNER, DEVICE, pending.ticket, generation=pending.generation, status=status,
                                   headers={"content-type": "application/json"}, body=response,
                                   declared_length=len(response))
        return pending

    with ThreadPoolExecutor(max_workers=1) as executor:
        ticket = executor.submit(relay)
        reply = case.post({**PAYLOAD, "session_mode": "browser", "device_id": DEVICE, "allow_kick": True})
        return reply, ticket.result()


def test_notice_fetch_uses_the_connected_browser_and_writes_receipt(case):
    case.store.connect(OWNER, DEVICE, BASE)
    reply, pending = browser_request(case)
    assert reply.status_code == 200, reply.text
    assert reply.json()["upserted"] == 1
    assert reply.json()["receipt"]["scope"] == "2026-10"
    assert pending.url == BASE + I8_PATH_PAYMENT_NOTICE
    form = parse_qs(pending.body.decode())
    assert "2026-10-01" in form["queryfilter"][0] and "2026-10-31" in form["queryfilter"][0]
    assert case.requests == case.cache_reads == []


@pytest.mark.parametrize("mode", [None, "", "unexpected"])
def test_explicit_mode_required_before_any_i8_client(case, mode):
    payload = {"year_month": "2026-10", "allow_kick": True}
    if mode is not None:
        payload["session_mode"] = mode
    assert case.post(payload).status_code == 400
    assert case.requests == case.cache_reads == []


@pytest.mark.parametrize("failure", ["disconnected", "wrong_device", "wrong_origin", "expired"])
def test_browser_session_failures_never_reach_direct_login(case, failure):
    if failure == "wrong_device":
        case.store.connect(OWNER, "other-device", BASE)
    if failure == "wrong_origin":
        case.store.connect(OWNER, DEVICE, "https://other.example.test")
    if failure == "expired":
        case.store.connect(OWNER, DEVICE, BASE)
        reply, _ = browser_request(case, status=401)
    else:
        reply = case.post({**PAYLOAD, "session_mode": "browser", "device_id": DEVICE, "allow_kick": True})
    expected = {
        "disconnected": (400, "i8_browser_relay_unavailable"),
        "wrong_device": (400, "i8_browser_relay_unavailable"),
        "wrong_origin": (409, "i8_strict_target_mismatch"),
        "expired": (502, "i8_strict_session_ended"),
    }
    assert (reply.status_code, reply.json()["code"]) == expected[failure]
    assert case.requests == case.cache_reads == []


def test_http_reuses_the_bound_account_cookie(case):
    case.cached = "i8-test=cached"
    reply = case.post()
    assert reply.status_code == 200, reply.text
    assert paths(case) == [I8_PATH_PAYMENT_NOTICE]
    assert case.cache_reads == [case.user]
    assert case.requests[0].headers["cookie"] == case.cached


def test_http_can_log_in_without_a_confirmation_when_there_is_no_conflict(case):
    case.online = False
    assert case.post().status_code == 200
    assert paths(case) == [login.LOGIN_PATH, login.LOGIN_PATH, I8_PATH_PAYMENT_NOTICE]


def test_only_one_concurrent_confirmation_can_kick(case):
    token = conflict_token(case.post({**PAYLOAD, "allow_kick": True}))
    assert paths(case) == [login.LOGIN_PATH]
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(case.post, [{**PAYLOAD, "kick_token": token}] * 2))
    assert sorted(reply.status_code for reply in replies) == [200, 400]
    assert paths(case) == [login.LOGIN_PATH, login.LOGIN_PATH, login.KICK_PATH, login.LOGIN_PATH, I8_PATH_PAYMENT_NOTICE]


@pytest.mark.parametrize("change", ["scope", "owner", "origin", "user", "expired", "invalid", "mode"])
def test_rejected_confirmation_causes_no_direct_request(case, monkeypatch, change):
    token = conflict_token(case.post())
    request, owner = {**PAYLOAD, "kick_token": token}, OWNER
    if change == "scope":
        request["year_month"] = "2026-11"
    elif change == "owner":
        owner = "other-owner"
    elif change == "origin":
        case.base = "https://other.example.test"
    elif change == "user":
        case.user = "other-i8-user"
    elif change == "expired":
        monkeypatch.setattr(session_policy, "time", SimpleNamespace(monotonic=lambda: float("inf")))
    elif change == "invalid":
        request["kick_token"] = "unissued-token"
    else:
        request["session_mode"] = "browser"
    reply = case.post(request, owner=owner)
    assert reply.status_code == 400, reply.text
    assert paths(case) == [login.LOGIN_PATH]


def test_confirmation_is_bound_to_the_operation(case):
    token = conflict_token(case.post())
    with pytest.raises(MustReportError, match="确认已失效"):
        with session_policy.unified_i8_session(
            {"session_mode": "http", "kick_token": token}, owner=OWNER,
            operation="different.operation", scope={"year_month": PAYLOAD["year_month"]},
        ):
            pytest.fail("a token from notice fetch cannot authorize a different operation")
    assert paths(case) == [login.LOGIN_PATH]


def test_confirmation_cannot_kick_again_on_immediate_session_expiry(case):
    token = conflict_token(case.post())
    case.expires = True
    reply = case.post({**PAYLOAD, "kick_token": token})
    assert reply.status_code == 409
    assert "detail" not in reply.json()
    assert paths(case).count(login.KICK_PATH) == 1
    assert case.post({**PAYLOAD, "kick_token": token}).status_code == 400
    assert paths(case).count(login.KICK_PATH) == 1


def test_kick_cancel_is_authenticated_owner_scoped_and_single_use(case):
    conflict = {**PAYLOAD, "session_mode": "http"}
    token = conflict_token(case.post(conflict))
    assert case.cancel(token, owner="").status_code == 401
    assert case.cancel(token, owner="different-account").status_code == 200
    assert case.post({**conflict, "kick_token": token}).status_code == 200
    assert paths(case).count(login.KICK_PATH) == 1
    assert case.cancel(token).status_code == 200
    assert case.post({**conflict, "kick_token": token}).status_code == 400

    token = conflict_token(case.post(conflict))
    assert case.cancel(token).status_code == 200
    assert case.cancel(token).status_code == 200
    assert case.post({**conflict, "kick_token": token}).status_code == 400
    assert paths(case).count(login.KICK_PATH) == 1
