"""看板取数：**执行记录派生**的三个待办（本模块**不重算**任何业务域的口径）。

⚠️⚠️ **为什么偏偏这三项要由后端算**（⛔ 不能拿"最近 N 条记录"在壳里扫）：
   `run_record` 是**流水表**（2026-09-21 实测：5 天 49 条 ≈ **10 条/天** ⇒ 一个月 ≈ **300 条**），
   而 `GET /api/m02/fetch/records` 是**窗口**（`limit ≤ 200`）⇒ 在窗口里找
   「**本月**有没有成功抓取」**会漏**，而且**漏了不报错**
   （症状 = 看板说"本月未抓" ⇒ 用户照着去重抓一次 ⇒ **白顶一次 i8 的号**）。
   ⇒ 本模块一律用 **SQL 对全表** COUNT / 排序 ⇒ 答案与表有多大**无关**。

口径依据（**唯一主人**）：《说明书》**§3.1.3**（每次抓取留一条执行记录 ⇒ 供看板提示
「本月尚未抓取」「最近一次抓取失败（含**表名与时间**）」）· **§4.6**（每次打印留一条 ⇒「打印投递失败」）。
判据 = `ACC-HOME-TODO-001` 的 `001-04` / `001-05`。

⚠️ **看板另外六项待办不在本模块** —— 未审批 / 归属待判定 / 计划未匹配 / 占位行 / 集采待确认 /
   调整单：它们都是**壳自己已加载行上的筛选**（`V.home`，口径与显示同源、随写动作即时变），
   ⛔ 后端**不另算一份**（两处实现 = 必漂；这正是本模块从 `gather()` 缩到三个的原因）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.period import default_period

#: 执行记录里的 `run_type`（`§3.1.3` 抓取 / `§4.6` 打印）
RUN_FETCH = "fetch"
RUN_PRINT = "print"

#: `default_period(table)` 的**调用点键** —— 付款侧键 ⇒ 默认年月 = **当月**（§9.2）
PERIOD_DEFAULT_KEY = "notice"


def _safe(fn, fallback, errors: dict, key: str):
    """取一项；失败 ⇒ 给 `fallback` 并**留原因**（**不因一个域坏了整页崩**，⛔ 也不许静默吞）。"""
    try:
        return fn()
    except Exception as exc:                                  # noqa: BLE001
        errors[key] = f"{type(exc).__name__}: {exc}"
        return fallback


def run_counts(s: Session) -> dict:
    """→ `{"counts": {...}, "latest": {...}, "errors": {...}}`（**三项**；`errors` 空 = 全部取到）。

    `counts`：`fetchDue`（本月是否**尚未**抓取，0/1）· `fetchFail` · `printFail`（最近有没有失败，0/1）
    `latest`：`fetchFail` / `printFail` 各自**最近那条失败记录**（`null` = 没有）
              —— ⭐ 给壳去说「表名 ＋ 时间」（**怎么说是壳的事**，本模块只给记录，⛔ 不拼字符串）。
    """
    errors: dict[str, str] = {}
    counts = {"fetchDue": 0, "fetchFail": 0, "printFail": 0}
    latest: dict[str, object] = {"fetchFail": None, "printFail": None}

    def fetch_due() -> int:
        """"本月"取**付款侧**默认年月（`default_period` 的调用点键 = `notice` ⇒ 当月，§9.2）。"""
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

    def last_failure(run_type: str):
        from app.mod02_i8.repository import recent_fetch_failures

        rows = recent_fetch_failures(s, run_type=run_type, limit=1)
        return rows[0] if rows else None

    counts["fetchDue"] = _safe(fetch_due, 0, errors, "fetchDue")
    for key, run_type in (("fetchFail", RUN_FETCH), ("printFail", RUN_PRINT)):
        rec = _safe(lambda rt=run_type: last_failure(rt), None, errors, key)
        counts[key] = 1 if rec is not None else 0
        if rec is not None:
            from app.mod02_i8.repository import run_record_out

            latest[key] = run_record_out(rec)

    return {"counts": counts, "latest": latest, "errors": errors}


__all__ = ["PERIOD_DEFAULT_KEY", "RUN_FETCH", "RUN_PRINT", "run_counts"]
