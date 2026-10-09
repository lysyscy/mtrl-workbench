"""付款通知书**列表的数据组装**（§4.2）—— **服务端渲染页与列表 API 共用的唯一出口**。

⭐ 2026-09-19（`§19` 批 4 · **S4① 数据侧归位**）：本模块整体**从 `notice_page.py` 搬来** ——
   那是**服务端渲染页**（随批 4 的删页一起消失），而 `GET /api/m03/notice-list`（**存活**，
   `notice_router.py`）在用 `build_page_data` ⇒ 删页**不能连数据侧一起删**
   （⛔ 会把新壳的数据源打断）。本次是**纯搬家、行为一字未改**。

⭐ **本模块只产数据**（列定义 / 每行的显示值 / 合计行 / 一页所需的一切），**不产任何 HTML**：
   「操作」列那类按钮 / 表单 HTML 属**页面**的事，由页面**渲染时**注入（页面已随批 4 删除）。

⚠️ 默认年月的口径键 `PERIOD_DEFAULT_KEY` 也住这里（`notice_http.notice_filters` 在用）。
"""

from __future__ import annotations

from app.core.money import to_money
from app.core.period import default_period
from app.mod03_notice.list_view import (
    NoticeFilters,
    build_rows,
    count_rows,
    filter_rows,
)
from app.mod03_notice.page import sort_rows
from app.mod05_flow.domain import PAY_STATUS_PAID

# ⚠️ 默认年月的**口径键** —— 必须是 `period.default_period()` 认得的付款侧键（"notice"），
#    不是控件标识 "nt"。§9.2：付款域类表默认 = **当月**（此前误传 "nt" ⇒ 落到"上月"分支）。
PERIOD_DEFAULT_KEY = "notice"


def _amt(value) -> str:
    """列表里的金额：**千分位 ＋ 2 位小数**（零值显示 `0.00`）。

    ⚠️ 与打印件的「零值金额格留空」（§4.2.5 / 001-10）**故意不同** —— 列表上留空会看不出"是不是没数"。
    """
    try:
        return f"{to_money(value):,.2f}"
    except Exception:  # noqa: BLE001
        return str(value or "")


def columns() -> list[dict]:
    """18 列（排序属性对齐原型：勾选 / 操作**不可排**）。"""
    def col(key, label, *, sortable=True, cls="", vsep=False, width=""):
        return {"key": key, "label": label, "sortable": sortable, "cls": cls, "vsep": vsep, "width": width}

    return [
        col("pick", "", sortable=False, cls="ctr", width="34px"),
        col("doc_date", "单据日期", width="96px"),
        col("bill_no", "单据编码", width="126px"),
        col("project_display", "付款项目"),
        col("category_label", "分类", width="78px"),
        col("bill_name", "单据名称"),
        col("biz_type", "业务类型"),
        col("payee", "收款单位"),
        col("jc_supplier", "集采实际供应商", width="152px"),
        col("input_by", "录入人", width="78px"),
        col("amount_approved_text", "审批金额", cls="num", width="112px"),
        col("pay_amount_text", "付款金额 ✎", cls="num", width="112px"),
        col("amount_paid_text", "已付金额", cls="num", width="106px"),
        col("stat_settle_text", "统计结算金额 ✎", cls="num", width="112px"),
        col("stat_paid_text", "统计付款金额 ✎", cls="num", width="112px"),
        col("approve_status", "审批状态", width="74px"),
        col("pay_status", "付款状态", width="82px"),
        col("actions", "操作", sortable=False, width="152px"),
    ]


def _row_dict(row) -> dict:
    """一行 → 各列的**显示值**（调用方只负责摆位置）。

    ⚠️ **不含「操作」列**：那一格是按钮 / 表单 HTML ⇒ 由页面渲染时注入（本模块不产 HTML）。
    """
    from app.mod03_notice.notice_actions import category_name

    return {
        "notice_id": row.notice_id,
        "doc_date": row.doc_date,
        "bill_no": row.bill_no,
        "project_display": row.project_display or row.project_name,
        "category_label": category_name(row.category),
        "bill_name": row.bill_name,
        "biz_type": row.biz_type,
        "payee": row.payee,
        # ⭐ 2026-09-19（`M5-5`）：不再是空占位 —— 该字段已随 M5 落地（人工录入 / 匹配确认，不受导入覆盖）
        # ⚠️ **直取、不得 `getattr(..., "")` 兜空**：兜空会把「`NoticeRow` 漏装该字段」变成**静默空串** ——
        #    症状是页面上供应商恒空、点「采用」反而把已匹配上的值清空（漏了也不报错，最难查）。
        "jc_supplier": str(row.jc_supplier or ""),
        "input_by": row.input_by,
        "amount_approved_text": _amt(row.amount_approved),
        "pay_amount_text": _amt(row.pay_amount),
        "amount_paid_text": _amt(row.amount_paid),
        "stat_settle_text": _amt(row.stat_settle),
        "stat_paid_text": _amt(row.stat_paid),
        "approve_status": row.approve_status,
        "pay_status": "已付清" if row.pay_status == PAY_STATUS_PAID else "未付清",
        "_row": row,
    }


def summary_row(data: dict) -> dict:
    """表内合计行（用户 2026-09-13 口径「**求和一律落在表内**」· 设计规则 `R7`）—— **只算非剔除行**。

    5 个数值列 = 审批金额 / 付款金额 / 已付金额 / 统计结算金额 / 统计付款金额
    （列序与原型 `sumRowOf(NT_THEAD, …)` 给的下标 `10…14` **一一对应**）。

    ⚠️ **口径与欠款一致**：剔除行**不计入**（原型 `sumRows = list.filter(ntLive)`）。
    ⚠️ 切到「分类 = 剔除」时该视图**全是剔除行** ⇒ **不给合计行**（不给一排 0，免得看着像坏了）。
    ⚠️ 首格写「合计」（与 `m08` 同款）；排序时该行由 `data-pin="1"` **钉在表尾**。

    ⚠️⚠️ **2026-09-20 修**：判据改成 `NoticeRow.is_live`（**唯一出口**）。
       本函数原先手写 `not excluded` —— 比 `ntLive` **少算**了「**撤单但有牵涉**」那一档
       （§4.2.7：i8 侧单据被删、但本系统里还挂着付款流水 / 集采关联 ⇒ 不许静默丢账，仍要计入）。
       注释里写着"与原型的 `ntLive` 一致"，实现却不是 ⇒ **这正是"同一事实多处写"那类静默错**：
       合计行会**悄悄少几笔**，而且只在"有撤单牵涉行"时才对不上，平时看不出来。
    """
    cols = columns()
    live = [
        rec["_row"] for rec in (data.get("rows") or ())
        if rec.get("_row") is not None and bool(rec["_row"].is_live)
    ]
    if not live:
        return {}
    out: dict[str, str] = {c["key"]: "" for c in cols}
    out[cols[0]["key"]] = "合计"
    for key, attr in (
        ("amount_approved_text", "amount_approved"),
        ("pay_amount_text", "pay_amount"),
        ("amount_paid_text", "amount_paid"),
        ("stat_settle_text", "stat_settle"),
        ("stat_paid_text", "stat_paid"),
    ):
        out[key] = _amt(sum((getattr(r, attr) or 0) for r in live))
    return out


def build_page_data(
    session,
    *,
    filters: NoticeFilters | None = None,
    sort_col: str = "",
    sort_dir: int = 0,
    flows_of=None,
    links_of=None,
    traces_of=None,
    draft: dict | None = None,
    draft_error: str = "",
    plan_ym: str = "",
    plan_docs=None,
) -> dict:
    """组装一页所需的一切（列表页与 API 共用同一个出口）。

    `draft` —— 表内草稿行（§4.2.6 手动新增 / 编辑）：`None` = 不显示；`{}` = 新增；带 `id` = 编辑该行。
    `plan_docs` + `plan_ym` —— 「按本月计划勾选」（§4.3.5）：计划月里出现的**单据号集合**；
       命中的行在本页**预勾选**，并回报"因项目筛选被跳过几条"。
    """
    from app.core.identity import current_operator
    from app.mod03_notice.notice_manual_actions import manual_project_options

    f = filters or NoticeFilters(period=default_period(PERIOD_DEFAULT_KEY))
    rows = build_rows(session, flows_of=flows_of, links_of=links_of, traces_of=traces_of)
    shown = filter_rows(rows, f, project_key=lambda r: r.ownership_id)
    counters = count_rows(rows, shown)

    picked: list[int] = []
    plan_report = ""
    if plan_ym:
        docs = {str(d or "").strip() for d in (plan_docs or ()) if str(d or "").strip()}
        shown_ids = {r.notice_id for r in shown}
        picked = [r.notice_id for r in shown if str(r.bill_no or "").strip() in docs]
        skipped = [
            r for r in rows
            if str(r.bill_no or "").strip() in docs and r.notice_id not in shown_ids
        ]
        plan_report = (
            f"已按 {plan_ym} 的付款计划勾选 {len(picked)} 条"
            f"（计划里出现 {len(docs)} 个单据号；视图参数已放宽到「全部月份 + 未付清」）；"
            f"**项目筛选一律不动** —— 另有 {len(skipped)} 条被当前项目筛选挡掉、本次跳过"
        )

    records = [_row_dict(r) for r in shown]
    if sort_col:
        # ⚠️ `page.sort_rows(rows, *, column, direction)` 用 `_cell()` 取值、
        #    `_sort_key()` 排序 —— 后者**已处理千分位**（`Decimal(text.replace(",", ""))`），
        #    所以显示值 "10,000.00" 会按**数值**排，不必另给排序键。
        records = sort_rows(records, column=sort_col, direction=sort_dir)

    picked_set = set(picked)
    for rec in records:
        rec["_picked"] = rec["notice_id"] in picked_set

    projects = _all_projects(session)
    return {
        "filters": f,
        "rows": records,
        "columns": columns(),
        "counters": counters,
        "project_options": _project_options(projects, rows),
        "manual_project_options": manual_project_options(projects),
        "operator": current_operator(),
        "draft": draft,
        "draft_error": draft_error,
        "has_manual_rows": any(r.is_manual for r in rows),
        "plan_ym": plan_ym,
        "plan_report": plan_report,
        "picked_count": len(picked),
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        "period_label": f.period or "全部",
        "exclude_view": f.category == "exclude",
    }


def _all_projects(session) -> list:
    """全部已建档项目（空表也返回空列表，**不假装有数据**）。

    ⭐ 取数经 `MOD-01` 的**包间出口**（`TAIL-218` 批 2）—— ⛔ 别去 `import …repository`（规则 C 守卫）。
    """
    from app.mod01_projects import service as P1S

    try:
        return list(P1S.list_projects(session))
    except Exception:  # noqa: BLE001
        return []


def _project_options(projects, rows) -> list[dict]:
    """项目多选的可选项：**取自己在列表里出现过的归属**（空表也给出全部已建档项目）。"""
    if not projects:
        seen: dict[str, str] = {}
        for r in rows:
            if r.ownership_id and (r.project_display or r.project_name):
                seen[str(r.ownership_id)] = r.project_display or r.project_name
        return [{"key": k, "label": v} for k, v in sorted(seen.items())]
    return [
        {"key": str(p.id), "label": getattr(p, "disp", "") or getattr(p, "warehouse_name", "") or f"#{p.id}"}
        for p in projects
    ]


__all__ = [
    "PERIOD_DEFAULT_KEY", "columns", "summary_row", "build_page_data",
]
