"""**壳自检**（`U2` / `U2b` / `U3` / `U4`）· **纯 Python · 不依赖浏览器**。

⭐⭐ **2026-09-30 `TAIL-201` 「退场」**（用户裁定 · 出处 = `.codebuddy/memory/2026-09-30.md` §22/§23）：
本件原先守五条 —— `U1`（壳切片 ⇄ 基准逐行对位）· `U5`（公共件 ⇄ 原型逐字）· `U2` · `U3` · `U4`。
沿革：`TAIL-200` 先把 `U1`/`U5` 的基准从「交付面那份交互原型」换成「**最新壳快照**」（消掉**双边同步**），
之后发现换完基准的 `U1`/`U5` 与 `shell_verify`（逐行**多重集** ＋ **盖章**）**同一个基准、同一件事两套账**
⇒ 遂**退场**：`U1`/`U5` **整半拆掉**，"壳变了没有 / 变在哪" 现在**只有一处账** =
`python tools/audit/shell_verify.py`（差异 ⇒ `rc=1` ⇒ 复核后 `--snapshot` 盖章归零）。

⚠️ **代价（本轮明确接受）**：`shell_verify` 比的是逐行**多重集** ⇒ **不看顺序**
   （把一段代码**原样挪到别处**它看不见 —— `U1` 当年能看见）。
⚠️ **顺带的好处**：跑本件**什么都不需要**（⛔ 交付面、⛔ 壳快照都不用）⇒ **目标机也能跑**。
⚠️ **名字是旧的**（`ui_parity` = "对位"）：⛔ 别按名字理解 —— 它现在**只查壳自己**（改名要动尺子清单/文档/变异，
   属"为改名而改名" ⇒ 不做；⛔ 但读者别被名字误导）。
⚠️ 更早的两层沿革留痕（`D18` 2026-09-17「壳 = 原型的整体复制、只换数据源 ⇒ 结构对齐由构造保证」·
   `TAIL-65` 2026-09-23 立 `U5`）见 §15 §四 `TAIL-200` / `TAIL-201` 两条销号行。

**它现在守四件**：
| 代号 | 守什么 | 判据 |
|---|---|---|
| `U2` | **演示数据与「假话」不得残留**（`D18` 产品化红线①） | ① 壳里出现原型的三张演示数组（`PJ` / `NT` / `FL`）⇒ **红**；② 壳里必须有「本页数据尚未接通」这句，且必须**按页**判（`WIRED.has(VIEW) ? '' : …`）⇒ **红** |
| `U2b` | ⭐ **已接线的页，它的演示数组必须已删**（"接线即清"，机器看管） | `WIRED` 里的页**逐页登记**了演示容器名 ⇒ 壳里还在、**且带内容** ⇒ **红** |
| `U3` | **`WIRED` 自洽** | 壳里必须有 `WIRED` 集合，且**它的每个成员都真实存在于 `V`**（防"标了个不存在的页"）⇒ **红** |
| `U4` | ⭐ **`WIRED` 的页必须真的指向后端**（2026-09-17 补） | 每页 `mNN` 默认检查 `/api/mNN`，复用其他领域的页按 `API_BY_PAGE` 指定入口。**这只是"接线点存在"，不是"调通了"** —— 标了已接线却没有对应入口仍报红。 |

⚠️ **本工具测不了什么（别误当已覆盖）**：**「标了已接后端，其实没接」** ——
   "某一页的数据由谁喂"无法从源码机械判定 ⇒ 那一条靠**真机自检**（`tools/probe/_shell_smoke.py` /
  `tools/probe/_shell_render_check.py`）与 `WIRED` 的人工维护。**「断言测不了」这句本身就是要害。**

跑法：
  `backend/.venv/Scripts/python.exe tools/audit/ui_parity.py`          # 人读表（有红 ⇒ rc=1）
  `backend/.venv/Scripts/python.exe tools/audit/ui_parity.py --json`   # 机读
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from shell_source import SHELL_PARTS, SHELL_PATH, read_shell  # noqa: E402  ← `P4`① 读取点收敛
import shell_api  # noqa: E402  ← ⭐ 2026-10-03 `TAIL-219` 批 1：切片算法搬去那边（唯一主人）

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: **历史原型路径** —— 本件不把它当基准（`U1`/`U5` 已于 2026-09-30 `TAIL-201` 退场）。
#: 留着只为一处**显式**用途：`backend/tests/test_ux_feedback.py` 那条「这处东西壳与原型**都没有**」的判据。
PROTO = ROOT / "delivery" / "demo" / "材料报表自动化工作台-交互原型.html"
# ⚠️ 2026-09-19（`P4`① 读取点收敛）：壳要拆成多件 ⇒ 源码一律走 `shell_source`。
#    `SHELL` 仍留作**存在性检查**（指 `index.html` 本体）；**读文本则用 `read_shell()`**（合并后的全部件）
#    —— 否则 `U2`（演示数组残留）与 `U4`（`/api/mNN` 在不在）会**静默**只看原型切片那一件。
SHELL = SHELL_PATH

# ⭐ 2026-10-03（`TAIL-219` 批 1）：切片起点 / 终点的正则**已搬走**，
#    唯一主人 = `tools/audit/shell_api.py::slices_of_lines`（⛔ 别在本件里再写一份）。
WIRED_RE = re.compile(r"const\s+WIRED\s*=\s*new\s+Set\(\s*\[([^\]]*)\]")

# U2 · 演示数组（原型里的三张假数据表）—— 接后端之后它们必须消失
DEMO_RE = re.compile(r"const\s+(PJ|NT|FL)\s*=")
# U2b ·「按页说实话」那句
# ⭐⭐ 2026-09-27（用户裁定 `B` · 守则 §3.6）：顶栏/侧栏**只给"还没接通"的页如实标注**，
#    接通的页**不挂任何状态牌**（上一版是每页挂一句「已接后端真实数据 / 原型态 · 数据为模拟值」——
#    那是**给我们自己看的进度牌**：铺在 16 页标题上对用户是噪音，且「原型态 / 模拟值」属开发话术）。
#    ⚠️ 「已接后端真实数据」这个常量**已随本轮删除**：它不再需要出现在壳里。
#    ⛔ **别退回"一律挂一句"**（无论说真话还是假话）—— 没标 = 正常可用，就是最诚实的状态。
PROTO_TEXT = "本页数据尚未接通"
# 机械费页复用过程资料的有效月值领域，接线必须命中其正式工作区入口。
API_BY_PAGE = {"m10": "/api/m06/workbench"}


def wired_api_issues(wired: list[str], source: str) -> list[str]:
    issues: list[str] = []
    for page in wired:
        if not re.fullmatch(r"m\d{2}", page):
            continue
        endpoint = API_BY_PAGE.get(page, f"/api/{page}")
        if endpoint not in source:
            issues.append(
                f"`WIRED` 标了 `{page}` 是「已接后端真实数据」，但壳里找不到 `{endpoint}` "
                "⇒ 这页其实没接（顶栏在对真数据说假话）"
            )
    return issues


def read_lines(p: pathlib.Path) -> list[str]:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def slices(lines: list[str]) -> dict[str, list[str]]:
    """按行首 `V.<名字>=` 切片，直到下一个 `V.` / `BIND.` / 顶层声明。

    ⭐ 2026-10-03（`TAIL-219` 批 1）：**算法已搬到** `shell_api.slices_of_lines`（唯一主人）
    —— 本处只转发，⛔ 别在本件里再写一份（那正是本次要治的"同一件事多处写"）。
    """
    return shell_api.slices_of_lines(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="壳自检（U2 / U2b / U3 / U4）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not SHELL.exists():
        print(f"⛔ 找不到前端壳：{SHELL}")
        return 1

    shell_lines = read_shell().replace("\r\n", "\n").split("\n")   # ← `P4`①：合并后的**全部件**
    s_views = slices(shell_lines)

    # ── U2 · 演示数组（红线①：假数据不得混进产物）＋「按页说实话」
    u2: list[str] = []
    for i, ln in enumerate(shell_lines, 1):
        m = DEMO_RE.search(ln)
        if m:
            u2.append(f"L{i} 残留演示数组 {m.group(1)}：{ln.strip()[:70]}")
    shell_text = "\n".join(shell_lines)
    # ⭐⭐ 2026-09-27（用户裁定 `B`）：U2 的"按页说实话"**改形**（能力不变、措辞换掉）——
    #    旧形是"壳里必须同时存在两种措辞"（保证顶栏能分清已接/未接）；现形是"**只有一种**：
    #    未接通的要如实说，且必须**按页判**"。⚠️ 这一条的能力是"不许对用户说假话"，⛔ 别删成"没了"。
    if PROTO_TEXT not in shell_text:
        u2.append(f"壳里找不到「{PROTO_TEXT}」⇒ 未接通的页不再如实标注（用户会以为它已经能用）")
    if not any("WIRED.has(" in l for l in shell_lines if PROTO_TEXT in l):
        u2.append(f"「{PROTO_TEXT}」不是**按页**判的 —— 必须写成 `WIRED.has(VIEW) ? '' : '…'` 那种形态；"
                  "⛔ 一律挂一句就是对已接线的页说假话（U2 当初立起来防的就是它）")

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
                    f"`{_page}` 已接通（在 `WIRED` 里），但演示数组 `{_arr}` 还在壳里 "
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
    #     默认查 `/api/mNN`，跨领域复用按 API_BY_PAGE；仍只证接线存在，不证运行调通。
    #     但强于只看 `WIRED`：标了"已接后端"却一个接口都没调，是**最廉价的一种假绿**。
    u4 = wired_api_issues(wired, shell_text)

    red = len(u2) + len(u3) + len(u4)

    if args.json:
        print(json.dumps({"u2": u2, "u3": u3, "u4": u4}, ensure_ascii=False, indent=2))
        return 1 if red else 0

    print("=" * 78)
    print(" 壳自检 · ui_parity —— 「演示数据不留 ／ WIRED 别乱标」")
    print("=" * 78)
    print(f" 壳（{len(s_views)} 个视图 · {len(SHELL_PARTS)} 件）· `WIRED` = {wired or '（未取到）'}")
    print()
    for name, items in (("U2 · 演示数组 / 假话残留", u2), ("U3 · WIRED 自洽", u3),
                        ("U4 · WIRED 的页是否真指向后端", u4)):
        print(f"─ {name} —— {'✅ 无' if not items else f'⛔ {len(items)} 条'}")
        for it in items[:10]:
            print("    " + it)
    print()
    print(f"结论：**必须修 {red}**" + ("（有红 ⇒ 非零退出）" if red else "（rc=0）"))
    print("⚠️ 「壳变了没有 / 变在哪」**不归本件**（`U1`/`U5` 已于 2026-09-30 `TAIL-201` 退场）"
          "⇒ 那一层看 `python tools/audit/shell_verify.py`（差异 ⇒ rc=1 ⇒ 复核后 `--snapshot` 盖章）。")
    print("⚠️ 它**测不了**「标了已接后端其实没接」—— 那一条靠真机自检 `tools/probe/_shell_smoke.py`。")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
