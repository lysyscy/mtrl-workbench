"""`MOD-07` **经济活动分析大表**页面的 HTML 装配（服务端渲染）。

规范：
- 五段骨架走 `page.render_list_page`；**数据区自己渲染**（`data_html`）—— 因为本表是
  **两行表头 + 刻意不可排**（§5.7.1 的 20 列最终模板：两行表头的 `<th>` 数与数据列数不等，
  排序会整体错位）。
- 列**不写字面量**：表头与列一律来自 `big_domain.BIG_HEADER` / `BIG_COLUMNS`（同一份）。
- 合计数由**表头叶数派生**（不写死 20）。
- 用户输入一律经 `esc()`；手填格**每格一个表单**（保存只作用于这一格，001-06）。

⛔ 本页**不得**出现「材料费 / 租分公司设备 / 不含税列 / 列设置 / 列宽 / 督办 / A3」——
   由 `big_domain.boundary_violations` 在**自检里**钉住（`tests/test_acc_rpt_big.py` 有反向灵敏度）。
"""

from __future__ import annotations

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc, render_list_page
from app.mod07_setl import big_domain as B
from app.mod07_setl.view import money_text

PAGE_ID = "m07-big"
from app.mod07_setl.big_domain import TITLE  # noqa: F401  ← 唯一出处已搬到域内核（`§19` 批 2）

TIPS = (
    "**手填 6 列**：开工时间（`YYYY-MM`）/ 机械费测算 / 合同（预估）价 / 产值累计（含税）/ 工程用油 / 备注；"
    "**其余列都是自动或派生**（材料与机械的取数列、派生列**一律只读**）。",
    f"**三个派生列**：{B.TOTAL_FORMULA} · {B.USE_RATE_FORMULA} · {B.OUTPUT_RATE_FORMULA}。",
    f"**主材累计（含税）**：{B.MAIN_MATERIAL_NOTE}",
    f"**出纸**：{B.PRINT_CHANNEL}（本系统**不提供页面打印**，§1.4.1）；**手填列不做补正** —— 错了就错了，下月填对（§5.7.2）。",
)

EXTRA_CSS = """
.dlg{border:1px solid var(--bd);border-radius:8px;padding:14px 16px;background:var(--sf);max-width:720px}
.dlg::backdrop{background:rgba(0,0,0,.28)}
.dlg h4{margin:0 0 8px;font-size:14px}
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
table.dt td.bigc{position:relative}
table.dt td.bigc input.inp{width:104px;padding-left:26px}
table.dt td.bigc em.ctag{position:absolute;left:6px;top:2px;font-size:9.5px;font-style:normal;color:var(--wn)}
.bigform{display:inline-flex;align-items:center;gap:2px;margin:0}
.pjsel{display:flex;flex-wrap:wrap;gap:6px 12px;max-height:220px;overflow:auto}
.pjsel label{white-space:nowrap}
.orderlist{display:flex;flex-direction:column;gap:4px;max-height:220px;overflow:auto}
.orderlist .oi{display:flex;align-items:center;gap:6px}
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _thead() -> str:
    """两行表头（逐列来自 `BIG_HEADER`）—— 列数由表头叶数派生，⛔ 不写死。"""
    top, bottom = [], []
    for group, subs in B.BIG_HEADER:
        if not subs:
            top.append(f'<th rowspan="2">{esc(group)}</th>')
        else:
            top.append(f'<th colspan="{len(subs)}">{esc(group)}</th>')
            bottom.extend(f"<th>{esc(s)}</th>" for s in subs)
    return f"<tr>{''.join(top)}</tr>" + (f"<tr>{''.join(bottom)}</tr>" if bottom else "")


def _cell_html(row: dict, col: dict, *, month: str) -> str:
    """一格（手填 ⇒ 表单 + 输入框；自动 / 派生 ⇒ 只读文本）。"""
    key, kind, fmt = col["key"], col["kind"], col["fmt"]
    value, source = B.cell_value(row, key)
    if kind != B.KIND_HAND:
        if key == "seq":
            text = str(value or "")
        elif key == "project":
            text = esc(str(value or ""))
        elif fmt == B.FMT_RATE:
            text = esc(B.rate_text(value)) if value is not None else '<span class="mut">—</span>'
        elif value is None:
            # 取数口未接入（主材累计）⇒ 「—」+ 说明；⛔ 绝不写 0（那会冒充"确实没有"）
            text = f'<span class="mut" title="{esc(B.MAIN_MATERIAL_UNAVAILABLE)}">—</span>'
        else:
            text = esc(money_text(value))
        cls = "num" if fmt in (B.FMT_MONEY, B.FMT_RATE) else ("ctr" if key == "seq" else "sm")
        return f'<td class="{cls}">{text}</td>'

    mark = (f'<em class="ctag" title="带入自 {esc(source)} 的最近一次录入值（未确认，改一下就转为本月录入）">'
            f'↺{esc(source[5:])}月</em>') if source else ""
    tip = (f"带入自 {source} 的最近一次录入值（未确认）" if source else f"{month} 本月手填")
    if fmt == B.FMT_TEXT:
        ph, cls = "可填", ""
    elif fmt == B.FMT_YM:
        ph, cls = "YYYY-MM", ""
    else:
        ph, cls = "待填", "num "
    return (
        f'<td class="num bigc">{mark}'
        f'<form class="bigform" method="post" action="/m07/big/cell">'
        f'<input type="hidden" name="period" value="{esc(month)}">'
        f'<input type="hidden" name="wh" value="{esc(row["warehouse"])}">'
        f'<input type="hidden" name="key" value="{esc(key)}">'
        f'<input class="inp {cls}{"ed" if source else ""}" name="value"'
        f' value="{esc(_disp(value, fmt))}" placeholder="{esc(ph)}" title="{esc(tip)}">'
        f'<button class="btn sm" type="submit" title="保存这一格（只动这一格）">✓</button>'
        "</form></td>"
    )


def _disp(value, fmt: str) -> str:
    """输入框里的值（`ym` / `text` 原样；金额 2 位小数；空 ⇒ 空串）。"""
    if value in (None, ""):
        return ""
    if fmt == B.FMT_MONEY:
        return f"{value:.2f}" if hasattr(value, "quantize") else str(value)
    return str(value)


def _totals_html(totals: dict) -> str:
    """合计行 —— 前两列合并放「合计」标签；其余逐列取自 `totals`（**比率列 / 开工时间 / 备注留空**，照原型）。"""
    cells = ['<td colspan="2" class="ctr">合计</td>']
    for col in B.BIG_COLUMNS[2:]:
        key = col["key"]
        if key not in B.TOTAL_KEYS:
            cells.append("<td></td>")
            continue
        v = totals.get(key)
        # 取数口未接入（主材累计）⇒ 「—」，⛔ 不写 0
        cells.append('<td class="num">' + ("<span class=\"mut\">—</span>" if v is None
                                           else esc(money_text(v))) + "</td>")
    return '<tr class="sumrow">' + "".join(cells) + "</tr>"


def _pick_panel(data: dict) -> str:
    """「选题」面板：候选多选（默认 = 全部候选）＋ 顺序调节（逐项上移 / 下移）。"""
    sel = list(data["selected"])
    boxes = "".join(
        f'<label><input class="chk" type="checkbox" name="pj" value="{esc(c["warehouse"])}"'
        f'{" checked" if c["warehouse"] in sel else ""}> {esc(c["display"])}</label>'
        for c in data["candidates"]
    ) or '<span class="mut">（项目档案里还没有「在建 · 非壳」的项目 —— 先去项目档案建档 / 同步）</span>'
    order_items = "".join(
        f'<div class="oi"><span class="sm">{i + 1}. {esc(w)}</span>'
        f'<form class="bigform" method="post" action="/m07/big/move">'
        f'<input type="hidden" name="period" value="{esc(data["month"])}">'
        f'<input type="hidden" name="wh" value="{esc(w)}">'
        f'<input type="hidden" name="dir" value="up">'
        f'<button class="btn sm" type="submit" title="上移一格">↑</button></form>'
        f'<form class="bigform" method="post" action="/m07/big/move">'
        f'<input type="hidden" name="period" value="{esc(data["month"])}">'
        f'<input type="hidden" name="wh" value="{esc(w)}">'
        f'<input type="hidden" name="dir" value="down">'
        f'<button class="btn sm" type="submit" title="下移一格">↓</button></form></div>'
        for i, w in enumerate(sel)
    ) or '<span class="mut">（表里还没有项目）</span>'
    return (
        '<details class="tip" data-seg="big-pick"><summary>选题（'
        f'{len(sel)} 项 · 可调顺序）</summary>'
        f'<div class="mut sm" style="margin:6px 0">{esc(B.SELECT_NOTE)}</div>'
        '<form method="post" action="/m07/big/pick">'
        f'<input type="hidden" name="period" value="{esc(data["month"])}">'
        f'<div class="pjsel">{boxes}</div>'
        '<div class="fi" style="margin-top:8px">'
        '<button class="btn sm" type="submit" name="selall" value="1">全选</button>'
        '<button class="btn sm" type="submit" name="selnone" value="1">清空</button>'
        '<button class="btn sm pri" type="submit">确定</button>'
        f'<span class="mut sm">候选 {len(data["candidates"])} 项（**在建 · 非壳**）</span></div>'
        "</form>"
        f'<div class="orderlist" style="margin-top:10px">{order_items}</div>'
        "</details>"
    )


def render_big_page(data: dict, flash: dict | None = None) -> str:
    month = data["month"]
    rows = data["rows"]
    filters = [
        {"label": "核算年月", "html":
            f'<input class="inp" type="month" name="period" value="{esc(month)}">'},
        {"label": "", "html": '<button class="btn pri" type="submit">查询</button>'
                              ' <a class="btn" href="/m07/big">重置</a>'},
        {"label": "动作", "html":
            f'<a class="btn pri" href="/m07/big/export?period={esc(month)}">按模板导出（Excel 打印）</a>'},
        {"label": "", "html":
            f'<span class="pill">项目 {len(rows)} · 候选 {len(data["candidates"])} · '
            f'带入 {data["carry_n"]} 格</span>'},
    ]
    body = "".join(
        "<tr>"
        + "".join(_cell_html(r, c, month=month) for c in B.BIG_COLUMNS)
        + "</tr>"
        for r in rows
    )
    table = (
        '<div class="tw"><table class="dt nosort" data-sort-key="m07:bigtable" style="min-width:1620px">'
        f"<thead>{_thead()}</thead><tbody>{body}{_totals_html(data['totals']) if rows else ''}"
        "</tbody></table></div>"
    )
    empty = (f'<div data-seg="empty"><div class="empty">{esc(B.empty_text(month))}</div></div>'
             if not rows else "")
    note = "" if data["mat_available"] else (
        f'<div class="mut sm" style="margin:6px 0">⚠️ {esc(B.MAIN_MATERIAL_NOTE)}'
        f'—— 集采台账（`MOD-11`）**尚未落地** ⇒ 该列暂显「—」（**不写 0**，免得冒充"确实没有"）。</div>')
    ex = (f'<div class="mut sm" style="margin-top:6px">出纸方式 = <b>{esc(B.PRINT_CHANNEL)}</b>；'
          "<b>本系统不提供页面打印</b>；手填列<b>不做补正</b>（§5.7.2）。</div>")
    data_area = (
        note + _pick_panel(data)
        + f'<div data-seg="data">{table}</div>' + empty
        + f'<div class="ma">{_flash_html(flash)}{ex}</div>'
    )
    section = render_list_page(
        page_id=PAGE_ID,
        title=f"{TITLE}（{month}）",
        tips=TIPS,
        filters=filters,
        columns=[],
        data_html=data_area,
        filter_action="/m07/big",
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>收发结存与活动大表</h1><nav>{_nav_html()}</nav></div>'
        f"{section}</div></body></html>"
    )


def _flash_html(flash: dict | None) -> str:
    if not flash or not flash.get("message"):
        return ""
    kind = str(flash.get("kind") or "warn")
    kind = kind if kind in ("ok", "warn", "err") else "warn"
    return f'<div class="notice {kind}">{esc(flash["message"])}</div>'


def render_export_page(data: dict) -> str:
    """「按模板导出」的**清单预览**（与页面**同一份行装配** ⇒ 两处同序同值）。

    ⚠️ **真实文件落盘 / 打包不在这里** —— 归切片 6 的 `ACC-X-EXP-001`（`TAIL-04`）；
       本页只出**导出形态**（模板列 / 数据区起点 / 行序），并把"出纸 = Excel 打印"写明。
    """
    month = data["month"]
    rows = data["rows"]
    body = "".join(
        "<tr>" + "".join(
            f'<td class="{"num" if c["fmt"] in (B.FMT_MONEY, B.FMT_RATE) else "sm"}">'
            + (esc(B.rate_text(B.cell_value(r, c["key"])[0]))
               if c["fmt"] == B.FMT_RATE and B.cell_value(r, c["key"])[0] is not None
               else (esc(money_text(B.cell_value(r, c["key"])[0]))
                     if c["fmt"] == B.FMT_MONEY and B.cell_value(r, c["key"])[0] is not None
                     else esc(str(B.cell_value(r, c["key"])[0] or ""))))
            + "</td>"
            for c in B.BIG_COLUMNS) + "</tr>"
        for r in rows
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>按模板导出 · {esc(TITLE)}</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>{esc(TITLE)} · 按模板导出</h1><nav>{_nav_html()}</nav></div>'
        f'<div class="card"><h4>导出形态（{esc(month)}）</h4>'
        f"<div class=\"mut sm\">模板 = 用户给的最终模板（<b>{len(B.BIG_COLUMNS)} 列</b> · 两行表头）；"
        "数据区起点**认标记文字**、不认定义名称（§7.1）；"
        f"出纸 = <b>{esc(B.PRINT_CHANNEL)}</b>（§1.4.1 · §5.7.2）。</div>"
        f"<div class=\"mut sm\">行序 = 大表自己的顺序（§5.7.3），与页面<b>同序同值</b>；"
        f"共 <b>{len(rows)}</b> 行。</div>"
        '<div data-seg="data"><div class="tw" style="margin-top:10px"><table class="dt nosort"><thead>'
        f"{_thead()}</thead><tbody>{body}</tbody></table></div></div>"
        '<div class="mut sm" style="margin-top:8px">⚠️ 真实文件落盘 / 打包归切片 6（`ACC-X-EXP-001`）；'
        "本页只出**导出形态与清单**。</div></div>"
        "</div></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "render_big_page", "render_export_page"]
