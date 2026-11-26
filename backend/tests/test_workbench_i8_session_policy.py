"""Every migrated HTTP route enforces the same i8 session and kick policy."""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import app_settings
from app.core.db import session_scope
from app.core.session import set_current_name
from app.main import _install_error_handlers
from app.mod01_projects.models import Project
from app.mod02_i8 import browser_broker, cookie_store, login, payable_source, router as m02, session_policy
from app.mod03_notice import router as m03
from app.mod03_notice.models import PaymentNotice
from app.mod06_proc import workbench_api as m06, workbench_i8
from app.mod07_setl import api as m07, fetch_service as settlement
from app.mod08_inv import router as m08, fetch_service as inventory
from app.mod11_jc import api as m11, fetch_service as contracts
from app.mod11_jc.models import JcContract

BASE = "https://i8.example.test"
MONTH = "2026-10"
ENDPOINTS = [
    ("/api/m02/sync/warehouses", {}),
    ("/api/m02/sync/common-projects", {}),
    ("/api/m02/fetch/preview", {"year_month": MONTH}),
    ("/api/m02/fetch/run", {"year_month": MONTH}),
    ("/api/m03/notices/warehouse-check", {"warehouse_name": "隔离仓库"}),
    ("/api/m06/workbench/i8-fetch", {"request_id": "isolated-workbench-fetch"}),
    ("/api/m07/fetch", {"month": MONTH, "confirm": True}),
    ("/api/m08/fetch", {"month": MONTH, "confirm": True}),
    ("/api/m11/fetch", {"since": "", "confirm": True}),
    ("/api/m11/auto-link-preview", {"notice_ids": [1]}),
]


@pytest.fixture(params=ENDPOINTS, ids=[path for path, _ in ENDPOINTS])
def route(request):
    return request.param


@pytest.fixture
def case(monkeypatch, rollback_db, tmp_path):
    state = SimpleNamespace(requests=[], reads=[], cookie="")
    monkeypatch.setattr(browser_broker, "_BROKER", browser_broker.BrowserBroker())
    monkeypatch.setattr(app_settings, "effective", lambda key, default: BASE if key == "i8_base_url" else default)
    monkeypatch.setattr(session_policy, "current_i8_credentials", lambda: ("isolated", ""))
    monkeypatch.setattr(session_policy, "_tokens", {})
    monkeypatch.setattr(login, "sm2_encrypt", lambda plain: plain)
    monkeypatch.setattr(cookie_store, "load", lambda user, origin: state.cookie)
    monkeypatch.setattr(cookie_store, "save", lambda cookie, **kw: setattr(state, "cookie", cookie))
    monkeypatch.setattr(m02.wh_cache, "CACHE_DIR", tmp_path / "warehouse-cache")
    monkeypatch.setattr(inventory.source_cache, "DIR", tmp_path / "inventory-cache")
    with session_scope() as session:
        project = Project(warehouse_name="隔离仓库", name_full="隔离项目", phid="i8-project")
        session.add(project)
        session.flush()
        target = JcContract(project_id=project.id, supplier="甲", contract_no="CGHT1")
        session.add(target)
        session.add_all(PaymentNotice(id=i, ph_id=f"session-test-{i}", ownership_id=project.id,
                                      category="jc", approve_status="已批", amount_approved=1, jc_supplier="甲")
                        for i in (1, 2))
        session.flush()
        state.contract_id = target.id

    def respond(request):
        assert request.url.host == httpx.URL(BASE).host
        path = request.url.path
        state.requests.append(path)
        if path == login.KICK_PATH:
            return httpx.Response(200)
        assert path == login.LOGIN_PATH
        if state.requests[-2:-1] == [login.KICK_PATH]:
            return httpx.Response(200, json={"accesstoken": "isolated"}, headers={"set-cookie": "i8-test=new"})
        return httpx.Response(200, json={"msg": json.dumps({"sessionID": "isolated", "userId": "isolated"})})

    http_client = httpx.Client
    def mock_client(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(respond))
        return http_client(**kwargs)

    monkeypatch.setattr(httpx, "Client", mock_client)

    def read(client, result, source):
        client._ensure_cookie()
        state.reads.append(source)
        return result

    monkeypatch.setattr(m02.WarehouseSource, "fetch", lambda self: read(self._client, [], "warehouse"))
    monkeypatch.setattr(m02.CommonProjectSource, "fetch", lambda self: read(self._client, [], "projects"))
    monkeypatch.setattr(m02.NoticeFetcher, "fetch_month", lambda self, month: read(self._client, [], month))
    monkeypatch.setattr(workbench_i8, "fetch_lists", lambda client: read(
        client, {kind: {"total": 0, "rows": []} for kind in workbench_i8.SOURCES}, "mechanical"))
    monkeypatch.setattr(settlement.report_export, "require_ready", lambda spec: None)
    monkeypatch.setattr(settlement.report_export, "export", lambda client, **kw: read(client, b"isolated", kw["spec_key"]))
    monkeypatch.setattr(settlement.importer, "parse_rows", lambda *a, **kw: [])
    monkeypatch.setattr(inventory.importer, "parse_rows", lambda *a, **kw: [])
    monkeypatch.setattr(contracts.ContractFetcher, "fetch_in_locked_batch", lambda self, **kw: read(
        self._client, [], kw["since"]))
    monkeypatch.setattr(payable_source, "fetch_payables", lambda client: read(client, [], "payables"))

    app = FastAPI()
    _install_error_handlers(app)
    for module in (m02, m03, m06, m07, m08, m11):
        app.include_router(module.router)

    @app.middleware("http")
    async def bind_identity(request: Request, call_next):
        set_current_name(request.headers.get("x-test-owner", "isolated"))
        return await call_next(request)

    with TestClient(app) as client:
        state.client = client
        yield state


@pytest.mark.parametrize("mode", [{}, {"session_mode": "unexpected"}], ids=["missing", "invalid"])
def test_session_mode_is_required_before_i8(case, route, mode):
    path, payload = route
    response = case.client.post(path, json={**payload, **mode, "allow_kick": True})
    if path == "/api/m11/auto-link-preview" and not mode:
        assert response.status_code == 200 and response.json()["needs_payables"]
    else:
        assert response.status_code == 400, response.text
    assert case.requests == case.reads == []


def test_disconnected_browser_stops_without_http_fallback(case, route):
    path, payload = route
    response = case.client.post(path, json={
        **payload, "session_mode": "browser", "device_id": "disconnected", "allow_kick": True,
    })
    assert (response.status_code, response.json()["code"]) == (400, "i8_browser_relay_unavailable"), response.text
    assert case.requests == case.reads == []


def conflict_token(response):
    assert response.status_code == 409, response.text
    error = response.json()
    assert error["code"] == "i8_online_conflict"
    return error["detail"]["kick_token"]


def test_online_conflict_requires_valid_single_use_confirmation(case, route):
    path, payload = route
    request = {**payload, "session_mode": "http", "allow_kick": True}
    token = conflict_token(case.client.post(path, json=request))
    assert case.requests == [login.LOGIN_PATH]
    assert case.reads == []

    invalid = case.client.post(path, json={**request, "kick_token": "unissued"})
    assert invalid.status_code == 400, invalid.text
    assert case.requests == [login.LOGIN_PATH]
    assert case.reads == []

    confirmed = case.client.post(path, json={**request, "kick_token": token})
    assert confirmed.status_code == 200, confirmed.text
    expected = [login.LOGIN_PATH, login.LOGIN_PATH, login.KICK_PATH, login.LOGIN_PATH]
    assert case.requests == expected
    assert case.reads

    replay = case.client.post(path, json={**request, "kick_token": token})
    assert replay.status_code == 400, replay.text
    assert case.requests == expected


@pytest.mark.parametrize("path", ["/api/m02/sync/warehouses", "/api/m02/sync/common-projects"])
def test_sync_still_accepts_session_fields_in_query(case, path):
    query = {"session_mode": "http", "allow_kick": "true", "expected_account": "isolated"}
    token = conflict_token(case.client.post(path, params=query))
    assert case.requests == [login.LOGIN_PATH]
    reply = case.client.post(path, params={**query, "kick_token": token})
    assert reply.status_code == 200, reply.text
    assert case.requests.count(login.KICK_PATH) == 1
    assert case.reads


def test_preview_confirmation_is_scope_bound_and_local_link_requires_no_i8(case):
    request = {"session_mode": "http", "notice_ids": [1]}
    token = conflict_token(case.client.post("/api/m11/auto-link-preview", json=request))
    changed = {**request, "kick_token": token, "notice_ids": [1, 2]}
    assert case.client.post("/api/m11/auto-link-preview", json=changed).status_code == 400
    saved = case.client.post("/api/m11/auto-link", json={"selections": [{
        "notice_id": 1, "contract_id": case.contract_id, "expected_amount": "1.00",
        "expected_jc_supplier": "甲", "expected_warehouse_key": "隔离仓库",
    }]})
    assert saved.status_code == 200 and saved.json()["linked"] == 1
    assert case.requests == [login.LOGIN_PATH]
    assert case.reads == []


def test_local_config_and_records_do_not_enter_session_policy(case):
    assert case.client.get("/api/m02/config").status_code == 200
    assert case.client.get("/api/m02/fetch/records").status_code == 200
    assert case.requests == case.reads == []
