"""Exercise the notice batch HTTP entry points against the real relay and isolated substitutes."""

from __future__ import annotations

import json
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core import app_settings
from app.core.errors import MustReportError
from app.core.config import Settings, get_settings
from app.core.session import COOKIE_NAME, make
from app.main import create_app
from app.mod02_i8 import browser_broker, client as i8_client, session_policy
from app.mod02_i8.browser_relay import assert_readonly
from app.mod02_i8.browser_session import StrictTargetMismatch
from app.mod03_notice import notice_executors, print_batch_store
from tests._auth import TestClient
from app.mod03_notice.print.signatures import check_signature_coverage
from tests.m03_helpers import make_notice, sign_cell, template, text_cell

BASE = "https://i8.example.test"
DEVICE = "notice-batch-test"
PATH = "/api/m03/print-batches"
IMAGE = b"\x89PNG\r\n\x1a\n" + b"data" * 30


@pytest.fixture
def setup_batch(monkeypatch):
    values = {"i8_base_url": BASE, "i8_print_id_material": "design-material"}
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: values)
    monkeypatch.setattr(app_settings, "_CACHE", values)
    get_settings.cache_clear()
    broker = browser_broker.BrowserBroker()
    monkeypatch.setattr(browser_broker, "_BROKER", broker)
    monkeypatch.setattr(print_batch_store, "_batches", {})
    local_rows = [make_notice(i, f"PN-{i}") for i in range(1, 4)]
    def load(ids):
        by_id = {row.id: row for row in local_rows}
        return [by_id[notice_id] for notice_id in ids]
    monkeypatch.setattr(print_batch_store, "load_batch_notices", load)
    monkeypatch.setattr(notice_executors, "load_batch_notices", load)
    monkeypatch.setattr(print_batch_store, "persist_batch_run", lambda *args: None)
    monkeypatch.setattr(notice_executors, "persist_batch_run", lambda *args: None)
    rendered = []
    sent = []
    logins = []

    def render(html):
        rendered.append(html)
        return b"%PDF-1.4\n" + html.encode("utf-8")

    def dispatch(pdf):
        sent.append(pdf)

    def login(**kwargs):
        logins.append(kwargs["allow_kick"])
        return SimpleNamespace(ok=False, conflict=True, detail="测试在线冲突")

    monkeypatch.setattr(notice_executors, "PdfRenderer",
                        lambda: SimpleNamespace(render_html_to_pdf=render, close=lambda: None))
    monkeypatch.setattr(print_batch_store, "dispatch_pdf", dispatch)
    monkeypatch.setattr(notice_executors, "print_dispatch", dispatch)
    monkeypatch.setattr(i8_client, "http_login", login)
    monkeypatch.setattr(i8_client.cookie_store, "load", lambda *_: None)
    monkeypatch.setattr(session_policy, "current_i8_credentials", lambda: ("i8-test", "unused"))

    api = TestClient(create_app())
    api.cookies.clear()
    api.cookies.set(COOKIE_NAME, make("notice-test-user"))
    broker.connect("notice-test-user", DEVICE, BASE)
    yield SimpleNamespace(api=api, broker=broker, sent=sent, rendered=rendered, logins=logins)
    get_settings.cache_clear()


def body(ids=(1, 2, 3), mode="print", session_mode="browser", **extra):
    return {"ids": list(ids), "mode": mode, "session_mode": session_mode,
            "device_id": DEVICE, **extra}


def reply_for(pending):
    target = urlsplit(pending.url)
    if target.path.endswith("/getPrintDesign"):
        sheet = {
            "cells": [text_cell(0, 0, "i8 notice"), sign_cell(0, 1, "项目经理"), sign_cell(0, 2, "未到达节点")],
            "globalSettings": {"cols": 3, "rows": 1},
        }
        setting = [{"printConfig": {"margin": {"top": 5, "left": 5, "right": 5, "down": 5}}}]
        return {"Data": {"printSchema": json.dumps([sheet]), "printSetting": json.dumps(setting)}}
    if target.path.endswith("/getInfo"):
        return {"Data": {"BillNo": "test"}}
    if target.path.endswith("/getDetInfo"):
        return {"Record": [{"ApplyAmt": 5}]}
    if target.path.endswith("/getFlowHisForPrint"):
        ph_id = parse_qs(target.query)["bizPk"][0]
        return {"data": [{"task_des": "项目经理", "signature": f"/sig/{ph_id}.png?s=test"}]}
    raise AssertionError(f"unexpected path {target.path}")


def pump(broker, *, second_image=None):
    requests = []
    stop = Event()
    pending_second = Event()
    release_second = Event()
    errors = []

    def run():
        try:
            while not stop.is_set():
                pending = broker.take_pending("notice-test-user", DEVICE, timeout=0.02)
                if not pending:
                    continue
                path = urlsplit(pending.url).path
                requests.append((pending.method, path))
                if path.startswith("/sig/"):
                    status, content_type, content = 200, "image/png", IMAGE
                    if path == "/sig/ph-2.png" and second_image:
                        pending_second.set()
                        assert release_second.wait(5)
                        if second_image == "session":
                            status, content_type, content = 200, "text/html", b"<html>login</html>"
                        else:
                            status, content_type, content = 200, "text/plain", b"not an image"
                else:
                    status, content_type, content = 200, "application/json", json.dumps(reply_for(pending)).encode()
                broker.complete(
                    "notice-test-user", DEVICE, pending.ticket, status=status,
                    headers={"content-type": content_type}, body=content, declared_length=len(content),
                    generation=pending.generation,
                )
        except Exception as exc:
            errors.append(exc)

    thread = Thread(target=run, daemon=True)
    thread.start()

    def done():
        release_second.set()
        stop.set()
        thread.join(timeout=5)
        assert not thread.is_alive() and not errors, errors

    return SimpleNamespace(requests=requests, pending_second=pending_second, release_second=release_second, done=done)


def wait_batch(api, batch_id):
    end = monotonic() + 7
    while monotonic() < end:
        response = api.get(f"{PATH}/{batch_id}")
        assert response.status_code == 200, response.text
        value = response.json()
        if value["status"] != "running":
            return value
        sleep(0.01)
    pytest.fail(f"batch not finished: {value}")


@pytest.mark.parametrize("second_image", ["not_image", "session"])
def test_print_stops_mid_batch_then_only_dispatches_reconfirmed_scope(setup_batch, second_image):
    env = setup_batch
    relay = pump(env.broker, second_image=second_image)
    try:
        start = env.api.post(f"{PATH}/prepare", json=body(ids=(1, 2, 3, 1)))
        assert start.status_code == 202, start.text
        handle = start.json()["batch_id"]
        assert start.json()["ids"] == [1, 2, 3]
        assert relay.pending_second.wait(5), relay.requests
        progress = env.api.get(f"{PATH}/{handle}").json()
        assert (progress["stage"], progress["prepared_count"], progress["current_bill_no"]) == ("preparing", 1, "PN-2")
        assert [item["status"] for item in progress["items"]] == ["prepared", "preparing", "pending"]
        assert progress["dispatched_count"] == 0 and env.sent == []
        assert env.api.post(f"{PATH}/{handle}/dispatch").status_code == 409

        relay.release_second.set()
        failed = wait_batch(env.api, handle)
        assert failed["status"] == "failed"
        assert failed["failed_bill_no"] == "PN-2"
        assert failed["stage"] == "preparing"
        assert failed["dispatched_count"] == 0 and env.sent == []
        assert len(env.rendered) == 1
        assert failed["items"][2]["status"] == "skipped"
        assert env.api.post(f"{PATH}/{handle}/dispatch").status_code == 409
        assert ("GET", "/sig/ph-3.png") not in relay.requests
        if second_image == "session":
            assert failed["session_stopped"] is True
            assert failed["failed_notice_id"] is None
            assert "会话异常页面" in failed["reason"]
            return
        assert failed["session_stopped"] is False
        assert failed["failed_notice_id"] == 2 and "签名" in failed["reason"]

        next_id = env.api.post(f"{PATH}/prepare", json=body(ids=(3, 1))).json()["batch_id"]
        ready = wait_batch(env.api, next_id)
        assert ready["status"] == "ready" and ready["prepared_count"] == 2 and env.sent == []
        assert [item["notice_id"] for item in ready["items"]] == [3, 1]
        assert env.api.post(f"{PATH}/{next_id}/dispatch").status_code == 202
        assert env.api.post(f"{PATH}/{next_id}/dispatch").status_code == 202
        dispatched = wait_batch(env.api, next_id)
        assert dispatched["dispatched_count"] == 2 and len(env.sent) == 2
        assert [item["notice_id"] for item in dispatched["result"]["items"]] == [3, 1]
        assert all(b"data:image/png" in pdf for pdf in env.sent)
        assert env.logins == []
    finally:
        relay.done()


@pytest.mark.parametrize("path", ["/batch", "/print-batches/prepare"])
@pytest.mark.parametrize("mode", ["print", "pdf"])
def test_explicit_mode_and_http_conflict_token_are_scoped(setup_batch, path, mode):
    env = setup_batch
    url = f"/api/m03{path}"
    omitted = body(mode=mode)
    del omitted["session_mode"]
    for request in (omitted, body(mode=mode, session_mode="auto")):
        assert env.api.post(url, json=request).status_code == 400
    assert env.logins == []
    conflict = env.api.post(url, json=body(mode=mode, session_mode="http"))
    assert conflict.status_code == 409, conflict.text
    ticket = conflict.json()["detail"]["kick_token"]
    assert env.logins == [False]
    changed = env.api.post(url, json=body((1, 3), mode=mode, session_mode="http", kick_token=ticket))
    assert changed.status_code in (202, 400)
    if changed.status_code == 202:
        assert "确认已失效" in wait_batch(env.api, changed.json()["batch_id"])["reason"]
    assert env.logins == [False]
    confirmed = env.api.post(url, json=body(mode=mode, session_mode="http", kick_token=ticket))
    if confirmed.status_code == 202:
        assert wait_batch(env.api, confirmed.json()["batch_id"])["status"] == "failed"
    else:
        assert confirmed.status_code == 200
        assert confirmed.json()["success"] == 0
        assert "i8 登录失败" in confirmed.json()["items"][0]["reason"]
    assert env.logins == [False, True]
    replay = env.api.post(url, json=body(mode=mode, session_mode="http", kick_token=ticket))
    if replay.status_code == 202:
        assert "确认已失效" in wait_batch(env.api, replay.json()["batch_id"])["reason"]
    else:
        assert replay.status_code == 400
    assert env.logins == [False, True] and not env.sent


@pytest.mark.parametrize("path", ["/batch", "/print-batches/prepare"])
def test_pdf_download_retry_never_dispatches(setup_batch, path):
    env = setup_batch
    relay = pump(env.broker)
    try:
        response = env.api.post(f"/api/m03{path}", json=body(ids=(1,), mode="pdf"))
        assert response.status_code in (200, 202), response.text
        result = response.json()
        if "batch_id" in result:
            batch_id = result["batch_id"]
            finished = wait_batch(env.api, batch_id)
            assert finished["dispatched_count"] == 0
            assert env.api.post(f"{PATH}/{batch_id}/dispatch").status_code == 409
            other = TestClient(create_app())
            other.cookies.clear()
            other.cookies.set(COOKIE_NAME, make("other-notice-user"))
            assert other.get(f"{PATH}/{batch_id}").status_code == 404
            result = finished["result"]
        assert result["success"] == 1
        download = result["items"][0]["download_url"]
        first = env.api.get(download)
        again = env.api.get(download)
        assert first.status_code == again.status_code == 200
        assert first.content == again.content and first.content.startswith(b"%PDF")
        assert ("GET", "/sig/ph-1.png") in relay.requests
        assert env.logins == env.sent == []
    finally:
        relay.done()


@pytest.mark.parametrize(("method", "path"), [
    ("POST", "/sig/a.png?s=test"), ("GET", "/sig/a.png"),
    ("GET", "/sig/../a.png?s=test"), ("GET", "/sig/%2e%2e/a.png?s=test"),
    ("GET", "/sig//a.png?s=test"), ("GET", "/sig/a.svg?s=test"),
])
def test_signature_url_allowlist_rejects_non_contract_paths(method, path):
    with pytest.raises(StrictTargetMismatch):
        assert_readonly(method, BASE + path)


def test_pdf_reports_partial_generation_and_keeps_downloadable_items(setup_batch):
    env = setup_batch
    relay = pump(env.broker, second_image="not_image")
    try:
        batch_id = env.api.post(f"{PATH}/prepare", json=body(mode="pdf")).json()["batch_id"]
        relay.release_second.set()
        batch = wait_batch(env.api, batch_id)
        assert batch["status"] == "failed"
        assert batch["prepared_count"] == 2 and batch["dispatched_count"] == 0
        items = batch["result"]["items"]
        assert [(item["notice_id"], item["ok"]) for item in items] == [(1, True), (2, False), (3, True)]
        assert items[0]["download_url"] == items[2]["download_url"] and not items[1]["download_url"]
        assert env.api.get(items[0]["download_url"]).headers["content-type"].startswith("application/zip")
        assert not env.sent
    finally:
        relay.done()


def test_missing_reached_signature_is_an_error_even_with_another_slot_filled():
    tpl = template([sign_cell(0, 0, "项目经理"), sign_cell(0, 1, "财务审核"),
                    sign_cell(0, 2, "未到达节点")], cols=3, rows=1)
    flow = [{"task_des": "项目经理"}, {"task_des": "财务审核"}]
    with pytest.raises(MustReportError, match="财务审核"):
        check_signature_coverage(tpl, flow, {"项目经理": "data:image/png;base64,AA"})
    coverage = check_signature_coverage(tpl, flow[:1], {"项目经理": "data:image/png;base64,AA"})
    assert coverage.blank_by_design == ["财务审核", "未到达节点"]
