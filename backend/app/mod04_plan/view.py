"""`MOD-04` 页面渲染（**服务端渲染 + PRG**，零前端构建、零 JS 重复实现）。

为什么**服务端渲染**而不是「静态页 + JSON API」：
- 页面骨架 / 筛选 / 排序 / 合计**只有一个出口**（`mod03_notice/page.py` 的 `render_list_page` / `sort_rows`
  与 `plan_ui.filter_plan_rows`）⇒ 不会像客户端那样把同一套逻辑再写一遍（副本必然漂移）；
- 交互走**表单往返（PRG）**：筛选 = GET 查询参数，改动 = POST 后 303 回原查询
  ⇒ 「行内改列**立刻落库**」「删除前列影响范围并确认」都是**服务端事实**，不靠前端状态。

⚠️ 口径回主人：《说明书》§4.3（付款计划）· 交互基准 = `demo/` 原型与 `设计规则`。
⚠️ 合计行置底的 CSS 必须随页面给出（`page.STICKY_BOTTOM_CSS`）—— 实测见 `ops/M3-合计行置底实测结论.md`。
"""

from __future__ import annotations

from app.core.money import to_money  # noqa: F401  （保留：金额出口一旦要用必须走它）
from app.mod03_notice.page import (
    BASE_CSS,
    STICKY_BOTTOM_CSS,
    VSEP_CSS,
    esc,
    render_list_page,
)
from app.mod04_plan.domain import ALL_RESULTS, BUCKET_ALL, BUCKET_MATCHED, BUCKET_UNMATCHED, bucket
from app.mod04_plan.plan_ui import (
    inline_editable_columns,
)
from app.mod05_flow.models import PAY_METHODS

# 基础样式已上移到页面件主人 `mod03_notice/page.py`（`BASE_CSS`）—— 各视图**不再各写一份**。
from app.mod03_notice.page import BASE_CSS  # noqa: E402  （保持下方引用名不变）
# 审查结果 → 标签色（原型 `revTag`）
_REV_TAG = {
    "完全匹配": "ok",
    "金额不符": "wn",
    "单据号查不到": "dg",
    "无单据号": "wn",
    "重复上报": "dg",
    "超过未付": "wn",
}

COLUMNS: tuple[dict, ...] = (
    {"key": "id", "label": "计划行号", "sortable": False},
    {"key": "year_month", "label": "单据年月", "sortable": True},
    {"key": "project_display", "label": "项目（填报：展示名 / 仓库名）", "sortable": True},
    {"key": "doc_no", "label": "单据号", "sortable": True},
    {"key": "flow_amount", "label": "i8 流程金额", "sortable": True},
    {"key": "paid_amount", "label": "已付款金额", "sortable": False},
    {"key": "unpaid_amount", "label": "剩余付款金额", "sortable": False},
    {"key": "planned_amount", "label": "本月预付款金额", "sortable": True},
    {"key": "pay_date", "label": "付款时间", "sortable": True},
    {"key": "pay_method", "label": "付款方式", "sortable": True},
    {"key": "remark", "label": "备注", "sortable": True},
    {"key": "audit_result", "label": "审查结果", "sortable": True},
    {"key": "op", "label": "操作", "sortable": False},
)

TIPS: tuple[str, ...] = (
    "付款计划 = i8 付款通知书的「本月预算版」（§4.3.1）：项目端报来 → 用户手工加「项目」列 → 导入 → 与 i8 通知书逐笔比对。",
    "「项目」列填的是**展示名或仓库名**（不是全名）；按这两个字段唯一匹配档案，查不到即标「未匹配」。",
    "系统**只提示、不拦截**；判定共 6 种，筛选下拉按**两档归并**（完全匹配 / 未匹配）。",
    "「已付款金额 / 剩余付款金额」两列由**命中的 i8 通知书**派生（已付＝流水汇总；未付＝审批金额−已付金额）；命中不到 → 留空。",
    "可手改列：付款时间 / 付款方式 / 备注；**单据号仅「未匹配」行可改**，改完点「再次匹配」重新比对。改动落库、不留痕。",
    "本表支持逐行删除与批量删除：**删除前列出影响范围**（行号 / 所属年月 / 审查结果），**只影响付款计划表**。",
    "**手动新增的计划行**：用于补录导入表里没有的计划 ⇒ **不被导入清理**（§9.5 只重写自动行），"
    "但**一样参与上面 6 种审查判定**（审查按行实时派生、不看来源）；**编辑只对手动行开放**（导入行要改请重导）。",
)


def hidden_filters(data: dict) -> str:
    """把当前筛选带回 POST（PRG 回原查询）。"""
    out = [f'<input type="hidden" name="year_month" value="{esc(data["year_month"])}">',
           f'<input type="hidden" name="review" value="{esc(data["audit_bucket"])}">']
    for k in data["project_ids"]:
        out.append(f'<input type="hidden" name="project" value="{esc(k)}">')
    if data.get("sort_col"):
        out.append(f'<input type="hidden" name="sort" value="{esc(data["sort_col"])}">')
        out.append(f'<input type="hidden" name="dir" value="{int(data.get("sort_dir") or 0)}">')
    return "".join(out)


def _filter_controls(data: dict) -> list[dict]:
    """筛选栏三项（§4.3.4）：年月 / 项目（多选）/ 审查结果 —— 年月走统一控件取值语法。"""
    selected = set(data["project_ids"])
    proj_opts = "".join(
        f'<option value="{esc(o["key"])}"{" selected" if o["key"] in selected else ""}>'
        f'{esc(o["label"] or o["key"])}</option>'
        for o in data["project_options"]
    )
    review_opts = "".join(
        f'<option value="{esc(b)}"{" selected" if b == data["audit_bucket"] else ""}>{esc(b)}</option>'
        for b in (BUCKET_ALL, BUCKET_MATCHED, BUCKET_UNMATCHED)
    )
    return [
        {
            "key": "year_month",
            "label": "单据年月（YYYY-MM / YYYY-MM~YYYY-MM / YYYY / 空=全部）",
            "html": f'<input name="year_month" value="{esc(data["year_month"])}" '
                    f'placeholder="2026-09" form="f-m04">',
        },
        {
            "key": "project_ids",
            "label": "项目（可多选）",
            "html": f'<select name="project" multiple size="3" form="f-m04">{proj_opts}</select>',
        },
        {
            "key": "audit_bucket",
            "label": "审查结果",
            "html": f'<select name="review" form="f-m04">{review_opts}</select>',
        },
    ]


def _cell_form(data: dict, row: dict, column: str, control: str) -> str:
    return (
        f'<form class="inline" method="post" action="/m04/cell">'
        f'<input type="hidden" name="row_id" value="{int(row["id"])}">'
        f'<input type="hidden" name="column" value="{esc(column)}">'
        f"{hidden_filters(data)}{control}"
        f'<button type="submit" title="保存本格（立刻落库、不留痕）">存</button></form>'
    )


def _row_html(data: dict, row: dict) -> str:
    """一行的 13 个格子 —— 可改列**逐格独立提交**（= 立刻落库），未匹配行才有「再次匹配」。

    ⚠️ 「编辑」**只对手动行**开放（导入行要改请重导，§4.3.3）；「删除」**所有行都有**（§4.3.6 逐行 + 批量）。
    """
    editable = set(inline_editable_columns(row["audit_result"]))
    matched = row["audit_result"] == "完全匹配"

    def txt(col: str, extra: str = "") -> str:
        if col not in editable:
            return esc(row[col]) or '<span class="mut">—</span>'
        ctl = (
            f'<input class="cell" name="value" value="{esc(row[col])}" {extra}>'
        )
        return _cell_form(data, row, col, ctl)

    doc_cell = (
        txt("doc_no")
        if "doc_no" in editable
        else (esc(row["doc_no"]) or '<span class="tag dg">未填</span>')
    )
    method_opts = "".join(
        f'<option value="{esc(m)}"{" selected" if m == row["pay_method"] else ""}>{esc(m)}</option>'
        for m in PAY_METHODS
    )
    method_cell = _cell_form(
        data, row, "pay_method", f'<select class="cell" name="value">{method_opts}</select>'
    ) if "pay_method" in editable else esc(row["pay_method"])

    tag = _REV_TAG.get(row["audit_result"], "wn")
    forced = ' <span class="tag wn">已强制通过</span>' if row["forced_through"] else ""
    manual_tag = '<span class="tag wn" title="手动新增行（不被导入清理，但一样参与审查）">手动</span> ' if row.get("is_manual") else ""
    edit_btn = (
        f'<form class="inline" method="post" action="/m04/row/draft">'
        f'<input type="hidden" name="row_id" value="{int(row["id"])}">{hidden_filters(data)}'
        f'<button type="submit" title="就地变草稿行（不新增行）">编辑</button></form>'
        if row.get("is_manual") else ""
    )
    # 强制通过（§4.3.4）—— 语义照原型 `PL` 页：**只提示不拦截 · 放行必须写备注 · 取消不留痕**。
    # ⚠️ 本页是**服务端渲染的过渡形态**（无 JS 弹窗 ⇒ 备注改为行内输入）；接壳时按原型改成弹窗。
    force_html = ""
    if matched:
        force_html = '<span class="mut sm">无需处理</span>'
    elif row["forced_through"]:
        force_html = (
            f'<span class="mut sm" title="{esc(row["forced_remark"])}">'
            f'{esc(row["forced_remark"])}</span>'
            f'<form class="inline" method="post" action="/m04/force-cancel">'
            f'<input type="hidden" name="row_id" value="{int(row["id"])}">{hidden_filters(data)}'
            f'<button type="submit" title="取消强制通过 → 回到原判定、备注清空（不产生留痕）">'
            f"取消强制通过</button></form>"
        )
    else:
        force_html = (
            f'<form class="inline" method="post" action="/m04/force">'
            f'<input type="hidden" name="row_id" value="{int(row["id"])}">{hidden_filters(data)}'
            f'<input class="cell" name="remark" placeholder="放行理由（必填）" '
            f'title="强制通过必须写备注（§4.3.4）—— 空备注会被拒绝">'
            f'<button type="submit" title="系统只提示、不拦截；放行必须写备注（留痕）">强制通过</button>'
            f"</form>"
        )
    op = (
        force_html
        + edit_btn
        + ("" if matched else f'<form class="inline" method="post" action="/m04/re-match">'
         f'<input type="hidden" name="row_id" value="{int(row["id"])}">{hidden_filters(data)}'
         f'<button type="submit" title="按当前单据号重新比对 i8 通知书">再次匹配</button></form>')
        + f'<a href="/m04/delete?ids={int(row["id"])}'
        + "".join(f"&amp;{k}={esc(v)}" for k, v in (
            ("year_month", data["year_month"]), ("review", data["audit_bucket"]),
            ("sort", data.get("sort_col") or ""), ("dir", int(data.get("sort_dir") or 0)),
        ))
        + "".join(f"&amp;project={esc(k)}" for k in data["project_ids"])
        + '"><button class="dg" type="button">删除</button></a>'
    )

    cells = [
        esc(row["id"]),
        esc(row["year_month"]),
        f'<span title="填报：{esc(row["project_input"])}">{esc(row["project_display"]) or "—"}</span>'
        + (f' <span class="tag wn">重名 {row["match_candidates"]} 条</span>'
           if row["match_status"] == "ambiguous" else "")
        + ('' if row["project_display"] else ' <span class="tag dg">未匹配</span>'),
        doc_cell,
        f'<span class="num">{esc(row["flow_amount"])}</span>',
        f'<span class="num">{esc(row["paid_amount"]) or "—"}</span>',
        f'<span class="num">{esc(row["unpaid_amount"]) or "—"}</span>',
        f'<span class="num">{esc(row["planned_amount"])}</span>',
        txt("pay_date", 'type="date"'),
        method_cell,
        txt("remark"),
        f'<span class="tag {tag}">{esc(row["audit_result"])}</span>{forced}',
        manual_tag + op,
    ]
    cls = "" if matched else ' class="hl"'
    if row.get("is_manual"):
        cls = ' class="manualrow"'
    return f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def _sort_columns(data: dict) -> list[dict]:
    """列头带上当前排序态（指示器由 `sort_rows` 的同一套状态驱动）。"""
    out = []
    for col in COLUMNS:
        col = dict(col)
        if col["sortable"]:
            cur = data.get("sort_col") == col["key"]
            d = int(data.get("sort_dir") or 0)
            col["label"] = col["label"] + (" ▲" if cur and d > 0 else " ▲↓" if cur and d < 0 else " ↕")
        out.append(col)
    return out


def render_m04(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """整页 HTML（服务端渲染）。"""
    from app.mod04_plan.plan_manual import DRAFT_FORM_ID, draft_row_html

    rows_html = "".join(_row_html(data, r) for r in data["rows"])
    if data.get("draft") is not None:
        # 表内草稿行（手动新增 / 编辑计划行）—— 列序与 COLUMNS 一致
        rows_html += draft_row_html(
            plan_row=data.get("draft") or None,
            project_options=data.get("manual_project_options") or [],
            default_ym=data.get("year_month") or "",
            error=data.get("draft_error") or "",
        )
    kpis = [
        {"k": k, "v": data["counts"].get(k, 0), "s": "笔 · 当前筛选"} for k in ALL_RESULTS
    ]
    win = data["window"]
    notice = ""
    if message:
        # ⚠️ `message` 走**查询串**（`?msg=`，见 router.page_m04）⇒ 属**外部输入**，必须转义。
        #    与 `MOD-03` 同款位置一致（`notice_page.py` 的 `esc(message)`）；`TAIL-05` 修补。
        notice = f'<div class="notice {esc(message_kind)}">{esc(message)}</div>'
    elif data.get("draft_error"):
        # 草稿行开不出来（如想编辑导入行）⇒ **必须说清为什么**，不能静默什么都不做
        notice = f'<div class="notice err">{esc(data["draft_error"])}</div>'

    body = render_list_page(
        page_id="m04",
        title="付款计划",
        tips=TIPS,
        kpis=kpis,
        filters=_filter_controls(data),
        columns=_sort_columns(data),
        rows_html=rows_html,        # 行需要"每格一个表单"⇒ 由本模块渲染整段 <tr>
        empty_text="当前筛选没有付款计划行",
        sort_key="m04:plans",
        summary=data["summary"],
        summary_sticky=True,
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>付款计划 · 材料报表自动化工作台</title>
<style>{BASE_CSS}{STICKY_BOTTOM_CSS}{VSEP_CSS}
nav a{{margin-right:12px;font-size:13px;color:var(--pri);text-decoration:none}}
h1+nav a.imp{{padding:3px 10px;border:1px solid var(--pri);border-radius:5px}}
h1+nav form{{display:inline}}
tr.manualrow>td{{background:var(--draft)}}
tr.draftrow>td{{background:var(--draft)}}
tr.draftrow input.cell,tr.draftrow select.cell{{max-width:120px}}
</style></head><body><div class="wrap">
<header><h1>付款计划</h1>
<nav><a href="/m01">项目档案</a><a href="/m02">i8 接入层</a><a href="/m03">付款通知书</a>
<a class="imp" href="/m04/import" title="导入付款计划 Excel（导入前先选「年月」，§4.3.3）">导入…</a>
<form method="post" action="/m04/row/draft">{hidden_filters(data)}
<button class="imp" type="submit" name="new" value="1" title="手动补一行计划（手动行不被导入清理，但一样参与审查）">＋ 手动新增计划行</button></form>
</nav>
<span class="pill" style="margin-left:auto">生效窗口：{esc(win["label"] or win["reason"])}</span></header>
{notice}
<form id="f-m04" method="get" action="/m04"></form>
<form id="{DRAFT_FORM_ID}" method="post" action="/m04/row/save">{hidden_filters(data)}</form>
{body}
<div class="kv" style="margin-top:12px">
  <div><b>显示条数</b><span>{len(data["rows"])} 条 ｜ 当月共 {data["total_in_month"]} 条</span></div>
  <div><b>按付款计划勾选</b><span>入口在「<b>付款通知书</b>」页（勾选与付款同处）；本页只留指路。</span></div>
  <div><b>默认筛选</b><span>年月 = 当月（§9.2）· 项目 = 全部 · 审查结果 = 全部</span></div>
</div>
</div></body></html>"""


def render_delete_confirm(data: dict, impacts: list, query: str) -> str:
    """删除前**列出影响范围**（§4.3.6）：行号 / 所属年月 / 审查结果 ⇒ 确认后才执行。"""
    items = "".join(
        f"<tr><td>{int(i.seq)}</td><td>{esc(i.year_month)}</td>"
        f'<td><span class="tag {_REV_TAG.get(i.result, "wn")}">{esc(i.result)}</span></td></tr>'
        for i in impacts
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>删除确认 · 付款计划</title>
<style>{BASE_CSS}</style></head><body><div class="wrap">
<header><h1>删除付款计划行 · 确认</h1></header>
<div class="notice err"><b>将删除 {len(impacts)} 行付款计划数据</b>。删除后需重新导入才能恢复。</div>
<div class="kv">
  <div><b>影响范围</b><span><b>只影响付款计划表</b>；不影响付款通知书与欠款统计</span></div>
</div>
<div class="tw" style="max-height:none"><table class="dt">
<thead><tr><th>行号</th><th>所属年月</th><th>审查结果</th></tr></thead>
<tbody>{items}</tbody></table></div>
<form method="post" action="/m04/delete" style="margin-top:12px;display:flex;gap:8px">
  <input type="hidden" name="ids" value="{esc(",".join(str(int(i.row_id)) for i in impacts))}">
  <input type="hidden" name="query" value="{esc(query)}">
  <button type="button" onclick="history.back()">取消</button>
  <button class="dg" type="submit">确认删除</button>
</form>
</div></body></html>"""


__all__ = ["BASE_CSS", "COLUMNS", "TIPS", "hidden_filters", "render_m04", "render_delete_confirm"]
