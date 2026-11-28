"""付款域页面装配（`MOD-03` / `MOD-04` / `MOD-05` 列表页骨架 · **纯函数**）。

依据：
- 《说明书》§4.1.2（付款域的**范围定义** —— 包含什么 / 不包含什么）
- `docs/requirements/interaction-rules.md`：**R1**（口径说明只给一个折叠块）· **R2**（`.kpis` 只在域级总览页）·
  **R4**（筛选栏）· **R10①**（空态给提示行、跨列数由表头派生）· **R13**（表头点击排序 ·
  **钉住行**含「合计 / 总计 / 小计」的行恒在最底、不参与排序 · **分段表**按「总求和」四段加竖线分隔）
- 合计行**视口吸附置底**的实测结论 → `docs/reference/sticky-total-row.md`（含"为什么原型那套 CSS 不生效"）

⚠️ 交付形态 = **后端托管单页**（零构建、零新模块）⇒ 页面骨架在这里装配成 HTML，由路由直接返回。
⚠️ **本模块只装配骨架**：业务取值回主人（《说明书》），筛选 / 排序的**判定**一律调各域 `domain` 的出口（不重写）。
"""

from __future__ import annotations

from app.mod03_notice.list_page import (
    DEFAULT_EMPTY_TEXT,
    LIST_PAGE_SEGMENTS,
    SEG_DATA,
    SEG_EMPTY,
    SEG_FILTER,
    SEG_KPIS,
    SEG_TIP,
    SORT_ASC,
    SORT_DESC,
    SORT_NONE,
    UNSORTABLE_LABELS,
    esc,
    is_sortable,
    nav_html,
    next_sort_direction,
    render_list_page,
    segment_sequence,
    sort_rows,
    tip_block_count,
)

# ============================================================ §4.1.2 付款域的范围定义

SCOPE_INCLUDED: tuple[str, ...] = (
    "付款通知书抓取、剔除、分类",
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

PAY_DOMAIN_IDS: tuple[str, ...] = ("m03", "m05")

# 付款域导航（**页面划分**）：一页一项主职责，`covers` = 它承载「包含」里的哪几项
PAY_DOMAIN_PAGES: tuple[dict, ...] = (
    {
        "id": "m03",
        "title": "付款通知书",
        "covers": ("付款通知书抓取、剔除、分类", "付款通知书标记与打印"),
    },
    {
        "id": "m05",
        "title": "付款流水与欠款统计",
        "covers": ("付款登记（流水）", "欠款统计与付款统计"),
    },
)


def pay_domain_nav() -> tuple[dict, ...]:
    """付款域导航条目（`m03` / `m05`）。"""
    return PAY_DOMAIN_PAGES


def nav_violations() -> list[str]:
    """导航与 §4.1.2 范围定义的**偏差清单**（空 = 合规）。

    三条：① 页面集合必须恰好是 `m03`/`m05`；② 每页声明的覆盖项必须落在「包含」里；
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


# 两个样式端点和外观卡片共用同一组颜色角色。
FONT_CSS = "@import url('/static/fonts/misans-web.css');\n"
DEFAULT_THEME = "松绿"

# ==== 主题定义区（THEME-DEF BEGIN）====
THEME_SEEDS: dict[str, dict[str, str]] = {
    DEFAULT_THEME: {
        "--bg": "#edf3f0", "--sf": "#ffffff", "--sf2": "#f2f7f5", "--sf3": "#e6efeb",
        "--tx": "#182c26", "--tx2": "#304640", "--mut": "#4c625b", "--mut2": "#526a61",
        "--on": "#ffffff",
        "--bd": "#cfddd7", "--bd2": "#e0e9e4", "--bd3": "#6b8177",
        "--pri": "#0c6b61", "--pri-d": "#09544c", "--pri-l": "#e6f2ee",
        "--pri-bd": "#98c5bc", "--pri-hl": "#4d9a90",
        "--sb": "#0b221d", "--sb-bd": "#28453e", "--sb-hd": "#f4faf7",
        "--sb-tx": "#d9e9e2", "--sb-mut": "#a9c1b7", "--sb-dis": "#a9c1b7",
        "--sb-hover": "#15352c", "--sb-on": "#17483d", "--sb-on-hl": "#effbf6",
        "--toast-bg": "#0b221d", "--code-bg": "#ffffff",
        "--row-hover": "#edf6f2", "--sel": "#c5e7dc", "--th-hover": "#ddeae4",
        "--ex-bg": "#f2f7f5", "--hl": "#f3eedf", "--hl-hover": "#ebdfc4",
        "--edit-l": "#f2ecdc", "--edit-bd": "#c8a265", "--void-bg": "#efece8",
        "--draft": "#eef1ea", "--del-line": "#6b8177",
        "--ok": "#215b45", "--ok-d": "#184433", "--ok-l": "#eaf4ed", "--ok-bd": "#b3cdbe",
        "--wn": "#69490c", "--wn-d": "#523808", "--wn-l": "#fcf2db", "--wn-bd": "#ddc58f",
        "--dg": "#962f38", "--dg-d": "#78222a", "--dg-l": "#f9eaea", "--dg-bd": "#e1b6b8",
        "--bl": "#245974", "--bl-d": "#1b4358", "--bl-l": "#ebf4f8", "--bl-bd": "#b5cedc",
        "--in": "#455650", "--in-d": "#32403b", "--in-l": "#eef2f0", "--in-bd": "#bac7c2",
        "--vi": "#5b3b8c", "--vi-d": "#452b6c", "--vi-l": "#f3effa", "--vi-bd": "#cabce3",
        "--mask": "rgba(8, 27, 22, 0.52)",
        "--shadow": "0 1px 2px rgba(8, 27, 22, 0.08)",
        "--shadow-pop": "0 6px 20px rgba(8, 27, 22, 0.14)",
        "--shadow-md": "0 16px 40px rgba(8, 27, 22, 0.2)",
        "--shadow-toast": "0 8px 22px rgba(8, 27, 22, 0.24)",
    },
}
# ==== /主题定义区（THEME-DEF END）====

THEME_SPEC = {
    DEFAULT_THEME: {"scene": "日常录入 · 台账核对", "style": "精工深墨松绿"},
}
REACT_THEME_SPEC = {
    name: {"description": spec["style"], "scene": spec["scene"], "label": name}
    for name, spec in THEME_SPEC.items()
}

GEOMETRY = {
    "--r": "6px", "--r2": "8px",
    "--fs": "'MiSans','Microsoft YaHei','PingFang SC',system-ui,sans-serif",
    "--fm": "var(--fs)",
}
REACT_GEOMETRY = {
    "--ui-scheme": "light",
    "--font-ui-size": "13.5",
    "--radius-input": "var(--r)",
    "--radius-card": "var(--r2)",
    "--radius-inner": "var(--r)",
    "--radius-pill": "var(--r)",
    "--motion-fast": "130ms",
}


def theme_name(name: str | None) -> str:
    """未设置、退役或未知的主题名显示为松绿。"""
    return name if name is not None and name in THEME_SEEDS else DEFAULT_THEME


def theme_variables(name: str | None) -> dict[str, str]:
    return {**THEME_SEEDS[theme_name(name)], **GEOMETRY}


def render_theme(name: str | None) -> str:
    body = "\n".join(f"  {key}:{value};" for key, value in theme_variables(name).items())
    return FONT_CSS + ":root{\n" + body + "\n}\n"


def theme_names() -> list[str]:
    return list(THEME_SEEDS)


THEME_CSS = render_theme(DEFAULT_THEME)


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
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 var(--fs);font-variant-numeric:tabular-nums}
button,input,select,textarea{font-family:var(--fs);font-variant-numeric:tabular-nums}
b,strong{font-weight:600}
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
/* 项目选择器（共用件 `proj_panel_html()`）—— 类名照原型（`.fi.pjwrap` ＋ `.pjsel`），样式只此一处 */
.pjwrap{position:relative}
.pjwrap>details>summary{list-style:none;display:inline-flex;align-items:center;gap:8px;min-width:126px}
.pjwrap>details>summary::-webkit-details-marker{display:none}
.pjwrap>details[open]>summary{border-color:var(--pri);color:var(--pri)}
.pjsel{position:absolute;z-index:5;top:calc(100% + 2px);left:0;min-width:220px;max-height:260px;overflow:auto;
       background:var(--sf);border:1px solid var(--bd3);border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.12);
       padding:6px 8px;display:flex;flex-direction:column;gap:4px}
.pjsel label{display:flex;gap:6px;align-items:center;font-size:12.5px;white-space:nowrap;color:var(--tx)}
/* 全站分组侧栏导航（唯一出口 `nav_html()`）—— **固定定位** ⇒ 调用方不必改 HTML 结构 */
.sbar{position:fixed;left:0;top:0;bottom:0;width:196px;overflow:auto;z-index:20;
      background:var(--sf);border-right:1px solid var(--bd);padding:10px 8px;font-size:12.5px}
.sbar .sb-h{font-weight:600;font-size:13px;margin:2px 0 8px 4px}
.sbar .sb-g{margin:9px 0 3px 4px;font-size:11px;color:var(--mut)}
.sbar .sb-i{display:flex;gap:6px;align-items:center;padding:4px 8px;border-radius:6px;color:var(--tx);
            text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sbar .sb-i:hover{background:var(--bd)}
.sbar .sb-i.on{background:var(--pri);color:var(--on)}
.sbar .sb-i.on .m{color:var(--on);opacity:.85}
.sbar .sb-i.dis{color:var(--mut);cursor:not-allowed}
.sbar .m{font-size:10px;color:var(--mut)}
body:has(>.sbar){padding-left:204px}
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

# ============================================================ 再导出（`TAIL-06` 2026-09-21 拆件）
#
# ⚠️ **本文件仍是老调用方眼里的"那个 page"**：`esc` / `sort_rows` / `SORT_*` /
#    `render_list_page` / `SEG_*` / `DEFAULT_EMPTY_TEXT` / `UNSORTABLE_LABELS` / `is_sortable` /
#    `tip_block_count` / `segment_sequence` / `nav_html` 全部**住在新件** `list_page.py` 里
#    （2026-09-21 为清 `T5` 的「>600 禁合入」红线而整体切出）⇒ 这里**再导出**，一处不改调用方。
# ⛔ 加新函数请加到**真正该住的那一件**（列表页骨架 → `list_page.py`；主题真源 → 本文件），
#    这里只留再导出与付款域范围口径。
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
