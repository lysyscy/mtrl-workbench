"""Process-local, owner-scoped handoff from notice preparation to dispatch."""

from __future__ import annotations

import secrets
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from app.core.errors import AppError, MustReportError, human_reason, log_exc
from app.mod02_i8.browser_relay import MODE_HTTP, resolve_mode
from app.mod02_i8.browser_session import StrictSessionStopped
from app.mod02_i8.client import I8OnlineConflictError
from app.mod02_i8.session_policy import unified_i8_session
from app.mod03_notice import pdf_cache
from app.mod03_notice.notice_executors import batch_resources, load_batch_notices, persist_batch_run
from app.mod03_notice.print.dispatch import dispatch_pdf
from app.mod03_notice.schemas import BatchRequest, BatchResponse, ItemOutcomeOut, PreparationItemOut, PrintBatchOut
from app.mod03_notice.service import (
    MODE_PDF, MODE_PRINT, BatchResult, ItemOutcome, PreparedPdf, complete_preparation,
    dispatch_prepared, prepare_batch,
)

_TTL_SECONDS = 15 * 60
_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notice-batch")
_index_lock = Lock()
_batches: dict[str, _PrintBatch] = {}


def confirmed_ids(req: BatchRequest) -> tuple[int, ...]:
    return tuple(dict.fromkeys(req.ids))


def batch_i8_session(req: BatchRequest, owner: str, ids: tuple[int, ...]):
    return unified_i8_session(
        req, owner=owner, operation="m03.batch",
        scope={"mode": req.mode, "ids": list(ids)}, require_explicit=True,
    )


def batch_response(result: BatchResult) -> BatchResponse:
    token = pdf_cache.put(result.files) if result.files else ""
    batch_name = Path(result.batch_dir).name if result.batch_dir else ""
    return BatchResponse(
        mode=result.mode, total=result.total, success=len(result.success), failed=len(result.failed),
        unprinted_bill_nos=result.unprinted_bill_nos, batch_dir=result.batch_dir,
        items=[
            ItemOutcomeOut(
                notice_id=item.notice_id, bill_no=item.bill_no, ok=item.ok,
                unverified=item.unverified, reason=item.reason, pdf_path=item.pdf_path,
                download_url=(
                    f"/api/m03/pdf/{token}" if item.ok and token
                    else f"/api/m03/pdf/{batch_name}/{Path(item.pdf_path).name}"
                    if item.pdf_path and batch_name else ""
                ),
            )
            for item in result.outcomes
        ],
    )


@dataclass
class _PrintBatch:
    batch_id: str
    owner: str
    mode: str
    ids: tuple[int, ...]
    started: datetime = field(default_factory=datetime.now)
    lock: Lock = field(default_factory=Lock)
    stage: str = "connecting"
    status: str = "running"
    current_id: int | None = None
    failed_id: int | None = None
    reason: str = ""
    session_stopped: bool = False
    kick_token: str = ""
    bill_nos: dict[int, str] = field(default_factory=dict)
    preparation: dict[int, ItemOutcome] = field(default_factory=dict)
    prepared: list[PreparedPdf] = field(default_factory=list)
    prepared_count: int = 0
    dispatch_outcomes: list[ItemOutcome] = field(default_factory=list)
    dispatched_count: int = 0
    result: BatchResponse | None = None
    expires_at: float = float("inf")

    def snapshot(self) -> PrintBatchOut:
        with self.lock:
            return self._snapshot()

    def _snapshot(self) -> PrintBatchOut:
        items = []
        for notice_id in self.ids:
            outcome = self.preparation.get(notice_id)
            if outcome is not None:
                status = "prepared" if outcome.ok else "failed"
            elif self.status == "running":
                status = "preparing" if notice_id == self.current_id else "pending"
            else:
                status = "skipped"
            items.append(PreparationItemOut(
                notice_id=notice_id, bill_no=self.bill_nos.get(notice_id, str(notice_id)),
                status=status, reason=outcome.reason if outcome else "",
            ))
        return PrintBatchOut(
            batch_id=self.batch_id, mode=self.mode, ids=self.ids,
            stage=self.stage, status=self.status, total=len(self.ids),
            prepared_count=self.prepared_count, dispatched_count=self.dispatched_count,
            dispatch_processed_count=len(self.dispatch_outcomes),
            current_bill_no=self.bill_nos.get(self.current_id, ""),
            failed_notice_id=None if self.session_stopped else self.failed_id,
            failed_bill_no=self.bill_nos.get(self.failed_id, ""),
            reason=self.reason, session_stopped=self.session_stopped, kick_token=self.kick_token,
            items=items, result=self.result,
        )

    def begin_item(self, notice_id: int, bill_no: str) -> None:
        with self.lock:
            self.current_id = notice_id
            self.bill_nos[notice_id] = bill_no

    def finish_item(self, outcome: ItemOutcome, pdf: PreparedPdf | None) -> None:
        with self.lock:
            self.stage = "preparing"
            self.preparation[outcome.notice_id] = outcome
            self.current_id = None
            if pdf is not None:
                self.prepared.append(pdf)
                self.prepared_count += 1
            elif self.failed_id is None:
                self.failed_id, self.reason = outcome.notice_id, outcome.reason

    def stop(self, exc: Exception) -> None:
        with self.lock:
            reason = exc.message if isinstance(exc, AppError) else human_reason("准备 PDF 失败", exc)
            self.reason = reason
            self.session_stopped = isinstance(exc, (StrictSessionStopped, I8OnlineConflictError))
            if isinstance(exc, I8OnlineConflictError) and isinstance(exc.detail, dict):
                self.kick_token = exc.detail.get("kick_token", "")
            self.failed_id = self.current_id
            if self.failed_id is not None:
                self.preparation[self.failed_id] = ItemOutcome(
                    self.failed_id, self.bill_nos[self.failed_id], False, reason=reason,
                )
            self.current_id = None

    def finish_preparation(self) -> BatchResult | None:
        with self.lock:
            self.expires_at = time.monotonic() + _TTL_SECONDS
            if self.mode == MODE_PRINT and self.prepared_count == len(self.ids) and not self.reason:
                self.status = "ready"
                return None
            result = complete_preparation(
                self.mode, self.ids, self.preparation, self.prepared, bill_nos=self.bill_nos,
            )
            self.result = batch_response(result)
            self.prepared.clear()
            self.status = "failed" if self.reason else "complete"
            return result


def _sweep() -> None:
    now = time.monotonic()
    for batch_id, batch in list(_batches.items()):
        with batch.lock:
            if batch.expires_at <= now:
                del _batches[batch_id]


def _find(owner: str, batch_id: str) -> _PrintBatch:
    with _index_lock:
        _sweep()
        batch = _batches.get(batch_id)
        if not batch or batch.owner != owner:
            raise HTTPException(404, "批次不存在或已过期。")
        return batch


def _persist(batch: _PrintBatch, result: BatchResult | None) -> None:
    if result is not None:
        try:
            persist_batch_run(result, batch.started)
        except Exception as exc:  # noqa: BLE001
            log_exc("保存通知书批次运行记录失败", exc)


def _prepare(batch: _PrintBatch, req: BatchRequest, startup: Future[None]) -> None:
    def connected() -> None:
        with batch.lock:
            batch.stage = "preparing"
        startup.set_result(None)

    try:
        with batch_i8_session(req, batch.owner, batch.ids):
            notices = load_batch_notices(batch.ids)
            with batch.lock:
                batch.bill_nos.update({
                    notice.id: (notice.bill_no or "").strip() or str(notice.id) for notice in notices
                })
            with batch_resources(batch.owner) as resources:
                prepare_batch(
                    notices, mode=batch.mode, **resources,
                    on_start=batch.begin_item, on_item=batch.finish_item, on_connected=connected,
                )
    except Exception as exc:  # noqa: BLE001
        batch.stop(exc)
        if not startup.done() and isinstance(exc, I8OnlineConflictError):
            startup.set_exception(exc)
    finally:
        result = batch.finish_preparation()
        if not startup.done():
            startup.set_result(None)
        _persist(batch, result)


def start_batch(owner: str, req: BatchRequest) -> PrintBatchOut:
    if not owner:
        raise MustReportError("请登录工作台后重新发起 i8 操作。")
    session_mode = resolve_mode(req.session_mode, require_explicit=True)
    batch = _PrintBatch(secrets.token_urlsafe(24), owner, req.mode, confirmed_ids(req))
    initial = batch.snapshot()
    with _index_lock:
        _sweep()
        _batches[batch.batch_id] = batch
    startup: Future[None] = Future()
    _workers.submit(copy_context().run, _prepare, batch, req, startup)
    if session_mode == MODE_HTTP:
        # Login is lazy. Wait through the first design request for the standard HTTP 409
        # confirmation, then leave rendering and the rest of the batch to the worker.
        startup.result()
        return batch.snapshot()
    return initial


def read_batch(owner: str, batch_id: str) -> PrintBatchOut:
    return _find(owner, batch_id).snapshot()


def start_dispatch(owner: str, batch_id: str) -> PrintBatchOut:
    batch = _find(owner, batch_id)
    with batch.lock:
        if batch.stage == "dispatching":
            return batch._snapshot()
        if batch.mode != MODE_PRINT or batch.status != "ready" or batch.expires_at <= time.monotonic():
            raise HTTPException(409, "只有已准备好全部 PDF 的打印批次可以投递。")
        batch.stage, batch.status = "dispatching", "running"
        batch.expires_at = float("inf")
        _workers.submit(copy_context().run, _dispatch, batch, tuple(batch.prepared))
        return batch._snapshot()


def _dispatch(batch: _PrintBatch, prepared: tuple[PreparedPdf, ...]) -> None:
    for pdf in prepared:
        batch.begin_item(pdf.notice_id, pdf.bill_no)
        outcome = dispatch_prepared(pdf, dispatch_pdf)
        with batch.lock:
            batch.dispatch_outcomes.append(outcome)
            batch.dispatched_count += int(outcome.ok)
    result = BatchResult(mode=MODE_PRINT, outcomes=batch.dispatch_outcomes)
    with batch.lock:
        batch.result = batch_response(result)
        batch.current_id = None
        batch.status = "complete"
        batch.prepared.clear()
        batch.expires_at = time.monotonic() + _TTL_SECONDS
    _persist(batch, result)
