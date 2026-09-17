"""付款域页面装配（`MOD-03` / `MOD-04` / `MOD-05` 列表页骨架 · **纯函数**）。

依据：
- 《说明书》§4.1.2（付款域的**范围定义** —— 包含什么 / 不包含什么）
- `demo/设计规则-提炼自付款通知书页.md`：**R1**（口径说明只给一个折叠块）· **R2**（`.kpis` 只在域级总览页）·
  **R4**（筛选栏）· **R10①**（空态给提示行、跨列数由表头派生）· **R13**（表头点击排序 ·
  **钉住行**含「合计 / 总计 / 小计」的行恒在最底、不参与排序 · **分段表**按「总求和」四段加竖线分隔）
- 合计行**视口吸附置底**的实测结论 → `ops/M3-合计行置底实测结论.md`（含"为什么原型那套 CSS 不生效"）

⚠️ 交付形态 = **后端托管单页**（零构建、零新模块）⇒ 页面骨架在这里装配成 HTML，由路由直接返回。
⚠️ **本模块只装配骨架**：业务取值回主人（《说明书》），筛选 / 排序的**判定**一律调各域 `domain` 的出口（不重写）。
"""

from __future__ import annotations

import html as _html
import re
from decimal import Decimal, InvalidOperation

# ============================================================ §4.1.2 付款域的范围定义

SCOPE_INCLUDED: tuple[str, ...] = (
    "付款通知书抓取、剔除、分类",
    "付款计划导入与审查",
    "付款登记（流水）",
    "欠款统计与付款统计",
    "付款通知书标记与打印",
)

SCOPE_EXCLUDED: tuple[str, ...] = (
    "项目端的入库/出库/审批操作",
    "大领导的审批动作",
    "会计记账",
    "集采欠款",
    "领导驾驶舱/大屏展示",
)

# 「不包含」的**可检出关键词** —— 它们**不得**出现在付款域任何页面的标题里
EXCLUDED_KEYWORDS: tuple[str, ...] = (
    "项目端操作", "入库", "出库", "审批动作", "大领导",
    "会计记账", "借贷", "集采欠款", "领导驾驶舱", "驾驶舱", "大屏",
)

PAY_DOMAIN_IDS: tuple[str, ...] = ("m03", "m04", "m05")

# 付款域导航（**页面划分**）：一页一项主职责，`covers` = 它承载「包含」里的哪几项
PAY_DOMAIN_PAGES: tuple[dict, ...] = (
    {
        "id": "m03",
        "title": "付款通知书",
        "covers": ("付款通知书抓取、剔除、分类", "付款通知书标记与打印"),
    },
    {
        "id": "m04",
        "title": "付款计划",
        "covers": ("付款计划导入与审查",),
    },
    {
        "id": "m05",
        "title": "付款流水与欠款统计",
        "covers": ("付款登记（流水）", "欠款统计与付款统计"),
    },
)


def pay_domain_nav() -> tuple[dict, ...]:
    """付款域导航条目（`m03` / `m04` / `m05`）。"""
    return PAY_DOMAIN_PAGES


def nav_violations() -> list[str]:
    """导航与 §4.1.2 范围定义的**偏差清单**（空 = 合规）。

    三条：① 页面集合必须恰好是 `m03`/`m04`/`m05`；② 每页声明的覆盖项必须落在「包含」里；
         ③ **「包含」的每一项都要有页面承载**、且任何页面标题**不得**出现「不包含」的项。
    """
    bad: list[str] = []
    ids = tuple(p["id"] for p in PAY_DOMAIN_PAGES)
    if ids != PAY_DOMAIN_IDS:
        bad.append(f"付款域页面应为 {PAY_DOMAIN_IDS}，实际 {ids}")

    covered: set[str] = set()
    for page in PAY_DOMAIN_PAGES:
        if not page.get("covers"):
            bad.append(f"{page['id']} 未声明它覆盖「包含」里的哪几项")
        extra = set(page.get("covers") or ()) - set(SCOPE_INCLUDED)
        if extra:
            bad.append(f"{page['id']} 声明了不在「包含」里的项：{sorted(extra)}")
        covered |= set(page.get("covers") or ())
        for kw in EXCLUDED_KEYWORDS:
            if kw in str(page.get("title") or ""):
                bad.append(f"{page['id']} 的标题含「不包含」项：{kw}")

    missing = set(SCOPE_INCLUDED) - covered
    if missing:
        bad.append(f"「包含」里没有页面承载的项：{sorted(missing)}")
    return bad


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
# ============================================================
# 主题变量 —— **全站唯一真源**（页面件主人 = 本文件）
# ============================================================
# 命名与语义**照 `demo/` 原型**（原型 = 交互规格主人；其 `:root` 与本表同名同义）。
# ⚠️ **为什么必须有这一层**：`sumrow` / `vsep` 两条规则本来就是从原型抄的（连 `var(--sf2)`、
#    `var(--bd)` 都照抄），却**没抄原型的 `:root`** ⇒ 变量无定义 ⇒ **整条声明静默失效**
#    （合计行吸附底色、内阴影、分段竖线全都不显示；2026-09-16 实测确认）。
#    本表补齐定义，并把 BASE_CSS 里的裸色值**全部**收进来（此后 CSS 里不再出现色值字面量）。
# ⚠️ **多主题约定（用户 2026-09-16 定：要支持多套主题自选）**：
#    ① **语义命名**（`--pri` 而非 `--blue`）—— 换一套主题时名字不变；
#    ② **成对颜色必须成组**：状态色按「主色 / 深字 / 浅底 / 浅边框」四档一组
#       （`--ok` `--ok-d` `--ok-l` `--ok-bd`），否则第 2 套会出现"新绿字配旧浅绿底"；
#    ③ **换主题 = 换这一份取值** ⇒ 零 CSS 改动（一套主题 ≈ 下面这段 `:root`）。
THEME_CSS = """
:root{
  --bg:#f5f7fa; --sf:#fff; --sf2:#fafafa; --sf3:#f4f4f5;
  --bd:#e4e7ed; --bd2:#ebeef5; --bd3:#dcdfe6;
  --tx:#303133; --tx2:#606266; --mut:#909399; --mut2:#c0c4cc;
  --pri:#409eff; --pri-d:#337ecc; --pri-l:#ecf5ff; --on:#fff;
  --ok:#67c23a; --ok-d:#529b2e; --ok-l:#f0f9eb; --ok-bd:#e1f3d8;
  --wn:#e6a23c; --wn-d:#b88230; --wn-l:#fdf6ec; --wn-bd:#faecd8;
  --dg:#f56c6c; --dg-d:#c45656; --dg-l:#fef0f0; --dg-bd:#fde2e2;
  --hl:#fff8f0; --draft:#fffdf5; --edit-l:#fffbe6; --row-hover:#f8fbff; --shadow:rgba(0,0,0,.12);
}
"""

STICKY_BOTTOM_CSS = (
    ".dt tbody tr.sumrow{position:sticky;bottom:0;z-index:2}"
    ".dt tbody tr.sumrow>td{background:var(--sf2);box-shadow:inset 0 1px 0 var(--bd)}"
)
# 段首列的**分段竖线**（「总求和」那种视觉分隔；四处一致由同一个 `_cells()` 出口保证）
# ⚠️ 原写法是 `var(--bd2)` —— **抄错了**：原型第 94 行用的是 `var(--bd)`（主边框），已照原型改正。
VSEP_CSS = ".dt th.vsep,.dt td.vsep{border-left:2px solid var(--bd)}"

# 全站共用的基础样式（页面件主人 = 本文件；`mod04` / `mod05` / `notice_pay` / `importer` 等视图**不再各写一份**）
# ⚠️ **自带主题变量**：`BASE_CSS` = `THEME_CSS` ＋ 基础样式 ⇒ 所有引用 `BASE_CSS` 的页面**自动获得**变量定义
#    （全工程 8 处引用，这样一处都不用改、也**不可能漏**）。
# ⚠️ 本段**不得再出现色值字面量** —— 一律走 `var(--…)`（换主题只改 `THEME_CSS` 一份）。
BASE_CSS = THEME_CSS + """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.wrap{max-width:1360px;margin:0 auto;padding:16px 18px 40px}
header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
header h1{font-size:18px;margin:0;font-weight:600}
section.view h3{font-size:15px;margin:0 0 10px;font-weight:500}
details.tip{background:var(--sf2);border:1px solid var(--bd);border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:13px}
details.tip summary{cursor:pointer;color:var(--tx2)}
details.tip ul{margin:6px 0 0;padding-left:18px;line-height:1.8}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.kpi{background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:8px 14px;min-width:118px}
.kpi .k{font-size:12px;color:var(--mut)}
.kpi .v{font-size:17px;font-weight:600}
.kpi .s{font-size:11px;color:var(--mut2)}
.fbar{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:10px 12px;margin-bottom:10px}
.fi{display:flex;flex-direction:column;gap:3px}
.fi label{font-size:12px;color:var(--mut)}
.fi input,.fi select{border:1px solid var(--bd3);border-radius:5px;padding:5px 8px;font-size:13px;min-height:30px}
.fi select[multiple]{min-height:64px}
.tw{overflow:auto;max-height:calc(100vh - 330px);min-height:220px;border:1px solid var(--bd);border-radius:6px;background:var(--sf)}
table.dt{width:100%;border-collapse:collapse}
.dt th,.dt td{padding:6px 9px;border-bottom:1px solid var(--bd2);font-size:12.5px;text-align:left;white-space:nowrap}
.dt th{position:sticky;top:0;z-index:2;background:var(--sf2);color:var(--tx2);font-weight:500}
.dt th .mut{color:var(--mut2);font-size:10px}
.dt th[data-sort-col]{cursor:pointer}
.dt th.nosort{background:var(--sf2)}
.dt .num{text-align:right;font-variant-numeric:tabular-nums}
.dt .now{white-space:nowrap}
.dt .ctr{text-align:center}
.dt tr.hl>td{background:var(--hl)}
.dt tr.empty>td{text-align:center;color:var(--mut);padding:26px 0}
.dt input.cell,.dt select.cell{border:1px solid var(--bd);border-radius:4px;padding:3px 6px;font-size:12.5px;background:var(--sf)}
.dt form.inline{display:inline-flex;gap:4px;align-items:center;margin:0}
button{border:1px solid var(--bd3);background:var(--sf);color:var(--tx);padding:4px 10px;border-radius:5px;cursor:pointer;font-size:12px}
button:hover{border-color:var(--pri);color:var(--pri)}
button.pri{background:var(--pri);border-color:var(--pri);color:var(--on)}
button.dg{background:var(--dg);border-color:var(--dg);color:var(--on)}
button:disabled{opacity:.5;cursor:not-allowed}
/* —— 类级基础控件与文字修饰（`TAIL-24` · 2026-09-17）——
   ⚠️ 上面几条用的是**元素选择器**（`button{}`）⇒ 只管 `<button>` 元素。本仓有 **15 处**
   `<a class="btn">`（重置 / 返回 / 取消 / 清除列筛选 / 查看原始行…）当按钮用 ⇒
   锚点拿不到 `button{}` 的样式，**会显示成纯链接文字**。`.inp` / `.sm` 此前同样**无任何规则**
   （`.inp` 只能靠调用点内联 style 兜，各页输入框长相不一）。
   ⚠️ `.mut` 原先**各页 `EXTRA_CSS` 各抄一份**，取值还不一致（`--mut` vs `--mut2`）⇒
   已删掉那两处页级副本，`.mut` / `.sm` / `.btn` / `.inp` **一律以本处为唯一真源**。 */
.btn{display:inline-block;text-decoration:none;border:1px solid var(--bd3);background:var(--sf);color:var(--tx);padding:4px 10px;border-radius:5px;cursor:pointer;font-size:12px;line-height:1.5}
.btn:hover{border-color:var(--pri);color:var(--pri)}
.btn.pri{background:var(--pri);border-color:var(--pri);color:var(--on)}
.btn.dg{background:var(--dg);border-color:var(--dg);color:var(--on)}
.btn[disabled],.btn:disabled{opacity:.5;cursor:not-allowed}
.btn[disabled]:hover{border-color:var(--bd3);color:var(--tx)}
.btn.sm{padding:2px 7px;font-size:11.5px}
.inp{border:1px solid var(--bd3);border-radius:5px;padding:5px 8px;font-size:13px;min-height:30px;background:var(--sf);color:var(--tx)}
.inp:focus{border-color:var(--pri);outline:2px solid var(--pri-l)}
.mut{color:var(--mut)}
.sm{font-size:11.5px}
.tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11.5px}
.tag.ok{background:var(--ok-l);color:var(--ok)}
.tag.wn{background:var(--wn-l);color:var(--wn)}
.tag.dg{background:var(--dg-l);color:var(--dg)}
.pill{display:inline-block;padding:3px 9px;border-radius:10px;background:var(--sf3);color:var(--mut);font-size:12px}
.notice{border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:13px}
.notice.ok{background:var(--ok-l);color:var(--ok-d);border:1px solid var(--ok-bd)}
.notice.err{background:var(--dg-l);color:var(--dg-d);border:1px solid var(--dg-bd)}
.notice.wn{background:var(--wn-l);color:var(--wn-d);border:1px solid var(--wn-bd)}
.kv{background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:12px 14px;margin-bottom:10px}
.kv div{display:flex;gap:10px;padding:3px 0;font-size:13px}
.kv b{min-width:110px;color:var(--mut);font-weight:400}
"""

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
        if f.get("html"):
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
    "SEG_TIP", "SEG_KPIS", "SEG_FILTER", "SEG_DATA", "SEG_EMPTY", "LIST_PAGE_SEGMENTS",
    "DEFAULT_EMPTY_TEXT", "THEME_CSS", "BASE_CSS", "STICKY_BOTTOM_CSS", "VSEP_CSS",
    "esc", "tip_block_count", "segment_sequence", "render_list_page",
    "UNSORTABLE_LABELS", "is_sortable", "SORT_NONE", "SORT_ASC", "SORT_DESC",
    "next_sort_direction", "sort_rows",
]
