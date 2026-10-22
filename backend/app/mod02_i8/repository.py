"""运行记录仓储（`MOD-02` 技术台账）。

依据：《说明书》§3.1.3（每次抓取留一条执行记录）。⚠️ **不参与任何业务统计**。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.identity import current_operator
from app.mod02_i8.models import RunRecord
from app.mod02_i8.schemas import RunRecordOut


def create_run_record(session: Session, *, run_type: str, target: str, total: int = 0,
                      started_at: datetime | None = None) -> RunRecord:
    """建一条执行记录（`status="running"`，由 `finish_run_record` 收尾）。

    ⚠️⚠️ **`started_at` 必须由调用方给"动作开始前"那一刻** —— 用户 2026-09-20 实测反馈：

    > 「（任务日志里）**耗时也一直是 0 秒**」

    真因**不是精度**，而是：**所有调用点都是"动作做完了才建记录、然后紧接着 finish"**
    （`mod02_i8.router._persist_fetch` / `notice_executors._persist_run` 都如此）
    ⇒ `started_at`（建记录那一刻）与 `finished_at`（下一行 finish）**几乎同刻** ⇒ 差恒 ≈ 0。

    ⇒ 正解 = 调用方在**动作开始前**取一个时刻传进来（各入口的 `t0 = datetime.now()`）。
    ⚠️ 不传 ⇒ 退回"建记录那刻"（= 旧的恒 0 行为）—— **只该给不关心耗时的地方用**。
    ⛔ 别把这里改成 `min(现在, 传入值)` 之类"兜底"：那会把"调用方忘了传"这件事**藏起来**，
       而"忘了传 ⇒ 耗时恒 0"正是这次要根除的那个坑。
    """
    rec = RunRecord(run_type=run_type, target=target, total_count=total, status="running",
                    triggered_by=current_operator())
    if started_at is not None:
        rec.started_at = started_at          # ⚠️ 显式值**覆盖**列默认（列上是 `default=datetime.now`）
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
    """最近的失败记录（供看板「最近一次抓取失败」提示）。

    ⚠️ 「失败」= `status IN ('failed','partial')` —— **部分成功也算失败**（`TAIL-46` 的三态里
       「已投递（未核实）」不并进"失败"，但本函数的用途是**提示有人要去看一眼**，故收进来）。
    """
    from sqlalchemy import select

    return list(
        session.execute(
            select(RunRecord)
            .where(RunRecord.run_type == run_type, RunRecord.status.in_(("failed", "partial")))
            .order_by(RunRecord.id.desc())
            .limit(limit)
        ).scalars().all()
    )


def run_record_out(r: RunRecord) -> RunRecordOut:
    """执行记录 → 出参（**唯一出口**）。

    ⚠️ 2026-09-21 提取：原先这段换算**内联在 `mod02_i8/router.py::fetch_records` 里**，
       看板记账端点要用同一形状 ⇒ 抽成一份（否则两处各写一遍，字段一改必漂）。
    """
    return RunRecordOut(
        id=r.id,
        run_type=r.run_type,
        target=r.target,
        status=r.status,
        success_count=r.success_count,
        fail_count=r.fail_count,
        error_message=r.error_message,
        started_at=r.started_at.isoformat(timespec="seconds"),
        finished_at=r.finished_at.isoformat(timespec="seconds") if r.finished_at else None,
        triggered_by=r.triggered_by,
        duration_seconds=((r.finished_at - r.started_at).total_seconds()
                          if r.finished_at and r.finished_at >= r.started_at else None),
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
    started_at: datetime | None = None,
) -> RunRecord:
    """**一步写一条**已完成的执行记录（§3.1.3）—— 供"一次抓取一条"的调用方直接用。

    ⚠️ 与 `create_run_record` / `finish_run_record` 的分工：那两个给**长任务**（先建 running、
    结束再补结果）；本函数给**一次成型的短任务**，避免调用方自己拼状态机。

    ⚠️⚠️ **`started_at` 与 `create_run_record` 同口径**：必须由调用方给"动作开始前"那一刻。
       不传 ⇒ `started_at`（列默认 `datetime.now`）与这里的 `finished_at` **同刻** ⇒ **耗时恒 0**。

    ⚠️⚠️⚠️ 本函数是**第二个"写执行记录"的出口**（`mod07_setl` / `mod08_inv` 的抓取走这里）——
       **"耗时"这一个口径在两处实现**。2026-09-20 修"耗时恒 0"时，第一轮**只改了
       `create_run_record`**、把这里漏了 ⇒ 收发结存 / 库存单据那两条**照旧恒 0**。
       这正是本项目最贵的一类错（同一个口径两处实现，改一处 = 静默分叉）。
       ⇒ 守卫已扩到**两个出口都查**（见 `tests/test_run_record_timing.py`）。
    """
    rec = RunRecord(
        run_type=run_type, target=target, status=status,
        success_count=success_count, fail_count=fail_count, total_count=total_count,
        error_message=error_message, detail=detail or {},
        triggered_by=operator or current_operator(), finished_at=datetime.now(),
    )
    if started_at is not None:
        rec.started_at = started_at          # ⚠️ 显式值**覆盖**列默认（列上是 `default=datetime.now`）
    session.add(rec)
    session.flush()
    return rec


__all__ = ["create_run_record", "finish_run_record", "recent_fetch_failures", "run_record_out",
           "save_run_record"]


def recent_records(session: Session, *, run_type: str, limit: int) -> list[RunRecord]:
    """按类型取最近执行记录；业务标记和待办解释仍由调用域决定。"""
    from sqlalchemy import select
    return list(session.execute(select(RunRecord).where(
        RunRecord.run_type == run_type
    ).order_by(RunRecord.id.desc()).limit(limit)).scalars().all())
