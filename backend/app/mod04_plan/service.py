"""`MOD-04` 组装层 —— 拉数据 → 跑审查 → 筛选 → 排序 → 视图数据（**给页面与 API 共用**）。

⚠️ **不重写任何判定**：审查走 `domain.audit_rows`、筛选走 `plan_ui.filter_plan_rows`、
   排序走 `page.sort_rows`、窗口态走 `plan_ui.window_button` —— 本文件只做**取数与装配**。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.page import sort_rows
from app.mod04_plan import repository as repo
from app.mod04_plan.domain import (
    ALL_RESULTS,
    BUCKET_ALL,
    NoticeAmounts,
    audit_rows,
    bucket,
)
from app.mod04_plan.plan_ui import (
    FILTER_FIELDS,
    default_selection,
    filter_plan_rows,
    window_button,
)
from app.mod05_flow import domain as flow_domain
from app.mod05_flow.models import PaymentFlow

# 界面上的「已付款金额 / 剩余付款金额」两列（由命中的通知书派生，§4.3.3）
DERIVED_COLUMNS: tuple[str, ...] = ("paid_amount", "unpaid_amount")

# 合计行求和的列（§4.3.1 表内合计；原型 `sumRowOf` 只求这两个有业务含义的金额列）
SUM_COLUMNS: tuple[str, ...] = ("flow_amount", "planned_amount")


def notice_amounts(s: Session) -> dict[str, NoticeAmounts]:
    """`单据号 → 通知书比对视图`（审批金额 ＋ 已付金额＝**流水汇总**，§4.3.4 / §4.4.2）。

    ⚠️ 已付金额只算**生效流水**（`flow_domain.effective_total`，同「已付金额」的唯一定义）。
    两次查询各一次（**不是 N+1**）。
    """
    notices = list(s.execute(select(PaymentNotice)).scalars().all())
    grouped: dict[int | None, list[dict]] = {}
    for f in s.execute(select(PaymentFlow)).scalars().all():
        grouped.setdefault(f.notice_id, []).append({"amount": f.amount, "status": f.status})

    out: dict[str, NoticeAmounts] = {}
    for n in notices:
        doc = str(n.bill_no or "").strip()
        if not doc:
            continue
        out[doc] = NoticeAmounts(
            doc_no=doc,
            approved=to_money(n.amount_approved),
            paid=flow_domain.effective_total(grouped.get(n.id, [])),
        )
    return out


def project_index(s: Session) -> dict[int, Project]:
    return {p.id: p for p in s.execute(select(Project)).scalars().all()}


def project_key(p: Project | None) -> str:
    """项目归并键 = **仓库名**（§2.7.4）；缺失时退化为 `#id`（**不猜**）。"""
    if p is None:
        return ""
    return p.warehouse_name or f"#{p.id}"


def project_label(p: Project | None) -> str:
    if p is None:
        return ""
    return p.disp or p.warehouse_name or p.name_full or f"#{p.id}"


def row_to_dict(r, projects: dict[int, Project], results: dict[int, str], notices: dict[str, NoticeAmounts]) -> dict:
    """一行计划 → 界面字典（含派生两列）。"""
    p = projects.get(r.project_id) if r.project_id else None
    hit = notices.get(str(r.doc_no or "").strip())
    return {
        "id": r.id,
        "year_month": r.year_month,
        "project_input": r.project_input,
        "project_key": project_key(p),
        "project_display": project_label(p),
        "match_status": r.match_status,
        "match_candidates": r.match_candidates,
        "doc_no": r.doc_no,
        "flow_amount": f"{to_money(r.flow_amount):.2f}",
        "paid_amount": f"{hit.paid:.2f}" if hit else "",
        "unpaid_amount": f"{hit.unpaid:.2f}" if hit else "",
        "planned_amount": f"{to_money(r.planned_amount):.2f}",
        "pay_date": r.pay_date,
        "pay_method": r.pay_method,
        "remark": r.remark,
        "audit_result": results.get(r.id, ""),
        "audit_bucket": bucket(results.get(r.id, "")),
        "forced_through": bool(r.forced_through),
        "forced_remark": r.forced_remark,
        # 手动行（§4.3 ＋ 用户 2026-09-16）：不被导入清理，但**一样被审查**（审查不看来源）
        "is_manual": bool(getattr(r, "is_manual", False)),
    }


def build_page_data(
    s: Session,
    *,
    year_month: str = "",
    project_ids: tuple | list = (),
    audit_bucket: str = BUCKET_ALL,
    sort_col: str = "",
    sort_dir: int = 0,
    draft: str = "",
    today: date | None = None,
) -> dict:
    """页面/接口**共用**的一份视图数据（筛选与排序**一律调已验收的出口**）。

    `draft` —— 草稿行**令牌**（`new` = 新增 / `<id>` = 编辑该**手动**行）：**在本出口内解析**
    （用调用方注入的 session），这样"离线自检注入假会话"能覆盖到草稿行这条路径。
    ⚠️ **手动行与导入行走同一条审查链路**（审查按行实时派生，`audit_rows` 不看来源）。
    """
    today = today or date.today()
    projects = project_index(s)
    notices = notice_amounts(s)
    draft_data, draft_error = _resolve_draft(s, draft)

    raw = repo.list_rows(s)
    as_dicts = [
        {"id": r.id, "year_month": r.year_month, "doc_no": r.doc_no,
         "flow_amount": to_money(r.flow_amount), "planned_amount": to_money(r.planned_amount)}
        for r in raw
    ]
    # 项目归并键：**一次算好**（避免在筛选谓词里回查 = 伪 N+1）
    key_by_row: dict[int, str] = {
        r.id: project_key(projects.get(r.project_id) if r.project_id else None) for r in raw
    }

    results_list = audit_rows(as_dicts, notices)
    results = {r["id"]: res for r, res in zip(as_dicts, results_list)}

    visible_ids = {
        r["id"]
        for r in filter_plan_rows(
            as_dicts,
            results,
            year_month=year_month,
            project_ids=project_ids,
            audit_bucket=audit_bucket,
            project_key=lambda r: key_by_row.get(r["id"], ""),
        )
    }

    rows = [row_to_dict(r, projects, results, notices) for r in raw if r.id in visible_ids]
    rows = sort_rows(rows, column=sort_col, direction=sort_dir) if sort_col else rows

    # 指标区：6 种判定在**当前筛选结果**下的条数（原型 m04 的 6 张卡）
    counts = {r: 0 for r in ALL_RESULTS}
    for one in rows:
        counts[one["audit_result"]] = counts.get(one["audit_result"], 0) + 1

    summary = {
        "doc_no": "合计",
        **{c: f"{sum((Decimal(r[c] or 0) for r in rows), Decimal('0')):.2f}" for c in SUM_COLUMNS},
    }

    # 项目候选 = 计划行里**能匹配到**的项目（键 = 仓库名；去重、含归档）
    keys: list[str] = []
    for r in raw:
        k = project_key(projects.get(r.project_id) if r.project_id else None)
        if k and k not in keys:
            keys.append(k)

    return {
        "year_month": year_month,
        "project_ids": list(project_ids or ()),
        "audit_bucket": audit_bucket,
        "rows": rows,
        "counts": counts,
        "summary": summary,
        "total_in_month": len([r for r in raw if not year_month or r.year_month == year_month]),
        "project_options": [
            {"key": k, "label": project_label(_project_by_key(projects, k))} for k in keys
        ],
        # 草稿行的项目候选 = **全部已建档项目**（键 = 档案行 id）；上表是"计划里出现过的项目"（键 = 仓库名）
        "manual_project_options": [
            {"key": str(p.id), "label": project_label(p)} for p in projects.values()
        ],
        "draft": draft_data,
        "draft_error": draft_error,
        "window": window_button(today.day),
        "filter_fields": list(FILTER_FIELDS),
        "sort_col": sort_col,
        "sort_dir": sort_dir,
    }


def _project_by_key(projects: dict[int, Project], key: str) -> Project | None:
    for p in projects.values():
        if project_key(p) == key:
            return p
    return None


def default_filters(today: date | None = None) -> dict:
    """默认筛选：**年月 = 北京时间当月**（§9.2：付款侧默认当月）· 其余为「全部」。"""
    return default_selection(today)


def _resolve_draft(s: Session, token: str) -> tuple[dict | None, str]:
    """把草稿令牌解析成草稿行数据（`None` = 不显示草稿行）。

    ⚠️ **只认字面量 `new`** —— 不要把 `"1"` 也当"新增"：那会让**编辑行号 1** 变成"新增一行"。
    """
    from app.mod04_plan.plan_manual import is_manual_row

    text = str(token or "").strip()
    if not text:
        return None, ""
    if text == "new":
        return {}, ""
    if not text.isdigit():
        return None, f"草稿参数非法：{text}"
    row = repo.get_row(s, int(text))
    if row is None:
        return None, f"要编辑的计划行 {text} 不存在"
    if not is_manual_row(row):
        return None, (
            "编辑只对**手动新增的计划行**开放 —— 导入行属项目端报来的原始数据；要改请重导（§4.3.3）"
        )
    return draft_from_row(row), ""


def draft_from_row(row) -> dict:
    """编辑某**手动行** ⇒ 草稿行的初值（各列的显示值）。"""
    return {
        "id": row.id,
        "year_month": str(row.year_month or ""),
        "project_id": row.project_id,
        "doc_no": str(row.doc_no or ""),
        "flow_amount": f"{to_money(row.flow_amount):.2f}",
        "planned_amount": f"{to_money(row.planned_amount):.2f}",
        "pay_date": str(row.pay_date or ""),
        "pay_method": str(row.pay_method or ""),
        "remark": str(row.remark or ""),
    }


__all__ = [
    "DERIVED_COLUMNS", "SUM_COLUMNS",
    "notice_amounts", "project_index", "project_key", "project_label", "row_to_dict",
    "build_page_data", "default_filters", "draft_from_row",
]
