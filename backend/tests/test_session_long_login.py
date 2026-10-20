"""长期登录的隔离验证：假密钥和内存 HTTP，不连接数据库或启动服务。"""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import hmac
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import session as SESS

KEY = b"isolated-long-login-key"


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setattr(SESS, "secret", lambda: KEY)


def signed(payload):
    """独立构造旧票或异常输入，不调用生产密钥。"""
    mac = hmac.new(KEY, payload.encode(), hashlib.sha256).digest()
    return payload + "." + base64.urlsafe_b64encode(mac).decode().rstrip("=")


@pytest.mark.parametrize("elapsed", [dt.timedelta(hours=12, seconds=1), dt.timedelta(days=3650)])
def test_signed_account_remains_valid_after_long_time(elapsed):
    issued = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    ticket = SESS.make("worker.with.dots", now=issued)
    identity = SESS.read(ticket, now=issued + elapsed)
    assert identity == "worker.with.dots"
    assert isinstance(identity, SESS.AccountIdentity)


@pytest.fixture
def memory_http(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core import db, logging as LOG

    def forbidden_database(*args, **kwargs):
        raise AssertionError("长期登录测试不得连接数据库")

    monkeypatch.setattr(db, "get_engine", forbidden_database)
    monkeypatch.setattr(LOG, "setup_logging", lambda: None)
    from app import main as MAIN
    from app.mod15_user import api as API

    root = Path(__file__).resolve().parents[1]
    for module in (SESS, API, MAIN):
        assert Path(module.__file__).resolve().is_relative_to(root)

    @contextmanager
    def memory_scope():
        yield object()

    def successful_login(session, *, account, password):
        assert account == "worker.with.dots" and password == "fake-password"
        return SimpleNamespace(account=account, name="Other display name")

    monkeypatch.setattr(API, "session_scope", memory_scope)
    monkeypatch.setattr(API.LG, "sign_in", successful_login)
    app = FastAPI()
    app.include_router(API.router)

    @app.post("/__session_probe")
    def probe():
        return {"account": SESS.current_name()}

    MAIN._install_session(app)
    MAIN._install_auth_gate(app)
    client = TestClient(app)
    yield client
    client.close()


def test_login_sets_persistent_cookie_and_logout_removes_identity(memory_http):
    client = memory_http
    response = client.post("/m15/login", data={
        "account": "worker.with.dots", "password": "fake-password", "next": "/app"
    }, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/app"
    cookie = SimpleCookie(response.headers["set-cookie"])[SESS.COOKIE_NAME]
    assert cookie["max-age"] == "34560000"  # 浏览器持久cookie为400天，服务器无时间过期。
    assert cookie["expires"] == ""
    assert cookie["httponly"] and cookie["samesite"] == "lax" and cookie["path"] == "/"
    assert not cookie["secure"]  # 保留局域网HTTP部署。
    assert client.post("/__session_probe").json() == {"account": "worker.with.dots"}
    response = client.post("/api/m15/logout")
    assert response.json()["ok"]
    assert "set-cookie" in response.headers, "退出必须由服务器发出清cookie响应"
    deleted = SimpleCookie(response.headers["set-cookie"])[SESS.COOKIE_NAME]
    assert deleted["max-age"] == "0" and deleted["path"] == "/"
    assert deleted["expires"]
    assert client.cookies.get(SESS.COOKIE_NAME) is None
    assert client.post("/__session_probe").status_code == 401


def test_pre_change_v2_ticket_is_no_longer_rejected_by_its_old_expiry(memory_http):
    # 用独立签名构造旧版v2格式：第三段原是过期戳，早已超过原12小时期限。
    encoded = base64.urlsafe_b64encode(b"worker.with.dots").decode().rstrip("=")
    ticket = signed(f"v2.{encoded}.946684800")  # 2000-01-01 UTC
    assert SESS.read(ticket, now=dt.datetime(2099, 1, 1, tzinfo=dt.timezone.utc)) == "worker.with.dots"
    memory_http.cookies.set(SESS.COOKIE_NAME, ticket)
    assert memory_http.post("/__session_probe").json() == {"account": "worker.with.dots"}


@pytest.mark.parametrize("part", [0, 1, 2, 3])
def test_tampering_each_signed_field_is_rejected_by_read_and_write_gate(memory_http, part):
    fields = SESS.make("worker.with.dots").split(".")
    fields[part] = ["v3", "YWRtaW4", "1", "A" * 43][part]
    tampered = ".".join(fields)
    assert SESS.read(tampered) is None
    memory_http.cookies.set(SESS.COOKIE_NAME, tampered)
    assert memory_http.post("/__session_probe").status_code == 401


def test_key_rotation_still_invalidates_signed_ticket(monkeypatch):
    ticket = SESS.make("worker.with.dots")
    monkeypatch.setattr(SESS, "secret", lambda: b"other-isolated-key")
    assert SESS.read(ticket) is None


@pytest.mark.parametrize("payload", [
    "d29ya2Vy.946684800", "d29ya2Vy.4102444800",  # 全部旧三段票，即便签名正确。
    "v1.d29ya2Vy.1", "v3.d29ya2Vy.1",            # 未知版本，即便按该版本重签。
    "v2.d29ya2Vy.not-a-timestamp", "v2.d29ya2Vy.1.2",
    "v2..1", "v2.IA.1", "v2._w.1",           # 空身份、空白身份、非法UTF-8。
])
def test_correct_signature_cannot_bypass_format_and_account_checks(memory_http, payload):
    ticket = signed(payload)
    assert SESS.read(ticket) is None
    memory_http.cookies.set(SESS.COOKIE_NAME, ticket)
    assert memory_http.post("/__session_probe").status_code == 401


@pytest.mark.parametrize("value", [None, "", "abc", "a.b", "a.b.c.d", "v2.a.1"])
def test_missing_or_garbage_cookie_remains_unauthenticated(value):
    assert SESS.read(value) is None
