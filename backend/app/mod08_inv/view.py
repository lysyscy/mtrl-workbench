"""`MOD-08` 库存单据明细页的 HTML 装配（**服务端渲染 ＋ PRG**）。

规范：
- 页面五段骨架一律走 `page.render_list_page`（口径说明 → 指标区 → 筛选栏 → 数据区 → 空态提示行）
- 列**不写字面量**：一律来自 `domain.INV_TABLE_COLUMNS`（改列只改那一处）
- 合计行 / 空态行的跨列数由**表头列数派生**（不写死数字）
- 用户输入一律经 `esc()` 出口；「操作」列只在页面上成立（`/api/*` 导出须剔除）

⚠️ 口径说明块**恒为 1 个**（设计规则 `R1`）；不写进度、不复述取值。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc, render_list_page
from app.mod08_inv import domain as D

PAGE_ID = "m08"
TITLE = "库存单据明细总表"

TIPS = (
    "**库存单据明细 = 对账主工具**（§5.4）：每张单据的每一行都在这里，平时对账主要看它。",
    "**两把钥匙都在**：同时带「仓库名」与「项目全名」，是三张核心表里最可靠的一张。",
    "**调整单（ENT-04）** 打在单据行上、**不被 i8 导出覆盖**，必须**留痕 + 留备注**；"
    "差异的修正只改库存单据 —— 过程资料的材料费**引用自本页**，随之反映。",
    "**三张产出**：单据明细总表（对账 / 调整单 + 留痕）· 过程资料透视（和项目交来的 Excel 对账）"
    "· 特殊费用月报表（独立新报表）。",
)

EXTRA_CSS = """
.dlg{border:1px solid var(--bd);border-radius:8px;padding:14px 16px;background:var(--sf);max-width:520px}
.dlg::backdrop{background:rgba(0,0,0,.28)}
.cfp{border:1px solid var(--bd);border-radius:6px;padding:10px;background:var(--sf2)}
.cfp table{border-collapse:collapse;font-size:12px}
.cfp td{padding:3px 8px;vertical-align:top}
.cfp .vlist{max-height:96px;overflow:auto;display:block}
.cfp label{white-space:nowrap;font-size:12px}
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
.warn{border:1px solid var(--wn-bd);background:var(--wn-l);color:var(--wn-d);padding:8px 12px;border-radius:6px;margin:8px 0}
"""


def money_text(value) -> str:
    """金额显示（千分位 · 2 位小数）；空值 ⇒ 空串（**不臆造 0**）。"""
    if value in (None, ""):
        return ""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:  # noqa: BLE001 - 非金额列一律原样
        return str(value)


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _cell_html(row: dict, key: str) -> str:
    if key == "ops":
        row_id = row.get("id")
        label = "查看/改调整单" if D.is_adjusted(row) else "打调整单"
        return f'<a class="btn sm" href="/m08/adjust/{esc(row_id)}">{label}</a>'
    if D.column_meta(key) and D.column_meta(key)["type"] == "num":
        return esc(money_text(D.raw_value(row, key)))
    return esc(D.cell_text(row, key))


def _rows_html(rows: list[dict]) -> str:
    body: list[str] = []
    for row in rows:
        cls = ' class="hl"' if D.is_adjusted(row) else ""
        tds = "".join(
            f'<td class="{"num" if c["type"] == "num" else ""}">{_cell_html(row, c["key"])}</td>'
            for c in D.INV_TABLE_COLUMNS
        )
        body.append(f"<tr{cls}>{tds}</tr>")
    return "".join(body)


def _summary_row(sums: dict) -> dict:
    """合计行：首格写「合计」（排序时被钉在表尾），数值列按 `sum_cells` 出口取值。"""
    out = {c["key"]: "" for c in D.INV_TABLE_COLUMNS}
    out[D.INV_TABLE_COLUMNS[0]["key"]] = "合计"
    for key in D.SUM_KEYS:
        out[key] = money_text(sums.get(key))
    return out


def _period_input(state: dict) -> str:
    return (
        '<input class="inp" name="period" style="min-width:190px" '
        f'value="{esc(state.get("period") or "")}" '
        'placeholder="2026-08 / 2026-01~2026-06 / 2026 / 留空=全部">'
    )


def _project_select(state: dict, projects: list[str]) -> str:
    chosen = {str(p) for p in (state.get("projects") or ())}
    opts = "".join(
        f'<option value="{esc(p)}"{" selected" if p in chosen else ""}>{esc(p)}</option>'
        for p in projects
    )
    return f'<select name="pj" multiple size="4" style="min-width:170px">{opts}</select>'


def _dir_select(state: dict) -> str:
    cur = state.get("direction") or D.DIRECTION_ALL
    opts = "".join(
        f'<option value="{esc(d)}"{" selected" if d == cur else ""}>{esc(d)}</option>'
        for d in D.DIRECTIONS
    )
    return f'<select name="dir">{opts}</select>'


def _only_adj_select(state: dict) -> str:
    on = bool(state.get("only_adjusted"))
    return (
        '<select name="only_adj">'
        f'<option value="0"{" selected" if not on else ""}>否</option>'
        f'<option value="1"{" selected" if on else ""}>是</option>'
        "</select>"
    )


def column_filter_panel(state: dict, values: dict) -> str:
    """**列筛选面板**：除末列「操作」外**每列**都给筛选入口（Excel 式语义，服务端实现）。

    - 文本 / 日期列 → 「包含」输入 ＋ 值清单多选
    - 枚举列 → 值清单多选
    - 数值列 → 「≥ / ≤」**区间** ＋ 值清单多选（两者都给；勾选**真的生效**）
    列内条件「与」、列间条件「与」；已设条件的列在标题上带「·」。
    """
    filters = state.get("col_filters") or {}
    hidden = "".join(
        [f'<input type="hidden" name="period" value="{esc(state.get("period") or "")}">']
        + [f'<input type="hidden" name="pj" value="{esc(p)}">' for p in (state.get("projects") or ())]
        + [f'<input type="hidden" name="dir" value="{esc(state.get("direction") or "")}">']
        + ([f'<input type="hidden" name="only_adj" value="1">'] if state.get("only_adjusted") else [])
    )
    rows_html: list[str] = []
    for col in D.INV_TABLE_COLUMNS:
        key = col["key"]
        if key in D.PAGE_ONLY_KEYS:
            continue
        f = filters.get(key) or {}
        hit = " ·" if key in filters else ""
        parts: list[str] = []
        if col["type"] in ("text", "date", "num"):
            parts.append(
                f'<input class="inp" style="width:150px" name="f_{key}" '
                f'value="{esc(f.get("q") or "")}" placeholder="包含…">'
            )
        if col["type"] == "num":
            parts.append(
                f'<input class="inp num" style="width:78px" name="f_{key}_min" '
                f'value="{esc(f.get("min") or "")}" placeholder="≥">'
                f'<input class="inp num" style="width:78px" name="f_{key}_max" '
                f'value="{esc(f.get("max") or "")}" placeholder="≤">'
            )
        picked = {str(v) for v in (f.get("v") or ())}
        checks = "".join(
            f'<label><input type="checkbox" class="chk" name="f_{key}_v" value="{esc(v)}"'
            f'{" checked" if v in picked else ""}> {esc(v)}</label>'
            for v in (values.get(key) or [])
        )
        parts.append(
            f'<span class="vlist">{checks or "<span class=mut>该列当前无值</span>"}</span>'
        )
        rows_html.append(
            f'<tr><td><b>{esc(col["label"])}{hit}</b></td><td>{"".join(parts)}</td></tr>'
        )
    return (
        f'<form class="cfp" method="get" action="/m08">{hidden}'
        '<div class="mut" style="margin-bottom:6px">列筛选（Excel 式：每列一个入口；'
        '条件之间是「与」；数值列既给区间、也可勾具体值）</div>'
        f'<table>{"".join(rows_html)}</table>'
        '<div style="margin-top:8px"><button class="btn" type="submit">应用列筛选</button>'
        ' <a class="btn" href="/m08">清除全部列筛选</a></div>'
        "</form>"
    )


def fetch_dialog_html(default_month: str, back: str = "/m08") -> str:
    """「按月抓取」弹窗 —— **默认月份 = 本页当前所选核算年月**（001-11）。

    ⚠️ 抓取只允许单月（§9.2）；且**必须事先告知会登录 i8 并强踢在线用户**，
    并**要求二次确认**（D9）—— 未勾选就在路由层拒绝。
    """
    from app.mod08_inv.fetch_service import CONFIRM_TOKEN, KICK_WARNING

    return (
        '<dialog class="dlg" id="fetchDlg">'
        "<h4>按月抓取 · 库存单据明细表（API-03）</h4>"
        '<form method="post" action="/m08/fetch">'
        f'<input type="hidden" name="back" value="{esc(back)}">'
        '<div class="fi"><label>核算年月（**单月**：起止同月）</label>'
        f'<input class="inp" id="fetchMonth" name="month" value="{esc(default_month)}" '
        'placeholder="YYYY-MM"></div>'
        f'<div class="warn">{esc(KICK_WARNING)}</div>'
        '<label class="sm"><input type="checkbox" name="confirm" '
        f'value="{esc(CONFIRM_TOKEN)}"> 我已知晓**会强踢在线用户**，确认抓取</label>'
        '<div style="margin-top:10px">'
        '<button class="btn" type="button" '
        'onclick="document.getElementById(\'fetchDlg\').close()">取消</button>'
        '<button class="btn pri" type="submit" data-act="fetchOne">开始抓取</button>'
        "</div></form></dialog>"
    )


def _flash_html(flash: dict | None) -> str:
    """抓取结果的**回执条**（成功 / 降级 / 用法错误）—— 降级必须**显式说明**（§3.6）。"""
    if not flash:
        return ""
    kind = str(flash.get("kind") or "")
    if kind == "ok":
        st = flash.get("stats") or {}
        return (
            '<div class="notice ok">抓取成功：<b>%s</b> 共 <b>%s</b> 行 —— '
            "新增 %s · 更新 %s · 删除 %s · <b>因有调整单而保留 %s</b>（§5.2.4：调整单不被 i8 导出覆盖）"
            "</div>"
            % (esc(flash.get("ym")), esc(flash.get("rows")), esc(st.get("inserted")),
               esc(st.get("updated")), esc(st.get("deleted")), esc(st.get("kept_with_adjustment")))
        )
    if kind == "degraded":
        return ('<div class="notice wn"><b>已降级为手动 Excel 导入</b>（§3.6）—— %s '
                '<a class="btn sm" href="/m08/import" data-act="manualImport">'
                "去手动导入 Excel →</a></div>"
                % esc(flash.get("message")))
    return '<div class="notice err">%s</div>' % esc(flash.get("message"))


def render_inv_page(data: dict, flash: dict | None = None) -> str:
    state = data["state"]
    filters = [
        {"label": "核算年月", "html": _period_input(state)},
        {"label": "项目（键 = 仓库名）", "html": _project_select(state, data["projects"])},
        {"label": "出入库方向", "html": _dir_select(state)},
        {"label": "只看被调整行", "html": _only_adj_select(state)},
        {"label": "", "html": '<button class="btn pri" type="submit">查询</button>'
                              ' <a class="btn" href="/m08">重置</a>'},
    ]
    buttons = []
    for kind in data["export_kinds"]:
        act = "exp" if kind["id"] == D.EXPORT_PLAIN else "expPivot"
        cls = "btn pri" if kind["id"] == D.EXPORT_PLAIN else "btn"
        buttons.append(
            f'<button class="{cls}" data-act="{act}" data-t="{esc(TITLE)}" '
            f'title="{esc(kind["hint"])}">{esc(kind["label"])}</button>'
        )
    buttons.insert(
        0,
        '<button class="btn" type="button" '
        'onclick="document.getElementById(\'fetchDlg\').showModal()">抓取 i8</button>'
        ' <a class="btn" href="/m08/import" data-act="manualImport"'
        ' title="i8 接口不可用时的降级通道（§3.6）：上传 i8 导出的 xlsx，'
        '走同一条解析 → 幂等落库管线">手动导入 Excel</a>',
    )
    filters.append({"label": "动作", "html": " ".join(buttons)})

    columns = [
        {"key": c["key"], "label": c["label"], "sortable": c["key"] not in D.PAGE_ONLY_KEYS}
        for c in D.INV_TABLE_COLUMNS
    ]
    section = render_list_page(
        page_id=PAGE_ID,
        title=f"{TITLE}（{len(data['rows'])} 行 · 入库 / 出库 / 调整净额见合计行）",
        tips=TIPS,
        filters=filters,
        columns=columns,
        rows_html=_rows_html(data["rows"]),
        summary=_summary_row(data["sums"]),
        empty_text="当前筛选条件下没有库存单据明细 —— 换个「核算年月 / 项目 / 出入库方向」，"
                   "或清掉列筛选",
        sort_key="m08:inv_detail",
        filter_action="/m08",                 # ⚠️ 不给 ⇒ 「查询」按钮是死的（控件不在表单里）
    )
    extra = (
        _flash_html(flash)
        + column_filter_panel(state, data["values"])
        + fetch_dialog_html(data["fetch_default_month"])
        + '<div class="mut sm" style="margin-top:6px">合计行只求<b>数量 / 金额 / 调整后金额 / 价税合计</b>；'
          '两个<b>单价列刻意不求和</b>（单位价求和无业务含义）⇒ 留空。</div>'
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>库存单据与调整单</h1><nav>{_nav_html()}</nav></div>'
        f"{section}{extra}"
        "</div></body></html>"
    )


def render_adjust_page(*, row: dict, adj: dict | None, errors: list[str] | None = None,
                       back: str = "/m08") -> str:
    """**调整单**页（打单 / 查改）—— 原始值只读、只改「调整后金额」＋ **必填备注**。"""
    err = "".join(f'<div class="warn">{esc(e)}</div>' for e in (errors or ()))
    kv = "".join(
        f"<div><b>{esc(k)}</b><span>{esc(v)}</span></div>"
        for k, v in (
            ("单据编号", f'{row.get("doc_no")} #{row.get("seq")}'),
            ("物料", f'{row.get("material")} {row.get("spec")}'.strip()),
            ("仓库", row.get("warehouse")),
            ("核算年月", row.get("ym")),
            ("i8 原始金额", money_text(row.get("amount"))),
        )
    )
    trail = ""
    if adj:
        trail = (
            '<div class="warn">留痕：金额 %s → %s；操作人 / 时间：%s · %s</div>'
            % (esc(money_text(adj.get("before"))), esc(money_text(adj.get("after"))),
               esc(adj.get("operator") or ""), esc(adj.get("at") or ""))
        )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>调整单 · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>调整单</h1><nav>{_nav_html()}</nav></div>'
        f'<div class="kv">{kv}</div>{err}{trail}'
        f'<form class="dlg" method="post" action="/m08/adjust/{esc(row.get("id"))}">'
        f'<input type="hidden" name="back" value="{esc(back)}">'
        '<div class="fi"><label>调整后金额 <b>*</b>（≥ 0；0 合法，负值不接受）</label>'
        f'<input class="inp num" name="amount" value="{esc(money_text(adj.get("after") if adj else row.get("amount")))}"></div>'
        '<div class="fi"><label>调整备注 <b>*</b>（说明为什么调）</label>'
        f'<input class="inp" name="remark" value="{esc((adj or {}).get("remark") or "")}"></div>'
        '<div style="margin-top:10px"><button class="btn pri" type="submit">保存调整单</button>'
        f' <a class="btn" href="{esc(back)}">返回</a></div>'
        '<div class="mut sm" style="margin-top:6px">调整单**独立存储** ⇒ i8 重新导出只刷新原始表、不动它；'
        '原始值恒可追溯。</div>'
        "</form></div></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "money_text",
           "column_filter_panel", "fetch_dialog_html", "render_inv_page", "render_adjust_page"]
