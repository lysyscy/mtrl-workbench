"""`MOD-05` 页面渲染（**服务端渲染 + PRG**）—— 四个页面：

| 页面 | 路径 | 内容 |
|---|---|---|
| 付款流水 | `/m05` | 列表（一次付款一条）+ **撤销（必填原因）** |
| 欠款 | `/m05/debt` | 三类合计 + **按项目看欠款**（按归属归集、未判定单列） |
| 逐月台账 | `/m05/ledger` | 两侧（辅材 / 机械）**共用同一个项目选择器** + **期初占位行** + 备注 |
| 付款统计 | `/m05/stats` | **左栏按项目 · 右栏时间轴**；粒度月 / 周（默认按周） |

⚠️ 骨架一律走 `mod03_notice/page.py::render_list_page`（五段：口径说明 → 指标区 → 筛选栏 → 数据区 → 空态）
   —— 本文件**不手写页骨架**；合计行置底走 `STICKY_BOTTOM_CSS`。
⚠️ 口径回主人：《说明书》§4.4（流水）· §4.5（欠款 / 台账 / 统计）。
"""

from __future__ import annotations

from app.mod03_notice.page import (
    BASE_CSS,
    SEG_DATA,
    SEG_EMPTY,
    STICKY_BOTTOM_CSS,
    VSEP_CSS,
    esc,
    render_list_page,
)

from app.core.nav import NAV  # noqa: F401 —— 全站导航的**唯一主人**（改动见 core/nav.py）

EXTRA_CSS = """
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.two>div{min-width:0}
.side h4{font-size:13.5px;margin:0 0 6px;font-weight:500;color:var(--tx2)}
.ok{color:var(--ok-d)}.wn{color:var(--wn-d)}.dg{color:var(--dg-d)}
.gridwrap{overflow:auto;max-height:none;border:1px solid var(--bd);border-radius:6px;background:var(--sf)}
.pick{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:10px 12px;margin-bottom:10px}
"""


# ---------------------------------------------------------------- 公共外壳


def _nav(current: str) -> str:
    out = []
    for href, label in NAV:
        bold = ' style="font-weight:600"' if href == current else ""
        out.append(f'<a href="{esc(href)}"{bold}>{esc(label)}</a>')
    return "".join(out)


def _shell(*, title: str, body: str, current: str, notice: str = "", extra: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · 材料报表自动化工作台</title>
<style>{BASE_CSS}{STICKY_BOTTOM_CSS}{VSEP_CSS}{EXTRA_CSS}
nav a{{margin-right:12px;font-size:13px;color:var(--pri);text-decoration:none}}
{extra}</style></head><body><div class="wrap">
<header><h1>{esc(title)}</h1><nav>{_nav(current)}</nav></header>
{notice}
{body}
</div></body></html>"""


def _notice(message: str, kind: str) -> str:
    return f'<div class="notice {esc(kind)}">{message}</div>' if message else ""


def _hidden(query: dict) -> str:
    """把当前查询带回 POST（PRG 回原查询）。"""
    out = []
    for k, v in query.items():
        if v is None or v == "":
            continue
        out.append(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">')
    return "".join(out)


# ================================================================ ① 付款流水


FLOW_TIPS: tuple[str, ...] = (
    "**一次付款一条流水** —— 不做金额累计覆盖；同一张通知书付多次就有多条流水（§4.4.2）。",
    "付款状态**只有两态**：已付清 / 未付清；判定基准 = **审批金额**（「统计付款金额」不参与状态判定）。",
    "撤销**必须填写原因**：空原因不被接受（撤销是留痕动作）；撤销后该笔**退出统计**、已付金额回退（§4.4.5）。",
    "撤销**只回退流水汇总** —— 不改 i8 源数据、不改两个统计字段。",
    "列表默认「北京时间当月」、**不分页**；状态 / 付款方式 / 关键词筛选**即时生效**。",
    "⭐ 「**导入历史付款**」入口在导航栏（`/m05/import`）：Excel 台账 → **预览（不写库）** → 确认落库 → **核对报告**；同批可整批回滚重导（§4.4.6）。",
)

FLOW_COLUMNS: tuple[dict, ...] = (
    {"key": "flow_no", "label": "流水号", "sortable": True, "vsep": True},
    {"key": "pay_date", "label": "付款日期", "sortable": True},
    {"key": "doc_no", "label": "单据号（所属通知书）", "sortable": True},
    {"key": "project_display", "label": "项目", "sortable": True},
    {"key": "amount", "label": "实付金额", "sortable": True},
    {"key": "pay_method", "label": "付款方式", "sortable": True},
    {"key": "status_label", "label": "状态", "sortable": True},
    {"key": "revoke_reason", "label": "撤销原因", "sortable": False},
    {"key": "created_at", "label": "登记时间", "sortable": True},
    {"key": "op", "label": "操作", "sortable": False},
)


def _flow_filters(data: dict) -> list[dict]:
    q = _flow_query(data)
    status_opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == data["status"] else ""}>{esc(t)}</option>'
        for v, t in (("", "全部状态"), ("effective", "生效"), ("revoked", "已撤销"))
    )
    method_opts = "".join(
        f'<option value="{esc(m)}"{" selected" if m == data["pay_method"] else ""}>{esc(m)}</option>'
        for m in [""] + list(data["pay_methods"])
    )
    proj_opts = "".join(
        f'<option value="{int(o["id"])}"{" selected" if data["project_id"] == o["id"] else ""}>'
        f'{esc(o["label"])}</option>'
        for o in data["project_options"]
    )
    return [
        {"key": "year_month", "label": "付款年月（空=全部）",
         "html": f'<input name="year_month" value="{esc(data["year_month"])}" placeholder="2026-09" form="f-m05">'},
        {"key": "status", "label": "状态",
         "html": f'<select name="status" form="f-m05">{status_opts}</select>'},
        {"key": "pay_method", "label": "付款方式",
         "html": f'<select name="pay_method" form="f-m05">{method_opts}</select>'},
        {"key": "project_id", "label": "项目",
         "html": f'<select name="project_id" form="f-m05"><option value="">全部项目</option>{proj_opts}</select>'},
        {"key": "keyword", "label": "关键词（流水号 / 日期）",
         "html": f'<input name="keyword" value="{esc(data["keyword"])}" form="f-m05">'},
    ]


def _flow_query(data: dict) -> dict:
    return {
        "year_month": data["year_month"], "status": data["status"],
        "pay_method": data["pay_method"],
        "project_id": "" if data["project_id"] is None else data["project_id"],
        "keyword": data["keyword"],
    }


def _flow_rows(data: dict) -> str:
    q = _flow_query(data)
    out = []
    for r in data["rows"]:
        dead = r["status"] == "revoked"
        status_html = (
            f'<span class="dg">已撤销</span>' if dead else '<span class="ok">生效</span>'
        )
        if dead:
            op = '<span class="mut">已撤销</span>'
        else:
            op = (
                f'<form class="inline" method="post" action="/m05/revoke">'
                f'<input type="hidden" name="flow_id" value="{int(r["id"])}">{_hidden(q)}'
                f'<input class="cell" name="reason" placeholder="撤销原因（必填）" required>'
                f'<button class="dg" type="submit" title="撤销后该笔退出统计">撤销</button></form>'
            )
        cells = [
            esc(r["flow_no"]) or '<span class="mut">—</span>',
            esc(r["pay_date"]) or '<span class="mut">—</span>',
            esc(r["doc_no"]) or '<span class="mut">—</span>',
            esc(r["project_display"]) or '<span class="mut">—</span>',
            f'<span class="num">{esc(r["amount"])}</span>',
            esc(r["pay_method"]),
            status_html,
            esc(r["revoke_reason"]) or '<span class="mut">—</span>',
            f'<span class="mut">{esc(r["created_at"])}</span>',
            op,
        ]
        cls = ' class="hl"' if dead else ""
        out.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    return "".join(out)


def render_m05(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """付款流水页。"""
    body = render_list_page(
        page_id="m05",
        title="付款流水",
        tips=FLOW_TIPS,
        kpis=data["kpis"],
        filters=_flow_filters(data),
        columns=list(FLOW_COLUMNS),
        rows_html=_flow_rows(data),
        empty_text="当前筛选没有付款流水",
        sort_key="m05:flows",
        summary=data["summary"],
        summary_sticky=True,
    )
    return _shell(
        title="付款流水", body=f'<form id="f-m05" method="get" action="/m05"></form>{body}',
        current="/m05", notice=_notice(message, message_kind),
    )


# ================================================================ ② 欠款


DEBT_TIPS: tuple[str, ...] = (
    "欠款**只有三类**：辅材 / 机械 / 集采（**没有第四类**，§4.2.3）。",
    "**辅材** = Σ辅材统计结算 − Σ辅材统计付款 ＋ 辅材期初；**机械** = 机械费结算金额 − Σ机械统计付款 ＋ 机械期初。",
    "**集采欠款不在本页计算** —— 它是**合同级实时**、由集采台账负责；本页只作合计展示（§4.5.1）。",
    "**期初占位行按其分类并入**辅材 / 机械，**不单列第四类**；**剔除记录不计入**欠款。",
    "「按项目看欠款」**按归属归集**：壳全名下的行**拆到各自的具体小微**；**未判定的单列**，不并入任何小微（§2.5.1）。",
)

DEBT_COLUMNS: tuple[dict, ...] = (
    {"key": "label", "label": "项目", "sortable": True, "vsep": True},
    {"key": "amount", "label": "欠款金额", "sortable": True},
    {"key": "note", "label": "说明", "sortable": False},
)


def render_m05_debt(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """欠款页（三类合计 ＋ 按项目归集）。"""
    kpis = [{"k": d["label"] + "欠款", "v": d["amount"], "s": "三类之一"} for d in data["by_category"]]
    kpis.append({"k": "欠款合计", "v": data["total"], "s": "辅材＋机械＋集采"})
    rows = []
    for it in data["by_project"]:
        note = "未判定（不并入任何小微）" if it["key"] == "未判定" else ""
        rows.append({"label": it["label"], "amount": it["amount"], "note": note})
    body = render_list_page(
        page_id="m05-debt",
        title="按项目看欠款",
        tips=DEBT_TIPS,
        kpis=kpis,
        filters=[],
        columns=list(DEBT_COLUMNS),
        rows=rows,
        empty_text="尚无欠款数据（付款通知书 / 期初占位行都为空）",
        sort_key="m05:debt",
        summary={"label": "合计", "amount": data["total"], "note": ""},
        summary_sticky=True,
    )
    warn = ""
    if not data["mech_settle_ready"]:
        warn = (
            '<div class="notice wn">⚠️ <b>机械费结算金额</b>的来源是<b>过程资料</b>（`MOD-06`，'
            "尚未接入）⇒ 当前<b>按 0 计</b>，机械欠款的结算侧<b>暂不成立</b>；"
            "这不是业务上的 0，接入后自动生效。</div>"
        )
    return _shell(
        title="欠款（辅材 / 机械 / 集采）", body=warn + body,
        current="/m05/debt", notice=_notice(message, message_kind),
    )


# ================================================================ ③ 逐月台账


LEDGER_TIPS: tuple[str, ...] = (
    "台账**两侧（辅材 / 机械）共用同一个「项目」选择器** —— 没有「切换口径」按钮（§4.5.4）。",
    "**第 1 行 = 期初占位行**：手填的、无通知书对应的结算与付款金额；**只带本口径的期初**。",
    "其后从**期初次月**起**逐月连续**出行：**空月也出行**（三列记 0），不会跳月。",
    "「欠款」列 = **当月新增欠款**（其他支出金额 − 付款），**不是累计**。",
    "**机械侧「其他支出金额」是派生只读、没有手填入口**；备注按「口径 + 项目 + 月」存。",
)

LEDGER_COLUMNS: tuple[dict, ...] = (
    {"key": "seq", "label": "序号", "sortable": False, "vsep": True},
    {"key": "month", "label": "月份", "sortable": True},
    {"key": "other_expense", "label": "其他支出金额", "sortable": True},
    {"key": "payment", "label": "付款", "sortable": True},
    {"key": "debt", "label": "欠款", "sortable": True},
    {"key": "remark", "label": "备注", "sortable": False},
    {"key": "op", "label": "操作", "sortable": False},
)


def _ledger_query(data: dict) -> dict:
    return {"project_id": data["project_id"]}


def _opening_form(side: dict, data: dict) -> str:
    """期初占位行录入（§4.5.2）：项目 = 当前选中；截止年月默认 = 该分类已有数据最早月的前一月。"""
    if not side["has_manual_input"]:
        return '<span class="mut">派生只读，无手填入口</span>'
    d = side["opening_default"]
    hint = "（该分类暂无数据 ⇒ 回退上月）" if d.get("fallback") else ""
    return (
        f'<form class="inline" method="post" action="/m05/opening">'
        f'<input type="hidden" name="category" value="{esc(side["category"])}">'
        f'<input type="hidden" name="project_id" value="{int(data["project_id"])}">'
        f'<input class="cell" name="cutoff_ym" value="{esc(d["cutoff_ym"])}" size="8" '
        f'title="截止 YYYY-MM 底{hint}">'
        f'<input class="cell num" name="settle_amount" placeholder="结算" size="8">'
        f'<input class="cell num" name="paid_amount" placeholder="付款" size="8">'
        f'<input class="cell" name="remark" placeholder="备注" size="10">'
        f'<button type="submit">录入期初</button></form>'
    )


def _ledger_table(side: dict, data: dict) -> str:
    q = _ledger_query(data)
    out = []
    for r in side["rows"]:
        if r["is_opening"]:
            op = (
                f'<form class="inline" method="post" action="/m05/opening/delete">'
                f'<input type="hidden" name="opening_id" value="{int(side["opening_id"] or 0)}">'
                f'{_hidden(q)}<button class="dg" type="submit" title="删除该期初占位行">删除期初</button>'
                f"</form>"
            )
            month = f'<span class="tag wn">期初</span> {esc(r["month"])}'
        else:
            op = (
                f'<form class="inline" method="post" action="/m05/ledger/remark">'
                f'<input type="hidden" name="category" value="{esc(side["category"])}">'
                f'<input type="hidden" name="project_id" value="{int(data["project_id"])}">'
                f'<input type="hidden" name="ym" value="{esc(r["month"])}">'
                f'{_hidden(q)}'
                f'<input class="cell" name="remark" value="{esc(r["remark"])}" placeholder="（空=清除）" size="12">'
                f'<button type="submit">存备注</button></form>'
            )
            month = esc(r["month"])
        cells = [
            esc(r["seq"]), month,
            f'<span class="num">{esc(r["other_expense"])}</span>',
            f'<span class="num">{esc(r["payment"])}</span>',
            f'<span class="num">{esc(r["debt"])}</span>',
            esc(r["remark"]) or '<span class="mut">—</span>',
            op,
        ]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    head_items = []
    for c in LEDGER_COLUMNS:
        head_items.append(f'<th{" class=\"vsep\"" if c.get("vsep") else ""}>{esc(c["label"])}</th>')
    head = "".join(head_items)
    return (
        f'<div class="side"><h4>{esc(side["label"])}</h4>'
        f'<div style="margin-bottom:6px">{_opening_form(side, data)}</div>'
        f'<div class="gridwrap"><table class="dt" data-sort="m05:ledger:{esc(side["category"])}">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(out)}</tbody></table></div></div>"
    )


def render_m05_ledger(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """逐月台账页 —— **项目选择器就是本页的筛选控件**（两侧共用同一个，§4.5.4）。

    五段骨架照旧（口径说明 → 指标区 → **筛选栏＝项目选择器** → **数据区＝两侧对照** → 空态），
    数据区用 `data_html` 整段自定义（它不是单表，而是一张左右对照）。
    """
    opts = "".join(
        f'<option value="{int(o["id"])}"{" selected" if int(o["id"]) == data["project_id"] else ""}>'
        f'{esc(o["label"])}</option>'
        for o in data["project_options"]
    )
    picker = {
        "key": "project_id",
        "label": "项目（两侧共用 · 本页无「切换口径」按钮）",
        "html": f'<select name="project_id" form="f-m05-ledger">{opts}</select>',
    }
    sides = "".join(_ledger_table(s, data) for s in data["sides"])
    empty = ""
    if not any(s["rows"] for s in data["sides"]):
        empty = (
            f'<div data-seg="{SEG_EMPTY}" class="mut" style="padding:18px;text-align:center">'
            "该项目暂无台账数据 —— 可先录「期初占位行」，或先有付款通知书</div>"
        )
    data_html = f'<div data-seg="{SEG_DATA}"><div class="two">{sides}</div>{empty}</div>'
    body = render_list_page(
        page_id="m05-ledger",
        title="逐月欠款台账",
        tips=LEDGER_TIPS,
        kpis=[],
        filters=[picker],
        columns=[],
        data_html=data_html,
        sort_key="m05:ledger",
    )
    return _shell(
        title="逐月欠款台账",
        body=f'<form id="f-m05-ledger" method="get" action="/m05/ledger"></form>{body}',
        current="/m05/ledger", notice=_notice(message, message_kind),
    )


# ================================================================ ④ 付款统计


STATS_TIPS: tuple[str, ...] = (
    "付款统计与**逐月台账同源互补**：两处的「付款」都取自**同一个出口**（Σ统计付款金额），不另算一套（§4.5.5）。",
    "**换粒度不换口径** —— 月 / 周只改**归桶方式**，金额口径不变。",
    "归桶依据 = **单据日期**；周桶的标签取该周**周一**日期。",
    "左栏**按项目**（未判定单列）、右栏**时间轴**；默认**按周**。",
    "项目列表的展示文字 = **完整项目名** —— 不得被当成日期截断（周粒度下的历史坑）。",
)

STATS_FIXED: tuple[dict, ...] = (
    {"key": "label", "label": "项目", "sortable": True, "vsep": True},
)


def render_m05_stats(data: dict, *, message: str = "", message_kind: str = "ok") -> str:
    """付款统计页（左按项目 · 右时间轴）。"""
    buckets = data["buckets"]
    columns = list(STATS_FIXED) + [
        {"key": f"b{i}", "label": b, "sortable": False, "vsep": i == 0} for i, b in enumerate(buckets)
    ]
    rows = []
    for item in data["left"]:
        row = {"label": item["label"]}
        for i, v in enumerate(item["cells"]):
            row[f"b{i}"] = v
        rows.append(row)
    summary = {"label": "合计（时间轴）"}
    for i, v in enumerate(data["right"]):
        summary[f"b{i}"] = v
    total_row = {"label": "Σ 统计付款金额", "b0": data["total"]}
    for i in range(1, len(buckets)):
        total_row[f"b{i}"] = ""

    gran = data["granularity"]
    switches = []
    for g, label in (("week", "按周"), ("month", "按月")):
        cls = ' class="pri"' if g == gran else ""
        switches.append(
            f'<a href="/m05/stats?granularity={esc(g)}&year={data["year"]}&quarter={data["quarter"] or ""}">'
            f'<button type="button"{cls}>{esc(label)}</button></a>'
        )
    switches = "".join(switches)
    head = (
        f'<div class="pick"><div class="fi"><label>粒度（换粒度不换口径）</label>'
        f'<span>{switches}</span></div>'
        f'<div class="fi"><label>年 / 季度</label><span class="pill">{data["year"]} 年'
        + (f' · 第 {data["quarter"]} 季度' if data["quarter"] else "")
        + f'</span></div><div class="fi"><label>当前粒度</label>'
        f'<span class="pill">{esc(data["granularity_label"])}</span></div></div>'
    )
    body = render_list_page(
        page_id="m05-stats",
        title="付款统计",
        tips=STATS_TIPS,
        kpis=[
            {"k": "Σ 统计付款金额", "v": data["total"], "s": "全量（剔除行不计）"},
            {"k": "桶数", "v": len(buckets), "s": data["granularity_label"]},
            {"k": "项目数", "v": len(rows) + 1, "s": "含未判定"},
        ],
        filters=[],
        columns=columns,
        rows=rows + [total_row],
        empty_text="所选窗口内没有付款数据",
        sort_key="m05:stats",
        summary=summary,
        summary_sticky=True,
    )
    return _shell(
        title="付款统计", body=head + body, current="/m05/stats",
        notice=_notice(message, message_kind),
    )


__all__ = [
    "NAV", "FLOW_COLUMNS", "FLOW_TIPS", "DEBT_COLUMNS", "DEBT_TIPS",
    "LEDGER_COLUMNS", "LEDGER_TIPS", "STATS_TIPS",
    "render_m05", "render_m05_debt", "render_m05_ledger", "render_m05_stats",
]
