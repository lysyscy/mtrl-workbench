"""付款域列表页**骨架装配器**（`MOD-03`/`MOD-04`/`MOD-05` 列表页 · **纯函数**）。

⭐ 本件自 `page.py` **整体切出**（`TAIL-06` · 2026-09-21 · 与 `§19` 四个暂留件收口同轮）——
`page.py` 原先 **804 行**（`T5` 的「>600 禁合入」红线），而它其实装着**两件不相干的东西**：
**主题真源**（CSS ＋ 派生）与**列表页骨架**（本件）。切开后两件都在 400 行以内。

依据：`demo/设计规则-提炼自付款通知书页.md`：**R1**（口径说明只给一个折叠块）· **R2**（`.kpis` 只在域级
总览页）· **R4**（筛选栏）· **R10①**（空态给提示行、跨列数由表头派生）· **R13**（表头点击排序 ·
**钉住行**含「合计 / 总计 / 小计」的行恒在最底、不参与排序 · **分段表**按「总求和」四段加竖线分隔）；
合计行**视口吸附置底**的实测结论 → `ops/M3-合计行置底实测结论.md`（含"为什么原型那套 CSS 不生效"）。

⚠️ **与 `page.py` 的关系**：`page.py` **再导出**本件的全部公开名 ⇒ 老调用方
   （`mod04_plan/service.py` 的 `sort_rows` · `notice_api_router` 的 `SORT_NONE` ·
   `mod06_proc/mech_ui.py` 的 `esc` …）**一行都不用改**；新代码可以直接从本件 import。
⚠️ 2026-09-21 起**服务端渲染层已清零**（`§19` 收口）⇒ 本件当前的消费者是**测试**
   （`test_page_shell.py` 钉「吸附置底的 CSS 契约」· `test_acc_pay_ia.py` 钉五段骨架）＋
   **纯函数复用**（排序 / 转义）。⛔ 别因为"没有页面在用了"就删 —— 它仍是**判据的观测面**。
"""

from __future__ import annotations

import html as _html
import re
from decimal import Decimal, InvalidOperation


# ============================================================ 列表页五段骨架

SEG_TIP = "tip"          # ① 口径说明（折叠）
SEG_KPIS = "kpis"        # ② 指标区
SEG_FILTER = "filter"    # ③ 筛选栏
SEG_DATA = "data"        # ④ 数据区（表格 + 滚动容器）
SEG_EMPTY = "empty"      # ⑤ 空态提示行

LIST_PAGE_SEGMENTS: tuple[str, ...] = (SEG_TIP, SEG_KPIS, SEG_FILTER, SEG_DATA, SEG_EMPTY)

DEFAULT_EMPTY_TEXT = "当前筛选没有数据"

# ⚠️ 「置底」是**两条独立要求**（别当成一条）：
#   ① **数据序置底** —— 合计行/空态行排在最后、不参与排序（`data-pin="1"` + `sort_rows(pinned=…)`）；
#   ② **视口吸附置底** —— 长表滚动时合计行仍可见，**只能靠 CSS**。
# 实测（`ops/M3-合计行置底实测结论.md`）：② 的 sticky **必须作用在 `<tr>` 上**；
#   写成 `.sumrow>td{position:sticky}`（原型现写法）**永不生效**（td 的包含块是表格行，没有位移空间）。
_SEG_RE = re.compile(r'data-seg="([a-z]+)"')
_TIP_RE = re.compile(r'<details[^>]*class="tip"')


def esc(value: object) -> str:
    """HTML 转义（用户输入 / 数据一律经此出口）。`None` ⇒ 空串。"""
    return "" if value is None else _html.escape(str(value), quote=True)


def tip_block_count(html: str) -> int:
    """页面里的**口径说明折叠块**个数 —— 必须**恒为 1**（R1：一个页面只给一个）。"""
    return len(_TIP_RE.findall(str(html)))


def segment_sequence(html: str) -> list[str]:
    """页面里**实际渲染出来的段**，按出现顺序（机器把手 = `data-seg`）。"""
    return _SEG_RE.findall(str(html))


def _render_tip(tips) -> str:
    """① 口径说明：**一个** `<details class="tip">`，多条口径**条目化**并进同一个块（R1）。"""
    tips = list(tips or ())
    items = "".join(f"<li>{esc(t)}</li>" for t in tips)
    return (
        f'<details class="tip" data-seg="{SEG_TIP}">'
        f'<summary>口径说明 · {len(tips)} 条 '
        f'<span class="mut sm">点开查看（默认收起，把空间让给数据）</span></summary>'
        f"<ul>{items}</ul></details>"
    )


def _render_kpis(kpis) -> str:
    """② 指标区：**段位恒在**（五段骨架），但 `.kpis` 大卡片只在「域级总览」白名单页出现（R2）。"""
    kpis = list(kpis or ())
    if not kpis:
        return f'<div data-seg="{SEG_KPIS}"></div>'
    items = "".join(
        f'<div class="kpi"><div class="k">{esc(k.get("k"))}</div>'
        f'<div class="v">{esc(k.get("v"))}</div>'
        f'<div class="s">{esc(k.get("s"))}</div></div>'
        for k in kpis
    )
    return f'<div class="kpis" data-seg="{SEG_KPIS}">{items}</div>'


def _render_filter_bar(filters, action: str = "") -> str:
    """③ 筛选栏：控件一律走**全站共用件**（`control` 给共用件的 id，不在本页另造控件）。

    - `filters[i]["html"]` —— 调用方**预渲染好**的控件 HTML（服务端渲染页用；**已由调用方转义**）；
    - 只给 `control` 时输出占位（骨架自检 / 未来前端接管用）；
    - `action` 非空 ⇒ 把整条筛选栏包进 `<form method="get" action="…">`。
      ⚠️ **必须给** —— 否则「查询」按钮是**死的**（控件不在任何表单里、提交不出参数）。
      实测 2026-09-16：`/m07` `/m08` 两页的筛选栏都没包表单（按钮点了没反应），
      而 `/m06` 自己在 `html` 里手包了一个 ⇒ 这里给口子、**别再让各页自己包**（会嵌套成两层 form）。
    """
    items: list[str] = []
    for f in filters or ():
        if f.get("raw"):
            # 调用方给**整段**（自己已含 `.fi` ＋ `<label>`，如共用件 `proj_panel_html()`）。
            # ⚠️ 不给这个口子 ⇒ 外面再包一层 ⇒ **`<label>` 出现两次**（原型只有一层）。
            items.append(f["html"])
        elif f.get("html"):
            items.append(f'<div class="fi"><label>{esc(f.get("label"))}</label>{f["html"]}</div>')
        else:
            items.append(
                f'<div class="fi"><label>{esc(f.get("label"))}</label>'
                f'<span class="ctl" data-ctl="{esc(f.get("control"))}"></span></div>'
            )
    inner = f'<div class="fbar" data-seg="{SEG_FILTER}">{"".join(items)}</div>'
    if not action:
        return inner
    return f'<form method="get" action="{esc(action)}">{inner}</form>'


# 「操作 / 处理」列**天然不可排**（R13）
UNSORTABLE_LABELS: tuple[str, ...] = ("操作", "处理")


def is_sortable(label: str) -> bool:
    """列头是否可排（R13）。"""
    return str(label or "").strip() not in UNSORTABLE_LABELS


def _sort_key(value: object):
    """排序键：能当金额 / 数字读的**按数值**排，其余按文本排（数值列不得按字符串排）。"""
    text = "" if value is None else str(value).strip()
    try:
        return (0, Decimal(text.replace(",", "")))
    except (InvalidOperation, ValueError):
        return (1, text)


def _cell(row, column):
    if isinstance(row, dict):
        return row.get(column)
    return getattr(row, column, "")


def _cell_cls(col: dict) -> str:
    """单元格附加类：`vsep` = **段首列**（左侧 2px 竖线，用于「总求和」那种分段视觉分隔）。

    ⚠️ 分段线必须**四处一致**（表头 / 数据行 / 合计行 / 总求和行）⇒ 所以四类行**共用同一个
       `_cells()` 出口**，而不是像原型那样手写 `<tr style="…">` 绕开出口（一绕就漏，实测漏过一张表）。
    """
    return ' class="vsep"' if col.get("vsep") else ""


def _cells(cols: list, values: list) -> str:
    """一行里的 `<td>` 串 —— **表头 / 数据行 / 合计行 / 总求和行共用**（分段线天然一致）。"""
    return "".join(f"<td{_cell_cls(c)}>{v}</td>" for c, v in zip(cols, values))


def _render_data(
    sort_key: str | None,
    cols: list,
    rows: list,
    rows_html: str,
    summaries: list,
    summary_sticky: bool,
    empty_text: str,
) -> str:
    """④ 数据区：表头 + 数据行 + （有则）合计行/总求和行；⑤ 空态提示行**紧跟数据行之后**渲染。

    ⚠️ 空态提示行的跨列数**由表头列数派生**（R10①，不得写死数字）。
    ⚠️ **两种「置底」是两件事**：
       · **数据序置底** = 合计行排在最后、且不参与排序（`data-pin="1"`，由 `sort_rows` 的 `pinned` 保证）；
       · **视口吸附置底** = 长表滚动时合计行仍可见 —— 由页面 CSS
         `.dt tbody tr.sumrow{position:sticky;bottom:0;z-index:2}` 提供。
       ⚠️ **实测（`ops/M3-合计行置底实测结论.md`）**：该 sticky **必须作用在 `<tr>` 上**；
          写成 `.sumrow>td{position:sticky}`（原型现写法）**永不生效** —— `td` 的包含块是表格行、
          行高 = 单元格高 ⇒ 没有可位移空间。
       ⚠️ **分段表 / 分组表**（分组合计要紧贴本组、或要加粗竖线分段）传 `summary_sticky=False`
          ⇒ 不给 `sumrow` 类（不吸附），但**仍然 `data-pin="1"`**（数据序照样钉在表尾）。
    """
    head: list[str] = []
    for idx, col in enumerate(cols):
        label = esc(col.get("label"))
        extra = " vsep" if col.get("vsep") else ""
        if bool(col.get("sortable")):
            head.append(
                f'<th class="srt{extra}" tabindex="0" role="button" data-sort-col="{idx}" '
                f'title="点击排序（升 → 降 → 原序）">{label}<span class="mut"> &#8597;</span></th>'
            )
        else:
            head.append(f'<th class="nosort{extra}" data-nosort="1">{label}</th>')

    body: list[str] = []
    if rows_html:
        # 行由调用方渲染（如需要"每格一个表单"的服务端页）—— ⚠️ **安全责任在调用方**（须自行转义）
        body.append(rows_html)
    else:
        for row in rows:
            body.append("<tr>" + _cells(cols, [esc(_cell(row, c.get("key"))) for c in cols]) + "</tr>")

    for summary in summaries:
        cls = "sum" + (" sumrow" if summary_sticky else "")
        body.append(
            f'<tr class="{cls}" data-pin="1">'
            + _cells(cols, [esc(summary.get(c.get("key"), "")) for c in cols])
            + "</tr>"
        )

    if not rows and not rows_html:
        body.append(
            f'<tr class="empty" data-seg="{SEG_EMPTY}">'
            f'<td colspan="{len(cols)}">{esc(empty_text or DEFAULT_EMPTY_TEXT)}</td></tr>'
        )

    key_attr = f' data-sort-key="{esc(sort_key)}"' if sort_key else ""
    return (
        f'<div class="tw" data-seg="{SEG_DATA}"><table class="dt" data-sort{key_attr}>'
        f"<thead><tr>{''.join(head)}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def nav_html(current: str = "") -> str:
    """全站**分组侧栏导航**（照原型：概览 / 主数据 · 基础 / 付款域 / 报表域 / 集采域 / 全局）。

    - `current` —— 当前页路由，**命中即高亮**（`on`，原型同款）
    - ⭐ **唯一渲染出口**：各页别再自己拼 `<nav>` —— 此前 `mod05` / `mod06` / `mod07` / `mod08`
      **各写一份**（`core/nav.py` 里那句"收成一处"只收了**数据**、没收**渲染**）
    - ⚠️ **未实现的页面照原样列出并标「未开工」**（`dis`、不可点）—— 用户要能**看见有哪些页面**
    - 形态 = `position:fixed` 侧栏 ＋ `body:has(>.sbar)` 让出左边距 ⇒ **调用方不必改 HTML 结构**
    """
    from app.core.nav import NAV_GROUPS

    blocks: list[str] = []
    for group, items in NAV_GROUPS:
        links: list[str] = []
        for href, label, module, ready in items:
            mod = f'<span class="m">{esc(module)}</span>'
            if not ready:
                links.append(
                    f'<span class="sb-i dis" title="该模块尚未开工">{mod}'
                    f"<span>{esc(label)}</span><span class=\"m\">未开工</span></span>"
                )
                continue
            on = " on" if href == (current or "") else ""
            links.append(f'<a class="sb-i{on}" href="{esc(href)}">{mod}<span>{esc(label)}</span></a>')
        blocks.append(f'<div class="sb-g">{esc(group)}</div>' + "".join(links))
    return (
        '<aside class="sbar" aria-label="全站导航">'
        '<div class="sb-h">材料报表工作台</div>' + "".join(blocks) + "</aside>"
    )


def render_list_page(
    *,
    page_id: str,
    title: str,
    tips=(),
    kpis=(),
    filters=(),
    columns=(),
    rows=(),
    rows_html: str = "",
    data_html: str = "",
    empty_text: str = DEFAULT_EMPTY_TEXT,
    sort_key: str | None = None,
    summary=None,
    summary_sticky: bool = True,
    filter_action: str = "",
    nav_current: str = "",
) -> str:
    """装配一个列表页：**固定五段**（口径说明 → 指标区 → 筛选栏 → 数据区 → 空态提示行）。

    ⚠️ 五段的**段位恒在、顺序不变**；空态提示行只在无数据时渲染，且**恒为最后一段**。

    - `columns[i]["sortable"]` —— 该列可排（「操作 / 处理」列须为 `False`）
    - `columns[i]["vsep"]` —— 该列是**段首**（加分段竖线；四处一致）
    - `rows` / `rows_html` —— 数据行：给 `rows_html` 时**由调用方渲染整段 `<tr>`**（安全责任在调用方）
    - `data_html` —— **整个数据区**（含 `.tw` 容器）由调用方渲染：用于**非单表**的数据区
      （如「左右两侧对照」的台账页）⇒ 给定时由调用方自行渲染 `data-seg="data"` 与其空态段
      （安全责任在调用方）
    - `summary` —— 合计行：传 `dict` 或 `dict` 列表（列表 = 合计行 ＋「总求和（本表）」等多行）
    - `summary_sticky` —— 合计行是否**视口吸附置底**（分段表 / 分组表传 `False`）
    - `filter_action` —— 非空 ⇒ 筛选栏包 `<form method="get" action="…">`（**服务端渲染页应一律给**，
      否则「查询」按钮是死的；⚠️ 已自己包过表单的页面（如 `mod06`）**不要再给**，会嵌套）
    """
    cols = [dict(c) for c in columns]
    rows = list(rows or ())
    # ⚠️ **空 dict 视为"没有合计行"**（2026-09-17 修）：调用方常写 `summary=calc(...)`，而 calc 在
    #    「不该有合计行」时返回 `{}`（如 m03 切到「分类 = 剔除」⇒ 视图全为剔除行 ⇒ 不给一排 0）。
    #    若不滤掉，会渲染出一行**格子全空**的 `<tr class="sum sumrow">` —— 比一排 0 更难看出问题。
    _raw_summaries = [summary] if isinstance(summary, dict) else list(summary or ())
    summaries = [s for s in _raw_summaries if s]
    return "\n".join(
        [
            # ⭐ **全站导航**（唯一出口）：放在每页最前 ⇒ **凡用本骨架渲染的页都自动有导航**
            #    （2026-09-17 加：此前各页各写一份、首页干脆没有 ⇒ 用户说"根本不知道都有哪些页面"）
            # ⚠️ `nav_current` 由调用方给**自己的路由**（给了才高亮；不给 = 不高亮，**不猜**）
            nav_html(nav_current),
            f'<section class="view" data-view="{esc(page_id)}">',
            f"<h3>{esc(title)}</h3>",
            _render_tip(tips),
            _render_kpis(kpis),
            _render_filter_bar(filters, filter_action),
            data_html
            or _render_data(sort_key, cols, rows, rows_html, summaries, summary_sticky, empty_text),
            "</section>",
        ]
    )


# ============================================================ 表头点击排序（R13）

SORT_NONE = 0
SORT_ASC = 1
SORT_DESC = -1


def next_sort_direction(current: int) -> int:
    """三态循环（与原型 `headSort` 同款）：**原序 → 升 → 降 → 原序**。"""
    cur = int(current)
    if cur == SORT_NONE:
        return SORT_ASC
    if cur == SORT_ASC:
        return SORT_DESC
    return SORT_NONE


def sort_rows(rows, *, column: str, direction: int, pinned=None) -> list:
    """按某列排序；`SORT_NONE` ⇒ 原序。

    ⚠️ **钉住行**（含「合计 / 总计 / 小计」的行、空态提示行）**恒在最底、不参与排序**（设计规则）。
    """
    data: list = []
    held: list = []
    for row in rows or ():
        (held if (pinned is not None and pinned(row)) else data).append(row)
    if int(direction) == SORT_NONE:
        return data + held
    ordered = sorted(data, key=lambda r: _sort_key(_cell(r, column)), reverse=int(direction) == SORT_DESC)
    return list(ordered) + held

__all__ = [
    "SCOPE_INCLUDED", "SCOPE_EXCLUDED", "EXCLUDED_KEYWORDS", "PAY_DOMAIN_IDS", "PAY_DOMAIN_PAGES",
    "pay_domain_nav", "nav_violations",
    "THEME_CSS", "BASE_CSS", "STICKY_BOTTOM_CSS", "VSEP_CSS",
    # ⚠️ 下面这批**住在新件 `list_page.py`**（`TAIL-06` 拆件），本文件只是**再导出**：
    "SEG_TIP", "SEG_KPIS", "SEG_FILTER", "SEG_DATA", "SEG_EMPTY", "LIST_PAGE_SEGMENTS",
    "DEFAULT_EMPTY_TEXT", "esc", "tip_block_count", "segment_sequence", "render_list_page",
    "nav_html", "UNSORTABLE_LABELS", "is_sortable", "SORT_NONE", "SORT_ASC", "SORT_DESC",
    "next_sort_direction", "sort_rows",
]
