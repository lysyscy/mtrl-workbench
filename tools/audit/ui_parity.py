"""**壳一致性核对器**（原型 ⇄ 前端壳）· **纯 Python · 不依赖浏览器**。

**为什么换了定义**（2026-09-17 · 用户裁定 `D18`）：
    旧定义是「**服务端渲染页**逐页对齐原型」—— 但前端已改成「**原型直接接数据**」：
    壳 = `demo/` 交互原型的**整体复制**，**只换数据源**。⇒ 结构对齐已由**构造**保证，
    再去数「表 / 筛 / 卡 / 折 / 合计 / 排序」**已经没有意义**（数的是同一份代码）。
    ⚠️ **旧口径（服务端页逐页对齐）已作废**；它原来盯的那批服务端渲染页，本身就在 `TAIL-27` 里要删掉。

**风险没有消失，只是挪了位置** ⇒ 本工具现在守三件事：
| 代号 | 守什么 | 判据 |
|---|---|---|
| `U1` | ⭐⭐ **原型逻辑一行不改**（D18 的硬约束）—— 把原型的筛选 / 排序 / 合计 / 勾选逻辑**顺手改掉**，就再没有"规格"可言了 | 壳的每个 `V.<页>` 切片 与原型同名切片**逐行一致**；差异未登记 ⇒ **红**（登记簿 `tools/ui_parity_expected.txt` · ⭐ 2026-09-25 起**可增可减**：新功能产生的正当差异照登；补回原型/消号时删行） |
| `U2` | **演示数据与"假话"不得残留**（D18 产品化红线①） | ① 壳里出现原型的三张演示数组（`PJ` / `NT` / `FL`）⇒ **红**；② 壳里必须**同时**存在「已接后端真实数据」与「原型态」两种措辞（缺任一种 ⇒ 顶栏又会**一律**说"全是虚构" = 对已接线页说假话）⇒ **红** |
| `U3` | **`WIRED` 自洽** | 壳里必须有 `WIRED` 集合，且**它的每个成员都真实存在于 `V`**（防"标了个不存在的页"）⇒ **红** |
| `U4` | ⭐ **`WIRED` 的页必须真的指向后端**（2026-09-17 补） | `WIRED` 里的每页 `mNN` ⇒ 壳里必须出现 `/api/mNN`。**这只是"接线点存在"，不是"调通了"** —— 但能挡住最廉价的一种假绿：把页标成"已接后端"而壳里**一个该模块的接口都没调**（顶栏就会对真数据说"已接"）⇒ **红** |
| `U5` | ⭐⭐ **壳公共件 ⇄ 原型里嵌的同段，逐行一致**（`TAIL-65` · 2026-09-23 立） | 登记表里的每个顶层件，**原型与壳必须逐字一致**（哈希比对）⇒ 不一致 / 任一侧缺件 ⇒ **红**。⚠️ **为什么必须有一条**：`U1` 只比**切片 `V.<页>`**，而"壳 83% 的地盘"在**切片之外**（表头模板 / 列序 / 枚举 / 纯函数）—— 那部分**原型里也存一份**（原型是交付面的交互规格，⛔ 不能给它加文件）⇒ **双份真源**；谁改一边 ⇒ 静默漂移（审计 §六 `C3`）。⇒ ⭐ 抽切片内的东西**之前**必须先立它（它是 `TAIL-64` 的闸门前置） |

⚠️ **本工具测不了什么（别误当已覆盖）**：**「标了已接后端，其实没接」** ——
    "某一页的数据由谁喂"无法从源码机械判定 ⇒ 那一条靠**真机自检**（`tools/probe/_shell_smoke.py` /
   `tools/probe/_shell_render_check.py`）与 `WIRED` 的人工维护。**「断言测不了」这句本身就是要害。**

跑法（⚠️ 2026-09-24 订正：尺子与探针的**真实位置** —— 旧写法 `tools/ui_parity.py` / `tools/_shell_smoke.py` 都已不存在）：
  `backend/.venv/Scripts/python.exe tools/audit/ui_parity.py`          # 人读表（有未登记漂移 ⇒ rc=1）
  `backend/.venv/Scripts/python.exe tools/audit/ui_parity.py --json`   # 机读
  `... --write-expected`                                                # 把当前漂移**登记**下来（人先审过再用）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

from shell_source import SHELL_PARTS, SHELL_PATH, read_shell  # noqa: E402  ← `P4`① 读取点收敛

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
# ⚠️ 2026-09-19（`P4`① 读取点收敛）：壳要拆成多件 ⇒ 源码一律走 `shell_source`。
#    `SHELL` 仍留作**存在性检查**（指 `index.html` 本体）；**读文本则用 `read_shell()`**（合并后的全部件）
#    —— 否则 `U2`（演示数组残留）与 `U4`（`/api/mNN` 在不在）会**静默**只看原型切片那一件。
SHELL = SHELL_PATH
EXPECTED = ROOT / "tools" / "ui_parity_expected.txt"

# 切片起点：行首的 `V.<名字> =`（壳与原型同构）
VIEW_RE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=")
# 切片终点：下一个 `V.` / `BIND.` / 顶层 `const` / `function` / 顶层 `let`|`var`
END_RE = re.compile(r"^(V\.[A-Za-z0-9_]+\s*=|BIND\.|const |function |let |var )")
WIRED_RE = re.compile(r"const\s+WIRED\s*=\s*new\s+Set\(\s*\[([^\]]*)\]")

# U2 · 演示数组（原型里的三张假数据表）—— 接后端之后它们必须消失
DEMO_RE = re.compile(r"const\s+(PJ|NT|FL)\s*=")
# U2b ·「按页说实话」的两种措辞必须都在（⛔ 注意：那句"全为虚构"的文案**本身留着是对的** ——
#        未接线的页正需要它；**坏的是对已接线的页也说它**。所以判的是"两种措辞齐不齐"，不是"有没有那句"）
WIRED_TEXT = "已接后端真实数据"
PROTO_TEXT = "原型态"

# ─────────────────────────────────────────────── `U5`（`TAIL-65`）：壳公共件 ⇄ 原型同段
#: 顶层声明（`U5` 认段用）
DECL_RE = re.compile(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|^function\s+([A-Za-z_$][\w$]*)\s*\(")
#: 纯注释行（`U5` 削段尾用）
COMMENT_RE = re.compile(r"^\s*(?://|/\*|\*|#)")

#: ⭐⭐ **`U5` 登记表**：这些件在**原型**与**壳**里各存一份，必须**逐字一致**。
#:
#: **怎么定的**（2026-09-23 立的当天逐条核过 · ⛔ 不是照抄谁的口径）：先用 `--u5-scan` 把两边
#: **同名顶层段**摆出来 —— 实测 **397 个同名，其中 319 个逐字一致、78 个已被接线有意改过**。
#: ⇒ 本表只收**规格面**那三类（模板 / 列序枚举口径常量 / 纯函数）；⛔ **已被接线有意改过**的
#: （`M` · `r2` · `projPanel` · `ACT` · `CHG` · `NO` · `WHM` … 那 78 个）**不收** —— 它们本来就该不一样。
#: ⭐ `TAIL-64`（表格/筛选/行模板配置化）每抽出一个新公共件，就把名字加进本表 ⇒ **那就是它的闸门**。
U5_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("表头 / 行模板（`*_THEAD`）—— 逐页列定义，`TAIL-64` 要配置化的原始材料", (
        "NT_THEAD", "PL_THEAD", "BIG_THEAD", "AWF_THEAD", "JCPAY_THEAD", "JCINV_THEAD",
        "INV_THEAD", "EXT_THEAD", "LED_THEAD", "DF_THEAD", "DIFF_THEAD", "FL_THEAD",
        "BP_THEAD", "PJ_THEAD", "JC_THEAD")),
    ("列序 / 枚举 / 口径常量 —— 界面与导出**共用**的字面表（改一处就得两处同改）", (
        "ENUMS", "IVC5", "BIGCOLS", "BIGFMT", "IV_FCOL", "IV_COLS", "IV_COLN", "LG_COLS",
        "NT_COLS", "MACH6_Z", "MACH6_RENT", "CAP_TOL", "ORD_MAX", "NOSORT_COL",
        "JCSUB_KIND", "ARC_TEXT", "LG_R_DEF", "EXT_BAL_NOTE")),
    ("纯函数 —— 无副作用、两边本就该同款（接线不该动它们）", (
        "$", "O", "N2", "PCT", "SIG", "uniqBy", "trailOf", "PROJ_META_KEY", "PROJ_META_FULL")),
    # ⭐ `TAIL-64`（2026-09-24 P0 试点）：**表格件** —— 表外壳（表头/行/空态/合计 ＋ `data-sort`）的
    #   统一出口，虚拟滚动将来挂这里。⭐ 每抽一个新公共件就把名字加进本表（见上方 `U5_GROUPS` 说明）。
    ("表格件（`TAIL-64`）—— 表外壳统一出口", (
        "TBL",)),
)

#: `U5` 登记表的**条目总数**（＝ 展平后相加）—— ⭐ 给 `T4` 的**计数锚点**用：
#:  文档里手抄的「登记 N 个规格件」必须等于它（2026-09-24 实测漂过一次：写 42、实 43）。
#:  ⛔ 别把 43 抄进文档 —— 抄了必漂；文档要写就写"别写死"或指回本常量。
U5_COUNT: int = sum(len(_names) for _group, _names in U5_GROUPS)


def read_lines(p: pathlib.Path) -> list[str]:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def slices(lines: list[str]) -> dict[str, list[str]]:
    """按行首 `V.<名字>=` 切片，直到下一个 `V.` / `BIND.` / 顶层声明。"""
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for ln in lines:
        m = VIEW_RE.match(ln)
        if m:
            cur = m.group(1)
            out[cur] = [ln]
            continue
        if cur is None:
            continue
        if END_RE.match(ln):
            cur = None
            continue
        out[cur].append(ln)
    return out


def top_segs(text: str) -> dict[str, str]:
    """**顶层段**（`U5` 用）：起点 = 顶层声明行（⛔ **不含 `V.` 切片内部**的东西），
    终点 = 下一个顶层声明 / `V.` / `BIND.` 行。

    ⚠️ **末尾的纯注释与空行要削掉** —— 接线层的习惯是在一个件后面补一句「⭐ 已接后端…」，
       那是**壳自己的话**、不是这个段的一部分；不削 ⇒ 每加一句注释就把 `U5` 撞红（假红）。
    """
    raw: dict[str, list[str]] = {}
    cur: str | None = None
    for ln in text.replace("\r\n", "\n").split("\n"):
        if END_RE.match(ln):
            cur = None
        m = DECL_RE.match(ln)
        if m and not VIEW_RE.match(ln):
            cur = m.group(1) or m.group(2)
            raw.setdefault(cur, [])
        if cur is not None:
            raw[cur].append(ln)
    out: dict[str, str] = {}
    for k, v in raw.items():
        while v and (not v[-1].strip() or COMMENT_RE.match(v[-1])):
            v.pop()
        out[k] = "\n".join(x.rstrip() for x in v)
    return out


def fp(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def load_expected() -> dict[str, set[str]]:
    """返回 {页: {指纹}}；文件格式 `<页> <指纹> [备注]`，`#` 开头为注释。"""
    exp: dict[str, set[str]] = {}
    if not EXPECTED.exists():
        return exp
    for raw in read_lines(EXPECTED):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            exp.setdefault(parts[0], set()).add(parts[1])
    return exp


def main() -> int:
    ap = argparse.ArgumentParser(description="壳一致性核对器")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-expected", action="store_true", help="把当前漂移登记进白名单")
    # ⚠️ 2026-09-23（`TAIL-65`）：`--proto` / `--u5-scan` 都是给 `U5` 用的 ——
    #    `--proto` 让反向灵敏度能**拿一份临时副本**证明"原型那侧改了也红"（⛔ 不必去动交付面）；
    #    `--u5-scan` 把两边**同名顶层段**摆出来（一致 / 已不同），登记表要扩的时候照着它挑。
    ap.add_argument("--proto", default=None, help="原型路径（默认 = 交付面那份）")
    ap.add_argument("--u5-scan", action="store_true", help="列出两边同名顶层段的现状（挑 `U5` 候选用）")
    args = ap.parse_args()

    proto = pathlib.Path(args.proto) if args.proto else PROTO
    if not proto.exists():
        print(f"⛔ 找不到原型：{proto}（它不在工程仓里，属交付面）")
        return 1
    if not SHELL.exists():
        print(f"⛔ 找不到前端壳：{SHELL}")
        return 1

    p_views = slices(read_lines(proto))
    shell_lines = read_shell().replace("\r\n", "\n").split("\n")   # ← `P4`①：合并后的**全部件**
    s_views = slices(shell_lines)
    exp = load_expected()

    if args.u5_scan:                                   # `TAIL-65`：挑 `U5` 候选用（不是判据）
        p_seg, s_seg = top_segs(proto.read_text(encoding="utf-8")), top_segs("\n".join(shell_lines))
        both = sorted(set(p_seg) & set(s_seg))
        same = [n for n in both if p_seg[n] == s_seg[n]]
        print("=" * 78)
        print(f" U5 候选扫描 —— 原型 {proto.name}（{len(p_seg)} 个顶层段） ⇄ 壳（{len(s_seg)} 个）")
        print("=" * 78)
        print(f" 同名顶层段 {len(both)} 个 · **逐字一致** {len(same)} 个 · 已不同 {len(both) - len(same)} 个"
              f" · 登记表当前收了 {sum(len(n) for _g, n in U5_GROUPS)} 个")
        print("\n ── 逐字一致（可入登记表的候选）──")
        print("   " + ", ".join(same))
        print("\n ── 已不同（⛔ 接线有意改过的，别登记）──")
        print("   " + ", ".join(n for n in both if n not in set(same)))
        return 0

    # ── U1 · 视图切片逐行一致
    u1: list[dict] = []
    missing: list[str] = []
    for key, plines in p_views.items():
        slines = s_views.get(key)
        if slines is None:
            missing.append(key)
            continue
        for i in range(max(len(plines), len(slines))):
            a = plines[i].rstrip() if i < len(plines) else "<无此行>"
            b = slines[i].rstrip() if i < len(slines) else "<无此行>"
            if a != b:
                u1.append({"key": key, "line": i + 1, "proto": a[:160], "shell": b[:160],
                           "fp": fp(a + "||" + b)})

    u1_new = [d for d in u1 if d["fp"] not in exp.get(d["key"], set())]
    u1_ok = [d for d in u1 if d["fp"] in exp.get(d["key"], set())]

    # ⭐ `U1` 登记簿**防腐化**（2026-09-24）：登记了、却**当前没有对应漂移** = **幽灵登记**
    #   （那条漂移已被修掉 / 因两边同改而指纹变了）⇒ 提示「可消号」。
    # ⭐⭐ 2026-09-25（用户裁定「登记簿可以变长」）：旧的「只准变短」**作废** ——
    #   新功能带来的正当差异**照登**（`--write-expected` 已改为**只追加**，⛔ 不重写文件）；
    #   ⚠️ 但**消号仍要人工删行**：本哨只提示，⛔ 不替人删（自动删会连带冲掉旁边的理由注释）。
    #   ⚠️ **只提示、不计入 `red`** —— 它不影响"壳现在是否一致"，但登记簿腐化之后
    #      「已登记放行 N 行」就成了一种**自我安慰**：登记时的理由早就不成立了。
    _now_fps = {d["fp"] for d in u1}
    ghosts = [(k, f) for k, fs in sorted(exp.items()) for f in sorted(fs) if f not in _now_fps]

    # ── U2 · 演示数组（红线①：假数据不得混进产物）＋「按页说实话」两种措辞
    u2: list[str] = []
    for i, ln in enumerate(shell_lines, 1):
        m = DEMO_RE.search(ln)
        if m:
            u2.append(f"L{i} 残留演示数组 {m.group(1)}：{ln.strip()[:70]}")
    shell_text = "\n".join(shell_lines)
    if WIRED_TEXT not in shell_text:
        u2.append(f"壳里找不到「{WIRED_TEXT}」⇒ 已接线的页会被说成原型态（界面对真数据说了假话）")
    if PROTO_TEXT not in shell_text:
        u2.append(f"壳里找不到「{PROTO_TEXT}」⇒ 未接线的页不再标明数据是模拟值")

    # ── U2b · **已接线的页，它的演示数组必须已删**（"接线即清"，机器看管）
    #     ⚠️ 只查 `WIRED` 里的页：未接线的页**正需要**演示数据（否则页面空着）。
    #     ⚠️⚠️ **声明关键字必须逐页写明**（`((数组名, 关键字正则), …)`，一页可登记多个容器），
    #        不能一律 `const` 也不能一律放宽：
    #        · 原型里**演示数据**用 `const` 声明（`const NT=[…]`），而**接后端后的活容器**是 `let`（`let WHM = {}`）
    #          ⇒ 一律放宽会**误报活容器**（实测：`let MACH6 = {}` / `let WHM = {}` 被当成残留演示数据）；
    #        · 但 `m09` 的 `AWF` 在原型里**本身就是 `let`**（`let AWF = {…}`）⇒ 只认 `const` 会**漏掉它**。
    #        两种坑都踩过 ⇒ 逐页显式登记 + 后面「必须带内容才算演示」的兜底。
    #     ⭐ 2026-09-18：值改成**一组**规格（一页可能有**多个**演示容器）—— `m07` 除了 `WHM`
    #        2026-09-18 起还有「结余」录入容器 `BAL_EX`（原型里是 `const BAL_EX = {…}` 演示值，
    #        接线后壳里必须是 `let BAL_EX = {}` **空容器**）。
    DEMO_BY_PAGE = {"m03": (("NT", "const"),), "m01": (("PJ", "const"),), "m04": (("PL", "const"),),
                    "m05": (("LG", "const"),), "m06": (("MACH6", "const"),),
                    "m07": (("WHM", "const"), ("BAL_EX", "const|let|var")),
                    "m08": (("IV", "const"),),
                    "m09": (("AWF", "const|let|var"),), "m14": (("RULE_EX", "const|let|var"),),
                    # ⭐ 2026-09-19（`M5-7`）：集采台账。演示容器 = `JC`（**已删**）+ 列序 `JC_COLS`（**已删**）。
                    #    登记它 = 让"将来谁把演示数据加回来"被当场抓住（`U2b` 只扫 `WIRED` 里的页）。
                    "m11": (("JC", "const"), ("JC_COLS", "const"))}
    _mw = WIRED_RE.search(shell_text)
    _wired_now = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", _mw.group(1)) if _mw else []
    for _page in _wired_now:
        for _arr, _kw in DEMO_BY_PAGE.get(_page, ()):
            # ⚠️ 还要**带内容**才算演示数据：`= {}` / `= []` 是**空容器**（后端填充用），不是残留演示值。
            _re_pat = rf"(?:{_kw})\s+{_arr}\s*=\s*(?:\{{\s*[^\s}}]|\[\s*[^\s\]])"
            if re.search(_re_pat, shell_text):
                u2.append(
                    f"`{_page}` 已标「已接后端真实数据」，但演示数组 `{_arr}` 还在壳里 "
                    f"⇒ 接线要连演示数据一起清（一份内容只许一个主人）"
                )

    # ── U3 · WIRED 自洽
    u3: list[str] = []
    wired: list[str] = []
    m = WIRED_RE.search("\n".join(shell_lines))
    if not m:
        u3.append("壳里找不到 `const WIRED = new Set([...])`")
    else:
        wired = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", m.group(1))
        if not wired:
            u3.append("`WIRED` 是空集合（一页都没接后端？）")
        for k in wired:
            if k not in s_views:
                u3.append(f"`WIRED` 里的 `{k}` 在壳里没有对应的 `V.{k}` 切片")

    # ── U4 · `WIRED` 的页必须真的指向后端（接线点存在）
    #     ⚠️ 判的是 `/api/mNN` 出现在壳里 —— **弱**：它证不了"运行时调通"。
    #     但强于只看 `WIRED`：标了"已接后端"却一个接口都没调，是**最廉价的一种假绿**。
    u4: list[str] = []
    for k in wired:
        m = re.match(r"^m(\d{2})$", k)
        if not m:
            continue                       # `home` 之类没有模块号：本检查不覆盖（记在报告里）
        if f"/api/m{m.group(1)}" not in shell_text:
            u4.append(
                f"`WIRED` 标了 `{k}` 是「已接后端真实数据」，但壳里找不到 `/api/m{m.group(1)}` "
                f"⇒ 这页其实没接（顶栏在对真数据说假话）"
            )

    # ── U5 · 壳公共件 ⇄ 原型里嵌的同段（`TAIL-65`）
    #     ⚠️ 与 `U1` 的分工：`U1` 管**切片 `V.<页>` 内部**，`U5` 管**切片之外**那些两边各存一份的件。
    u5: list[str] = []
    p_seg = top_segs(proto.read_text(encoding="utf-8"))
    s_seg = top_segs(shell_text)
    u5_ok = 0
    for _group, _names in U5_GROUPS:
        for _n in _names:
            a, b = p_seg.get(_n), s_seg.get(_n)
            if a is None or b is None:
                u5.append(f"`{_n}` 在登记表里，但**{'原型' if a is None else '壳'}里找不到这个段** ⇒ "
                          f"幽灵条目（件改了名 / 删了 ⇒ 登记表也得同步）")
            elif a != b:
                u5.append(f"`{_n}` 两边**已不同**（原型 {fp(a)} / 壳 {fp(b)}）⇒ "
                          f"要么**原型与壳同改同句**，要么把它从登记表划掉（写明理由）")
            else:
                u5_ok += 1

    red = len(u1_new) + len(u2) + len(u3) + len(u4) + len(u5) + len(missing)

    if args.write_expected:
        # ⭐⭐ 2026-09-25（用户裁定「登记簿可以变长」）：本命令由**整份重写**改为**只追加** ——
        #   旧版 `EXPECTED.write_text(head + 当前漂移)` 会**冲掉登记簿里的历史注释**
        #   （那些 2026-09-20/21 的销号理由），且**幽灵登记会被静默清掉**（消号必须人工决定）。
        import datetime as _dt

        head = [
            "# 壳一致性核对器 · 已登记漂移（ui_parity_expected.txt）",
            "# ⚠️ **可增可减**（2026-09-25 用户裁定）：新功能产生的正当差异**照登**；补回原型逻辑 ⇒ 人工删行（脚本只提示）。",
            "# 格式：`<页> <指纹> [备注]`；指纹 = md5(原型行 + '||' + 壳行)[:8]。",
            "",
        ]
        old_all = read_lines(EXPECTED) if EXPECTED.exists() else []
        known: set[str] = set()
        for _t in old_all:
            _s = _t.strip()
            if _s and not _s.startswith("#") and len(_s.split()) >= 2:
                known.add(_s.split()[1])
        add = [f"{d['key']} {d['fp']}  # 原型: {d['proto'][:50]}｜壳: {d['shell'][:50]}"
               for d in u1 if d["fp"] not in known]
        text = old_all if old_all else head
        if add:
            text = list(text) + [
                f"# ⭐ {_dt.date.today().isoformat()} 新增登记 {len(add)} 条"
                f"（口径：2026-09-25 用户裁定「登记簿可以变长」· 见 `journal/2026-09-25.md`）", ""] + add
        EXPECTED.write_text("\n".join(text).rstrip("\n") + "\n", encoding="utf-8")
        print(f"新增登记 {len(add)} 条（原有 {len(old_all)} 行**一字未动**）⇒ {EXPECTED.name}")
        return 0

    if args.json:
        print(json.dumps({"u1_new": u1_new, "u1_ok": len(u1_ok), "u2": u2, "u3": u3, "u4": u4,
                          "u5": u5, "u5_ok": u5_ok, "missing": missing},
                         ensure_ascii=False, indent=2))
        return 1 if red else 0

    print("=" * 78)
    print(" 壳一致性核对器 · ui_parity —— 「原型逻辑一行不改 ／ 演示数据不留 ／ WIRED 别乱标」")
    print("=" * 78)
    print(f" 原型 {proto.name}（{len(p_views)} 个视图）  ⇄  壳（{len(s_views)} 个视图 · {len(SHELL_PARTS)} 件）")
    print(f" 已登记放行 {sum(len(v) for v in exp.values())} 条 · `WIRED` = {wired or '（未取到）'}")
    print()
    print(f"─ U1 · 视图切片逐行一致 —— "
          f"{'✅ 无未登记漂移' if not u1_new else f'⛔ {len(u1_new)} 行未登记'}（已登记放行 {len(u1_ok)} 行）")
    for d in u1_new[:25]:
        print(f"    [{d['key']} L{d['line']}] 原型: {d['proto'][:70]}")
        print(f"    {' ' * len(d['key'])}   {' ' * 6} 壳  : {d['shell'][:70]}")
    if len(u1_new) > 25:
        print(f"    …还有 {len(u1_new) - 25} 行")
    if ghosts:                       # 登记簿防腐化：登记的漂移已经不存在了 ⇒ 该消号
        print(f"    ⚠️ 登记簿有 {len(ghosts)} 条**幽灵登记**（当前已无对应漂移 ⇒ 可消号，"
              f"⛔ 消号要人工删行）：" + "、".join(f"{k} {f}" for k, f in ghosts[:8]))
    if missing:
        print(f"─ U1b · 壳里缺切片 —— ⛔ {len(missing)} 个：{', '.join(missing)}")
    print(f"─ U5 · 公共件 ⇄ 原型同段（`TAIL-65`）—— "
          + (f"✅ 登记 {u5_ok} 个**全部逐字一致**" if not u5 else f"⛔ {len(u5)} 条"
             + f"（其余 {u5_ok} 个一致）"))
    for it in u5[:10]:
        print("    " + it)
    for name, items in (("U2 · 演示数组 / 假话残留", u2), ("U3 · WIRED 自洽", u3),
                        ("U4 · WIRED 的页是否真指向后端", u4)):
        print(f"─ {name} —— {'✅ 无' if not items else f'⛔ {len(items)} 条'}")
        for it in items[:10]:
            print("    " + it)
    print()
    print(f"结论：**必须修 {red}**" + ("（有红 ⇒ 非零退出）" if red else "（rc=0）"))
    print("⚠️ 它**测不了**「标了已接后端其实没接」—— 那一条靠真机自检 `tools/probe/_shell_smoke.py`。")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
