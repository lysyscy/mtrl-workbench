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

import re

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
# ⭐ 2026-09-19（`§19` 性能·**主题②**）：**取值本尊换成了 `demo/` 原型那一套**（此前是另一套
#    「站点配色」）。原委：本表的**第三路消费者 = 前端壳** `backend/app/web/index.html`
#    （经 `GET /static/theme.css`）—— 壳原先自带一份 `:root`（同名的 16 个取值都不同），
#    那是**第二份真源**；用户 2026-09-19 裁定「**服务端渲染页迟早删干净、只看壳**」⇒ 以**壳现值**
#    为准（观感零变化），服务端那几页跟着变（它们本就在删除清单上）。同时把壳需要的角色
#    （中性档 `--in-*` / 特殊档 `--vi-*` / 侧栏 `--sb-*` / 阴影 `--shadow-*` / 几何与字体
#    `--r` `--r2` `--fs` `--fm`）**一并收进本表** ⇒ 壳此后**零本地变量定义**（只有一条 `<link>`）。
#    ⛔ 再往壳里写色值字面量或自带 `:root` ⇒ `test_theme.py` 的红灯（已扫壳）。
THEME_CSS = """
:root{
  /* 中性 / 表面 */
  --bg:#f4f6f9; --sf:#fff; --sf2:#f8fafc; --sf3:#f4f4f5;
  --bd:#e3e8ef; --bd2:#eef1f5; --bd3:#c4ccd8;
  --tx:#1f2329; --tx2:#5c6675; --mut:#8b95a5; --mut2:#c9d0da;
  --on:#fff;
  /* 主色（四档 ＋ 高亮档） */
  --pri:#2563eb; --pri-d:#1d4ed8; --pri-l:#eff5ff; --pri-bd:#dbeafe; --pri-hl:#93c5fd;
  /* 状态色：绿 / 琥珀 / 红 —— 各四档成组 */
  --ok:#16a34a; --ok-d:#15803d; --ok-l:#f0fdf4; --ok-bd:#bbf7d0;
  --wn:#d97706; --wn-d:#92400e; --wn-l:#fffbeb; --wn-bd:#fde68a;
  --dg:#dc2626; --dg-d:#991b1b; --dg-l:#fef2f2; --dg-bd:#fecaca;
  /* 中性档（普通 / 未付款）与特殊档（集采 / 紫）—— 同样四档成组 */
  --in:#64748b; --in-d:#475569; --in-l:#f1f5f9; --in-bd:#e2e8f0;
  --vi:#7c3aed; --vi-d:#6d28d9; --vi-l:#f5f3ff; --vi-bd:#ddd6fe;
  /* 行态 / 可改格 */
  --row-hover:#fafbfc; --ex-bg:#fafafa; --hl:#fff8f0; --hl-hover:#fef3c7;
  --sel:#e0e7ff; --void-bg:#fffbf5; --draft:#fffdf5; --edit-l:#fffbeb; --edit-bd:#fcd34d;
  --th-hover:#e9eef5; --del-line:#d4d4d4;
  /* 侧栏（深色面板）与提示条 */
  --sb:#1e293b; --sb-bd:#334155; --sb-tx:#cbd5e1; --sb-mut:#7c8ba1; --sb-dis:#4b5563;
  --sb-hover:#273449; --sb-on:#0f172a; --sb-on-hl:#60a5fa;
  --toast-bg:#1e293b; --code-bg:#fff9;
  /* 阴影 / 遮罩 */
  --shadow:0 1px 2px #0f172a12; --shadow-pop:0 8px 24px #0f172a26;
  --shadow-md:0 12px 32px #0f172a2e; --shadow-toast:0 8px 22px #0f172a3d; --mask:#0f172a66;
  /* 几何与字体（非颜色；壳与页面共用同一份，故一并收进真源） */
  --r:8px; --r2:12px;
  --fs:'Microsoft YaHei','PingFang SC',system-ui,-apple-system,'Segoe UI',sans-serif;
  --fm:ui-monospace,'Cascadia Mono',Consolas,monospace;
}
"""

# ============================================================ 多主题（《说明书》§7.7）
# ⭐ 用户 2026-09-20 定：预置主题清单**≥10 套**（"换着玩"）。
#
# ⚠️⚠️ **为什么是"种子 + 派生"而不是 12 份手抄**：
#   一套主题 = **67 个变量**（色值 ＋ 几何/字体）⇒ 12 套手抄 = **800 多个值**，
#   必然出现**漏项**（引用了没定义 ⇒ 整条声明静默失效）与**跨套漂移**（第 3 套的
#   `--ok-l` 忘了跟着 `--ok` 改 ⇒ "新绿字配旧浅绿底"，§7.7 明确要防的就是这个）。
#   ⇒ 改成**一行种子 → 派生整套**：清单再长，**产出形态不变**（仍是"一份变量取值"），
#     而"每套覆盖同一组变量名"**由构造保证**（不是靠人记）。
#
# ⚠️ **默认套不走派生** —— 它**原样沿用**下面那段 `THEME_CSS` 字面量 ⇒ **观感零变化**，
#    `BASE_CSS` / `test_theme.py` 的既有断言**一个字都不用动**（零破坏）。


def _rgb(c: str) -> tuple[int, int, int]:
    c = str(c).lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _hex(x) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in x)


def _mix(a: str, b: str, t: float) -> str:
    """线性混色：`t=0` 全取 `a`、`t=1` 全取 `b`。

    ⚠️ **`--x-l`（浅底）要朝"本套的底色"混、⛔ 不是朝白色混** —— 否则深色主题会派生出一堆
       白底浅色块（深色主题里的"浅底"必须是"比底色稍亮"）。
    """
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ca, cb)))


def _lum(c: str) -> float:
    r, g, b = _rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _on(c: str) -> str:
    """该色**上面**的前景色（黑或白）—— 按亮度选，保证能看清。

    ⚠️ 区外函数 ⇒ 只许用区里那两个常量（⛔ 不写字面量）。
    """
    return _PURE_WHITE if _lum(c) < 0.58 else _PURE_BLACK


# ==== 主题定义区（THEME-DEF BEGIN）====
# ⚠️⚠️ **本区是"颜色字面量"唯一允许出现的地方**（`test_theme.py` 按这两个标记断区）
#   —— §7.7 说的「一份主题变量表统管」就是它。⛔ 别把色值写到区外。
_PURE_BLACK = "#000000"
_PURE_WHITE = "#ffffff"

#: 三个状态色 ＋ 中性档 ＋ 特殊档的**种子**（每套主题一样，只有色相不同）
_STATE_SEEDS = {"ok": "#16a34a", "wn": "#d97706", "dg": "#dc2626",
                "in": "#64748b", "vi": "#7c3aed"}


def _derive(seed: dict) -> dict[str, str]:
    """种子 → **整套变量**（67 个）。每套都由这一个函数产出 ⇒ 覆盖面天然一致。"""
    bg, sf, tx = seed["bg"], seed["sf"], seed["tx"]
    pri = seed["pri"]
    dark = bool(seed.get("dark"))
    # 表面 / 中性：深色套往**更亮**走、浅色套往**更暗**走
    step = -1 if dark else 1
    v = {
        "--bg": bg,
        "--sf": sf,
        "--sf2": _mix(sf, bg, 0.45),
        "--sf3": _mix(sf, bg, 0.85),
        "--bd": _mix(bg, tx, 0.14),
        "--bd2": _mix(bg, tx, 0.07),
        "--bd3": _mix(bg, tx, 0.32),
        "--tx": tx,
        "--tx2": _mix(tx, bg, 0.32),
        "--mut": _mix(tx, bg, 0.55),
        "--mut2": _mix(tx, bg, 0.78),
        "--on": _on(pri),
    }
    # 主色四档 ＋ 高亮档（浅底朝**底色**混 ⇒ 深色套自动得到"暗底"）
    v["--pri"] = pri
    v["--pri-d"] = _mix(pri, "#000000" if not dark else "#ffffff", 0.22)
    v["--pri-l"] = _mix(pri, bg, 0.90 if not dark else 0.86)
    v["--pri-bd"] = _mix(pri, bg, 0.66 if not dark else 0.72)
    v["--pri-hl"] = _mix(pri, bg, 0.35 if not dark else 0.45)
    # 状态 / 中性档 / 特殊档：各四档成组（§7.7 硬要求）
    for k, c in _STATE_SEEDS.items():
        v[f"--{k}"] = c
        v[f"--{k}-d"] = _mix(c, "#000000" if not dark else "#ffffff", 0.28)
        v[f"--{k}-l"] = _mix(c, bg, 0.90 if not dark else 0.84)
        v[f"--{k}-bd"] = _mix(c, bg, 0.66 if not dark else 0.72)
    # 行态 / 可改格
    v["--row-hover"] = _mix(sf, pri, 0.06)
    v["--ex-bg"] = _mix(sf, bg, 0.75)
    v["--hl"] = _mix(bg, "#d97706", 0.10 if not dark else 0.14)
    v["--hl-hover"] = _mix(bg, "#d97706", 0.20 if not dark else 0.24)
    v["--sel"] = _mix(bg, pri, 0.22 if not dark else 0.30)
    v["--void-bg"] = _mix(bg, "#dc2626", 0.06 if not dark else 0.10)
    v["--draft"] = _mix(bg, "#d97706", 0.05 if not dark else 0.09)
    v["--edit-l"] = _mix(bg, "#d97706", 0.12 if not dark else 0.16)
    v["--edit-bd"] = _mix(bg, "#d97706", 0.42)
    v["--th-hover"] = _mix(bg, pri, 0.10 if not dark else 0.16)
    v["--del-line"] = _mix(tx, bg, 0.70)
    # 侧栏（深色面板 —— 与内容区**拉开**，故从 tx 往黑走）
    sb = _mix(tx, "#0b1220", 0.62) if not dark else _mix(bg, "#000000", 0.45)
    v["--sb"] = sb
    v["--sb-bd"] = _mix(sb, "#ffffff", 0.14)
    v["--sb-tx"] = _mix(sb, "#ffffff", 0.72)
    v["--sb-mut"] = _mix(sb, "#ffffff", 0.48)
    v["--sb-dis"] = _mix(sb, "#ffffff", 0.28)
    v["--sb-hover"] = _mix(sb, "#ffffff", 0.10)
    v["--sb-on"] = _mix(sb, "#000000", 0.35)
    v["--sb-on-hl"] = _mix(pri, "#ffffff", 0.35)
    v["--toast-bg"] = sb if not dark else _mix(bg, "#ffffff", 0.10)
    v["--code-bg"] = "#fff9" if not dark else "#ffffff14"
    # 阴影 / 遮罩（透明度固定，深浅由"叠在什么底上"决定）
    v["--shadow"] = "0 1px 2px #0f172a12" if not dark else "0 1px 2px #00000040"
    v["--shadow-pop"] = "0 8px 24px #0f172a26" if not dark else "0 8px 24px #00000059"
    v["--shadow-md"] = "0 12px 32px #0f172a2e" if not dark else "0 12px 32px #00000066"
    v["--shadow-toast"] = "0 8px 22px #0f172a3d" if not dark else "0 8px 22px #00000073"
    v["--mask"] = "#0f172a66" if not dark else "#000000a6"
    return v


#: 几何与字体 —— **所有主题共用**（不是颜色；换主题不该改变尺寸与字号）
GEOMETRY = {
    "--r": "8px", "--r2": "12px",
    "--fs": "'Microsoft YaHei','PingFang SC',system-ui,-apple-system,'Segoe UI',sans-serif",
    "--fm": "ui-monospace,'Cascadia Mono',Consolas,monospace",
}

#: ⭐ **预置主题清单的种子表**（加一套 = 加一行；《说明书》§7.7 列了清单与取向）
THEME_SEEDS: dict[str, dict] = {
    "默认": {},                                            # ⚠️ 空 = 用下面那段字面量（观感零变化）
    "靛青": {"bg": "#f5f6fb", "sf": "#ffffff", "tx": "#1e1b33", "pri": "#4f46e5"},
    "松绿": {"bg": "#f4f8f6", "sf": "#ffffff", "tx": "#16241f", "pri": "#0d9488"},
    "琥珀": {"bg": "#fbf7f1", "sf": "#ffffff", "tx": "#2a2117", "pri": "#d97706"},
    "绛红": {"bg": "#fbf5f5", "sf": "#ffffff", "tx": "#2a1a1a", "pri": "#dc2626"},
    "石墨": {"bg": "#f4f5f7", "sf": "#ffffff", "tx": "#22252a", "pri": "#475569"},
    "米黄": {"bg": "#faf6ee", "sf": "#fffdf8", "tx": "#2b2418", "pri": "#8b5e34"},
    "蓝灰工控": {"bg": "#eef1f5", "sf": "#fbfcfe", "tx": "#1b2430", "pri": "#1e40af"},
    "深色": {"bg": "#0f172a", "sf": "#172033", "tx": "#e2e8f0", "pri": "#60a5fa", "dark": True},
    "深色·松绿": {"bg": "#0d1b19", "sf": "#142623", "tx": "#d7e8e3", "pri": "#2dd4bf", "dark": True},
    "深色·琥珀": {"bg": "#1c1917", "sf": "#262220", "tx": "#e7e0d8", "pri": "#fbbf24", "dark": True},
    "深色·靛青": {"bg": "#12111f", "sf": "#1b1a2e", "tx": "#e0def0", "pri": "#818cf8", "dark": True},
    "高对比": {"bg": "#ffffff", "sf": "#ffffff", "tx": "#000000", "pri": "#0000ee"},
}
# ==== /主题定义区（THEME-DEF END）====


#: 未设置时的回落套（§7.7 ④）—— ⚠️ **必须在 `THEMES` 构造之前定义**：`render_theme` 会读它，
#:   而 `THEMES = {… render_theme(n) …}` 是**模块级立即求值** ⇒ 定义晚了就是 `NameError`。
DEFAULT_THEME = "默认"


def render_theme(name: str) -> str:
    """主题名 → CSS（**唯一产出出口**）。⚠️ **非法名 / 未设置 ⇒ 显式回落默认套**（§7.7）。"""
    if name == DEFAULT_THEME or name not in THEME_SEEDS:
        return THEME_CSS
    seed = THEME_SEEDS[name]
    if not seed:
        return THEME_CSS
    v = _derive(seed)
    v.update(GEOMETRY)
    missing = [k for k in _var_names() if k not in v]
    # ⚠️⚠️ §7.7「缺项即**显式报错**，不得静默沿用旧值」—— 这里**必须报**，⛔ 不能 `if k in v` 跳过：
    #    跳过 = 引用那条变量的声明**静默失效**（页面少一块样式、且**没有任何错误信号**），
    #    正是 §7.7 要防的那类错。报错**要带名字**（裸 `KeyError` 只说一个键、看不出是哪套主题缺的）。
    if missing:
        raise ValueError(
            f"主题「{name}」缺变量 {missing} —— §7.7：每套必须覆盖同一组变量名，缺项即显式报错"
            "（⛔ 不得静默沿用旧值）")
    body = "\n".join(f"  {k}:{v[k]};" for k in _var_names())
    return ":root{\n" + body + "\n}\n"


def _var_names() -> list[str]:
    """变量**名**的基准序（取自默认套）—— ⛔ 顺序也由它定，免得多套之间漂。"""
    return list(re.findall(r"(--[a-z0-9-]+):", THEME_CSS))


def theme_coverage_gaps() -> dict[str, list[str]]:
    """**覆盖面校验**：每套主题缺哪些变量名（空 dict = 全部齐）。

    ⚠️ 这是 §7.7「每套必须覆盖同一组变量名，**缺项即显式报错、不得静默沿用旧值**」的落点 ——
       缺项时引用它的那条声明 **不报错、只是静默失效**（页面少一块样式），是最难查的一类错。
    """
    base = set(_var_names())
    out: dict[str, list[str]] = {}
    for name, seed in THEME_SEEDS.items():
        if not seed:                                  # 「默认」= 走字面量，本身就是基准
            continue
        # ⚠️ **直接算派生结果的键**，⛔ 不靠"渲染一遍再正则抠" ——
        #    渲染会在缺项时**抛错**（那是对的），但那样这个函数就成了"要么空、要么崩"，
        #    没法给出"缺哪些"的清单。
        got = set(_derive(seed)) | set(GEOMETRY)
        if got != base:
            out[name] = sorted(base - got) + [f"+多余 {x}" for x in sorted(got - base)]
    return out


def theme_names() -> list[str]:
    """预置主题清单（**可列举** —— §7.7 判据的一条）。"""
    return list(THEME_SEEDS)


#: 清单 → 成品 CSS（**唯一真源的成品形态**）
#:
#: ⚠️⚠️ `render_theme` 在**缺变量**时是**显式抛错**的（那是 §7.7 的要求）——
#:    但这里是**模块级立即构造**，抛出来就是**导入即崩** ⇒ 那时连"哪套缺哪个变量"都看不到。
#:    ⇒ 所以这里**接住它、把原因记下来**（`_THEME_BUILD_ERROR`），让调用方/判据能**读出原因**。
#:    ⛔ 这**不是把错误吞掉**：`render_theme(name)` 该抛还抛（运行时照样显式报错），
#:       而且 `test_theme.py` 会断言 `_THEME_BUILD_ERROR` 为空 ⇒ 有缺项**必定变红**。
_THEME_BUILD_ERROR = ""
try:
    THEMES: dict[str, str] = {n: render_theme(n) for n in THEME_SEEDS}
except ValueError as _exc:                          # pragma: no cover —— 正常永远不进来
    THEMES = {}
    _THEME_BUILD_ERROR = str(_exc)


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
.sbar .sb-h{font-weight:700;font-size:13px;margin:2px 0 8px 4px}
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
from app.mod03_notice.list_page import (                      # noqa: F401
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
