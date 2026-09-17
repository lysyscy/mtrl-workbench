"""付款通知书列表页（§4.2 · 原型 `V.m03`）—— **服务端渲染**。

五段骨架由 `mod03_notice/page.py::render_list_page` 统一装配（**本页不手写骨架**）。
表头/列宽/筛选项对齐原型：18 个 `th`（勾选 ＋ 16 个数据列 ＋ 操作）· 6 项筛选。

⚠️ **本单元只做"看得见"**：列表 + 筛选 + 计数。行级动作（批量改分类 / 剔除 / 手动新增）与
   批量付款、操作列内容属下一单元 —— 故「操作」列本页**渲染为空**，**不放点不动的按钮**。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import to_money
from app.core.period import MODE_ALL, MODE_MONTH, MODE_SPAN, MODE_YEAR, default_period, period_range
from app.mod03_notice.list_view import (
    CATEGORY_LABELS,
    CATEGORY_OPTIONS,
    NoticeFilters,
    build_rows,
    count_rows,
    filter_rows,
)
from app.mod03_notice.page import (
    BASE_CSS,
    STICKY_BOTTOM_CSS,
    VSEP_CSS,
    esc,
    render_list_page,
    sort_rows,
)
from app.mod05_flow.domain import PAY_STATUS_PAID, PAY_STATUS_UNPAID

PAGE_ID = "m03-notices"
SORT_KEY = "m03:notices"
PERIOD_SCOPE = "nt"          # 统一时间控件的**调用点标识**（对齐原型 `scope:'nt'`）
# ⚠️ 默认年月的**口径键** —— 必须是 `period.default_period()` 认得的付款侧键（"notice"），
#    不是控件标识 "nt"。§9.2：付款域类表默认 = **当月**（此前误传 "nt" ⇒ 落到"上月"分支）。
PERIOD_DEFAULT_KEY = "notice"

from app.core.nav import NAV  # noqa: F401 —— 全站导航的**唯一主人**（改动见 core/nav.py）

TIPS = (
    "抓取按**单据日期**的起止（闭区间）**按月全量**、不选项目、不分页（§4.2.1）；触发一律**人工点击**。",
    "**剔除**：按四类规则（业务类型 / 付款项目名 / 单据名称关键字 / 录入人）命中即剔除，"
    "**标记保留、默认隐藏、不销毁数据**；人工批量剔除的记录可由「恢复剔除」放开，**规则命中的不放开**（§4.2.2）。",
    "**分类**只有三类（机械 / 集采 / 辅材），无「其他」类；**手改后重新抓取不被覆盖**（§4.2.3 / §4.2.4）。",
    "**三金额**：**审批金额**为 i8 源数据（只读）；统计结算金额 · 统计付款金额为**旁路**"
    "（⚠️ 原「付款金额（源）」已于 2026-09-16 取消），"
    "上限 = 审批金额（超额**拦截并保留原值**）；列表上的「付款金额」= 审批金额 − 已付金额，是**派生显示列**（§4.2.5）。",
    "**「分类 = 剔除」是专用视图**：切到它时**不再受审批状态 / 付款状态约束**，"
    "且**同时列出 i8 已撤单的行**（按来源分档：人工剔除 / 规则命中 / i8 已撤单，**不混作一谈**）（§4.2.2 / §4.2.7）。",
    "**已付金额 = 生效流水汇总**（已撤销的流水不计入）；**付款状态只有两态**，判定基准 = 审批金额（§4.4.2）。",
    "待付款单据一律来自**系统内勾选**（不依赖外部文件或手输清单）；批量打印 / 仅导出 PDF **共用同一次勾选**（§4.6）。",
)

# 时间模式（统一控件的能力由调用点声明，§4.1 口径）
_PERIOD_MODES = {MODE_MONTH: "月", MODE_SPAN: "跨月", MODE_YEAR: "年", MODE_ALL: "全部"}


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
    """一行 → 各列的**显示值**（页面只负责摆位置）。"""
    from app.mod03_notice.notice_actions import category_name
    from app.mod03_notice.notice_row import action_cell

    return {
        "notice_id": row.notice_id,
        "doc_date": row.doc_date,
        "bill_no": row.bill_no,
        "project_display": row.project_display or row.project_name,
        "category_label": category_name(row.category),
        "bill_name": row.bill_name,
        "biz_type": row.biz_type,
        "payee": row.payee,
        "jc_supplier": "",                      # 集采实际供应商属 M5（MOD-11），本单元留空
        "input_by": row.input_by,
        "amount_approved_text": _amt(row.amount_approved),
        "pay_amount_text": _amt(row.pay_amount),
        "amount_paid_text": _amt(row.amount_paid),
        "stat_settle_text": _amt(row.stat_settle),
        "stat_paid_text": _amt(row.stat_paid),
        "approve_status": row.approve_status,
        "pay_status": "已付清" if row.pay_status == PAY_STATUS_PAID else "未付清",
        # 「操作」列 = 对**本系统记录**的处置（R18）：手动行 ⇒ 编辑/删除；有生效流水 ⇒ 撤销付款；
        # 有关联 ⇒ 查看关联；一个都不满足 ⇒ 「—」。⚠️ i8 行永不给编辑 / 删除。
        "actions": action_cell(row),
        "_row": row,
    }


def summary_row(data: dict) -> dict:
    """表内合计行（用户 2026-09-13 口径「**求和一律落在表内**」· 设计规则 `R7`）—— **只算非剔除行**。

    5 个数值列 = 审批金额 / 付款金额 / 已付金额 / 统计结算金额 / 统计付款金额
    （列序与原型 `sumRowOf(NT_THEAD, …)` 给的下标 `10…14` **一一对应**）。

    ⚠️ **口径与欠款一致**：剔除行**不计入**（原型 `sumRows = list.filter(ntLive)`）。
    ⚠️ 切到「分类 = 剔除」时该视图**全是剔除行** ⇒ **不给合计行**（不给一排 0，免得看着像坏了）。
    ⚠️ 首格写「合计」（与 `m08` 同款）；排序时该行由 `data-pin="1"` **钉在表尾**。
    """
    cols = columns()
    live = [
        rec["_row"] for rec in (data.get("rows") or ())
        if rec.get("_row") is not None and not bool(getattr(rec["_row"], "excluded", False))
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


def _filter_controls(data: dict) -> list[dict]:
    """6 项筛选（原型同款）：年月（**统一控件取值语法**）/ 单据日期区间 / 项目 / 分类 / 审批状态 / 付款状态。"""
    f: NoticeFilters = data["filters"]
    start, end = period_range(f.period)
    rng = f"{start or '—'} ~ {end or '—'}"
    modes = " / ".join(_PERIOD_MODES[m] for m in (MODE_MONTH, MODE_SPAN, MODE_YEAR, MODE_ALL))

    # ⭐ 项目选择器走**共用件**（原型 `projPanel(...)` 的服务端等价物）——
    #    此前是本页自造的 `<select multiple size="3">` ⇒ 与原型结构对不上（`pjwrap` 恒为 0）。
    from app.mod03_notice.proj_panel import proj_panel_html

    proj_html = proj_panel_html(data["project_options"], selected=f.project_ids,
                                form="f-m03", label="项目")
    cat_opts = "".join(
        f'<option value="{esc(c)}"{" selected" if c == f.category else ""}>{esc(CATEGORY_LABELS[c])}</option>'
        for c in CATEGORY_OPTIONS
    )
    astat_opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == f.approve_status else ""}>{esc(v or "全部")}</option>'
        for v in ("", "已批", "未批")
    )
    stat_opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == f.pay_status else ""}>{esc(lbl)}</option>'
        for v, lbl in (("", "全部"), (PAY_STATUS_UNPAID, "未付清"), (PAY_STATUS_PAID, "已付清"))
    )
    return [
        {"key": "period", "label": f"单据年月（{modes}）",
         "html": f'<input name="period" value="{esc(f.period)}" placeholder="2026-09" form="f-m03">'},
        {"key": "range", "label": "对应单据日期（闭区间）",
         "html": f'<input readonly value="{esc(rng)}" form="f-m03">'},
        {"key": "project_ids", "raw": True, "html": proj_html},
        {"key": "category", "label": "分类",
         "html": f'<select name="category" form="f-m03">{cat_opts}</select>'},
        {"key": "approve_status", "label": "审批状态",
         "html": f'<select name="approve_status" form="f-m03">{astat_opts}</select>'},
        {"key": "pay_status", "label": "付款状态",
         "html": f'<select name="pay_status" form="f-m03">{stat_opts}</select>'},
        {"key": "reset", "label": "",
         "html": '<button form="f-m03" type="reset">重置</button>'},
        {"key": "counters", "label": "",
         "html": f'<span class="pill">{esc(data["counters"].text())}</span>'},
    ]


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
    from app.mod03_notice.notice_actions import manual_project_options

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
    """全部已建档项目（空表也返回空列表，**不假装有数据**）。"""
    from app.mod01_projects.repository import list_projects  # type: ignore

    try:
        return list(list_projects(session))
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


def _render_rows_html(data: dict) -> str:
    from app.mod03_notice.notice_row import STAT_CELL_KEYS, draft_row_html, stat_cell

    field_of_cell = {v: k for k, v in STAT_CELL_KEYS.items()}
    cols = data["columns"]
    out: list[str] = []
    for rec in data["rows"]:
        row = rec["_row"]
        cls = ' class="hl"' if row.in_exclude_view else ""
        cells = []
        for c in cols:
            key = c["key"]
            value = rec.get(key, "")
            klass = ' class="%s"' % c["cls"] if c.get("cls") else ""
            if key == "pick":
                # 勾选框**只在页面上出现**（API 返回纯数据，不含 HTML）。
                # ⚠️ 归 `f-act`（POST 批量动作）而不是筛选表单 `f-m03`（GET）：
                #    一个控件只能隶属一个表单，「批量动作作用于勾选行」是它的主要用途。
                # ⚠️ `_picked` = 「按本月计划勾选」命中的行（§4.3.5）—— 服务端预勾选。
                checked = " checked" if rec.get("_picked") else ""
                value = (f'<input type="checkbox" class="chk" name="ids" '
                         f'value="{row.notice_id}"{checked} form="f-act">')
            elif key in field_of_cell:
                # 两个**旁路统计金额（可手改）** ⇒ 行内输入框（上限 = 审批金额；已手改 ⇒ 黄底）
                value = stat_cell(row, field_of_cell[key], rec.get(key, ""))
            elif key == "bill_no" and row.in_exclude_view:
                # 剔除 / 撤单行**带上来源分档**（口径：不混作一谈）
                value = f'{esc(value)} <span class="tag">{esc(row.exclude_reason)}</span>'
            cells.append(f"<td{klass}>{value}</td>")
        out.append(f"<tr{cls}>" + "".join(cells) + "</tr>")

    if data.get("draft") is not None:
        # 表内草稿行（§4.2.6 手动新增 / 编辑）—— 列序与表头一致
        out.append(
            draft_row_html(
                columns=cols,
                notice=data.get("draft") or None,
                project_options=data.get("manual_project_options") or [],
                operator=data.get("operator") or "",
                error=data.get("draft_error") or "",
            )
        )
    return "".join(out)


# ---------------------------------------------------------------- 批量动作条（R3 / R14）

BULK_HINT = "批量动作一律**作用于勾选行**（批量 = 对勾选集操作，不是对整表操作）；勾选用左侧复选框"


def hidden_filters(data: dict) -> str:
    """把**当前筛选**放进批量动作表单（PRG 回来时停在原查询，不回第一页）。"""
    f: NoticeFilters = data["filters"]
    pairs = [
        ("period", f.period or ""),
        ("category", f.category or ""),
        ("approve_status", f.approve_status or ""),
        ("pay_status", f.pay_status or ""),
        ("sort", data.get("sort_col") or ""),
        ("dir", str(int(data.get("sort_dir") or 0))),
    ]
    hidden = "".join(f'<input type="hidden" name="{k}" value="{esc(v)}">' for k, v in pairs)
    hidden += "".join(
        f'<input type="hidden" name="project" value="{esc(k)}">' for k in (f.project_ids or ())
    )
    return hidden


def action_bar_html(data: dict, *, today=None) -> str:
    """批量动作条：改分类 ×3 · 剔除 / 恢复剔除 · 批量付款 · 按本月计划勾选 · 批量打印 / 仅导出 PDF。

    ⚠️ 「按本月计划勾选」**只在该窗口内可点**（§4.3.2：付款计划生效 = 每月 10 号 → 月底），
       窗口外**先禁用**并说明原因（R14①：能预防就不要等用户撞上去）。
    """
    from datetime import date

    from app.mod04_plan.domain import in_effective_window, window_label

    day = (today or date.today()).day
    open_ = in_effective_window(day)
    plan_btn = (
        '<button formaction="/m03/notices/pick-plan" formnovalidate>按本月计划勾选</button>'
        if open_
        else (
            f'<button disabled title="{esc(window_label(day))}">按本月计划勾选</button>'
            f'<span class="mut sm">{esc(window_label(day))}</span>'
        )
    )
    return f"""
<div class="bulk"><span class="mut sm">{esc(BULK_HINT)}</span>
<form id="f-act" method="post" action="/m03/notices/category">{hidden_filters(data)}
<button name="category" value="material" title="把勾选行改为「辅材」">改辅材</button>
<button name="category" value="mechanical" title="把勾选行改为「机械」">改机械</button>
<button name="category" value="jc" title="把勾选行改为「集采」">改集采</button>
<button formaction="/m03/notices/exclude" title="人工批量剔除：标记保留、默认隐藏、不销毁数据">批量剔除</button>
<button formaction="/m03/notices/restore" title="只恢复「人工批量剔除」的行；规则命中的不恢复">恢复剔除</button>
<button formaction="/m03/pay" formmethod="get" title="打开批量付款窗口（勾选若干条 → 一次动作）">批量付款…</button>
{plan_btn}
<button formaction="/m03/notices/output" name="mode" value="print" title="勾选的通知书 → 取 i8 版式 → 渲染 PDF → 投递打印机">批量打印</button>
<button formaction="/m03/notices/output" name="mode" value="pdf" title="与批量打印共用同一次勾选；只渲染落盘、不投递">仅导出 PDF</button>
<button formaction="/m03/notices/draft" name="new" value="1" title="手动新增一行付款通知书（增行模式：表尾出现草稿行）">＋ 手动新增通知书</button>
</form></div>"""


def render_notice_page(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """渲染整页（五段骨架走 `render_list_page`；数据行由本页渲染 —— 要带勾选框与操作列）。"""
    cols = [{k: v for k, v in c.items() if k != "cls"} for c in data["columns"]]
    filters = list(_filter_controls(data)) + [
        {"key": "bulk", "label": "批量动作", "html": action_bar_html(data)}
    ]
    body = render_list_page(
        page_id=PAGE_ID,
        title="付款通知书",
        tips=TIPS,
        kpis=[],                      # R2：`.kpis` 只在域级总览页 —— 本页不放
        filters=filters,
        columns=cols,
        rows_html=_render_rows_html(data),
        empty_text="当前筛选没有付款通知书（可切「分类 = 剔除」查看被剔除 / 已撤单的行）",
        sort_key=SORT_KEY,
        summary=summary_row(data),
    )
    notice = ""
    if message:
        notice = f'<div class="notice {esc(message_kind)}">{esc(message)}</div>'
    elif data.get("draft_error"):
        # 草稿行开不出来（如想编辑 i8 行）⇒ **必须说清为什么**，不能静默什么都不做
        notice = f'<div class="notice err">{esc(data["draft_error"])}</div>'
    elif data.get("plan_report"):
        # 「按本月计划勾选」的回报（§4.3.5）：勾了几条 / 计划里几个号 / 被项目筛选跳过几条
        notice = f'<div class="notice wn">{esc(data["plan_report"])}</div>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>付款通知书 · 材料报表自动化工作台</title>
<style>{BASE_CSS}{STICKY_BOTTOM_CSS}{VSEP_CSS}
.fbar .fi input,.fbar .fi select{{max-width:240px}}
.pill{{margin-left:auto;font-size:12px;color:var(--tx2)}}
.tag{{display:inline-block;margin-left:6px;padding:0 6px;border:1px solid var(--dg);border-radius:8px;
      font-size:11px;color:var(--dg-d);background:var(--dg-l)}}
.tag.wn{{border-color:var(--wn);color:var(--wn-d);background:var(--wn-l)}}
.bulk{{flex:1 0 100%;display:flex;flex-wrap:wrap;gap:6px;align-items:center;
       border-top:1px dashed var(--bd);padding-top:8px;margin-top:2px}}
.bulk form{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.bulk .mut{{margin-right:6px}}
tr.draftrow>td{{background:var(--draft)}}
tr.draftrow input.cell,tr.draftrow select.cell{{max-width:130px}}
details.pop{{display:inline-block;position:relative}}
details.pop>summary{{cursor:pointer;color:var(--pri);font-size:12px;list-style:none}}
details.pop>summary::-webkit-details-marker{{display:none}}
details.pop .popbody{{position:absolute;z-index:9;right:0;top:20px;background:var(--sf);border:1px solid var(--bd);
       border-radius:6px;padding:8px 10px;box-shadow:0 4px 14px var(--shadow);min-width:240px}}
details.pop .popbody input{{width:100%;border:1px solid var(--bd3);border-radius:5px;padding:4px 6px;
       font-size:12.5px;margin:6px 0}}
a.lnk{{color:var(--pri);font-size:12px;text-decoration:none}}
.dt input.ed{{background:var(--edit-l);border-color:var(--wn)}}
.dt td button{{margin-left:2px;padding:2px 6px}}
</style></head><body>
<nav class="nav">{_nav()}</nav>
{notice}
<form id="f-m03" method="get" action="/m03/notices"></form>
<form id="f-stat" method="post" action="/m03/notices/stat">{hidden_filters(data)}</form>
{body}
</body></html>"""


def _nav() -> str:
    return "".join(f'<a href="{esc(href)}">{esc(label)}</a>' for href, label in NAV)


# ---------------------------------------------------------------- 查看关联（只读页 · R18）


def render_trace_page(data: dict) -> str:
    """「查看关联」**纯只读**页（R18）：

    上半 = 单据 / 项目 / 供应商 / 关联 / 两金额 / 付款状态；下半 = 该行**付款流水子表**（含已撤销那几条）。

    ⚠️ **零副作用**：不开任何写路径、不动勾选、不留痕。
    ⚠️ 「集采实际供应商 / 集采合同关联」属 `MOD-11`（集采台账，**尚未落地**）⇒ 现显示「—」并注明，
       **不臆造**取值（`list_view._links_by_notice` 是唯一的接入点，M5 落地后本页自动有内容）。
    """
    from app.mod03_notice.notice_actions import category_name
    from app.mod05_flow.domain import effective_total, payment_status

    flows = data.get("flows") or []
    paid = effective_total([{"status": f.get("status"), "amount": f.get("amount")} for f in flows])
    status = payment_status(paid, data.get("approve_amount") or 0)

    rows = [
        ("单据编码", data.get("bill_no")), ("单据日期", data.get("doc_date")),
        ("单据名称", data.get("bill_name")), ("付款项目", data.get("project_name")),
        ("分类", category_name(data.get("category"))), ("审批状态", data.get("approve_status")),
        ("统计结算金额", data.get("stat_settle")), ("统计付款金额", data.get("stat_paid")),
        ("已付金额（生效流水汇总）", f"{to_money(paid):.2f}"),
        ("付款状态", "已付清" if status == PAY_STATUS_PAID else "未付清"),
        ("集采实际供应商", "—（集采台账属 MOD-11，尚未落地）"),
        ("集采合同关联", "—（同上；入口在「集采实际供应商」列）"),
        ("行来源", "手动新增行（无 i8 单据）" if data.get("is_manual") else "i8 抓取行（源数据，只读）"),
        ("i8 已撤单", "是（已退出全部统计）" if data.get("i8_revoked") else "否"),
    ]
    kv = "".join(f"<div><b>{esc(k)}</b><span>{esc(v)}</span></div>" for k, v in rows)

    if flows:
        body = "".join(
            f"<tr><td>{esc(f.get('flow_no'))}</td><td>{esc(f.get('pay_date'))}</td>"
            f"<td class='num'>{esc(f.get('amount'))}</td><td>{esc(f.get('pay_method'))}</td>"
            f"<td>{esc(f.get('status_label'))}</td><td>{esc(f.get('revoke_reason'))}</td>"
            f"<td>{esc(f.get('revoked_at'))}</td></tr>"
            for f in flows
        )
        table = (
            '<div class="tw"><table class="dt"><thead><tr>'
            "<th>流水号</th><th>付款日期</th><th>金额</th><th>实际付款方式</th>"
            "<th>状态</th><th>撤销原因</th><th>撤销时间</th>"
            f"</tr></thead><tbody>{body}</tbody></table></div>"
        )
    else:
        table = '<div class="tw"><table class="dt"><tbody><tr class="empty"><td>该行还没有付款流水</td></tr></tbody></table></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>查看关联 · 付款通知书</title>
<style>{BASE_CSS}
</style></head><body>
<div class="wrap">
<nav class="nav">{_nav()}</nav>
<section class="view"><h3>查看关联 · {esc(data.get("bill_no"))}（纯只读，不改任何数据）</h3>
<div class="kv">{kv}</div>
{table}
<p><a class="lnk" href="{esc(LIST_URL_BACK)}">← 返回付款通知书列表</a></p>
</section></div>
</body></html>"""


LIST_URL_BACK = "/m03/notices"


__all__ = [
    "PAGE_ID", "SORT_KEY", "PERIOD_SCOPE", "PERIOD_DEFAULT_KEY", "NAV", "TIPS",
    "columns", "build_page_data", "render_notice_page", "render_trace_page",
    "action_bar_html", "hidden_filters", "BULK_HINT",
]
