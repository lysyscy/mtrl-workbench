"""`MOD-06` 过程资料页的 HTML 装配（**服务端渲染**）。

规范：
- 骨架走 `page.render_list_page`（口径说明 → 指标区 → 筛选栏 → 数据区 → 空态提示行）；
  数据区因含**表签 ＋ 两种表**，走 `data_html` 口子（与 `MOD-05` 台账页同款）。
- 列**不写字面量** —— 一律来自 `domain.PROC_COLUMNS` / `DIFF_COLUMNS`（改列只改那一处）。
- 金额显示走 `mod08_inv.view.money_text`（**不另写一份格式化**）。
- ⛔ 材料列**只读**：本页只渲染文本，**不生成任何材料输入框**（§5.2.3 · `DEV-R-01`）。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc, render_list_page
from app.mod06_proc import domain as D
from app.mod06_proc import mech_ui
from app.mod08_inv.view import money_text

PAGE_ID = "m06"
TITLE = "过程资料"

TIPS = (
    "**过程资料 = 每个项目每月一份的「项目成本台账」**（§5.2）；列结构与列数以 §5.2.2 为准。"
    "报**分公司工程科**，每月 5-10 号。",
    "**⭐ 材料数据单向流**：i8 → 库存单据（唯一可改的源）→ 过程资料（**引用，派生只读**）。"
    "材料列随之反映，**不独立维护、也不独立承载差异**。",
    "**三个数据来源**：① 库存单据**引用**（入库 / 出库各列）② 人工录入（机械费各项，近期不做、先手录）"
    "③ **调整单**（打在库存单据行上、只改库存单据）。",
    "**⭐ 调整单机制（§5.2.4）**：打在「库存单据的行」上、**不被 i8 导出覆盖**、必须**留痕 + 留备注**。",
    "展示形态 = **两张表 ＋ 一张差异表**；**进页面默认停在表② 调整后表**。",
    "**差异表是「入口」不是「死表」**：点差异行 → 跳转库存单据页并自动筛出改过的行。",
    "与付款域的「统计金额」是同一种设计思想：**源数据不动，用旁路载体承载人工判断**。",
)

EXTRA_CSS = """
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
.tb2{display:inline-flex;gap:0;border:1px solid var(--bd3);border-radius:6px;overflow:hidden}
.tb2 a{padding:5px 14px;font-size:13px;color:var(--tx);text-decoration:none;border-right:1px solid var(--bd3)}
.tb2 a:last-child{border-right:0}
.tb2 a.on{background:var(--pri);color:var(--on)}
.pjsel{display:flex;flex-wrap:wrap;gap:10px;max-height:150px;overflow:auto;padding:6px 2px}
.pjsel label{display:flex;gap:5px;align-items:center;font-size:13px;white-space:nowrap}
.dt td.vsep,.dt th.vsep{border-left:2px solid var(--bd)}
.tot td{background:var(--sf2);font-weight:500}
.mini{font-size:12px;color:var(--mut);margin-top:6px}
.exp{margin-bottom:10px}
.exp>summary{cursor:pointer;font-size:13px;color:var(--tx2)}
.exp .fbar{margin-bottom:0}
.mech{margin-top:12px}
.mech>summary{cursor:pointer;font-size:13px;color:var(--tx2)}
.mech .mechf{margin-top:8px}
.mech .fbar{margin-bottom:0}
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _tabbar(state: dict) -> str:
    items = []
    for tab, label in D.TABS:
        on = " on" if tab == state["tab"] else ""
        href = f'/m06?pj={esc(state["warehouse"])}&tab={tab}'
        items.append(f'<a class="{on.strip()}" href="{href}">{esc(label)}</a>')
    return f'<div class="tb2">{"".join(items)}</div>'


def _proj_panel(state: dict, projects: list[str]) -> str:
    """项目选择：**单选（radio）**、**不给全选 / 清空**、**选中即收起**（001-04）。

    服务端实现 ⇒ 选中即 `onchange` 提交表单并重渲染（面板随之收起 —— 默认 `<details>` 收起态）。
    """
    radios = "".join(
        f'<label><input type="radio" name="pj" value="{esc(p)}" '
        f'{"checked" if p == state["warehouse"] else ""}'
        f' onchange="this.form.submit()"> {esc(p)}</label>'
        for p in projects
    ) or '<span class="mut">（库存单据里还没有仓库 —— 先抓 `API-03`）</span>'
    return (
        f'<form method="get" action="/m06"><input type="hidden" name="tab" value="{state["tab"]}">'
        f'<details><summary>切换项目（单选 · 键 = 仓库名）</summary>'
        f'<div class="pjsel">{radios}</div></details></form>'
    )


def _import_link(state: dict) -> str:
    """「过程资料历史导入」入口 —— 历史段**唯一的修改通道**（§5.2.5 ②）。"""
    return (f'<a class="btn sm" href="/m06/import?pj={esc(state.get("warehouse") or "")}"'
            ' data-act="procImport">过程资料历史导入</a>')


def _head_html(cols) -> str:
    """表头：分段竖线落在**段首列**（与数据行 / 合计行 / 总求和行四处一致）。"""
    vsep_at = {k for _name, keys in D.SUM_SEGMENTS for k in keys[:1]}
    ths = []
    for col in cols:
        cls = ' class="vsep"' if col["key"] in vsep_at else ""
        ths.append(f'<th{cls}>{esc(col["label"])}</th>')
    return f"<tr>{''.join(ths)}</tr>"


EMPTY_MATERIAL_TIP = ("该段该核算月没有数据 —— 不臆造 0。历史段请走「过程资料历史导入」再导一次；"
                      "正式段请先抓库存单据明细（API-03）")


def _matrix_html(rows: list[dict], totals: dict, segments) -> str:
    vsep = {k for _n, ks in D.SUM_SEGMENTS for k in ks[:1]}
    body: list[str] = []
    for row in rows:
        history = row.get("section") == D.SECTION_HISTORY
        tag = ('<span class="tag wn">历史段</span>' if history
               else '<span class="tag ok">正式段</span>')
        tds = [f'<td class="now">{esc(row.get(D.YM_KEY))} {tag}</td>']
        for col in D.PROC_COLUMNS[1:]:
            key = col["key"]
            cls = "num" + (" vsep" if key in vsep else "")
            if row.get("material_empty") and key in D.MATERIAL_KEYS:
                tds.append(f'<td class="{cls}">'
                           f'<span class="mut" title="{esc(EMPTY_MATERIAL_TIP)}">—</span></td>')
            else:
                tds.append(f'<td class="{cls}">{esc(money_text(row.get(key)))}</td>')
        body.append(f"<tr>{''.join(tds)}</tr>")

    # ① 每个数据列下方给「合计」行（001-05）
    sum_tds = ['<td>合计</td>']
    for col in D.PROC_COLUMNS[1:]:
        sum_tds.append(f'<td class="num">{esc(money_text(totals.get(col["key"])))}</td>')
    body.append(f'<tr class="sumrow" data-pin="1">{"".join(sum_tds)}</tr>')

    # ② 「总求和」行：四段各占一段，`colspan` = 该段列数（001-06）
    tot_tds = ['<td>总求和（本表）</td>']
    for seg in segments:
        tot_tds.append(
            f'<td class="num vsep" colspan="{seg["span"]}">{esc(seg["name"])}合计 '
            f'{esc(money_text(seg["total"]))}</td>'
        )
    body.append(f'<tr class="tot" data-pin="1">{"".join(tot_tds)}</tr>')
    return (
        '<div class="tw"><table class="dt" data-sort data-sort-key="m06:proc">'
        f"<thead>{_head_html(D.PROC_COLUMNS)}</thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _diff_html(diffs: list[dict], totals: dict) -> str:
    body: list[str] = []
    for row in diffs:
        tds = []
        for col in D.DIFF_COLUMNS:
            key = col["key"]
            if key == "ops":
                href = esc(D.jump_query(row))
                tds.append(f'<td class="ctr"><a class="btn sm" href="{href}">查看原始行 →</a></td>')
                continue
            cls = ' class="num"' if col["type"] == "num" else ""
            value = money_text(row.get(key)) if col["type"] == "num" else esc(row.get(key))
            tds.append(f"<td{cls}>{value}</td>")
        body.append(f"<tr>{''.join(tds)}</tr>")

    # 差异表的「合计」行：**只有 原值 / 调整后 / 差额 三列可求和**（001-07）
    n = len(D.DIFF_COLUMNS)
    lead_span = [c["key"] for c in D.DIFF_COLUMNS].index(D.DIFF_SUM_KEYS[0])
    tds = [f'<td colspan="{lead_span}">合计</td>']
    for key in D.DIFF_SUM_KEYS:
        tds.append(f'<td class="num">{esc(money_text(totals.get(key)))}</td>')
    tail = n - lead_span - len(D.DIFF_SUM_KEYS)
    if tail > 0:
        tds.append(f'<td colspan="{tail}"></td>')
    body.append(f'<tr class="sumrow" data-pin="1">{"".join(tds)}</tr>')
    return (
        '<div class="tw"><table class="dt" data-sort data-sort-key="m06:diff">'
        f"<thead>{_head_html(D.DIFF_COLUMNS)}</thead><tbody>{''.join(body)}</tbody></table></div>"
    )


DIFF_FIRST = D.DIFF_SUM_KEYS[0]      # 「合计」标签所在列的起点（原值列；见 `_diff_html`）


# --------------------------------------------------------------- 导出（§7.1 · ACC-RPT-EXP-001）


def _export_strip(data: dict) -> str:
    """卡头「按模板导出」展开区（001-01/02/03）。

    ⚠️ **必须渲染在 `.tw` 之外** —— 本页的 `.tw` 是滚动容器，浮层面板放进去会被裁（001-03）；
       服务端渲染下它就是一个 `<details>`（与 `_proj_panel` 同一套做法）。
    ⚠️ 展开区内的提交一律带 `expopen` 令牌 ⇒ 「用户清空后点导出」不会被当成「没动过」（001-02）。
    """
    exp = data["export"]
    st = data["state"]
    boxes = "".join(
        f'<label><input type="checkbox" name="exppj" value="{esc(p)}"'
        f'{" checked" if p in exp["selected"] else ""}> {esc(p)}</label>'
        for p in exp["projects"]
    ) or '<span class="mut">（库存单据里还没有仓库 —— 先抓 `API-03`）</span>'
    n = len(exp["selected"])
    title = "按所选项目导出（每项目一份）" if n else "请先选项目"
    return (
        f'<details class="exp" data-seg="exp-strip"{" open" if exp["open"] else ""}>'
        "<summary>按模板导出（每项目一份）…</summary>"
        '<form method="get" action="/m06">'
        '<input type="hidden" name="expopen" value="1">'
        f'<input type="hidden" name="pj" value="{esc(st["warehouse"])}">'
        f'<input type="hidden" name="tab" value="{st["tab"]}">'
        '<div class="fbar">'
        '<div class="fi"><label>项目（可多选）</label>'
        f'<div class="pjsel">{boxes}</div></div>'
        f'<div class="fi"><label>批量</label><span>'
        '<button class="btn sm" type="submit" name="expset" value="all">全选</button> '
        '<button class="btn sm" type="submit" name="expset" value="none">清空</button>'
        f'</span><span class="mut sm">已选 {n} 个项目</span></div>'
        '<div class="fi"><label>导出</label><span>'
        f'<button class="btn sm pri" type="submit" formaction="/m06/export"'
        f'{" disabled" if not n else ""} title="{esc(title)}">导出</button> '
        f'<a class="btn sm" href="/m06?pj={esc(st["warehouse"])}&amp;tab={st["tab"]}">取消</a>'
        "</span></div>"
        '<div class="mut sm" style="flex-basis:100%">导出取数 = 当前所显示的 '
        f'<b data-exp-tab="1">{esc(exp["tab_name"])}</b>'
        "（§7.1：数据永远来自页面的筛选结果，模板只管长什么样）</div>"
        f'<div class="mut sm" style="flex-basis:100%">{_export_note()}</div>'
        "</div></form></details>"
    )


def _export_cols_parts() -> tuple[str, str]:
    """`(N 列模板, 列构成说明)` —— **只有这一处读列定义**（清单正文与形态说明共用，别各写一份）。

    ⚠️ 反例教训：本单元首版把「17 列模板」写了两遍（形态说明 ＋ 清单正文），
       反向灵敏度里改坏其中一处**仍然全绿**（另一处把断言喂饱了）⇒ 去重成单一出口。
    """
    return (
        f"{len(D.PROC_COLUMNS)} 列模板",
        f"核算月 ｜ 入库 {len(D.CATEGORIES)} 类 ｜ 出库 {len(D.CATEGORIES)} 类 ｜ "
        f"机械 {len(D.MECH_COLUMNS)} 列",
    )


def _export_note() -> str:
    """导出形态说明 —— **页面提示与清单预览共用同一份文案**（不各写一遍）。

    ⚠️ 本仓说明文字不做 `**强调**` 标记解析（`_render_tip` 一律只 `esc`）⇒ 强调由视图直接拼 `<b>`。
    """
    cols, _ = _export_cols_parts()
    return (f"导出形态：<b>每项目一份</b>（{cols} · 报分公司工程科）；"
            "选 <b>2 个以上</b> ⇒ 打成一个 <b>zip</b>。文件名含项目与当前年月（§7.1）。")


def render_export_preview(data: dict) -> str:
    """导出清单预览页（`GET /m06/export`）—— **形态与原型一致**：1 个文件 / N 个项目打 zip。

    ⚠️ 本页只给**清单**；**真实文件写出**归切片 6 的 `ACC-X-EXP-001`（与 `TAIL-04` 同一条尾巴）。
    """
    exp = data["export"]
    cols, cols_how = _export_cols_parts()
    content = f"内容 = <b>{cols}</b>（{cols_how}），报<b>分公司工程科</b>（§5.2.2）。"
    if not exp["count"]:
        body = '<div class="notice wn">请先选择要导出的项目 —— 展开区里「已选 0 个项目」时导出按钮是禁用的。</div>'
    elif exp["zip"]:
        rows = "".join(
            f'<tr><td class="fc">{i}</td><td>{esc(f["name"])}</td></tr>'
            for i, f in enumerate(exp["files"], 1)
        )
        body = (
            f'<div class="notice ok">选了 <b>{exp["count"]}</b> 个项目 ⇒ 打成一个 '
            f'<b>zip</b>：<span class="fc">{esc(exp["zip_name"])}</span>，'
            f'内含 <b>{exp["count"]}</b> 个文件（每个 = 一个项目的 {cols}）。</div>'
            '<div class="tw"><table class="dt"><thead><tr><th>#</th>'
            '<th>文件（每项目一份）</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )
    else:
        body = (
            f'<div class="notice ok">将生成 <b>1 个文件</b>：'
            f'<span class="fc">{esc(exp["files"][0]["name"])}</span><br>{content}</div>'
        )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>导出 · {esc(TITLE)}</title><style>{BASE_CSS}{EXTRA_CSS}</style></head><body>"
        '<div class="wrap"><div class="hd"><h1>导出 · 过程资料（按模板 · 每项目一份）</h1>'
        f'<nav>{_nav_html()}</nav></div><section class="view">'
        f'<h3>导出 · {esc(TITLE)}（按模板 · 每项目一份）</h3>'
        f"{body}"
        '<div class="mini">导出取数 = 当前所显示的 '
        f'<b data-exp-tab="1">{esc(exp["tab_name"])}</b>（§7.1；切表后本页取数随之改变）。</div>'
        f'<div class="mini">{_export_note()}</div>'
        '<div class="mini">⚠️ 本页只给<b>清单</b>：<b>真实文件写出</b>属切片 6 的 '
        '<code>ACC-X-EXP-001</code>（把这里列出的文件真正落盘 / 打包）。</div>'
        f'<p><a class="btn" href="/m06?pj={esc(data["warehouse"])}&amp;tab={data["state"]["tab"]}">返回过程资料</a></p>'
        "</section></div></body></html>"
    )


def render_proc_page(data: dict, *, message: str = "", kind: str = "ok", mech_ym: str = "") -> str:
    state = data["state"]
    tab = state["tab"]
    ncols = len(D.PROC_COLUMNS)
    notice = mech_ui.notice_html(message, kind)      # 回执条（PRG 回来）—— 一律 esc

    if tab == D.TAB_DIFF:
        table = (
            _diff_html(data["diffs"], data["diff_totals"]) if data["diffs"]
            else f'<div class="tw"><table class="dt"><thead>{_head_html(D.DIFF_COLUMNS)}</thead>'
                 f'<tbody><tr class="empty" data-seg="empty"><td colspan="{len(D.DIFF_COLUMNS)}">'
                 "该项目本月没有打过调整单（差异表为空）—— 差异的修正入口在库存单据页"
                 "</td></tr></tbody></table></div>"
        )
    elif data["rows"]:
        table = _matrix_html(data["rows"], data["totals"], data["segments"])
    else:
        table = (
            f'<div class="tw"><table class="dt"><thead>{_head_html(D.PROC_COLUMNS)}</thead>'
            f'<tbody><tr class="empty" data-seg="empty"><td colspan="{ncols}">'
            "该项目还没有库存单据数据 —— 先抓 `API-03` 库存单据明细，或用「过程资料历史导入」"
            "</td></tr></tbody></table></div>"
        )

    section = render_list_page(
        page_id=PAGE_ID,
        title=f"{TITLE} · {data['warehouse'] or '（未选项目）'}",
        tips=TIPS,
        filters=[
            {"label": "项目（单选 · 键 = 仓库名）", "html": _proj_panel(state, data["projects"])},
            {"label": "表", "html": _tabbar(state)},
            {"label": "历史段", "html": _import_link(state)},
            {"label": "", "html": f'<span class="pill">{ncols} 列 ｜ 每项目每月一份 ｜ 报分公司工程科</span>'},
        ],
        columns=[],
        data_html=_export_strip(data) + table + mech_ui.block_html(data, ym=mech_ym),
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>过程资料</h1><nav>{_nav_html()}</nav></div>'
        f"{notice}"
        f"{section}"
        '<div class="mini">总求和行的四段 = 入库 / 出库 / 机械（前 4 列）/ 不含税（后 2 列）——'
        '不含税两列<b>单独成段</b>、不并入机械前 4 列；各段 colspan = 该段列数，行内跨列数之和'
        '恒等于表头列数。</div>'
        f'<div class="mini">分段（§5.2.5）：<b>历史段</b> = 核算月 ≤ 截止核算月 '
        f'<b>{esc(data["cutoff_ym"] or "（未设定 ⇒ 一律正式段）")}</b> —— 材料列来自<b>导入的定稿快照</b>、'
        '<b>不引用库存单据</b>；<b>正式段</b> = 其后 —— 材料列<b>只读引用</b>库存单据。'
        '<b>两段互不覆盖</b>（重抓 i8 不动历史段 · 重导历史不动正式段）。</div>'
        '<div class="mini">材料列<b>只读</b>：正式段要改 ⇒ 回库存单据页打<b>调整单</b>；'
        f'⛔ <b>历史段不提供行内编辑</b>（要改只能走「过程资料历史导入」再导一次：同批回滚重导 /'
        '另起新批次）；本页<b>不提供材料费编辑入口</b>。'
        f'历史段批次：<b>{len(data["history_batches"])}</b> 批已登记（回滚后不再计入）。</div>'
        "</div></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "render_proc_page", "render_export_preview"]
