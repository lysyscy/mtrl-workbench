"""**壳一致性核对器**（原型 ⇄ 前端壳）· **纯 Python · 不依赖浏览器**。

**为什么换了定义**（2026-09-17 · 用户裁定 `D18`）：
    旧定义是「**服务端渲染页**逐页对齐原型」—— 但前端已改成「**原型直接接数据**」：
    壳 = `demo/` 交互原型的**整体复制**，**只换数据源**。⇒ 结构对齐已由**构造**保证，
    再去数「表 / 筛 / 卡 / 折 / 合计 / 排序」**已经没有意义**（数的是同一份代码）。
    ⚠️ **旧口径（服务端页逐页对齐）已作废**；它原来盯的那批服务端渲染页，本身就在 `TAIL-27` 里要删掉。

**风险没有消失，只是挪了位置** ⇒ 本工具现在守三件事：
| 代号 | 守什么 | 判据 |
|---|---|---|
| `U1` | ⭐⭐ **原型逻辑一行不改**（D18 的硬约束）—— 把原型的筛选 / 排序 / 合计 / 勾选逻辑**顺手改掉**，就再没有"规格"可言了 | 壳的每个 `V.<页>` 切片 与原型同名切片**逐行一致**；差异未登记 ⇒ **红**（登记簿 `tools/ui_parity_expected.txt` · **只准变短**） |
| `U2` | **演示数据与"假话"不得残留**（D18 产品化红线①） | ① 壳里出现原型的三张演示数组（`PJ` / `NT` / `FL`）⇒ **红**；② 壳里必须**同时**存在「已接后端真实数据」与「原型态」两种措辞（缺任一种 ⇒ 顶栏又会**一律**说"全是虚构" = 对已接线页说假话）⇒ **红** |
| `U3` | **`WIRED` 自洽** | 壳里必须有 `WIRED` 集合，且**它的每个成员都真实存在于 `V`**（防"标了个不存在的页"）⇒ **红** |
| `U4` | ⭐ **`WIRED` 的页必须真的指向后端**（2026-09-17 补） | `WIRED` 里的每页 `mNN` ⇒ 壳里必须出现 `/api/mNN`。**这只是"接线点存在"，不是"调通了"** —— 但能挡住最廉价的一种假绿：把页标成"已接后端"而壳里**一个该模块的接口都没调**（顶栏就会对真数据说"已接"）⇒ **红** |

⚠️ **本工具测不了什么（别误当已覆盖）**：**「标了已接后端，其实没接」** ——
    "某一页的数据由谁喂"无法从源码机械判定 ⇒ 那一条靠**真机自检**（`tools/_shell_smoke.py` /
   `tools/_shell_render_check.py`）与 `WIRED` 的人工维护。**「断言测不了」这句本身就是要害。**

跑法：
  `backend/.venv/Scripts/python.exe tools/ui_parity.py`          # 人读表（有未登记漂移 ⇒ rc=1）
  `backend/.venv/Scripts/python.exe tools/ui_parity.py --json`   # 机读
  `... --write-expected`                                          # 把当前漂移**登记**下来（人先审过再用）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
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
    args = ap.parse_args()

    if not PROTO.exists():
        print(f"⛔ 找不到原型：{PROTO}（它不在工程仓里，属交付面）")
        return 1
    if not SHELL.exists():
        print(f"⛔ 找不到前端壳：{SHELL}")
        return 1

    p_views = slices(read_lines(PROTO))
    shell_lines = read_lines(SHELL)
    s_views = slices(shell_lines)
    exp = load_expected()

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
    #     ⚠️⚠️ **声明关键字必须逐页写明**（`(数组名, 关键字正则)`），不能一律 `const` 也不能一律放宽：
    #        · 原型里**演示数据**用 `const` 声明（`const NT=[…]`），而**接后端后的活容器**是 `let`（`let WHM = {}`）
    #          ⇒ 一律放宽会**误报活容器**（实测：`let MACH6 = {}` / `let WHM = {}` 被当成残留演示数据）；
    #        · 但 `m09` 的 `AWF` 在原型里**本身就是 `let`**（`let AWF = {…}`）⇒ 只认 `const` 会**漏掉它**。
    #        两种坑都踩过 ⇒ 逐页显式登记 + 后面「必须带内容才算演示」的兜底。
    DEMO_BY_PAGE = {"m03": ("NT", "const"), "m01": ("PJ", "const"), "m04": ("PL", "const"),
                    "m05": ("LG", "const"), "m06": ("MACH6", "const"),
                    "m07": ("WHM", "const"), "m08": ("IV", "const"),
                    "m09": ("AWF", "const|let|var")}
    _mw = WIRED_RE.search(shell_text)
    _wired_now = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", _mw.group(1)) if _mw else []
    for _page in _wired_now:
        _spec = DEMO_BY_PAGE.get(_page)
        if not _spec:
            continue
        _arr, _kw = _spec
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

    red = len(u1_new) + len(u2) + len(u3) + len(u4) + len(missing)

    if args.write_expected:
        head = [
            "# 壳一致性核对器 · 已登记漂移（ui_parity_expected.txt）",
            "# ⚠️ **只准变短** —— 补回原型逻辑 / 删掉多余的改动 ⇒ 删掉对应行（脚本会提示「可消号」）。",
            "# 格式：`<页> <指纹> [备注]`；指纹 = md5(原型行 + '||' + 壳行)[:8]。",
            "",
        ]
        body = [f"{d['key']} {d['fp']}  # 原型: {d['proto'][:50]}｜壳: {d['shell'][:50]}" for d in u1]
        EXPECTED.write_text("\n".join(head + body) + "\n", encoding="utf-8")
        print(f"已登记 {len(body)} 条漂移 ⇒ {EXPECTED.name}")
        return 0

    if args.json:
        print(json.dumps({"u1_new": u1_new, "u1_ok": len(u1_ok), "u2": u2, "u3": u3, "u4": u4,
                          "missing": missing},
                         ensure_ascii=False, indent=2))
        return 1 if red else 0

    print("=" * 78)
    print(" 壳一致性核对器 · ui_parity —— 「原型逻辑一行不改 ／ 演示数据不留 ／ WIRED 别乱标」")
    print("=" * 78)
    print(f" 原型 {PROTO.name}（{len(p_views)} 个视图）  ⇄  壳 index.html（{len(s_views)} 个视图）")
    print(f" 已登记放行 {sum(len(v) for v in exp.values())} 条 · `WIRED` = {wired or '（未取到）'}")
    print()
    print(f"─ U1 · 视图切片逐行一致 —— "
          f"{'✅ 无未登记漂移' if not u1_new else f'⛔ {len(u1_new)} 行未登记'}（已登记放行 {len(u1_ok)} 行）")
    for d in u1_new[:25]:
        print(f"    [{d['key']} L{d['line']}] 原型: {d['proto'][:70]}")
        print(f"    {' ' * len(d['key'])}   {' ' * 6} 壳  : {d['shell'][:70]}")
    if len(u1_new) > 25:
        print(f"    …还有 {len(u1_new) - 25} 行")
    if missing:
        print(f"─ U1b · 壳里缺切片 —— ⛔ {len(missing)} 个：{', '.join(missing)}")
    for name, items in (("U2 · 演示数组 / 假话残留", u2), ("U3 · WIRED 自洽", u3),
                        ("U4 · WIRED 的页是否真指向后端", u4)):
        print(f"─ {name} —— {'✅ 无' if not items else f'⛔ {len(items)} 条'}")
        for it in items[:10]:
            print("    " + it)
    print()
    print(f"结论：**必须修 {red}**" + ("（有红 ⇒ 非零退出）" if red else "（rc=0）"))
    print("⚠️ 它**测不了**「标了已接后端其实没接」—— 那一条靠真机自检 `tools/_shell_smoke.py`。")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
