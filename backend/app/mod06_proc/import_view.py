"""`MOD-06` **过程资料历史导入页**（§5.2.5 ①②）—— 三步：**列说明 ＋ 选文件 → 预览 → 确认**。

⚠️ 交互形态与付款域的「历史付款流水导入」**同构**（§5.2.5 ② 明写「复用同一套」）：
   解析 / 校验 / **预览（不写库）** / 批次 / **整批回滚** / **核对报告**。
⚠️ 本页**只渲染**：解析在 `importer.py`、落库在 `repository.import_snapshot`（**只写历史段**）。
⚠️ 页面文案**不用 `**` 标记**（本仓说明文字统一只 `esc`）⇒ 强调直接拼 `<b>`。
"""

from __future__ import annotations

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc
from app.mod06_proc import domain as D

TITLE = "过程资料历史导入"

_STEPS = (
    ("①", "列说明 ＋ 选文件", "按表头认列（列序不限）：一列「核算月」＋ 至少一列材料列；"
                             "点「解析并预览」——<b>这一步不写库</b>。"),
    ("②", "预览", "将写入 <b>N 个月</b> · <b>异常行清单</b> · <b>列提示</b> —— 顺手确认「截止核算月」，"
                  "确认无误再往下。"),
    ("③", "确认导入", "写快照 ＋ 记<b>批次号</b>（同批可整批回滚重导）；完成后给「<b>核对报告</b>」："
                     "截止月内 i8 有数、而本批没有的月份（历史段<b>不回落</b> i8，这些月一定印空）。"),
)

EXTRA_CSS = """
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
.imp .steps{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 14px}
.imp .step{flex:1 1 240px;min-width:220px;background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:10px 12px}
.imp .step b{color:var(--pri)}
.imp .step .mut{font-size:12.5px}
.imp .blk{margin:14px 0}
.imp .blk h3{font-size:14px;margin:0 0 6px;font-weight:600}
.imp table{width:100%;border-collapse:collapse;font-size:13px}
.imp th,.imp td{border:1px solid var(--bd);padding:5px 8px;text-align:left}
.imp th{background:var(--sf2);font-weight:500}
.imp td.num,.imp th.num{text-align:right;font-variant-numeric:tabular-nums}
.imp .upload{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.imp .gridwrap{max-height:420px;overflow:auto}
.imp .pjsel{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _shell(*, body: str, current: str = "/m06/import", notice: str = "") -> str:
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>{esc(TITLE)}</h1><nav>{_nav_html()}</nav></div>'
        f'<section class="view" data-view="{esc(current)}"><h3>{esc(TITLE)}</h3>'
        f"{notice}{body}</section></div></body></html>"
    )


def _notice(message: str, kind: str = "ok") -> str:
    if not str(message or ""):
        return ""
    k = str(kind or "ok")
    k = k if k in ("ok", "wn", "err") else "ok"
    return f'<div class="notice {k}">{esc(message)}</div>'


def _steps_html() -> str:
    return "".join(
        f'<div class="step"><b>{n} {esc(t)}</b><div class="mut">{d}</div></div>'
        for n, t, d in _STEPS
    )


def _cols_html() -> str:
    mats = [c["label"] for c in D.PROC_COLUMNS if c["key"] in D.MATERIAL_KEYS]
    return (
        '<div class="blk"><h3>① 列说明（按表头文字认列 · 列序不限）</h3>'
        '<table class="cols"><thead><tr><th>列</th><th>填什么</th><th>要求</th></tr></thead><tbody>'
        "<tr><td>核算月</td><td>如 2026-08（也认 2026/8 · 202608）</td><td><b class=\"wn\">必填</b></td></tr>"
        f'<tr><td>材料列</td><td>{esc(" / ".join(mats))}</td><td><b class="wn">至少 1 列</b></td></tr>'
        "</tbody></table>"
        '<p class="mut sm" style="margin-top:6px">'
        "• 表头可以带「金额」「（元）」等尾缀，会被自动去掉。<br>"
        "• ⛔ <b>机械 6 列不导入</b> —— 机械列全段<b>手录</b>（回过程资料页的「机械手录」区块录）。<br>"
        "• 只填了核算月、一个材料金额都没有的行会被列进「异常清单」"
        "（分不清「确实为 0」还是「漏填」）。<br>"
        "• 一列材料列都认不出来 ⇒ <b>整份拒绝</b>（那不像是过程资料的定稿文件）。"
        "</p></div>"
    )


def _project_html(data: dict) -> str:
    if not data["projects"]:
        return ('<div class="blk"><h3>项目</h3><p class="mut">'
                "还没有可导入的项目 —— 先在「库存单据」页抓一次库存单据明细，"
                "项目键 = <b>仓库名</b>（§2.7.4）。</p></div>")
    opts = "".join(
        f'<option value="{esc(p)}"{" selected" if p == data["warehouse"] else ""}>{esc(p)}</option>'
        for p in data["projects"]
    )
    return (
        '<div class="blk"><h3>项目（导入到哪一个项目 · 键 = 仓库名）</h3>'
        '<form class="pjsel" method="get" action="/m06/import">'
        f'<select class="inp" name="pj">{opts}</select>'
        '<button class="btn sm" type="submit">切换</button>'
        f'<span class="mut sm">当前截止核算月：<b>{esc(data["cutoff_ym"] or "（未设定 ⇒ 一律正式段）")}</b></span>'
        "</form></div>"
    )


def _upload_html(data: dict) -> str:
    off = "" if data["warehouse"] else " disabled"
    return (
        '<div class="blk"><h3>选文件</h3>'
        '<form class="upload" method="post" action="/m06/import/preview" enctype="multipart/form-data">'
        f'<input type="hidden" name="pj" value="{esc(data["warehouse"])}">'
        '<input type="file" name="file" accept=".xlsx" required>'
        f'<button class="btn sm pri" type="submit"{off}>解析并预览（不写库）</button>'
        '<span class="mut sm">只读第一个工作表；上限 2000 行。</span></form></div>'
    )


def _rows_table(preview: dict) -> str:
    keys = [k for k in D.DATA_KEYS if k in D.MATERIAL_KEYS]
    head = "".join(f'<th class="num">{esc(D.column_meta(k)["label"])}</th>' for k in keys)
    body = []
    for row in preview["rows"][:300]:
        tds = "".join(f'<td class="num">{esc(row.get(k) or "—")}</td>' for k in keys)
        body.append(f'<tr><td>{esc(row.get("ym"))}</td>{tds}</tr>')
    inner = "".join(body) or f'<tr><td colspan="{len(keys) + 1}" class="mut">（没有可写入的行）</td></tr>'
    return (f'<div class="gridwrap"><table><thead><tr><th>核算月</th>{head}</tr></thead>'
            f"<tbody>{inner}</tbody></table></div>")


def _preview_html(data: dict, preview: dict, token: str) -> str:
    anomalies = "".join(
        f'<tr><td>{a["line"]}</td><td>{esc(a.get("ym") or "—")}</td><td>{esc(a["reason"])}</td></tr>'
        for a in preview["anomalies"]
    ) or '<tr><td colspan="3" class="mut">（无）</td></tr>'
    mech = "· ".join(esc(x) for x in preview["ignored_mech"]) or "（无）"
    unknown = "· ".join(esc(x) for x in preview["unknown_headers"]) or "（无）"
    return (
        '<div class="blk"><h3>② 预览 —— <b>尚未写库</b></h3>'
        f"<p>项目 <b>{esc(data['warehouse'])}</b> · 将写入 <b>{preview['writable']}</b> 个月"
        f"（{esc('、'.join(preview['months']) or '—')}） · "
        f'异常 <b class="dg">{len(preview["anomalies"])}</b> 行。</p>'
        f"{_rows_table(preview)}"
        '<h4 style="margin:12px 0 4px;font-size:13.5px">异常清单（不入库）</h4>'
        '<div class="gridwrap"><table><thead><tr><th>行</th><th>核算月</th><th>原因</th></tr></thead>'
        f"<tbody>{anomalies}</tbody></table></div>"
        '<h4 style="margin:12px 0 4px;font-size:13.5px">列提示</h4>'
        f'<p class="sm">⛔ 未导入的机械列：{mech}（机械列<b>全段手录</b>，见过程资料页「机械手录」）<br>'
        f"未识别的列（已忽略）：{unknown}</p>"
        '<form method="post" action="/m06/import/confirm">'
        f'<input type="hidden" name="token" value="{esc(token)}">'
        f'<input type="hidden" name="pj" value="{esc(data["warehouse"])}">'
        '<div class="fbar"><div class="fi"><label>截止核算月</label>'
        f'<input class="inp" name="cutoff_ym" value="{esc(preview["default_cutoff"])}" '
        'placeholder="YYYY-MM"></div>'
        '<div class="fi"><label>&nbsp;</label><span>'
        '<button class="btn sm pri" type="submit">确认导入（写历史段 ＋ 记批次）</button></span></div>'
        "</div>"
        '<div class="mut sm">默认 = 导入数据里<b>最大的核算月</b>（§5.2.5 ①：一次设定、可改）。'
        "≤ 截止核算月的月份走<b>历史段</b>（取本批快照）；其后的月份仍走<b>正式段</b>（只读引用库存单据）。</div>"
        "</form></div>"
    )


def _report_html(data: dict, report: dict) -> str:
    rows = "".join(f"<tr><td>{esc(m)}</td></tr>" for m in report["rows"]) or (
        '<tr><td class="mut">（无 —— 截止月内 i8 有数据的月份都导到了）</td></tr>')
    return (
        '<div class="blk"><h3>③ 核对报告</h3>'
        f"<p>批次 <b>{esc(report['batch'])}</b> · 截止核算月 <b>{esc(report['cutoff_ym'])}</b> · "
        f"本批月份 {esc('、'.join(report['months']) or '—')}</p>"
        f'<p>⚠️ 截止月内 <b class="wn">{report["count"]}</b> 个月在 <b>i8 有库存单据、而本批快照里没有</b> '
        "—— 历史段<b>不回落 i8</b>，这些月<b>一定会印空</b>：</p>"
        '<div class="gridwrap"><table><thead><tr><th>核算月（将显示为空）</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        '<p class="mut sm">若某月确实该有数 ⇒ 补进 Excel 再导一次（新批次），或先整批回滚再重导。</p>'
        '<form method="post" action="/m06/import/rollback" '
        "onsubmit=\"return confirm('确定整批回滚？该批快照将置为已回滚（留痕、不物理删）。')\">"
        f'<input type="hidden" name="batch" value="{esc(report["batch"])}">'
        f'<input type="hidden" name="pj" value="{esc(data["warehouse"])}">'
        '<button class="btn sm" type="submit">整批回滚后重导</button></form></div>'
    )


def render_import_page(data: dict, *, message: str = "", kind: str = "ok",
                       preview: dict | None = None, token: str = "",
                       report: dict | None = None) -> str:
    body = f'<div class="imp">{_notice(message, kind)}{_project_html(data)}{_cols_html()}'
    if preview is None:
        body += f'<div class="blk"><h3>三步走</h3><div class="steps">{_steps_html()}</div></div>'
        body += _upload_html(data)
        body += (f'<div class="blk"><h3>历史段批次</h3><p class="sm">'
                 f"已登记 <b>{len(data['batches'])}</b> 批（回滚后不再计入）；"
                 "⛔ 历史段<b>不提供行内编辑</b>（要改只能再导一次，§5.2.5 ②）。</p></div>")
    else:
        body += _preview_html(data, preview, token)
    if report is not None:
        body += _report_html(data, report)
    body += "</div>"
    return _shell(body=body)


__all__ = ["TITLE", "render_import_page"]
