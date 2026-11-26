"""Notice fetch jobs through the API, with a fake i8 and isolated PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.db import session_scope
from app.core.errors import ExternalServiceError
from app.core.session import set_current_name
from app.main import _install_error_handlers
from app.mod01_projects.models import Project
from app.mod02_i8.models import RunRecord
from app.mod03_notice import fetch_jobs, notice_executors
from app.mod03_notice.models import NoticeFetchJob, PaymentNotice
from app.mod03_notice.router import router
from app.mod11_jc import repository as jc, service as links
from app.mod11_jc.models import JcContract
from tests.test_acc_jc_pay_link import _project
from tests.test_jc_auto_link import contract, notice, source

JOB_PATH = "/api/m03/notices/fetch-jobs"
MONTH = "2026-10"
OWNER = "notice-test-account"


def app_for_jobs():
    app = FastAPI()
    _install_error_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def identity(request: Request, call_next):
        set_current_name(request.headers.get("x-test-owner", OWNER))
        return await call_next(request)

    return app


def fetched_row(code, title="", project="项目全名", **changes):
    return {
        "ph_id": code, "bill_no": code, "project_name": project,
        "approve_status": "已批", "amount_approved": "100.01",
        "doc_date": "2026-10-04", "payee": "资产处集中采购",
        "fields": {"BillName": title}, **changes,
    }


class FakeI8:
    def __init__(self):
        self.closed = Event()

    def close(self):
        self.closed.set()


@pytest.fixture
def job_api(rollback_db, monkeypatch):
    queued = []
    client = FakeI8()
    monkeypatch.setattr(fetch_jobs, "unified_i8_session", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(fetch_jobs, "open_i8_client", lambda **kw: client)

    class QueueThread:
        def __init__(self, *, target, args, daemon, name):
            assert daemon
            self.run = lambda: target(*args)

        def start(self):
            queued.append(self.run)

    monkeypatch.setattr(fetch_jobs, "Thread", QueueThread)
    with TestClient(app_for_jobs()) as api:
        yield api, client, queued


def start(api, **fields):
    response = api.post(JOB_PATH, json={
        "year_month": MONTH, "session_mode": "browser", "expected_account": OWNER, **fields,
    })
    assert response.status_code == 202, response.text
    return response.json()


def install_payable_snapshot(monkeypatch, fake, rows):
    reads = []

    def read(client):
        assert client is fake
        reads.append(client)
        if isinstance(rows, Exception):
            raise rows
        return rows

    monkeypatch.setattr(notice_executors, "fetch_payables", read)
    return reads


def test_fetched_batch_limits_automatic_matching_to_new_or_just_approved(job_api, monkeypatch):
    api, fake, queued = job_api
    with session_scope() as s:
        project = _project(s, "__新通知书集采__")
        project.name_full = "项目全名"
        local = contract(s, project, "CGHT100", supplier="乙")
        exact = contract(s, project, "CGHT1")
        existing = [
            notice(s, project, "NEWLY", supplier="甲", approve_status="未批"),
            notice(s, project, "ALREADY", supplier="甲"),
            notice(s, project, "UNBOUND", supplier="甲", approve_status="未批"),
            notice(s, project, "LINKED", supplier="甲", approve_status="未批"),
            notice(s, project, "REVOKED", supplier="甲", approve_status="未批", i8_revoked=True),
        ]
        links.act_link_notice(s, notice_id=existing[2].id, contract_id=exact.id)
        links.act_unlink_notice(s, notice_id=existing[2].id)
        links.act_link_notice(s, notice_id=existing[3].id, contract_id=exact.id)
        local_id, exact_id = local.id, exact.id
        s.add(Project(name_full="待指定小微", project_type="shell"))
    rows = [
        fetched_row("LOCAL", "CGHT100材料款"),
        fetched_row("AMOUNT", "甲钢材款"),
        fetched_row("NEWLY", "甲钢材款"),
        fetched_row("ALREADY", "CGHT1材料款"),
        fetched_row("UNBOUND", "CGHT1材料款"),
        fetched_row("LINKED", "CGHT100材料款"),
        fetched_row("REVOKED", "CGHT1材料款"),
        fetched_row("UNAPPROVED", "CGHT1材料款", approve_status="未批"),
        fetched_row("EXCLUDED", "CGHT1材料款", biz_type="付劳务公司款"),
        fetched_row("NO_AMOUNT", "CGHT1材料款", amount_approved="0"),
        fetched_row("MATERIAL", "CGHT1材料款", payee="普通材料"),
        fetched_row("REVIEW", "普通钢材款"),
        fetched_row("UNRESOLVED", "缺少关键词", project="待指定小微"),
    ]
    monkeypatch.setattr(notice_executors.NoticeFetcher, "fetch_month", lambda *args: rows)
    reads = install_payable_snapshot(monkeypatch, fake, [source()])
    accepted = start(api)
    assert accepted["stage"] == "fetching_notices" and accepted["result"] is None
    assert start(api)["id"] == accepted["id"]
    assert len(queued) == 1
    queued.pop()()
    assert fake.closed.is_set()
    complete = api.get(JOB_PATH + "/active").json()
    assert (complete["id"], complete["status"], complete["stage"]) == (accepted["id"], "completed", "completed")
    result = complete["result"]
    assert [result[k] for k in ("fetched", "saved", "upserted", "created", "updated",
                               "ignored_count", "excluded", "unresolved")] == [13, 12, 12, 7, 5, 1, 1, 1]
    assert result["ignored"][0]["bill_no"] == "UNRESOLVED"
    assert result["notices_saved"] and result["auto_linked"] == 3 and len(reads) == 1
    assert {r["code"]: r["target"]["contract_id"] for r in result["auto_linked_items"]} == {
        "LOCAL": local_id, "AMOUNT": exact_id, "NEWLY": exact_id,
    }
    assert result["manual_review"] == 1 and result["manual_review_items"][0]["code"] == "REVIEW"
    assert result["manual_review_items"][0]["candidates"] and not result["payable_source_failed"]
    with session_scope() as s:
        stored = {n.id: n for n in s.scalars(select(PaymentNotice))}
        assert {stored[nid].ph_id: ids for nid, ids in jc.links_by_notice(s, list(stored)).items()} == {
            "LOCAL": [local_id], "AMOUNT": [exact_id], "NEWLY": [exact_id], "LINKED": [exact_id],
        }
        assert next(n for n in stored.values() if n.ph_id == "UNBOUND").jc_auto_link_blocked

    second = start(api)
    assert second["id"] != accepted["id"]
    queued.pop()()
    result = api.get(f"{JOB_PATH}/{second['id']}").json()["result"]
    assert result["upserted"] == result["auto_linked"] == result["manual_review"] == 0
    assert len(reads) == 1


@pytest.mark.parametrize("mode", ["all_local", "empty", "no_match", "payable_failure", "fetch_failure", "save_failure"])
def test_fetch_job_distinguishes_saved_notices_and_source_failures(job_api, monkeypatch, mode):
    api, fake, queued = job_api
    with session_scope() as s:
        project = _project(s, "__抓取回执__")
        project.name_full = "项目全名"
        contract(s, project, "CGHT1")
    rows = [] if mode == "empty" else [fetched_row("LOCAL", "CGHT1材料款")]
    if mode in ("no_match", "payable_failure"):
        rows.append(fetched_row("AMOUNT", "甲材料款"))

    def read_notices(*args):
        if mode == "fetch_failure":
            raise ExternalServiceError("付款通知书来源异常")
        return rows

    monkeypatch.setattr(notice_executors.NoticeFetcher, "fetch_month", read_notices)
    payables = ExternalServiceError("应付来源异常") if mode == "payable_failure" else [source(amount="200.00")]
    reads = install_payable_snapshot(monkeypatch, fake, payables)
    if mode == "save_failure":
        def fail_save(*args, **kwargs):
            raise RuntimeError("isolated save error")
        monkeypatch.setattr(notice_executors, "_save_fetched_rows", fail_save)

    job = start(api)
    queued.pop()()
    final = api.get(f"{JOB_PATH}/{job['id']}").json()
    result = final["result"]
    if mode in ("fetch_failure", "save_failure"):
        assert final["status"] == "failed" and not result["notices_saved"]
        assert result["saved"] == 0 and result["fetch_error"] and not result["payable_source_failed"]
        with session_scope() as s:
            assert s.scalar(select(PaymentNotice)) is None
    else:
        assert final["status"] == "completed" and result["notices_saved"] and not result["fetch_error"]
        assert result["saved"] == len(rows) and result["auto_linked"] == int(bool(rows))
        assert result["payable_source_failed"] == (mode == "payable_failure")
        if mode == "payable_failure":
            assert result["payable_source_error"] == "应付来源异常"
            assert result["manual_review_items"][0]["rule_code"] == "payable_source_failed"
        if mode == "no_match":
            assert result["manual_review_items"][0]["rule_code"] == "no_exact_payable"
    assert len(reads) == int(mode in ("no_match", "payable_failure"))


@pytest.mark.parametrize("checkpoint", [False, True])
def test_stale_job_recovery_and_account_scoped_ack(job_api, monkeypatch, checkpoint):
    api, _, _ = job_api
    job = start(api)
    job_path = f"{JOB_PATH}/{job['id']}"
    assert api.post(job_path + "/ack").status_code == 409
    with session_scope() as s:
        stored = s.get(NoticeFetchJob, job["id"])
        if checkpoint:
            stored.stage = "matching_jc"
            stored.result_json = {"year_month": MONTH, "fetched": 2, "upserted": 1, "saved": 2, "notices_saved": True}
    monkeypatch.setattr(fetch_jobs, "BOOT_ID", "different-boot")
    foreign = {"x-test-owner": "other-account"}
    assert api.get(job_path, headers=foreign).status_code == 404
    assert api.post(job_path + "/ack", headers=foreign).status_code == 404
    assert api.get(JOB_PATH + "/active", headers=foreign).json() is None
    with TestClient(app_for_jobs()) as reopened:
        recovered = reopened.get(JOB_PATH + "/active").json()
        assert recovered["id"] == job["id"] and recovered["status"] == "failed"
        assert recovered["completed_at"] and "服务已重启" in recovered["error_message"]
        assert recovered["result"]["notices_saved"] == checkpoint
        error = "matching_error" if checkpoint else "fetch_error"
        assert recovered["result"][error] == recovered["error_message"]
        acked = reopened.post(job_path + "/ack").json()
        assert acked["acknowledged_at"]
        assert reopened.post(job_path + "/ack").json()["acknowledged_at"] == acked["acknowledged_at"]
        assert reopened.get(JOB_PATH + "/active").json() is None
        assert reopened.get(job_path).json()["result"] == recovered["result"]
        assert start(reopened)["id"] != job["id"]


def test_daemon_job_reports_stages_and_concurrent_start_reuses_it(monkeypatch):
    prefix = "job-" + uuid4().hex
    ready_to_save, after_save, allow_save, allow_payable = (Event() for _ in range(4))
    fake = FakeI8()
    started = []
    with session_scope() as s:
        project = _project(s, prefix)
        project.name_full = prefix
        contract(s, project, "CGHT1")
        pid = project.id
    def open_client(**kwargs):
        started.append(fake)
        return fake

    monkeypatch.setattr(fetch_jobs, "unified_i8_session", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(fetch_jobs, "open_i8_client", open_client)
    monkeypatch.setattr(notice_executors.NoticeFetcher, "fetch_month", lambda *a: [fetched_row(prefix, "甲材料款", prefix)])
    save = notice_executors._save_fetched_rows

    def wait_before_save(*args, **kwargs):
        ready_to_save.set()
        assert allow_save.wait(10)
        return save(*args, **kwargs)

    def wait_for_payable(client):
        assert client is fake
        with session_scope() as s:
            assert s.scalar(select(PaymentNotice.id).where(PaymentNotice.ph_id == prefix)) is not None
        after_save.set()
        assert allow_payable.wait(10)
        return [source(project=prefix)]

    monkeypatch.setattr(notice_executors, "_save_fetched_rows", wait_before_save)
    monkeypatch.setattr(notice_executors, "fetch_payables", wait_for_payable)
    headers = {"x-test-owner": prefix}
    try:
        with TestClient(app_for_jobs()) as api, ThreadPoolExecutor(2) as pool:
            def post():
                return api.post(JOB_PATH, json={"session_mode": "browser", "year_month": MONTH}, headers=headers)

            replies = [pool.submit(post) for _ in range(2)]
            initial = [reply.result(timeout=10) for reply in replies]
            assert all(reply.status_code == 202 for reply in initial)
            job_id = initial[0].json()["id"]
            assert initial[1].json()["id"] == job_id and started == [fake]
            assert ready_to_save.wait(10)
            assert api.get(JOB_PATH + "/active", headers=headers).json()["stage"] == "saving_notices"
            allow_save.set()
            assert after_save.wait(10)
            matching = api.get(f"{JOB_PATH}/{job_id}", headers=headers).json()
            assert matching["stage"] == "matching_jc" and matching["result"]["saved"] == 1
            allow_payable.set()
            assert fake.closed.wait(10)
            result = api.get(JOB_PATH + "/active", headers=headers).json()
            assert result["status"] == "completed" and result["result"]["auto_linked"] == 1
            run_id = result["result"]["receipt"]["id"]
            with session_scope() as s:
                nid = s.scalar(select(PaymentNotice.id).where(PaymentNotice.ph_id == prefix))
                assert jc.payment_of_notice(s, nid) is not None
            with session_scope() as s:
                s.execute(delete(RunRecord).where(RunRecord.id == run_id))
    finally:
        allow_save.set()
        allow_payable.set()
        if started:
            assert fake.closed.wait(10)
        with session_scope() as s:
            s.execute(delete(NoticeFetchJob).where(NoticeFetchJob.account == prefix))
            s.execute(delete(PaymentNotice).where(PaymentNotice.ph_id == prefix))
            s.execute(delete(JcContract).where(JcContract.project_id == pid))
            s.delete(s.get(Project, pid))
