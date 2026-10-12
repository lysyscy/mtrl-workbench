"""真实登录后的账号身份、旧会话歧义及假 i8 归属；只写隔离库外层回滚事务。"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import db, identity as ID, session as SESS
from app.mod15_user import api as API, domain as D, repository as R
from app.mod15_user.models import UserAccount
from tests.acc_plugin import acc

SECRET = b"isolated-identity-test-secret"


@pytest.fixture(autouse=True)
def fake_session_key(monkeypatch):
    """所有签名均用进程内假密钥，不能生成或修改持久密钥。"""
    monkeypatch.setattr(SESS, "secret", lambda: SECRET)


def legacy_ticket(label: str) -> str:
    """按改前格式独立签假会话，不调用生产密钥出口。"""
    encoded = base64.urlsafe_b64encode(label.encode()).decode().rstrip("=")
    expires = int((dt.datetime.now() + dt.timedelta(hours=1)).timestamp())
    payload = f"{encoded}.{expires}"
    signature = base64.urlsafe_b64encode(
        hmac.new(SECRET, payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{payload}.{signature}"


@pytest.fixture
def isolated_identity(monkeypatch, request):
    """HTTP 与身份出口共用测试库事务，账号查询仅看本用例的假账号。"""
    from app import main as MAIN

    engine = db.get_engine()
    assert engine.url.database and engine.url.database.endswith("_test"), "只允许隔离测试库"
    prefix = f"__identity_{uuid4().hex}_"
    with engine.connect() as connection:
        outer = connection.begin()

        @contextmanager
        def scope():
            with Session(bind=connection, expire_on_commit=False,
                         join_transaction_mode="create_savepoint") as session:
                try:
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

        def fake_users(session):
            return list(session.scalars(select(UserAccount).where(
                UserAccount.account.startswith(prefix, autoescape=True)
            ).order_by(UserAccount.id)))

        monkeypatch.setattr(db, "session_scope", scope)
        monkeypatch.setattr(API, "session_scope", scope)
        monkeypatch.setattr(R, "all_users", fake_users)
        monkeypatch.setattr(SESS, "secret", lambda: SECRET)
        if getattr(request, "param", "minimal") == "production":
            from app.core.config import get_settings

            settings = get_settings().model_copy(update={
                "app_env": "dev", "allowed_ip_cidrs": "", "cors_allow_origins": "",
                "session_secret": "fake-application-key", "i8_user": "fake-env-i8",
                "i8_password": "fake-env-i8-password",
            })
            monkeypatch.setattr(MAIN, "get_settings", lambda: settings)
            monkeypatch.setattr(MAIN, "setup_logging", lambda: None)
            app = MAIN.create_app()
        else:
            app = FastAPI()
            # 与create_app的装配顺序一致；运行时auth_gate在session_loader外层。
            MAIN._install_session(app)
            MAIN._install_auth_gate(app)
            app.include_router(API.router)

        @app.get("/__identity_probe")
        def probe():
            with scope() as session:
                me = API._me(session)
                return {"account": me.account if me else None,
                        "operator": ID.current_operator(),
                        "i8": ID.current_i8_credentials() if me else None}

        def create(suffix, *, name, role=D.ROLE_USER, password="fake-password"):
            with scope() as session:
                row = R.create(session, account=prefix + suffix, name=name,
                               role=role, password=password,
                               i8_user="fake-i8-" + suffix, i8_password="fake-i8-password-" + suffix)
                return row

        try:
            yield TestClient(app), create, scope, prefix
        finally:
            SESS.set_current_name("")
            outer.rollback()


def login(client, user, password="fake-password"):
    # 手工播的旧票没有浏览器域；清理测试载具，避免与HTTP下发的域票重复。
    client.cookies.clear()
    response = client.post("/m15/login", data={"account": user.account, "password": password},
                           follow_redirects=False)
    assert response.status_code == 303
    assert client.cookies.get(SESS.COOKIE_NAME)


@acc("ACC-USR-MGMT-001", "001-02")
@pytest.mark.parametrize("collision", ["same-name", "account-is-name", "name-is-account"])
def test_login_keeps_worker_identity_and_rejects_admin_actions(isolated_identity, collision):
    client, create, scope, prefix = isolated_identity
    admin = create("admin", name=prefix + "shared", role=D.ROLE_ADMIN)
    worker_name = admin.name if collision == "same-name" else (
        admin.account if collision == "name-is-account" else "Worker display")
    worker = create("worker", name=worker_name)
    if collision == "account-is-name":
        with scope() as session:
            session.get(UserAccount, admin.id).name = worker.account
    login(client, worker)
    me = client.get("/api/m15/users").json()["me"]
    assert me is not None, "成功登录后必须解析出本人账号"
    assert me["id"] == worker.id and me["role"] == D.ROLE_USER
    before = client.get("/api/m15/users").json()["counts"]["total"]
    result = client.post("/api/m15/actions/create", json={
        "account": prefix + "forbidden", "name": "Forbidden fake user", "password": ""
    }).json()
    assert result["ok"] is False
    assert client.get("/api/m15/users").json()["counts"]["total"] == before


@acc("ACC-USR-MGMT-001", "001-02")
@pytest.mark.parametrize("isolated_identity", ["production"], indirect=True)
def test_create_app_login_uses_real_assembly_and_rejects_admin_actions(isolated_identity):
    client, create, _, prefix = isolated_identity
    create("admin", name="Same display", role=D.ROLE_ADMIN)
    worker = create("worker", name="Same display")
    login(client, worker)
    me = client.get("/api/m15/users").json()["me"]
    assert me is not None and me["id"] == worker.id and me["role"] == D.ROLE_USER
    assert not client.post("/api/m15/actions/create", json={
        "account": prefix + "forbidden", "name": "Forbidden fake user", "password": ""
    }).json()["ok"]
    assert client.get("/__identity_probe").json()["i8"] == [
        "fake-i8-worker", "fake-i8-password-worker"]


@acc("ACC-USR-MGMT-001", "001-13")
def test_login_uses_own_preferences_i8_and_display_name(isolated_identity):
    client, create, scope, _ = isolated_identity
    admin = create("admin", name="Same display", role=D.ROLE_ADMIN)
    worker = create("worker", name="Same display")
    login(client, worker)
    assert client.post("/api/m15/ui-scale", json={"ui_scale": "large"}).json()["ok"]
    from app.mod03_notice.page import theme_names

    theme = list(theme_names())[0]
    assert client.post("/api/m15/theme", json={"theme": theme}).json()["ok"]
    with scope() as session:
        assert session.get(UserAccount, worker.id).ui_scale == "large"
        assert session.get(UserAccount, admin.id).ui_scale != "large"
        assert session.get(UserAccount, worker.id).theme == theme
        assert session.get(UserAccount, admin.id).theme != theme
        assert R.theme_by_account(session, SESS.read(client.cookies.get(SESS.COOKIE_NAME))) == theme
    probe = client.get("/__identity_probe").json()
    assert probe == {"account": worker.account, "operator": "Same display",
                     "i8": ["fake-i8-worker", "fake-i8-password-worker"]}
    # 改显示姓名不改变新会话的账号归属，留痕仍用最新显示姓名。
    with scope() as session:
        session.get(UserAccount, worker.id).name = "Updated display"
    assert client.get("/__identity_probe").json()["operator"] == "Updated display"
    assert client.get("/api/m15/users").json()["me"]["id"] == worker.id
    assert client.post("/api/m15/actions/i8", json={
        "id": worker.id, "i8_user": "fake-i8-updated", "i8_password": "fake-updated-password"
    }).json()["ok"]
    assert client.get("/__identity_probe").json()["i8"] == [
        "fake-i8-updated", "fake-updated-password"]
    assert not client.post("/api/m15/actions/i8", json={
        "id": admin.id, "i8_user": "forbidden-fake-i8"
    }).json()["ok"]
    with scope() as session:
        session.get(UserAccount, admin.id).name = worker.account
    assert client.get("/__identity_probe").json()["i8"] == [
        "fake-i8-updated", "fake-updated-password"]
    assert client.get("/__identity_probe").json()["operator"] == "Updated display"


@acc("ACC-USR-MGMT-001", "001-03")
@pytest.mark.parametrize("label_kind", ["name", "account"])
def test_legacy_session_requires_new_login(isolated_identity, label_kind):
    client, create, _, _ = isolated_identity
    worker = create("worker", name="Unique display")
    client.cookies.set(SESS.COOKIE_NAME, legacy_ticket(getattr(worker, label_kind)))
    assert client.get("/api/m15/users").json()["me"] is None
    assert client.post("/api/m15/ui-scale", json={"ui_scale": "large"}).status_code == 401
    login(client, worker)
    assert client.get("/api/m15/users").json()["me"]["id"] == worker.id


@acc("ACC-USR-MGMT-001", "001-03")
@pytest.mark.parametrize("collision", ["same-name", "cross-name", "deleted-collision", "historical-name-reuse"])
def test_ambiguous_legacy_session_cannot_write_or_select_a_user(isolated_identity, collision):
    client, create, scope, prefix = isolated_identity
    admin = create("admin", name=prefix + "legacy", role=D.ROLE_ADMIN)
    worker = create("worker", name=admin.name)
    label = admin.name
    if collision == "cross-name":
        with scope() as session:
            session.get(UserAccount, admin.id).name = worker.account
            session.get(UserAccount, worker.id).name = "Worker display"
        label = worker.account
    elif collision == "deleted-collision":
        with scope() as session:
            session.get(UserAccount, admin.id).deleted_at = dt.datetime.now()
    elif collision == "historical-name-reuse":
        # 隔离模拟历史标签归属变化；不声称产品已有改名入口。
        with scope() as session:
            session.get(UserAccount, admin.id).name = "Changed historical owner"
    client.cookies.set(SESS.COOKIE_NAME, legacy_ticket(label))
    assert client.get("/api/m15/users").json()["me"] is None
    assert client.post("/api/m15/ui-scale", json={"ui_scale": "large"}).status_code == 401


@acc("ACC-USR-MGMT-001", "001-03")
def test_legal_login_and_account_named_like_a_version(isolated_identity):
    client, create, _, _ = isolated_identity
    worker = create("v2.account.with.dots", name="", password="")
    login(client, worker, password="")
    assert client.get("/api/m15/users").json()["me"]["id"] == worker.id
    assert client.get("/__identity_probe").json()["operator"] == worker.account
    assert client.post("/api/m15/logout").json()["ok"]
    assert client.get("/api/m15/users").json()["me"] is None


@acc("ACC-USR-MGMT-001", "001-03")
def test_version_is_structural_and_signed():
    for label in ("v2", "v2.admin", "uid:1", "张.伟", "...", "legacy:v2"):
        ticket = SESS.make(label)
        account = SESS.read(ticket)
        assert account == label and isinstance(account, SESS.AccountIdentity)
        assert SESS.read(legacy_ticket(label)) is None
        version, encoded, expires, signature = ticket.split(".")
        assert SESS.read(f"v3.{encoded}.{expires}.{signature}") is None
        assert SESS.read(f"{encoded}.{expires}.{signature}") is None
        # 即便版本篡改后重签，也不能把未知格式当旧票解释。
        payload = f"v3.{encoded}.{expires}"
        signed = base64.urlsafe_b64encode(hmac.new(
            SECRET, payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        assert SESS.read(f"{payload}.{signed}") is None
        assert version == "v2"


@acc("ACC-USR-MGMT-001", "001-03")
def test_internal_label_matches_once_and_disabled_session_policy_is_unchanged(isolated_identity):
    client, create, scope, prefix = isolated_identity
    worker = create("worker", name=prefix + "worker")
    with scope() as session:
        assert R.by_identity(session, worker.account).id == worker.id
    login(client, worker)
    with scope() as session:
        session.get(UserAccount, worker.id).status = D.STATUS_DISABLED
    # 原规则只禁止再次登录；不在这批改变已签会话的停用策略。
    assert client.get("/api/m15/users").json()["me"]["id"] == worker.id
    assert client.post("/api/m15/ui-scale", json={"ui_scale": "large"}).json()["ok"]
    assert client.post("/m15/login", data={
        "account": worker.account, "password": "fake-password"
    }, follow_redirects=False).status_code == 200
