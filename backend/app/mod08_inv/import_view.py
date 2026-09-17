"""`MOD-08` **库存单据明细 · 手动 Excel 导入页**（§3.6 的降级通道）—— 三步：选文件 → 预览 → 确认。

> **为什么需要它**：`API-03` 接口不可用时（§3.6）**必须有手动通道**，否则「i8 一坏就断粮」。
> ⚠️ 与抓取**同一条管线**：上传的就是 i8 导出的那个 `.xlsx` ⇒ 同一个解析器
>   （`importer.parse_rows`：按表头认列 · 缺关键列即报错）＋ 同一个幂等落库（`upsert_details`）。

⚠️ 本页**没有「整批回滚」**：库存单据是**幂等刷新**（键 = 核算年月 ＋ 仓库 ＋ 单据编号 ＋ 序号）
   ⇒ 「导错了」= **改好文件再导一次**（同月同仓库会被更新而不是新增，§9.5）。
   ⛔ 这与付款域 / 过程资料历史段的「批次 ＋ 整批回滚」**不是同一形态** —— 那两处是**只增不改的旁路账**。
⚠️ 页面文案**不用 `**` 标记**（本仓说明文字统一只 `esc`）⇒ 强调直接拼 `<b>`。
"""

from __future__ import annotations

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc
from app.mod08_inv.importer import IGNORED_HEADERS, REQUIRED_HEADERS

TITLE = "库存单据 · 手动导入 Excel"

_STEPS = (
    ("①", "选文件", "上传 <b>i8 导出的那个 xlsx</b>（原样，不用改列名）；点「解析并预览」"
                   "——<b>这一步不写库</b>。"),
    ("②", "预览", "按「核算年月 ＋ 仓库」分组给出行数与金额合计；确认无误再往下。"),
    ("③", "确认导入", "走<b>同一条幂等刷新管线</b>：同月同仓库重导 = <b>更新</b>，不会新增重复行；"
                     "⛔ <b>调整单一行不动</b>（§5.2.4）。"),
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
"""


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _shell(*, body: str, notice: str = "") -> str:
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>{esc(TITLE)}</h1><nav>{_nav_html()}</nav></div>'
        '<section class="view" data-view="m08-import">'
        f"<h3>{esc(TITLE)}</h3>{notice}{body}</section></div></body></html>"
    )


def _notice(message: str, kind: str = "ok") -> str:
    if not str(message or ""):
        return ""
    k = str(kind or "ok")
    k = k if k in ("ok", "wn", "err") else "ok"
    return f'<div class="notice {k}">{esc(message)}</div>'


def _cols_html() -> str:
    rows = "".join(f"<tr><td>{esc(h)}</td></tr>" for h in REQUIRED_HEADERS)
    return (
        '<div class="blk"><h3>① 文件要求（列清单的主人 = i8 导出表头）</h3>'
        "<p class=\"sm\">就是 i8「<b>库存单据明细</b>」导出的那个 <b>xlsx</b> —— <b>原样上传</b>即可。"
        "表头不在固定行也能认（前 10 行内自动找）；列按下表认名、<b>不按位置</b>。</p>"
        '<table><thead><tr><th>必须有这些列（少一列 ⇒ 整份拒绝并指出缺哪一列）</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        f'<p class="mut sm">⛔ 以下源列<b>刻意不采</b>：{esc(" / ".join(IGNORED_HEADERS))}'
        "（本系统不建「是否作废」字段）。<br>"
        "• 核算年月取 <b>「核算年」＋「核算月」两列</b>，<b>不是</b>「单据日期」（§9.2 / §3.4）。<br>"
        "• 金额列非数字 ⇒ <b>报错并指出行号</b>，不静默丢行。</p></div>"
    )


def _upload_html() -> str:
    return (
        '<div class="blk"><h3>选文件</h3>'
        '<form class="upload" method="post" action="/m08/import/preview" '
        'enctype="multipart/form-data">'
        '<input type="file" name="file" accept=".xlsx" required>'
        '<button class="btn sm pri" type="submit">解析并预览（不写库）</button>'
        '<span class="mut sm">只读「报表1 / Sheet1」（没有就取第一个工作表）。</span>'
        "</form></div>"
    )


def _groups_html(preview: dict) -> str:
    rows = "".join(
        f'<tr><td>{esc(g["ym"])}</td><td>{esc(g["warehouse"])}</td>'
        f'<td class="num">{g["rows"]}</td><td class="num">{esc(g["amount"])}</td></tr>'
        for g in preview["groups"]
    ) or '<tr><td colspan="4" class="mut">（没有可写入的行）</td></tr>'
    return (
        '<div class="gridwrap"><table><thead><tr><th>核算年月</th><th>仓库</th>'
        f'<th class="num">行数</th><th class="num">金额合计</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _preview_html(preview: dict, token: str) -> str:
    return (
        '<div class="blk"><h3>② 预览 —— <b>尚未写库</b></h3>'
        f"<p>解析出 <b>{preview['rows']}</b> 行，落在 <b>{len(preview['groups'])}</b> 个"
        f"「核算年月 ＋ 仓库」范围里（刷新就按这个范围做幂等）。</p>"
        f"{_groups_html(preview)}"
        '<form method="post" action="/m08/import/confirm">'
        f'<input type="hidden" name="token" value="{esc(token)}">'
        '<p style="margin-top:10px">'
        '<button class="btn sm pri" type="submit">确认导入（写库 · 幂等刷新）</button></p>'
        '<div class="mut sm">同月同仓库重导 = <b>更新</b>（键 = 核算年月 ＋ 仓库 ＋ 单据编号 ＋ 序号）；'
        "本次不再出现、且<b>没有调整单</b>的行会被删掉（不留残影）；"
        '⛔ <b>有调整单的行一定保留</b>，调整单本身一行不改（§5.2.4 · `ENT-04`）。</div>'
        "</form></div>"
    )


def _result_html(result: dict) -> str:
    rows = "".join(
        f'<tr><td>{esc(g["ym"])}</td><td>{esc(g["warehouse"])}</td><td class="num">{g["rows"]}</td>'
        f'<td class="num">{g["inserted"]}</td><td class="num">{g["updated"]}</td>'
        f'<td class="num">{g["deleted"]}</td><td class="num">{g["kept_with_adjustment"]}</td></tr>'
        for g in result["groups"]
    ) or '<tr><td colspan="7" class="mut">（没有范围）</td></tr>'
    t = result["totals"]
    return (
        '<div class="blk"><h3>③ 导入结果</h3>'
        '<div class="gridwrap"><table><thead><tr><th>核算年月</th><th>仓库</th>'
        '<th class="num">行数</th><th class="num">新增</th><th class="num">更新</th>'
        '<th class="num">删除</th><th class="num">因调整单保留</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        f'<p>合计：新增 <b>{t["inserted"]}</b> · 更新 <b>{t["updated"]}</b> · '
        f'删除 <b>{t["deleted"]}</b> · <b>因有调整单而保留 {t["kept_with_adjustment"]}</b>'
        f'（共 {len(result["groups"])} 个「核算年月 ＋ 仓库」范围）。</p>'
        '<p class="mut sm">⚠️ 这批是<b>手动上传</b>的（降级通道）—— 看板「本月是否抓过」看的是'
        "<b>抓取</b>执行记录，手动导入不计入。</p></div>"
    )


def render_import_page(*, message: str = "", kind: str = "ok", preview: dict | None = None,
                       token: str = "", result: dict | None = None) -> str:
    body = f'<div class="imp">{_notice(message, kind)}{_cols_html()}'
    if preview is None and result is None:
        body += f'<div class="blk"><h3>三步走</h3><div class="steps">' + "".join(
            f'<div class="step"><b>{n} {esc(t)}</b><div class="mut">{d}</div></div>'
            for n, t, d in _STEPS) + "</div></div>"
        body += _upload_html()
    if preview is not None:
        body += _preview_html(preview, token)
    if result is not None:
        body += _result_html(result)
    body += "</div>"
    return _shell(body=body)


__all__ = ["TITLE", "render_import_page"]
