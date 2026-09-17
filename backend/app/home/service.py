"""看板取数：**从各域出口取 9 个计数**（本模块**不重算**任何域的口径）。

- 每项都调**该域自己的出口**（`repository` / `service` / `domain`）⇒ 口径只有一处实现。
- 未实现域（集采 / 差异登记）⇒ **0**（由 `domain.UNIMPLEMENTED` 标注，页面显式说明）。
- ⚠️ 任一域取数失败**不得让整页崩**：该域记 0 并把原因收进 `errors`（**禁静默**）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.period import default_period
from app.home import domain as D

#: 打印/抓取执行记录里的 `run_type`
RUN_FETCH = "fetch"
RUN_PRINT = "print"

#: `default_period(table)` 的**调用点键** —— 付款侧键 ⇒ 默认年月 = **当月**（§9.2）
PERIOD_DEFAULT_KEY = "notice"


def _safe(fn, fallback: int = 0, errors: dict | None = None, key: str = "") -> int:
    """取一项；失败 ⇒ 记 0 并留原因（**不因一个域坏了整页**）。"""
    try:
        return int(fn())
    except Exception as exc:                                  # noqa: BLE001
        if errors is not None:
            errors[key or "?"] = f"{type(exc).__name__}: {exc}"
        return fallback


def gather(s: Session) -> dict:
    """→ `{key: 计数}`（9 项；调用方用 `D.dashboard()` 补 0 与标注）。"""
    errors: dict[str, str] = {}
    out: dict[str, int] = {k: 0 for k in D.todo_keys()}

    # ① 未审批（`MOD-03` 出口）：有效行 = 未剔除、未撤单（§4.2.2 / §4.2.7）
    def nt_unapproved() -> int:
        from app.mod03_notice.domain import APPROVE_STATUS_DONE
        from app.mod03_notice.repository import notices_as_dicts

        return sum(1 for r in notices_as_dicts(s)
                   if str(r.get("approve_status") or "") != APPROVE_STATUS_DONE
                   and not r.get("excluded") and not r.get("i8_revoked"))

    # ② 占位行（`MOD-01` 出口）：仓库名以占位前缀开头
    def placeholder() -> int:
        from app.mod01_projects.models import PLACEHOLDER_PREFIX
        from app.mod01_projects.repository import all_projects

        return sum(1 for p in all_projects(s)
                   if str(p.warehouse_name or "").startswith(PLACEHOLDER_PREFIX))

    # ③ 归属待判定（`MOD-01` 出口）：**壳存在、而壳下还没有具体小微行**（§2.5.1）
    def ownership() -> int:
        from app.mod01_projects.models import TYPE_SHELL, TYPE_SMALL
        from app.mod01_projects.repository import all_projects

        ps = all_projects(s)
        has_small = {p.parent_shell_id for p in ps
                     if p.project_type == TYPE_SMALL and p.parent_shell_id}
        return sum(1 for p in ps if p.project_type == TYPE_SHELL and p.id not in has_small)

    # ④ 计划未匹配（`MOD-04` 出口）：判定走本域的审查引擎，**本页不另算**（§4.3.4）
    def plan_unmatched() -> int:
        from app.mod04_plan import domain as PD
        from app.mod04_plan.repository import list_rows
        from app.mod04_plan.service import notice_amounts

        rows = [PD.row_as_dict(r) if hasattr(PD, "row_as_dict") else _row_dict(r)
                for r in list_rows(s)]
        verdicts = PD.audit_rows(rows, notice_amounts(s))
        return sum(1 for v in verdicts if v != PD.R_MATCHED)

    # ⑤ 抓取执行记录（`MOD-02` 出口）：本月尚未抓取 / 最近一次失败（§3.1.3）
    #    "本月"取**付款侧**默认年月（`default_period` 的调用点键 = `notice` ⇒ 当月，§9.2）
    def fetch_due() -> int:
        from app.mod02_i8.models import RunRecord

        ym = default_period(PERIOD_DEFAULT_KEY)
        n = s.execute(
            select(func.count()).select_from(RunRecord).where(
                RunRecord.run_type == RUN_FETCH,
                RunRecord.status == "success",
                RunRecord.started_at >= datetime.strptime(ym + "-01", "%Y-%m-%d"),
            )
        ).scalar_one_or_none()
        return 0 if int(n or 0) > 0 else 1                 # 有成功记录 ⇒ 不提示

    def run_failures(run_type: str) -> int:
        from app.mod02_i8.repository import recent_fetch_failures

        return len(recent_fetch_failures(s, run_type=run_type, limit=5))

    out["ntUnapproved"] = _safe(nt_unapproved, errors=errors, key="ntUnapproved")
    out["placeholder"] = _safe(placeholder, errors=errors, key="placeholder")
    out["ownership"] = _safe(ownership, errors=errors, key="ownership")
    out["planUnmatched"] = _safe(plan_unmatched, errors=errors, key="planUnmatched")
    out["fetchDue"] = _safe(fetch_due, errors=errors, key="fetchDue")
    out["fetchFail"] = _safe(lambda: run_failures(RUN_FETCH), errors=errors, key="fetchFail")
    out["printFail"] = _safe(lambda: run_failures(RUN_PRINT), errors=errors, key="printFail")
    # ⑥ 未实现域：**显式记 0**（由 `domain.UNIMPLEMENTED` 标注）
    for k in D.UNIMPLEMENTED:
        out[k] = 0

    return {"counts": out, "errors": errors}


def _row_dict(row) -> dict:
    """计划行 → 普通字典（供 `MOD-04` 的纯函数审查用）。"""
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


__all__ = ["RUN_FETCH", "RUN_PRINT", "gather"]
