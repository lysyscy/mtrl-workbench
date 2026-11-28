"""Owner-scoped print batches with recovery of durable dispatch receipts."""

from __future__ import annotations

import os
import re
import secrets
import time
from tempfile import NamedTemporaryFile
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import BinaryIO

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import PROJECT_ROOT
from app.core.errors import AppError, MustReportError, human_reason, log_exc
from app.mod02_i8.browser_relay import MODE_BROWSER, MODE_HTTP, resolve_mode
from app.mod02_i8.browser_session import StrictSessionStopped
from app.mod02_i8.client import I8OnlineConflictError
from app.mod02_i8.login import I8AuthFailedError
from app.mod02_i8.session_policy import unified_i8_session
from app.mod03_notice import pdf_cache
from app.mod03_notice.notice_executors import batch_resources, load_batch_notices, persist_batch_run
from app.mod03_notice.print.dispatch import (
    A4BlockedError, DispatchAttempt, DispatchOutcome, DispatchPlan, lock_a4_channel,
)
from app.mod03_notice.schemas import (
    A4BlockOut, BatchRequest, BatchResponse, ItemOutcomeOut, PreparationItemOut,
    PrintBatchExportOut, PrintBatchOut, PrintDispatchRequest,
)
from app.mod03_notice.service import (
    MODE_PRINT, BatchResult, ItemOutcome, PreparedPdf, complete_preparation,
    dispatch_prepared, prepare_batch,
)

_TTL_SECONDS = 15 * 60
MAX_PENDING_PREPARE_BATCHES = 8
STATE_DIR = PROJECT_ROOT / "var" / "state" / "print-batches"
_INTERRUPTED_DELIVERY = "结果待核实：投递过程中服务中断，请先核对打印机出纸，勿盲目重打"
_INTERRUPTED_PREPARATION = "准备 PDF 时工作台服务中断，请重新确认并准备本批。"
_BATCH_ID = re.compile(r"[A-Za-z0-9_-]{32}")
_pending_preparations: set[str] = set()
_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notice-batch")
_index_lock = Lock()
_batches: dict[str, _PrintBatch] = {}


def confirmed_ids(req: BatchRequest) -> tuple[int, ...]:
    return tuple(dict.fromkeys(req.ids))


def batch_i8_session(req: BatchRequest, owner: str, ids: tuple[int, ...]):
    return unified_i8_session(
        req, owner=owner, operation="m03.batch",
        scope={"mode": req.mode, "ids": list(ids)},
    )


def batch_response(result: BatchResult) -> BatchResponse:
    token = pdf_cache.put(result.files) if result.files else ""
    batch_name = Path(result.batch_dir).name if result.batch_dir else ""
    return BatchResponse(
        mode=result.mode, total=result.total, success=len(result.success), failed=len(result.failed),
        unknown=len(result.unknown), unprinted_bill_nos=result.unprinted_bill_nos, batch_dir=result.batch_dir,
        items=[
            ItemOutcomeOut(
                notice_id=item.notice_id, bill_no=item.bill_no, ok=item.ok,
                unverified=item.unverified, reason=item.reason, pdf_path=item.pdf_path,
                download_url=(
                    f"/api/m03/pdf/{token}" if item.ok and token
                    else f"/api/m03/pdf/{batch_name}/{Path(item.pdf_path).name}"
                    if item.pdf_path and batch_name else ""
                ),
                **item.receipt_fields(),
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
    dispatch_lock: Lock = field(default_factory=Lock)
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
    dispatch_outcomes: dict[int, ItemOutcome] = field(default_factory=dict)
    a4_blocked: A4BlockOut | None = None
    export_token: str = ""
    dispatched_count: int = 0
    result: BatchResponse | None = None
    expires_at: float = field(default_factory=lambda: time.time() + _TTL_SECONDS)
    channels: tuple[str, ...] = ()

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
            delivery = self.dispatch_outcomes.get(notice_id)
            report = delivery or outcome
            receipt = delivery.receipt_fields() if delivery else {}
            if self.stage == "dispatching" and notice_id == self.current_id and not delivery:
                receipt = {"delivery_status": "in_flight", "channel": self.channels[0] if self.channels else ""}
            items.append(PreparationItemOut(
                notice_id=notice_id, bill_no=self.bill_nos.get(notice_id, str(notice_id)),
                status=status, reason=report.reason if report else "",
                **receipt,
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
            items=items, result=self.result, a4_blocked=self.a4_blocked,
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
            self.expires_at = time.time() + _TTL_SECONDS
            _checkpoint(self)

    def stop(self, exc: Exception) -> None:
        with self.lock:
            reason = exc.message if isinstance(exc, AppError) else human_reason("准备 PDF 失败", exc)
            self.reason = reason
            self.session_stopped = isinstance(exc, (StrictSessionStopped, I8OnlineConflictError, I8AuthFailedError))
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
            self.expires_at = time.time() + _TTL_SECONDS
            if self.mode == MODE_PRINT and self.prepared_count == len(self.ids) and not self.reason:
                self.status = "ready"
                _checkpoint(self)
                return None
            result = complete_preparation(
                self.mode, self.ids, self.preparation, self.prepared, bill_nos=self.bill_nos,
            )
            self.result = batch_response(result)
            self.prepared.clear()
            self.status = "failed" if self.reason else "complete"
            _checkpoint(self)
            return result


class _StoredBatch(BaseModel):
    owner: str
    started: datetime
    updated_at: float
    expires_at: float
    channels: tuple[str, ...]
    snapshot: PrintBatchOut


def _atomic_write(path: Path, write: Callable[[BinaryIO], object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f"{path.stem}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
        finally:
            stream.close()
            _remove_file(temporary)


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log_exc("清理打印批次临时状态失败", exc)


def _save_state(batch: _PrintBatch) -> None:
    if batch.mode != MODE_PRINT:
        return
    snapshot = batch._snapshot().model_copy(update={"kick_token": ""})
    stored = _StoredBatch(
        owner=batch.owner, started=batch.started, updated_at=time.time(),
        expires_at=batch.expires_at, channels=batch.channels, snapshot=snapshot,
    )
    _atomic_write(STATE_DIR / f"{batch.batch_id}.json",
                  lambda stream: stream.write(stored.model_dump_json().encode("utf-8")))


def _checkpoint(batch: _PrintBatch) -> None:
    try:
        _save_state(batch)
    except OSError as exc:
        log_exc("保存打印批次状态失败", exc)


def _load_state(batch_id: str) -> _StoredBatch | None:
    if not _BATCH_ID.fullmatch(batch_id):
        return None
    try:
        data = _StoredBatch.model_validate_json((STATE_DIR / f"{batch_id}.json").read_bytes())
        if data.snapshot.batch_id == batch_id and data.snapshot.mode == MODE_PRINT:
            return data
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        log_exc("读取打印批次状态失败", exc)
    return None


def _restore_batch(data: _StoredBatch) -> _PrintBatch:
    view = data.snapshot
    batch = _PrintBatch(
        view.batch_id, data.owner, view.mode, view.ids, started=data.started,
        stage=view.stage, status=view.status, failed_id=view.failed_notice_id,
        reason=view.reason, session_stopped=view.session_stopped, prepared_count=view.prepared_count,
        dispatched_count=view.dispatched_count, result=view.result, a4_blocked=view.a4_blocked,
        expires_at=data.expires_at, channels=data.channels,
    )
    for item in view.items:
        batch.bill_nos[item.notice_id] = item.bill_no
        if item.status in ("prepared", "failed"):
            batch.preparation[item.notice_id] = ItemOutcome(
                item.notice_id, item.bill_no, item.status == "prepared", reason=item.reason,
            )
        attempts = tuple(DispatchAttempt(**attempt.model_dump()) for attempt in item.attempts)
        if item.delivery_status == "in_flight":
            attempts = (DispatchAttempt("unknown", _INTERRUPTED_DELIVERY, channel=item.channel),)
        if attempts:
            receipt = DispatchOutcome(attempts)
            batch.dispatch_outcomes[item.notice_id] = ItemOutcome(
                item.notice_id, item.bill_no, receipt.last.status == "accepted",
                unverified=receipt.last.status != "failed", reason=receipt.last.reason, delivery=receipt,
            )
    if batch.status == "running" and batch.stage == "dispatching":
        batch.stage, batch.status = "done", "complete"
        batch.reason = "服务中断，未开始投递的单据仍显示为待投递。"
        _checkpoint(batch)
    elif batch.status in ("ready", "running"):
        was_ready = batch.status == "ready"
        batch.status = "failed"
        batch.reason = (
            "服务已重启，请重新确认并准备本批 PDF。" if was_ready else _INTERRUPTED_PREPARATION
        )
        batch.a4_blocked = None
        _checkpoint(batch)
    return batch


def _sweep(now: float) -> None:
    for batch_id, batch in list(_batches.items()):
        with batch.lock:
            if batch.status != "running" and batch.expires_at <= now:
                del _batches[batch_id]
                _remove_file(STATE_DIR / f"{batch_id}.json")


def _stored_batches(now: float) -> Iterator[_StoredBatch]:
    for path in STATE_DIR.glob("*.json"):
        if path.stem in _batches:
            continue
        data = _load_state(path.stem)
        if data is not None:
            if data.expires_at > now:
                yield data
            else:
                _remove_file(path)
    for path in STATE_DIR.glob("*.tmp"):
        try:
            if path.stat().st_mtime + _TTL_SECONDS <= now:
                _remove_file(path)
        except OSError:
            continue


def prune_expired() -> None:
    """Remove expired receipt files even when there is no incoming batch traffic."""
    with _index_lock:
        now = time.time()
        _sweep(now)
        for _ in _stored_batches(now):
            pass


def _find(owner: str, batch_id: str) -> _PrintBatch:
    with _index_lock:
        now = time.time()
        _sweep(now)
        batch = _batches.get(batch_id)
        if batch is None:
            data = _load_state(batch_id)
            if data is not None and data.owner == owner:
                if data.expires_at > now:
                    batch = _restore_batch(data)
                    _batches[batch_id] = batch
                else:
                    _remove_file(STATE_DIR / f"{batch_id}.json")
        if batch is None or batch.owner != owner:
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
            _checkpoint(batch)
        startup.set_result(None)

    try:
        # Browser context is copied at admission. HTTP confirmation is consumed by the worker.
        with (batch_i8_session(req, batch.owner, batch.ids) if req.session_mode == MODE_HTTP else nullcontext()):
            notices = load_batch_notices(batch.ids)
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
    session_mode = resolve_mode(req.session_mode)
    ids = confirmed_ids(req)
    with (batch_i8_session(req, owner, ids) if session_mode == MODE_BROWSER else nullcontext()):
        context = copy_context()
    bill_nos = {notice.id: (notice.bill_no or "").strip() or "单号缺失" for notice in load_batch_notices(ids)}
    with _index_lock:
        if len(_pending_preparations) >= MAX_PENDING_PREPARE_BATCHES:
            raise MustReportError("当前待准备的打印批次较多，请稍候重试。")
        _sweep(time.time())
        batch = _PrintBatch(secrets.token_urlsafe(24), owner, req.mode, ids, bill_nos=bill_nos)
        initial = batch.snapshot()
        try:
            _save_state(batch)
        except OSError as exc:
            log_exc("初始化打印批次状态失败", exc)
            raise MustReportError("暂时无法保存打印批次，请稍候重试。") from None
        _batches[batch.batch_id] = batch
        _pending_preparations.add(batch.batch_id)

    def release_slot(_future=None) -> None:
        with _index_lock:
            _pending_preparations.discard(batch.batch_id)

    startup: Future[None] = Future()
    try:
        worker = _workers.submit(context.run, _prepare, batch, req, startup)
    except RuntimeError as exc:
        release_slot()
        with _index_lock:
            del _batches[batch.batch_id]
            _remove_file(STATE_DIR / f"{batch.batch_id}.json")
        log_exc("未能安排打印批次准备", exc)
        raise MustReportError("暂时无法准备本批，请稍候重试。") from None
    worker.add_done_callback(release_slot)
    if session_mode == MODE_HTTP:
        # Login is lazy. Wait through the first design request for the standard HTTP 409
        # confirmation, then leave rendering and the rest of the batch to the worker.
        startup.result()
        return batch.snapshot()
    return initial


def read_batch(owner: str, batch_id: str) -> PrintBatchOut:
    return _find(owner, batch_id).snapshot()


def read_active_batch(owner: str) -> PrintBatchOut | None:
    with _index_lock:
        now = time.time()
        _sweep(now)
        for data in _stored_batches(now):
            if data.owner == owner:
                batch = _restore_batch(data)
                _batches[batch.batch_id] = batch
        batches = sorted(
            (batch for batch in _batches.values() if batch.owner == owner and batch.mode == MODE_PRINT),
            key=lambda batch: batch.started,
            reverse=True,
        )
    recent = None
    for batch in batches:
        snapshot = batch.snapshot()
        if snapshot.status == "running" and snapshot.stage == "dispatching":
            return snapshot
        if recent is None:
            recent = snapshot
    return recent


def _require_ready(batch: _PrintBatch) -> None:
    if batch.expires_at <= time.time():
        raise HTTPException(404, "批次不存在或已过期。")
    if batch.mode != MODE_PRINT or batch.status != "ready" or len(batch.prepared) != len(batch.ids):
        raise HTTPException(409, "只有已准备好全部 PDF 的打印批次可以执行此操作。")


def start_dispatch(owner: str, batch_id: str, req: PrintDispatchRequest | None = None) -> PrintBatchOut:
    batch = _find(owner, batch_id)
    with batch.dispatch_lock:
        with batch.lock:
            if batch.stage in ("dispatching", "done"):
                return batch._snapshot()
            _require_ready(batch)

        # Capability checks can take time. Leave status reads and export available during the probe.
        plan = None
        block = None
        try:
            plan = lock_a4_channel(**(req.model_dump(exclude_none=True) if req else {}))
        except A4BlockedError as exc:
            block = A4BlockOut(
                reason=exc.message, attempts=exc.detail["attempts"],
                export_action=f"/api/m03/print-batches/{batch_id}/export-pdf",
            )
        with batch.lock:
            _require_ready(batch)
            batch.a4_blocked = block
            if plan is None:
                _checkpoint(batch)
                return batch._snapshot()
            batch.stage, batch.status = "dispatching", "running"
            batch.channels = ("ipp",)
            batch.expires_at = time.time() + _TTL_SECONDS
            try:
                _save_state(batch)
                _workers.submit(copy_context().run, _dispatch, batch, tuple(batch.prepared), plan)
            except (OSError, RuntimeError) as exc:
                batch.stage, batch.status, batch.channels = "preparing", "ready", ()
                _checkpoint(batch)
                log_exc("未能安排打印批次投递", exc)
                raise MustReportError("本批尚未投递，请稍候重试。") from None
            return batch._snapshot()


def export_prepared(owner: str, batch_id: str) -> PrintBatchExportOut:
    batch = _find(owner, batch_id)
    with batch.lock:
        _require_ready(batch)
        if not batch.export_token or not pdf_cache.get(batch.export_token):
            batch.export_token = pdf_cache.put([(pdf.filename, pdf.content) for pdf in batch.prepared])
        return PrintBatchExportOut(download_url=f"/api/m03/pdf/{batch.export_token}")


def _dispatch(batch: _PrintBatch, prepared: tuple[PreparedPdf, ...], plan: DispatchPlan) -> None:
    try:
        for pdf in prepared:
            with batch.lock:
                batch.current_id = pdf.notice_id
                batch.expires_at = time.time() + _TTL_SECONDS
                _save_state(batch)
            outcome = dispatch_prepared(pdf, plan.send)
            with batch.lock:
                batch.dispatch_outcomes[pdf.notice_id] = outcome
                batch.dispatched_count += int(outcome.ok)
                batch.current_id = None
                _save_state(batch)
    except OSError as exc:
        with batch.lock:
            batch.reason = "保存投递进度失败，本批已停止。请先核对打印机出纸情况。"
        log_exc("保存打印批次投递进度失败", exc)
    result = BatchResult(mode=MODE_PRINT, outcomes=list(batch.dispatch_outcomes.values()))
    _persist(batch, result)
    with batch.lock:
        batch.result = batch_response(result)
        batch.status = "complete"
        batch.current_id = None
        batch.prepared.clear()
        batch.expires_at = time.time() + _TTL_SECONDS
        _checkpoint(batch)
