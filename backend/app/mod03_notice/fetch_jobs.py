"""Durable receipts for the notice fetch worker in the workbench process."""
from __future__ import annotations

from contextlib import ExitStack, closing
from datetime import datetime
from threading import Lock, Thread
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import AppError, DataConflictError, MustReportError, human_reason
from app.core.session import set_current_name
from app.mod02_i8.browser_relay import MODE_HTTP, open_i8_client, resolve_mode
from app.mod02_i8.client import I8Client
from app.mod02_i8.fetch_task import build_fetch_params
from app.mod02_i8.notice_source import NoticeFetcher
from app.mod02_i8.session_policy import unified_i8_session
from app.mod03_notice.models import NoticeFetchJob
from app.mod03_notice.notice_executors import run_notice_fetch
from app.mod03_notice.schemas import FetchJobOut, FetchJobStage, FetchRequest, FetchResponse

BOOT_ID = uuid4().hex
STAGE_LABELS: dict[FetchJobStage, str] = {
    "fetching_notices": "正在抓取付款通知书…",
    "saving_notices": "正在保存通知书…",
    "matching_jc": "正在自动关联集采合同…",
    "completed": "抓取完成",
    "failed": "本批处理未完成",
}
_start_lock = Lock()


def _snapshot(job: NoticeFetchJob) -> FetchJobOut:
    return FetchJobOut(
        id=job.id, account=job.account, year_month=job.year_month, status=job.status,
        stage=job.stage, stage_label=job.stage_label, result=job.result_json,
        error_message=job.error_message, created_at=job.created_at, updated_at=job.updated_at,
        completed_at=job.completed_at, acknowledged_at=job.acknowledged_at,
    )


def _progress(job: NoticeFetchJob, stage: FetchJobStage, result: FetchResponse) -> None:
    now = datetime.now()
    job.stage = stage
    job.stage_label = STAGE_LABELS[stage]
    job.result_json = result.model_dump(mode="json")
    job.updated_at = now
    if stage in ("completed", "failed"):
        job.status = stage
        job.completed_at = now
        job.error_message = result.fetch_error or result.matching_error


def _fail(job: NoticeFetchJob, message: str) -> None:
    result = (FetchResponse.model_validate(job.result_json) if job.result_json is not None else
              FetchResponse(year_month=job.year_month, fetched=0, upserted=0))
    if result.notices_saved:
        result.matching_error = message
    else:
        result.fetch_error = message
    _progress(job, "failed", result)


def _reconcile(session: Session, job: NoticeFetchJob) -> None:
    if job.status != "running" or job.boot_id == BOOT_ID:
        return
    session.refresh(job, with_for_update=True)
    if job.status == "running" and job.boot_id != BOOT_ID:
        _fail(job, "服务已重启，本批处理已中断。请核对已保存的通知书和关联结果。")


def _run(job_id: int, account: str, month: str, client: I8Client) -> None:
    set_current_name(account)

    def report(session: Session, stage: FetchJobStage, result: FetchResponse) -> None:
        _progress(session.get(NoticeFetchJob, job_id), stage, result)

    with closing(client):
        try:
            run_notice_fetch(month, client, progress=report)
        except Exception as exc:
            with session_scope() as session:
                job = session.get(NoticeFetchJob, job_id)
                action = job.stage_label.removeprefix("正在").rstrip("…")
                message = exc.message if isinstance(exc, AppError) else human_reason(action + "失败", exc)
                _fail(job, message)


def start_job(account: str, request: FetchRequest) -> FetchJobOut:
    if not account:
        raise MustReportError("请登录工作台后再发起抓取。")
    month = build_fetch_params(request.year_month)["year_month"]
    mode = resolve_mode(request.session_mode)
    with _start_lock, ExitStack() as resources:
        with session_scope() as session:
            active = session.scalar(select(NoticeFetchJob).where(
                NoticeFetchJob.account == account, NoticeFetchJob.year_month == month,
                NoticeFetchJob.status == "running",
            ))
            if active is not None:
                _reconcile(session, active)
                if active.status == "running":
                    return _snapshot(active)

        with unified_i8_session(
            request, owner=account, operation="m03.notices.fetch-jobs", scope={"year_month": month},
        ):
            client = resources.enter_context(closing(open_i8_client(owner=account)))
            if mode == MODE_HTTP:
                NoticeFetcher(client).validate_session(month)

        with session_scope() as session:
            job = NoticeFetchJob(
                account=account, year_month=month, status="running", stage="fetching_notices",
                stage_label=STAGE_LABELS["fetching_notices"], boot_id=BOOT_ID,
            )
            session.add(job)
            session.flush()
            initial = _snapshot(job)
        try:
            Thread(target=_run, args=(initial.id, account, month, client),
                   daemon=True, name=f"notice-fetch-{initial.id}").start()
        except RuntimeError as exc:
            with session_scope() as session:
                job = session.get(NoticeFetchJob, initial.id)
                _fail(job, human_reason("无法启动付款通知书抓取任务", exc))
                return _snapshot(job)
        resources.pop_all()  # The worker now owns the client.
        return initial


def read_active_job(account: str) -> FetchJobOut | None:
    with session_scope() as session:
        job = session.scalar(select(NoticeFetchJob).where(
            NoticeFetchJob.account == account, NoticeFetchJob.acknowledged_at.is_(None),
        ).order_by(NoticeFetchJob.id.desc()).limit(1))
        if job is None:
            return None
        _reconcile(session, job)
        return _snapshot(job)


def read_job(account: str, job_id: int, *, acknowledge: bool = False) -> FetchJobOut | None:
    with session_scope() as session:
        stmt = select(NoticeFetchJob).where(NoticeFetchJob.id == job_id, NoticeFetchJob.account == account)
        job = session.scalar(stmt.with_for_update() if acknowledge else stmt)
        if job is None:
            return None
        _reconcile(session, job)
        if acknowledge:
            if job.status == "running":
                raise DataConflictError("抓取仍在进行，请在完成后关闭结果。")
            if job.acknowledged_at is None:
                job.acknowledged_at = job.updated_at = datetime.now()
        return _snapshot(job)
