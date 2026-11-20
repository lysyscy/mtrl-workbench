"""Exercise the notice batch HTTP entry points against the real relay and isolated substitutes."""

from __future__ import annotations

import io
import json
import struct
import zipfile
from concurrent.futures import Future
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter

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
from app.mod03_notice.print import dispatch as channels, ipp
from app.mod03_notice.schemas import BatchRequest
from app.mod03_notice.print.signatures import check_signature_coverage
from tests.m03_helpers import make_notice, sign_cell, template, text_cell

BASE = "https://i8.example.test"
DEVICE = "notice-batch-test"
PATH = "/api/m03/print-batches"
IMAGE = b"\x89PNG\r\n\x1a\n" + b"data" * 30


@pytest.fixture
def setup_batch(monkeypatch, tmp_path):
    values = {"i8_base_url": BASE, "i8_print_id_material": "design-material"}
    monkeypatch.setenv("PRINTER_IPP_URL", "ipp://configured-printer.example.test:631/ipp/print")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: values)
    monkeypatch.setattr(app_settings, "_CACHE", values)
    get_settings.cache_clear()
    broker = browser_broker.BrowserBroker()
    monkeypatch.setattr(browser_broker, "_BROKER", broker)
    monkeypatch.setattr(print_batch_store, "_batches", {})
    monkeypatch.setattr(print_batch_store, "_pending_preparations", set())
    monkeypatch.setattr(print_batch_store, "STATE_DIR", tmp_path / "print-batches")
    local_rows = [make_notice(i, f"PN-{i}") for i in range(1, 4)]
    def load(ids):
        by_id = {row.id: row for row in local_rows}
        return [by_id[notice_id] for notice_id in ids]
    monkeypatch.setattr(print_batch_store, "load_batch_notices", load)
    monkeypatch.setattr(notice_executors, "load_batch_notices", load)
    records = []
    monkeypatch.setattr(print_batch_store, "persist_batch_run", lambda result, _started: records.append(result))
    monkeypatch.setattr(notice_executors, "persist_batch_run", lambda *args: None)
    rendered = []
    sent = []
    logins = []

    def render(html):
        rendered.append(html)
        return b"%PDF-1.4\n" + html.encode("utf-8")

    operations = []
    def printer(url, *, content, **kwargs):
        operation, attributes, pdf = decode_request(content)
        operations.append((str(url), operation, attributes))
        if operation == 0x0004:
            assert not pdf
        else:
            assert operation == 0x0002
            sent.append(pdf)
        return ipp_response(job_id=len(sent) or None)

    def login(**kwargs):
        logins.append(kwargs["allow_kick"])
        return SimpleNamespace(ok=False, conflict=True, detail="测试在线冲突")

    monkeypatch.setattr(notice_executors, "PdfRenderer",
                        lambda: SimpleNamespace(render_html_to_pdf=render, close=lambda: None))
    monkeypatch.setattr(ipp.httpx, "post", printer)
    monkeypatch.setattr(i8_client, "http_login", login)
    monkeypatch.setattr(i8_client.cookie_store, "load", lambda *_: None)
    monkeypatch.setattr(session_policy, "current_i8_credentials", lambda: ("i8-test", "unused"))

    api = TestClient(create_app())
    api.cookies.clear()
    api.cookies.set(COOKIE_NAME, make("notice-test-user"))
    broker.connect("notice-test-user", DEVICE, BASE)
    yield SimpleNamespace(api=api, broker=broker, sent=sent, rendered=rendered, logins=logins,
                          operations=operations, printer=printer, records=records, notices=local_rows)
    get_settings.cache_clear()


def decode_request(content):
    _, _, operation, _ = struct.unpack_from(">BBHI", content)
    cursor, group = 8, 0
    attributes = {}
    while (tag := content[cursor]) != 3:
        cursor += 1
        if tag < 0x10:
            group = tag
            continue
        size = int.from_bytes(content[cursor:cursor + 2], "big")
        name = content[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
        size = int.from_bytes(content[cursor:cursor + 2], "big")
        attributes[name] = (group, tag, content[cursor + 2:cursor + 2 + size])
        cursor += 2 + size
    return operation, attributes, content[cursor + 1:]


def ipp_response(status=0, *, job_id=None, message=""):
    response = struct.pack(">BBHI", 1, 1, status, 1)
    if message:
        value = message.encode()
        response += b"\x01\x41\x00\x0estatus-message" + len(value).to_bytes(2, "big") + value
    if job_id is not None:
        response += b"\x02\x21\x00\x06job-id\x00\x04" + job_id.to_bytes(4, "big")
        response += b"\x23\x00\x09job-state\x00\x04\x00\x00\x00\x03"
    return httpx.Response(200, content=response + b"\x03", headers={"Content-Type": "application/ipp"})


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
                relay_failure = None
                if path.startswith("/sig/"):
                    status, content_type, content = 200, "image/png", IMAGE
                    if path == "/sig/ph-2.png" and second_image:
                        pending_second.set()
                        assert release_second.wait(5)
                        if second_image == "session":
                            status, content_type, content = 200, "text/html", b"<html>login</html>"
                        elif second_image == "relay_expired":
                            status, content_type, content = 599, "", b""
                            relay_failure = "session-ended"
                        elif second_image == "json_expired":
                            status, content_type, content = 200, "application/json", b'{"Code":"401"}'
                        else:
                            status, content_type, content = 200, "text/plain", b"not an image"
                else:
                    status, content_type, content = 200, "application/json", json.dumps(reply_for(pending)).encode()
                broker.complete(
                    "notice-test-user", DEVICE, pending.ticket, status=status,
                    headers={"content-type": content_type}, body=content, declared_length=len(content),
                    generation=pending.generation, relay_failure=relay_failure,
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


@pytest.mark.parametrize("second_image", ["not_image", "session", "relay_expired", "json_expired"])
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
        assert progress["dispatched_count"] == 0 and env.operations == []
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
        if second_image != "not_image":
            assert failed["session_stopped"] is True
            assert failed["failed_notice_id"] is None
            assert ("会话异常页面" if second_image == "session" else "会话已失效") in failed["reason"]
            return
        assert failed["session_stopped"] is False
        assert failed["failed_notice_id"] == 2 and "签名" in failed["reason"]

        next_id = env.api.post(f"{PATH}/prepare", json=body(ids=(3, 1))).json()["batch_id"]
        ready = wait_batch(env.api, next_id)
        assert ready["status"] == "ready" and ready["prepared_count"] == 2 and env.sent == []
        assert [item["notice_id"] for item in ready["items"]] == [3, 1]
        assert env.api.post(f"{PATH}/{next_id}/dispatch").status_code == 202
        assert env.api.post(f"{PATH}/{next_id}/dispatch").status_code in (200, 202)
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
        assert confirmed.status_code == 502
        assert confirmed.json()["code"] == "i8_auth_failed"
        assert "i8 登录未成功" in confirmed.json()["message"]
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


@pytest.mark.parametrize("blocked_mode", ["driver", "raw", "ipp", "auto"])
def test_blocked_channel_exports_or_switches_same_prepared_batch(setup_batch, monkeypatch, blocked_mode):
    env = setup_batch
    relay = pump(env.broker)
    address = "ipp://a4-printer.example.test:631/ipp/print"
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595.28, height=841.89)
    writer.write(output)
    a4_pdf = output.getvalue()

    def render_a4(html):
        env.rendered.append(html)
        return a4_pdf

    monkeypatch.setattr(notice_executors, "PdfRenderer",
                        lambda: SimpleNamespace(render_html_to_pdf=render_a4, close=lambda: None))

    def printer(url, *, content, **kwargs):
        if "a4-printer.example.test" in str(url):
            return env.printer(url, content=content, **kwargs)
        operation, attributes, document = decode_request(content)
        env.operations.append((str(url), operation, attributes))
        assert operation == 0x0004 and not document
        # The device defaults to A4 but rejects the explicit media constraint.
        return ipp_response(0x040B, message="default is A4 but explicit A4 is unsupported")

    def must_not_send(*args):
        pytest.fail("A channel without explicit A4 was invoked")

    monkeypatch.setattr(ipp.httpx, "post", printer)
    monkeypatch.setattr(channels, "send_driver", must_not_send)
    monkeypatch.setattr(channels, "send_raw", must_not_send)
    try:
        batch_id = env.api.post(f"{PATH}/prepare", json=body()).json()["batch_id"]
        ready = wait_batch(env.api, batch_id)
        request_total = len(relay.requests)
        assert ready["status"] == "ready" and ready["prepared_count"] == 3
        response = env.api.post(f"{PATH}/{batch_id}/dispatch", json={"mode": blocked_mode, "printer_name": "Driver"})
        assert response.status_code == 200, response.text
        blocked = response.json()
        block = blocked["a4_blocked"]
        assert blocked["batch_id"] == batch_id and blocked["status"] == "ready"
        assert block["code"] == "a4_blocked" and block["can_switch_channel"]
        assert env.api.get(f"{PATH}/{batch_id}").json()["a4_blocked"] == block
        assert len(env.operations) == (1 if blocked_mode in ("ipp", "auto") else 0)
        if blocked_mode == "auto":
            assert [item["channel"] for item in block["attempts"]] == ["ipp", "driver", "raw"]
            assert "explicit A4 is unsupported" in block["attempts"][0]["reason"]
        assert env.sent == []

        export = env.api.post(block["export_action"])
        assert export.status_code == 200, export.text
        download = env.api.get(export.json()["download_url"])
        with zipfile.ZipFile(io.BytesIO(download.content)) as zipped:
            assert zipped.namelist() == ["PN-1.pdf", "PN-2.pdf", "PN-3.pdf"]
            for name in zipped.namelist():
                assert zipped.read(name) == a4_pdf
                page = PdfReader(io.BytesIO(zipped.read(name))).pages[0]
                assert (float(page.mediabox.width), float(page.mediabox.height)) == (595.28, 841.89)
        assert len(relay.requests) == request_total and env.sent == []

        switched = env.api.post(f"{PATH}/{batch_id}/dispatch", json={"mode": "ipp", "printer_uri": address})
        assert switched.status_code == 202 and switched.json()["a4_blocked"] is None
        finished = wait_batch(env.api, batch_id)
        assert finished["batch_id"] == batch_id and finished["dispatched_count"] == 3
        assert len(relay.requests) == request_total and len(env.rendered) == 3
        valid_ops = [(operation, attrs) for url, operation, attrs in env.operations if "a4-printer" in url]
        assert [operation for operation, _ in valid_ops] == [4, 2, 2, 2]
        for _, attrs in valid_ops:
            assert attrs[b"media"] == (2, 0x44, b"iso_a4_210x297mm")
            assert attrs[b"document-format"] == (1, 0x49, b"application/pdf")
            assert attrs[b"ipp-attribute-fidelity"] == (1, 0x22, b"\x01")
    finally:
        relay.done()


def test_refresh_reads_original_progress_and_three_delivery_states(setup_batch, monkeypatch):
    env = setup_batch
    relay = pump(env.broker)
    second_started, release = Event(), Event()

    def printer(url, *, content, **kwargs):
        response = env.printer(url, content=content, **kwargs)
        if len(env.sent) == 2:
            second_started.set()
            assert release.wait(5)
            return ipp_response(0x0400, message="queue disabled")
        if len(env.sent) == 3:
            raise httpx.ReadError("connection dropped after receiving PDF")
        return response

    monkeypatch.setattr(ipp.httpx, "post", printer)
    try:
        batch_id = env.api.post(f"{PATH}/prepare", json=body()).json()["batch_id"]
        assert wait_batch(env.api, batch_id)["status"] == "ready"
        path = f"{PATH}/{batch_id}"
        response = env.api.post(path + "/dispatch", json={"mode": "auto"})
        assert response.status_code == 202 and response.json()["stage"] == "dispatching"
        assert second_started.wait(5)
        refreshed = TestClient(create_app())
        refreshed.cookies.set(COOKIE_NAME, make("notice-test-user"))
        progress = refreshed.get(PATH + "/active").json()
        assert progress == refreshed.get(path).json()
        assert progress["batch_id"] == batch_id and progress["dispatch_processed_count"] == 1
        assert [(row["delivery_status"], row["job_id"]) for row in progress["items"]] == [
            ("accepted", 1), ("in_flight", None), ("pending", None),
        ]
        other = TestClient(create_app())
        other.cookies.set(COOKIE_NAME, make("different-user"))
        assert other.get(PATH + "/active").json() is None
        assert other.get(path).status_code == 404
        assert other.post(path + "/dispatch").status_code == 404
        assert other.post(path + "/export-pdf").status_code == 404
        assert refreshed.post(path + "/dispatch", json={"mode": "raw"}).json() == progress

        release.set()
        done = wait_batch(refreshed, batch_id)
        assert refreshed.get(PATH + "/active").json() == done
        assert refreshed.post(path + "/dispatch").json() == done
        assert len(env.sent) == 3 and [operation for _, operation, _ in env.operations] == [4, 2, 2, 2]
        assert done["dispatch_processed_count"] == 3 and done["dispatched_count"] == 1
        items = done["result"]["items"]
        assert [item["delivery_status"] for item in items] == ["accepted", "failed", "unknown"]
        assert done["result"]["success"] == done["result"]["failed"] == done["result"]["unknown"] == 1
        assert done["result"]["unprinted_bill_nos"] == ["PN-2"]
        assert items[0]["job_id"] == 1 and items[0]["job_state"] == 3
        assert "queue disabled" in items[1]["attempts"][0]["reason"]
        assert items[2]["attempts"][0]["status"] == "unknown"
        assert len(env.records) == 1
        assert [item.delivery.last.status for item in env.records[0].outcomes] == ["accepted", "failed", "unknown"]
    finally:
        release.set()
        relay.done()


@pytest.mark.parametrize("path", ["/batch", "/print-batches/prepare"])
def test_pdf_auth_failure_stops_before_trying_a_second_bill_type(setup_batch, monkeypatch, path):
    env = setup_batch
    env.notices[1].bill_type = "mechanical"
    values = {"i8_base_url": BASE, "i8_print_id_material": "design-material",
              "i8_print_id_mechanical": "design-mechanical"}
    monkeypatch.setattr(app_settings, "_CACHE", values)
    calls = []
    def reject(**kwargs):
        calls.append(kwargs["allow_kick"])
        return SimpleNamespace(ok=False, conflict=False, detail="upstream-only-auth-fixture")
    monkeypatch.setattr(i8_client, "http_login", reject)

    response = env.api.post("/api/m03" + path, json=body((1, 2), mode="pdf", session_mode="http"))
    if path == "/batch":
        assert response.status_code == 502
        assert response.json()["code"] == "i8_auth_failed"
    else:
        assert response.status_code == 202
        failed = wait_batch(env.api, response.json()["batch_id"])
        assert failed["session_stopped"] is True
        assert failed["items"][1]["status"] == "skipped"
    assert "i8 登录未成功" in response.text
    assert "upstream-only-auth-fixture" not in response.text
    assert calls == [False] and not env.rendered and not env.sent


class _DeferredWorker:
    def __init__(self):
        self.jobs = []

    def submit(self, run, *args):
        future = Future()
        self.jobs.append((future, run, args))
        return future


def test_restart_recovers_ready_scope_and_interrupted_dispatch_receipts(setup_batch, monkeypatch):
    env = setup_batch
    relay = pump(env.broker)
    try:
        original = env.api.post(f"{PATH}/prepare", json=body()).json()["batch_id"]
        assert wait_batch(env.api, original)["status"] == "ready"
        with print_batch_store._index_lock:
            print_batch_store._batches.clear()
        restored = env.api.get(f"{PATH}/active").json()
        assert (restored["batch_id"], restored["status"], restored["ids"]) == (original, "failed", [1, 2, 3])
        assert [item["bill_no"] for item in restored["items"]] == ["PN-1", "PN-2", "PN-3"]
        assert "重新确认" in restored["reason"]
        assert env.api.post(f"{PATH}/{original}/dispatch").status_code == 409
        handle = env.api.post(f"{PATH}/prepare", json=body(restored["ids"])).json()["batch_id"]
        assert wait_batch(env.api, handle)["status"] == "ready"
    finally:
        relay.done()

    class SimulatedProcessStop(BaseException):
        pass

    state_path = print_batch_store.STATE_DIR / f"{handle}.json"
    def persisted():
        return json.loads(state_path.read_text(encoding="utf-8"))
    sends = []

    def send(content):
        sends.append(content)
        disk = persisted()
        assert disk["owner"] == "notice-test-user" and disk["channels"] == ["ipp"]
        assert disk["snapshot"]["stage"] == "dispatching"
        items = disk["snapshot"]["items"]
        statuses = [item["delivery_status"] for item in items]
        assert content.startswith(b"%PDF-")
        if len(sends) == 1:
            assert statuses == ["in_flight", "pending", "pending"]
            return ipp.IppOutcome("accepted", "accepted receipt", job_id=17)
        assert statuses == ["accepted", "in_flight", "pending"]
        assert items[0]["job_id"] == 17 and items[0]["attempts"][0]["reason"] == "accepted receipt"
        raise SimulatedProcessStop

    worker = _DeferredWorker()
    monkeypatch.setattr(print_batch_store, "_workers", worker)
    monkeypatch.setattr(print_batch_store, "lock_a4_channel",
                        lambda **_: channels.DispatchPlan("ipp", "ipp://fixture", "", (("ipp", send),)))
    assert env.api.post(f"{PATH}/{handle}/dispatch").status_code == 202
    assert persisted()["snapshot"]["stage"] == "dispatching" and not sends
    _, run, args = worker.jobs[0]
    with pytest.raises(SimulatedProcessStop):
        run(*args)

    with print_batch_store._index_lock:
        print_batch_store._batches.clear()
    with pytest.raises(HTTPException) as foreign:
        print_batch_store.read_batch("different-owner", handle)
    assert foreign.value.status_code == 404
    recovered = env.api.get(f"{PATH}/{handle}").json()
    assert (recovered["batch_id"], recovered["stage"], recovered["status"]) == (handle, "done", "complete")
    assert [item["delivery_status"] for item in recovered["items"]] == ["accepted", "unknown", "pending"]
    assert recovered["items"][0]["job_id"] == 17
    assert "勿盲目重打" in recovered["items"][1]["reason"]
    assert env.api.post(f"{PATH}/{handle}/dispatch").status_code == 200
    assert len(worker.jobs) == 1 and len(sends) == 2
    assert all(path.suffix == ".json" for path in print_batch_store.STATE_DIR.iterdir())

    record = persisted()
    record["expires_at"] = 1
    state_path.write_text(json.dumps(record), encoding="utf-8")
    print_batch_store._batches.clear()
    print_batch_store.prune_expired()
    assert not state_path.exists()
    assert env.api.get(f"{PATH}/{handle}").status_code == 404


def test_prepare_admission_releases_capacity_on_completion_and_submit_failure(setup_batch, monkeypatch):
    store = print_batch_store
    monkeypatch.setattr(store, "MAX_PENDING_PREPARE_BATCHES", 1)
    worker = _DeferredWorker()
    monkeypatch.setattr(store, "_workers", worker)
    request = BatchRequest(ids=[1], session_mode="browser", device_id=DEVICE)
    owner = "notice-test-user"
    started = store.start_batch(owner, request)
    with pytest.raises(MustReportError, match="稍候重试"):
        store.start_batch(owner, request)
    assert list(store._batches) == [started.batch_id]
    assert len(worker.jobs) == 1
    worker.jobs[0][0].set_result(None)
    assert not store._pending_preparations

    def reject(*args):
        raise RuntimeError("mock rejected queue submission")
    monkeypatch.setattr(worker, "submit", reject)
    with pytest.raises(MustReportError, match="稍候重试"):
        store.start_batch(owner, request)
    assert not store._pending_preparations
    assert list(store._batches) == [started.batch_id]
    assert list(store.STATE_DIR.glob("*.json")) == [store.STATE_DIR / f"{started.batch_id}.json"]


def test_queued_browser_batch_never_switches_to_a_new_connection(setup_batch, monkeypatch):
    env = setup_batch
    worker = _DeferredWorker()
    monkeypatch.setattr(print_batch_store, "_workers", worker)
    start = env.api.post(f"{PATH}/prepare", json=body((1, 2)))
    assert start.status_code == 202
    env.broker.connect("notice-test-user", DEVICE, BASE)
    future, run, args = worker.jobs[0]
    future.set_result(run(*args))
    failed = env.api.get(f"{PATH}/{start.json()['batch_id']}").json()
    assert failed["status"] == "failed" and failed["session_stopped"] is True
    assert "重新连接" in failed["reason"]
    assert env.broker.take_pending("notice-test-user", DEVICE, timeout=0) is None
    assert not env.sent and not env.rendered
