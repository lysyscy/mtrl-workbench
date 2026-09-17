"""`MOD-09` 特殊费用月报表页的 HTML 装配（**服务端渲染 ＋ PRG**）。

规范：
- 五段骨架走 `page.render_list_page`（口径说明 → 指标区 → 筛选栏 → 数据区 → 空态提示行）；
  **数据区整段自渲染**（本表 = 自动项行 ＋ N 个手填行 ＋ 合计行，骨架的单表合计满足不了）
- 列**不写字面量**：一律来自 `domain.AWF_COLUMNS`（改列只改那一处）
- 空态提示行 / 合计行的**跨列数由表头列数派生**（不写死）
- 用户输入一律经 `esc()` 出口；**「操作」列只在页面上成立**（`domain.PAGE_ONLY_KEYS`）
- ⚠️ 口径说明块**恒为 1 个**（设计规则 `R1`）；不写进度、不复述取值

⛔ 本页**不给单独的导出按钮** —— 它随「逐月欠款台账」导出（§5.5 / §7.1，见页面卡底说明）。
"""

from __future__ import annotations

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc, render_list_page
from app.mod09_fee import domain as D

PAGE_ID = "m09"
TITLE = "特殊费用月报表"

TIPS = (
    "**本页 = 「特殊费用月报表」**（§5.5）—— 一张**独立的新报表**，**不是**库存单据的第 3 张透视表："
    "它 = **1 个自动项**（安全文明施工费，按 CBS 分类）+ **N 个手填项**（可增项、项名可改）。",
    "⚠️ **「安文费」是那个 CBS 类目的名字，不是这张报表的名字** —— 两者别混着叫。",
    "**自动项来源**：库存单据明细的 WBS / CBS 字段 —— 取该 **核算年月 ＋ 该项目** 下 "
    "`CBS-安文费` 类目的**出库**金额（**只读，不可改**）。",
    "**手填项按「核算年月 ＋ 项目」各存一份**（项目键 = 仓库名，§2.7.4）；"
    "**未录的那一份不做带入**（带入只属活动大表 §5.7.2）—— 为空即表示「该月 · 该项目」还没录。",
    "取值判据：手填项**只拦「非数字」，允许 0 与负数**（§8.4 三档中的**最宽松**一档 —— "
    "手填项是「自行加项」的费用行、可能是调整性质）。",
)

EXTRA_CSS = """
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
.head{display:flex;align-items:center;gap:10px;margin:6px 0 10px}
.head h4{font-size:15px;margin:0}
.head .sp{margin-left:auto;display:flex;align-items:center;gap:8px}
.head form{margin:0}
.pjsel{display:flex;flex-direction:column;gap:4px;max-height:180px;overflow:auto;padding:6px 2px}
.pjsel label{font-size:12.5px;white-space:nowrap}
.note{border:1px solid var(--bd);border-radius:6px;padding:8px 12px;margin:8px 0;font-size:12.5px;color:var(--tx2);background:var(--sf)}
.notice{border-radius:6px;padding:8px 12px;margin:8px 0;font-size:13px}
.notice.ok{border:1px solid var(--ok-bd);background:var(--ok-l);color:var(--ok-d)}
.notice.err{border:1px solid var(--dg-bd);background:var(--dg-l);color:var(--dg-d)}
.tw{max-height:none}
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _flash_html(flash: dict | None) -> str:
    """写动作的回执条（**必须显式**：删除要带「重算后的合计」，非法输入要说清"已保留原值"）。"""
    if not flash:
        return ""
    kind = "ok" if str(flash.get("kind")) == "ok" else "err"
    return f'<div class="notice {kind}">{esc(flash.get("message") or "")}</div>'


def _project_panel(state: dict, cands: list) -> str:
    """项目选择：**单选（radio）**、**不给全选 / 清空**、**选中即提交并收起**（001-06）。

    ⚠️ 候选**只给键（仓库名）**做值 —— **不得渲染成对象字面量**（`[object Object]`，001-06）。
    ⚠️ 本控件**裸放在筛选栏那一个 GET 表单里**（不自己包 `<form>` ⇒ 否则嵌套两层表单）。
    """
    cur = state.get("project") or ""
    radios = "".join(
        f'<label><input type="radio" name="pj" value="{esc(c.key)}"'
        f'{" checked" if c.key == cur else ""} onchange="this.form.submit()"> {esc(c.display)}'
        f'{esc("（归档）" if c.archived else "")}</label>'
        for c in cands
    ) or '<span class="mut">（档案里还没有带仓库的项目 —— 先去「项目档案」建档）</span>'
    return f'<details open><summary>切换项目（单选 · 键 = 仓库名）</summary><div class="pjsel">{radios}</div></details>'


def _ym_input(state: dict) -> str:
    """核算年月 —— **只开放「按月」**（§5.5 能力 8）：用 `type="month"`，天然给不出跨月 / 整年 / 全部。"""
    return (f'<input type="month" name="ym" style="min-width:150px" '
            f'value="{esc(state.get("ym") or "")}">')


def _tag(text: str, kind: str) -> str:
    return f'<span class="tag {kind}">{esc(text)}</span>'


def _auto_row_html(row: dict) -> str:
    """自动项行（**只读**）：恒为第一条数据行，操作格写「自动项不可改」。"""
    return (
        '<tr data-kind="auto">'
        f'<td><b>{esc(D.AUTO_NAME_MAIN)}</b>（{esc(D.AUTO_NAME_NOTE)}）</td>'
        f'<td>{_tag(row["source"], "ok")}</td>'
        f'<td class="num">{esc(D.money_text(row["amount"]))}</td>'
        f'<td class="num">{esc(row["share"])}</td>'
        f'<td class="ctr mut">{esc(row["ops"])}</td>'
        "</tr>"
    )


def _manual_row_html(row: dict) -> str:
    """手填行：项名可改 · 金额可填 · 可删（**都在同一个 POST 表单里，靠 `op` 指明哪一行**）。"""
    i = row["index"]
    return (
        f'<tr data-kind="manual" data-i="{i}">'
        f'<td><input class="cell" name="name_{i}" value="{esc(row["item"])}" '
        f'placeholder="项名（可改、可加项）"></td>'
        f'<td>{_tag(row["source"], "wn")}</td>'
        f'<td class="num"><input class="cell num" style="width:120px" name="amount_{i}" '
        f'value="{esc(D.money_text(row["amount"]))}"></td>'
        f'<td class="num">{esc(row["share"])}</td>'
        f'<td class="ctr"><button class="btn sm" type="submit" name="op" value="save:{i}">保存</button> '
        f'<button class="btn sm" type="submit" name="op" value="del:{i}">删除</button></td>'
        "</tr>"
    )


def _empty_row_html(ym: str, project_display: str) -> str:
    """空态提示行（001-05）：**跨列数 = 表头列数**（由 `AWF_COLUMNS` 派生，不写死）。"""
    return (
        f'<tr class="empty" data-seg="empty"><td colspan="{D.EMPTY_COLSPAN}">'
        f"<b>{esc(ym)}</b> · <b>{esc(project_display)}</b> 还没有手填项 —— "
        f"点上方「＋ 增加手填项」补录（按「核算年月 ＋ 项目」各存一份，未录的那一份不计入）"
        "</td></tr>"
    )


def _sum_row_html(summary: dict) -> str:
    """合计行（表内、`sumrow` 吸附置底）：合计 = 自动项 ＋ Σ 手填项。"""
    cells = []
    for col in D.AWF_COLUMNS:
        key = col["key"]
        cls = "num" if col["type"] == "num" else ("ctr" if key == "ops" else "")
        value = summary.get(key) or ""
        cells.append(f'<td class="{cls}">{esc(value)}</td>')
    return f'<tr class="sumrow">{"".join(cells)}</tr>'


def _table_html(data: dict) -> str:
    rows = [_auto_row_html(data["auto"])]
    rows += [_manual_row_html(r) for r in data["manuals"]]
    if not data["manuals"]:
        rows.append(_empty_row_html(data["ym"], data["project_display"]))
    rows.append(_sum_row_html(data["summary"]))
    head = "".join(
        f'<th class="{"num" if c["type"] == "num" else ""}">{esc(c["label"])}</th>'
        for c in D.AWF_COLUMNS
    )
    return (
        '<div class="tw" data-seg="data">'
        f'<table class="dt" data-sort-key="m09:awf"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _data_html(data: dict) -> str:
    """数据区 = **增加手填项的 POST 表单**（独立于筛选栏那个 GET 表单，避免嵌套）＋ 表格。"""
    state = data["state"]
    add_form = (
        '<div class="head"><h4>特殊费用月报表</h4><span class="sp">'
        f'<form method="post" action="/m09/add">'
        f'<input type="hidden" name="ym" value="{esc(state.get("ym") or "")}">'
        f'<input type="hidden" name="pj" value="{esc(state.get("project") or "")}">'
        '<button class="btn" type="submit">＋ 增加手填项</button></form>'
        f'<span class="pill" title="{esc(D.EXPORT_NOTE)}">{esc(D.EXPORT_NOTE)}</span>'
        "</span></div>"
    )
    return add_form + f'<form method="post" action="/m09/cell">{_table_html(data)}</form>'


def render_fee_page(data: dict, flash: dict | None = None) -> str:
    state = data["state"]
    filters = [
        {"label": "项目（单选 · 键 = 仓库名）", "html": _project_panel(state, data["projects"])},
        {"label": "核算年月（只按月）", "html": _ym_input(state)},
        {"label": "", "html": '<button class="btn pri" type="submit">查询</button>'
                              f' <a class="btn" href="/m09">重置</a>'},
        {"label": "", "html": f'<span class="pill">1 个自动项 ＋ <b>{data["count"]}</b> 个手填项 ｜ '
                             '每项目每月一份 ｜ 报分公司工程科</span>'},
    ]
    section = render_list_page(
        page_id=PAGE_ID,
        title=f"{TITLE} · {data['ym']} · {data['project_display'] or '（未选项目）'}",
        tips=TIPS,
        filters=filters,
        data_html=_data_html(data),
        filter_action="/m09",          # ⚠️ 不给 ⇒ 「查询」按钮是死的（控件不在表单里）
    )
    extra = (
        _flash_html(flash)
        + '<div class="note"><b>自动项来源：</b>库存单据明细的 WBS / CBS 字段 —— '
          f'本页取 <b>{esc(D.CBS_AWF)}</b> 类目的<b>{esc(D.DIRECTION_OUT)}</b>金额，'
          '**按所选核算年月 ＋ 所选项目**（项目按仓库名取，§2.7.4）。'
          '<b>手填项按「核算年月 ＋ 项目」各存一份</b>；未录的那一份<b>不做带入</b>，'
          '为空即表示"该月 · 该项目"还没录。</div>'
        + f'<div class="note">{D.EXPORT_BOUNDARY} —— {esc(D.EXPORT_NOTE)}。</div>'
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>特殊费用月报表</h1><nav>{_nav_html()}</nav></div>'
        f"{section}{extra}"
        "</div></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "render_fee_page"]
