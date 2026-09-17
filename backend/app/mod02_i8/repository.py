"""运行记录仓储（`MOD-02` 技术台账）。

依据：《说明书》§3.1.3（每次抓取留一条执行记录）。⚠️ **不参与任何业务统计**。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.mod02_i8.models import RunRecord


def create_run_record(session: Session, *, run_type: str, target: str, total: int = 0) -> RunRecord:
    rec = RunRecord(run_type=run_type, target=target, total_count=total, status="running")
    session.add(rec)
    session.flush()
    return rec


def finish_run_record(
    session: Session,
    rec: RunRecord,
    *,
    status: str,
    success: int,
    fail: int,
    detail: dict,
    error_message: str = "",
) -> None:
    rec.status = status
    rec.success_count = success
    rec.fail_count = fail
    rec.detail = detail
    rec.error_message = error_message
    rec.finished_at = datetime.now()
    session.flush()


def recent_fetch_failures(session: Session, *, run_type: str = "fetch", limit: int = 5) -> list[RunRecord]:
    """最近的失败记录（供看板「最近一次抓取失败」提示）。"""
    from sqlalchemy import select

    return list(
        session.execute(
            select(RunRecord)
            .where(RunRecord.run_type == run_type, RunRecord.status.in_(("failed", "partial")))
            .order_by(RunRecord.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def save_run_record(
    session: Session,
    *,
    run_type: str,
    target: str,
    status: str,
    success_count: int = 0,
    fail_count: int = 0,
    total_count: int = 0,
    error_message: str = "",
    detail: dict | None = None,
    operator: str = "",
) -> RunRecord:
    """**一步写一条**已完成的执行记录（§3.1.3）—— 供"一次抓取一条"的调用方直接用。

    ⚠️ 与 `create_run_record` / `finish_run_record` 的分工：那两个给**长任务**（先建 running、
    结束再补结果）；本函数给**一次成型的短任务**，避免调用方自己拼状态机。
    """
    rec = RunRecord(
        run_type=run_type, target=target, status=status,
        success_count=success_count, fail_count=fail_count, total_count=total_count,
        error_message=error_message, detail=detail or {},
        triggered_by=operator or "manual", finished_at=datetime.now(),
    )
    session.add(rec)
    session.flush()
    return rec


__all__ = ["create_run_record", "finish_run_record", "recent_fetch_failures", "save_run_record"]
