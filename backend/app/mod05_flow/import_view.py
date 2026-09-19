"""历史付款流水导入页（**§4.4.6**）—— 交互规格主人 = `demo/设计规则` §六 **第 43 条**。

三步：**① 列说明 ＋ 选文件 → ② 预览（四块） → ③ 确认导入**；完成后给「**核对报告**」。
⚠️ 本页**只渲染**；解析在 `importer.py`、落库与重算在 `repository.py`。
"""

from __future__ import annotations

from app.mod03_notice.page import BASE_CSS, STICKY_BOTTOM_CSS, VSEP_CSS, esc
from app.core.nav import NAV
from app.mod05_flow.importer import COLUMNS

# ⚠️ 2026-09-19（`TAIL-27` · `§19` **批 3**）：下面这四个是**共用件**（`EXTRA_CSS` ＋ `_nav`/`_shell`/
#    `_notice`）—— 原先住在 `mod05_flow/view.py`（本模块的**页面渲染件**，随本批删除）；因为
#    **本页（历史付款导入 = m05 的暂留件 ✓）要复用**它们 ⇒ **搬到这里**。
#    ⛔ 别再往已删的 `view.py` 里加东西；要加共用件请放本文件或 `mod03_notice/page.py`。

EXTRA_CSS = """
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.two>div{min-width:0}
.side h4{font-size:13.5px;margin:0 0 6px;font-weight:500;color:var(--tx2)}
.ok{color:var(--ok-d)}.wn{color:var(--wn-d)}.dg{color:var(--dg-d)}
.gridwrap{overflow:auto;max-height:none;border:1px solid var(--bd);border-radius:6px;background:var(--sf)}
.pick{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:10px 12px;margin-bottom:10px}
"""


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

_STEPS = (
    ("①", "列说明 ＋ 选文件", "按固定列序填：A 单据号 · B 付款金额 · C 付款时间 · D 付款方式 · E 备注；"
                             "点「解析并预览」——**这一步不写库**。"),
    ("②", "预览（四块）", "将写入 **N 条** · **未匹配清单** · **异常清单** · **未识别的付款方式取值** —— "
                          "确认无误再往下。"),
    ("③", "确认导入", "落库并记**批次号**（同批可整批回滚重导）；完成后给「**核对报告**」："
                     "该批月份里**一条流水都没有的通知书**（用来发现 Excel 漏记）。"),
)


def _css() -> str:
    return """
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
.imp .cols td:first-child{width:36px;text-align:center;font-weight:600}
.imp .upload{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.imp .gridwrap{max-height:420px}
"""


def _cols_html() -> str:
    rows = "".join(
        f"<tr><td>{esc(letter)}</td><td>{esc(name)}</td>"
        f"<td>{'<b class="wn">必填</b>' if required else '可空'}</td></tr>"
        for letter, name, required in COLUMNS
    )
    return (
        '<div class="blk"><h3>① 列说明（按位置取，从 A 列开始）</h3>'
        '<table class="cols"><thead><tr><th>列</th><th>填什么</th><th>要求</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        '<p class="mut sm" style="margin-top:6px">'
        '• 首行若是表头会被自动跳过并提示。<br>'
        '• **付款方式可空**（不会替你填「现汇」）；填了但认不出的，会归入「其他」并**把原文留在备注**。<br>'
        '• 单据号必须是 i8 单据编码（形如 FKTZS2026090466）；**本地查不到的会列进「未匹配清单」**，不会静默丢掉。'
        '</p></div>'
    )


def _upload_html() -> str:
    return (
        '<div class="blk"><h3>选文件</h3>'
        '<form class="upload" method="post" action="/m05/import/preview" enctype="multipart/form-data">'
        '<input type="file" name="file" accept=".xlsx" required>'
        '<button class="pri" type="submit">解析并预览（不写库）</button>'
        '<span class="mut sm">只读第一个工作表；上限 5000 行。</span></form></div>'
    )


def _preview_html(preview, token: str) -> str:
    """四块：将写入 / 未匹配 / 异常 / 未识别付款方式。"""
    rows = "".join(
        f"<tr><td>{esc(r['bill_no'])}</td><td class='num'>{esc(r['amount'])}</td>"
        f"<td>{esc(r['pay_date'])}</td><td>{esc(r['pay_method'] or '（空）')}</td>"
        f"<td>{esc(r['remark'])}</td></tr>"
        for r in preview["rows"][:300]
    ) or '<tr><td colspan="5" class="mut">（没有可写入的行）</td></tr>'
    unmatched = "".join(
        f"<tr><td>{r['line']}</td><td>{esc(r['bill_no'])}</td><td class='num'>{esc(r['amount'])}</td>"
        f"<td>{esc(r['pay_date'])}</td></tr>"
        for r in preview["unmatched"]
    ) or '<tr><td colspan="4" class="mut">（无 —— 全部单据号都匹配上了）</td></tr>'
    anomalies = "".join(
        f"<tr><td>{a['line']}</td><td>{esc(a.get('bill_no') or '—')}</td><td>{esc(a['reason'])}</td></tr>"
        for a in preview["anomalies"]
    ) or '<tr><td colspan="3" class="mut">（无）</td></tr>'
    unknown = "· ".join(esc(u) for u in preview["unknown_methods"]) or "（无）"
    header = (
        '<div class="blk"><h3>② 预览 —— <b>尚未写库</b></h3>'
        f"<p>将写入 <b>{preview['writable']}</b> 条；"
        f"未匹配 <b class=\"wn\">{len(preview['unmatched'])}</b> 条；"
        f"异常 <b class=\"dg\">{len(preview['anomalies'])}</b> 条。"
        + ("（检测到首行是表头，已自动跳过）" if preview.get("skipped_header") else "")
        + "</p>"
    )
    body = (
        f'<h4 style="margin:12px 0 4px;font-size:13.5px">将写入（前 300 行）</h4>'
        f'<div class="gridwrap"><table><thead><tr><th>单据号</th><th class="num">付款金额</th>'
        f'<th>付款时间</th><th>付款方式</th><th>备注</th></tr></thead><tbody>{rows}</tbody></table></div>'
        f'<h4 style="margin:12px 0 4px;font-size:13.5px">未匹配清单（单据号在本地找不到 —— 多半是该月通知书还没抓）</h4>'
        f'<div class="gridwrap"><table><thead><tr><th>行</th><th>单据号</th>'
        f'<th class="num">付款金额</th><th>付款时间</th></tr></thead><tbody>{unmatched}</tbody></table></div>'
        f'<h4 style="margin:12px 0 4px;font-size:13.5px">异常清单（不入库）</h4>'
        f'<div class="gridwrap"><table><thead><tr><th>行</th><th>单据号</th><th>原因</th></tr></thead>'
        f'<tbody>{anomalies}</tbody></table></div>'
        f'<h4 style="margin:12px 0 4px;font-size:13.5px">未识别的付款方式取值（已归入「其他」、原文进备注）</h4>'
        f'<p>{unknown}</p>'
        f'<form method="post" action="/m05/import/confirm">'
        f'<input type="hidden" name="token" value="{esc(token)}">'
        f'<button class="pri" type="submit">确认导入（写库并记批次）</button>'
        f'</form></div>'
    )
    return header + body


def _report_html(report: dict) -> str:
    rows = "".join(
        f"<tr><td>{esc(r['bill_no'])}</td><td>{esc(r['doc_date'])}</td>"
        f"<td>{esc(r['project_name'])}</td><td class='num'>{esc(r['amount_approved'])}</td></tr>"
        for r in report["rows"][:300]
    ) or '<tr><td colspan="4" class="mut">（无 —— 这些月份的每张通知书都有流水了）</td></tr>'
    return (
        '<div class="blk"><h3>③ 核对报告</h3>'
        f"<p>批次 <b>{esc(report['batch'])}</b> · 涉及月份 "
        f"{esc('、'.join(report['months']) or '—')} · "
        f"其中 <b class=\"wn\">{report['count']}</b> 张通知书**一条流水都没有**：</p>"
        f'<div class="gridwrap"><table><thead><tr><th>单据号</th><th>单据日期</th>'
        f'<th>付款项目</th><th class="num">审批金额</th></tr></thead><tbody>{rows}</tbody></table></div>'
        '<p class="mut sm">⚠️ 这一块**比导入本身更值钱**：它就是"Excel 有没有漏记"的显式清单 —— '
        '若某张单确实付过，请补进 Excel 再重导该批。</p>'
        f'<form method="post" action="/m05/import/rollback" onsubmit="return confirm(\'确定整批回滚？'
        f'该批流水将置为已撤销（留痕、不物理删）。\')">'
        f'<input type="hidden" name="batch" value="{esc(report["batch"])}">'
        f'<button type="submit">整批回滚后重导</button></form></div>'
    )


def render_import_page(*, current: str = "/m05/import", message: str = "", kind: str = "ok",
                       preview=None, token: str = "", report=None) -> str:
    steps = "".join(
        f'<div class="step"><b>{esc(n)} {esc(t)}</b><div class="mut">{esc(d)}</div></div>'
        for n, t, d in _STEPS
    )
    body = f'<div class="imp">{_cols_html()}'
    if preview is None:
        body += f'<div class="blk"><h3>三步走</h3><div class="steps">{steps}</div></div>'
        body += _upload_html()
    else:
        body += _preview_html(preview, token)
    if report is not None:
        body += _report_html(report)
    body += "</div>"
    return _shell(title="历史付款流水导入", body=body, current=current,
                  notice=_notice(message, kind), extra=_css())


__all__ = ["render_import_page"]
