"""付款计划**页面交互内核**（`MOD-04` · **纯函数**）—— 筛选栏 · 行内改列 · 再次匹配 · 删除 · 生效窗口按钮态。

依据：《说明书》§4.3.2（业务节律 / 生效窗口）· §4.3.3（数据入口与可手改列）· §4.3.4（审查 6 种 + 筛选两档）
      · §4.3.6（历史保留 / 列表内删除）· §4.3.7（10 号截止）。

⚠️ **与 `domain.py` 的分工**（2026-09-15 拆分，工程纪律 >400 行须拆）：
   · `domain.py` = **审查引擎与口径基础件**（判定 6 种 / 项目列匹配 / 生效窗口基础件）；
   · 本文件 = **页面交互内核**，一切判定**调用 `domain` 的出口**，**不另写一套**（否则副本必然漂移）。
   ⚠️ 两处**不得各留一份定义**：`can_edit_doc` / `re_audit` / `bucket` / `in_effective_window` 只在 `domain.py`。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import MustReportError
from app.core.period import ALL_MODES, MODE_ALL, MODE_MONTH, MODE_SPAN, MODE_YEAR
from app.mod04_plan.domain import (
    BUCKET_ALL,
    EDITABLE_COLUMNS,
    WINDOW_START_DAY,
    bucket,
    can_edit_doc,
    in_effective_window,
    re_audit,
    window_label,
)

# ---------------------------------------------------------------- 筛选栏（§4.3.3 / §4.3.4）
#
# 三项筛选（= 原型 `.fbar` 的三项）：**单据年月 / 项目（可多选）/ 审查结果**。
# ⚠️ 年月**走全站统一的核算年月控件**（`core.period.PERIOD_COMPONENT`）—— **不新造控件**。

FILTER_FIELDS: tuple[str, ...] = ("year_month", "project_ids", "audit_bucket")
PERIOD_SCOPE = "plan"                                   # 调用点声明（抓取 / 导入只给「月」）
_MODE_LABELS = {MODE_MONTH: "月", MODE_SPAN: "跨月", MODE_YEAR: "年", MODE_ALL: "全部"}
FILTER_PERIOD_MODES: tuple[str, ...] = tuple(_MODE_LABELS[m] for m in ALL_MODES)


def period_filter_modes() -> tuple[str, ...]:
    """筛选栏「单据年月」给用户看的那几个模式（= 统一控件的四种模式，一名不多）。"""
    return FILTER_PERIOD_MODES


def default_selection(today=None) -> dict:
    """筛选栏**默认值**（§9.2）：年月 = **付款侧默认当月**；项目 = 全部；审查结果 = 全部。

    ⚠️ 复用 `domain.default_plan_filters` 的年月出口，**不另写一套默认值**。
    """
    from app.mod04_plan.domain import default_plan_filters

    return {
        "year_month": default_plan_filters(today)["year_month"],
        "project_ids": [],
        "audit_bucket": BUCKET_ALL,
    }


def period_filter_is_shared_control() -> bool:
    """年月筛选确实**复用全站唯一的时间控件**（而不是本页自造一个下拉）。"""
    from app.core.period import PERIOD_COMPONENT

    return (
        PERIOD_COMPONENT["id"] == "acc-period"
        and tuple(PERIOD_COMPONENT["modes"]) == (MODE_MONTH, MODE_SPAN, MODE_YEAR, MODE_ALL)
        and FILTER_PERIOD_MODES == ("月", "跨月", "年", "全部")
    )


def period_months(value: str) -> tuple[str, str] | None:
    """时间范围取值 → 闭区间 `(起月, 止月)`（`YYYY-MM`）；**「全部」⇒ `None`**。

    ⚠️ 计划表**按月归档**（`year_month` 是真实且带索引的列）⇒ 本表按**月**做闭区间比较；
       取值解析仍走 `core.period`（**统一控件、不另造一套取值语法**）。
    """
    from app.core.period import MODE_ALL, MODE_MONTH, MODE_SPAN, MODE_YEAR, parse_period

    mode, v = parse_period(value or "")
    if mode == MODE_ALL:
        return None
    if mode == MODE_MONTH:
        return v, v
    if mode == MODE_YEAR:
        return f"{v}-01", f"{v}-12"
    if mode == MODE_SPAN:
        a, b = v.split("~")
        return a, b
    return None


def filter_plan_rows(
    rows: list[dict],
    results: dict,
    *,
    year_month: str = "",
    project_ids: tuple | list = (),
    audit_bucket: str = BUCKET_ALL,
    project_key=None,
) -> list[dict]:
    """筛选（**即时生效**）：① 单据年月 ② 项目（多选）③ 审查结果（**两档归并**）。

    - 年月 = **闭区间**（单月 / 跨月 / 整年 / 全部走同一个解析出口）
    - 项目 = 按 `project_key(row)` 归并后**多选**命中；不选 = 全部
    - 审查结果 = 传 `BUCKET_ALL` 不过滤；否则按 `bucket(判定)` 粗筛
    """
    bounds = period_months(year_month)
    keys = {str(k) for k in (project_ids or ())}
    out: list[dict] = []
    for row in rows:
        ym = str(row.get("year_month") or "")
        if bounds is not None and not (bounds[0] <= ym <= bounds[1]):
            continue
        if keys and project_key is not None and str(project_key(row) or "") not in keys:
            continue
        if audit_bucket and audit_bucket != BUCKET_ALL:
            if bucket(str(results.get(row.get("id")) or "")) != audit_bucket:
                continue
        out.append(row)
    return out


# ---------------------------------------------------------------- 行内改列（§4.3.3）

DOC_COLUMN = "doc_no"


@dataclass
class InlineEdit:
    """行内改列的落库结果。⚠️ `trace` **恒为 `None`** —— 这几处**不留痕**（不属 §9.3 留痕范围）。"""

    row_id: int
    column: str
    value: str
    persisted: bool = True
    trace: object | None = None


def inline_editable_columns(result: str) -> tuple[str, ...]:
    """该行**可手改**的列：付款时间 / 付款方式 / 备注；**单据号只对「未匹配」行开放**（§4.3.3）。"""
    if can_edit_doc(result):
        return (DOC_COLUMN,) + EDITABLE_COLUMNS
    return EDITABLE_COLUMNS


def inline_edit(*, row_id: int, column: str, value: object, allowed) -> InlineEdit:
    """行内改列（§4.3.3）：**立刻落库、不被导入覆盖、不留痕**。

    可改集合由调用点用 `inline_editable_columns(result)` 给出 —— 不在集合里的一律**显式拒绝**。
    """
    allowed = tuple(allowed or ())
    if column not in allowed:
        raise MustReportError(
            f"「{column}」不在本行可手改的列里（可改：{'、'.join(allowed) if allowed else '无'}）"
        )
    return InlineEdit(row_id=int(row_id), column=column, value=str(value if value is not None else "").strip())


# ---------------------------------------------------------------- 再次匹配（§4.3.3）


@dataclass
class ReMatchResult:
    notice_id: int
    doc_no: str
    result: str


def re_match(row: dict, notices_by_doc: dict, rows_for_dup: list[dict] | None = None) -> ReMatchResult:
    """「再次匹配」= 按**当前单据号**重跑**同一个审查引擎**（§4.3.3）—— 不另写一套判定。"""
    result = re_audit(row, notices_by_doc, rows_for_dup)
    return ReMatchResult(
        notice_id=int(row.get("id") or 0),
        doc_no=str(row.get("doc_no") or "").strip(),
        result=result,
    )


# ---------------------------------------------------------------- 列表内删除（§4.3.6）

# ⚠️ 删除**只影响付款计划表** —— 付款通知书与欠款统计一点不动
AFFECTED_TABLES: tuple[str, ...] = ("plan_row",)


@dataclass
class DeleteImpact:
    """删除影响范围的一行（§4.3.6：行号 / 所属年月 / 审查结果）。"""

    row_id: int
    seq: int
    year_month: str
    result: str


def delete_impact(rows: list[dict], targets, results: dict) -> list[DeleteImpact]:
    """删除前**列出影响范围**（§4.3.6）—— 逐行删除与批量删除共用同一出口。"""
    want = {int(t) for t in (targets or ())}
    out: list[DeleteImpact] = []
    for seq, row in enumerate(rows, start=1):
        rid = int(row.get("id") or 0)
        if rid in want:
            out.append(
                DeleteImpact(
                    row_id=rid,
                    seq=seq,
                    year_month=str(row.get("year_month") or ""),
                    result=str(results.get(rid) or ""),
                )
            )
    return out


def delete_rows(rows: list[dict], targets, picked, *, confirmed: bool) -> tuple[list[dict], set]:
    """逐行 / 批量删除（§4.3.6）：**必须先列出影响范围并确认**；只删该行；**勾选集合同步收敛**。

    返回 `(剩余行, 收敛后的勾选集合)`。⚠️ **不触碰**付款通知书与欠款统计（`AFFECTED_TABLES`）。
    """
    if not confirmed:
        raise MustReportError("删除前必须先列出影响范围并确认（§4.3.6）")
    want = {int(t) for t in (targets or ())}
    kept = [r for r in rows if int(r.get("id") or 0) not in want]
    return kept, {int(x) for x in (picked or set())} - want


# ---------------------------------------------------------------- 生效窗口按钮态（§4.3.2 / §4.3.7）


def window_button(day_of_month: int) -> dict:
    """「按付款计划勾选」按钮的**可用性**（§4.3.2 / §4.3.7）：窗口外**先禁用**，不是点了才拦。"""
    day = int(day_of_month)
    if in_effective_window(day):
        return {"enabled": True, "label": window_label(day), "reason": ""}
    return {
        "enabled": False,
        "label": "",
        "reason": (
            f"付款计划每月 {WINDOW_START_DAY} 号起生效、当月底结束 —— 今天是 {day} 号，尚未进入生效窗口"
        ),
    }


__all__ = [
    "FILTER_FIELDS", "PERIOD_SCOPE", "FILTER_PERIOD_MODES",
    "period_filter_modes", "period_filter_is_shared_control", "period_months", "filter_plan_rows",
    "default_selection",
    "DOC_COLUMN", "InlineEdit", "inline_editable_columns", "inline_edit",
    "ReMatchResult", "re_match",
    "AFFECTED_TABLES", "DeleteImpact", "delete_impact", "delete_rows", "window_button",
]
