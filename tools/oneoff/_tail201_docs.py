#!/usr/bin/env python
r"""`TAIL-201`（**退场**）**落纸**（2026-09-30）：活规则作废（5 处）＋ 理由句换真理由（4 处）＋
文档（阈值表/architecture/delivery-surface/deployment）＋ 台账收尾（销号/计数/口令）。

⚠️ 逐处先断言命中数；改完 round-trip 核一遍。⛔ 历史留痕（施工图/守则/归档件里的旧说法）不动。
用法：干跑 / `--write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
DES = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-表格筛选配置化-20260924.md"
THR = ROOT / "ops" / "阈值表.md"
ARCH = ROOT / "docs" / "architecture.md"
FACE = ROOT / "docs" / "delivery-surface.md"
DEP = ROOT / "docs" / "deployment.md"
T1 = ROOT / "backend" / "tests" / "test_ux_pages.py"
T2 = ROOT / "backend" / "tests" / "test_ux_numbers.py"
T3 = ROOT / "backend" / "tests" / "test_wired_m05.py"
NL = "\r\n"

ROW4 = (
    "| `TAIL-201` | ⭐ **`U1`/`U5` 退场**（`ui_parity` 只留 `U2`/`U2b`/`U3`/`U4`） | "
    "**销号依据** = 用户 2026-09-30 裁定「退场」（出处 = `.codebuddy/memory/2026-09-30.md` §22/§23）⇒ 已办："
    "① `ui_parity.py` **整半拆掉** `U1`（切片相对基准）与 `U5`（公共件 ⇄ 原型）＋ 撤 `--proto`/`--write-expected`/"
    "`--u5-scan` ＋ 撤 `EXPECTED`/登记簿/`U5_GROUPS`/`U5_COUNT`/`top_segs`/`fp`/`load_expected`"
    "（⚠️ `PROTO` **留**：`test_ux_feedback.py` 那条「壳与原型都没有」的判据要它）；② **先解耦消费者**"
    "（否则 import 先崩）：`audit_drift.py` 撤 ③ 号 `U5_COUNT` 锚点 ＋ `_U5_ANCHOR_RE`（`T4` 由 **4 类**减到 "
    "**3 类**）· `_mut_shell.py` 撤 `U1` 靶（**4/4 → 3/3**）· `_mut_countanchors.py` 头注；③ **删件 4 件** = "
    "`_mut_u5.py` · `_mut_uiparity.py` · `test_ui_parity_base.py`（已删）· `ui_parity_expected.txt`"
    "（630 条历史**已在** `tools/oneoff/_归档-20260930/`）；④ `shell_verify.py` 的 `newest_snapshot` "
    "**收回私有**（公开的理由随退场消失）＋ 把「原样挪个位置它看不见」那句改成 **⛔ 这一层现在没人守 ⇒ "
    "本轮明确接受**；⑤ ⭐ **活规则作废 5 处**：施工图 §四-2「新公共件要登记进 `U5_GROUPS`」· 施工图 §六 那条量测 · "
    "施工图 §8.10 的 `P4-c-a` 步骤（「先跑 `U1` 逐页对位量」**已无对象**）· 计划 `TAIL-64` 行同一条闸门 · "
    "`ops/阈值表.md` 的 `T4` 描述（见下）；⑥ **理由句换真理由 4 处**（`test_ux_pages` / `test_ux_numbers` / "
    "`test_wired_m05` ×2：原先写「它在 `U5` 登记表里 ⇒ 不许改」 —— 凭据没了 ⇒ 换成「它是界面文案/口径，"
    "改了要跑 `acc_*` ＋ 真机」）；⑦ **顺带**：`shell_source.py`/`audit_common.py` 两处理由改墓碑 · "
    "`_m14_parity.py` 头注标失效（它伺候的就是退场那两半） | 2026-09-30 |"
)


def _edit(p: pathlib.Path, pairs: list[tuple[str, str]], dry: bool) -> None:
    t = p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    for old, new in pairs:
        n = t.count(old)
        assert n == 1, f"⛔ {p.name}：锚点命中 {n} 次（期望 1）—— {old[:70]!r}"
        t = t.replace(old, new, 1)
    if not dry:
        p.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
        assert p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == t, f"⛔ {p.name} 写回不一致"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dry = not a.write

    _edit(THR, [
        ("③ `U5` 登记条目数 ", ""),
        ("④ ⭐ **本表自己的数字", "③ ⭐ **本表自己的数字"),
        ("| **4 类** | `T4` **计数锚点**", "| **3 类** | `T4` **计数锚点**"),
    ], dry)
    _edit(ARCH, [
        ("（V.* 切片与 demo 原型逐行一致 = ui_parity U1）",
         "（⭐ 2026-09-30 `TAIL-201`：**已不再逐行对位原型** —— `ui_parity` 的 `U1`/`U5` 已退场；"
         "「壳变了没有」看 `shell_verify`）"),
    ], dry)
    _edit(FACE, [
        ("（⭐ **2026-09-30** `TAIL-200` 起**不再是** `ui_parity` 的基准 —— 基准已换成**最新壳快照**）",
         "（⭐ **2026-09-30** `TAIL-201` 起 `ui_parity` **不再比任何基准** —— `U1`/`U5` 已整半退场）"),
    ], dry)
    _edit(DEP, [
        ("⭐ **`ui_parity` 不在此列**（2026-09-30 `TAIL-200`）：它的基准 = **最新壳快照**，而那份"
         "**在包里**（`pack.ps1` ② 会带上）⇒ **目标机也能跑**（⛔ 不再需要交付面）。",
         "⭐ **`ui_parity` 不在此列**（2026-09-30 `TAIL-200` → `TAIL-201`）：`U1`/`U5` 退场后它**只查壳自己** "
         "⇒ **什么都不需要**（⛔ 交付面、⛔ 壳快照都不用）⇒ **目标机开箱就能跑**。"),
        ("⚠️ **`ui_parity` 不受影响**（2026-09-30 `TAIL-200`：它的基准是**壳快照**，在包里） |",
         "⚠️ **`ui_parity` 不受影响**（2026-09-30 `TAIL-201`：它只查壳自己，不用任何基准） |"),
    ], dry)
    print("   ✅ 阈值表 / architecture / delivery-surface / deployment（4 份）")

    _edit(T1, [
        ("既没有 `ui_parity` 的 `U1` 可比",
         "既没有 `ui_parity` 的 `U1` 可比（⚠️ 2026-09-30 `TAIL-201`：`U1` 与登记簿**已退场** ⇒ 本句只作留痕）"),
    ], dry)
    _edit(T2, [
        ("`*_THEAD` 全在 `ui_parity` 的 **`U5` 登记表**里（原型与壳必须逐字一致）",
         "~~`*_THEAD` 全在 `ui_parity` 的 `U5` 登记表里~~（⚠️ 2026-09-30 `TAIL-201`：`U5` **已退场** ⇒ "
         "这条理由**作废**；⛔ 但「不许随手改表头」的**真理由没变** —— 它们是界面文案/口径，改了要跑 `acc_*` ＋ 真机）"),
    ], dry)
    _edit(T3, [
        ("（U1 视图一致 ＋ **U2b 已接线页不得留演示数组**；",
         "（⭐ 2026-09-30 `TAIL-201`：`U1` 已退场 ⇒ 现只剩 **U2/U2b/U3/U4**；"
         "「壳变了没有」看 `shell_verify` ＋ **U2b 已接线页不得留演示数组**；"),
        ("（它在 `ui_parity` 的 `U5` 登记表里：原型与壳必须逐字一致）",
         "（⚠️ 2026-09-30 `TAIL-201`：`U5` 已**退场** ⇒ 这条理由作废；真理由 = 它是**界面口径**，"
         "改了要跑 `acc_*` ＋ 真机）"),
    ], dry)
    print("   ✅ 4 条判据的「理由句」换成真理由")

    plan = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    des = DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    des = _edit_str(des, [
        ("2. ⭐ **新公共件放**壳侧公共件区 **＋ 原型同段，并登记进 `U5_GROUPS`** —— `U5_GROUPS` 第一组的注释已经写明："
         "「`TAIL-64` 每抽出一个新公共件，就把名字加进本表 ⇒ **那就是它的闸门**」。",
         "2. ⛔ ~~**新公共件放**壳侧公共件区 **＋ 原型同段，并登记进 `U5_GROUPS`**~~ —— "
         "⭐ **2026-09-30 `TAIL-201` 起这条作废**（`U5` 与原型那一路**整体退场**，⛔ 不必再「双边同步」）。"
         "**新公共件现在的闸门** = 挂**判据 ＋ 反向灵敏度** ＋ `shell_verify` 盖章（差异 ＝ 要你确认）"),
        ("⚠️ `thCount` / `sumRowOf` **没进 `U5_GROUPS`**",
         "⚠️ ~~`thCount` / `sumRowOf` **没进 `U5_GROUPS`**~~（⭐ 2026-09-30 `TAIL-201`：`U5` 已退场 ⇒ "
         "这条「两边一致没人守」的记载随之失效；原句见 git 历史）"),
        ("| **`P4-c-a`（试点 1 处）** | 先跑 `ui_parity` 的 `U1` **逐页对位量**，挑**两侧本来就逐行对齐**（0 偏移）的那一页；",
         "| **`P4-c-a`（试点 1 处）** | ⚠️ ~~先跑 `ui_parity` 的 `U1` 逐页对位量、挑 0 偏移的页~~ "
         "（⭐ 2026-09-30 `TAIL-201`：**那一步已无对象** —— 原型那一路退场 ⇒ **随便挑一页**即可，"
         "编号不再需要照顾「原型侧对齐」）；"),
    ], "施工图")
    plan = _edit_str(plan, [
        ("；⚠️ 抽出新公共件时**把它加进 `U5_GROUPS`** = 本条自己的闸门",
         "；⛔ ~~抽出新公共件时把它加进 `U5_GROUPS`~~ = 这条闸门**已作废**（⭐ 2026-09-30 `TAIL-201`：`U5` 退场 "
         "⇒ 新公共件改靠**判据＋变异** ＋ `shell_verify` 盖章守）"),
        ("| `TAIL-201` ⭐ **`U1`/`U5` 与 `shell_verify` 重叠**（`TAIL-200` 换基准后的产物） | "
         "⏳ **待你一句话**（`C` 类 · 见 §三）",
         "| `TAIL-201` ⭐ **`U1`/`U5` 与 `shell_verify` 重叠**（`TAIL-200` 换基准后的产物） | "
         "✅ **已办（2026-09-30 · 用户裁「退场」）**"),
        ("A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **200** 条",
         "A 类 **3** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **201** 条"),
        ("A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **200**",
         "A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **201**"),
        ("＋ **`TAIL-201`**（**已裁：`U1`/`U5` 退场** · ⏳ **待施工** —— ⚠️ 要**整轮预算**，施工图 = "
         "`.codebuddy/memory/2026-09-30.md` **§23**））·",
         "⇒ ⭐ **`TAIL-201` 已办**（`U1`/`U5` **整半退场** ⇒ 「壳变了没有」只有 `shell_verify` 一处账 · "
         "§15 §四））·"),
    ], "计划（文本级）")
    # §一 → §四
    lines = plan.split("\n")
    idx = next((i for i, l in enumerate(lines) if l.startswith("| `TAIL-201` | ⭐ **`U1`/`U5` 退场**")), None)
    assert idx is not None, "⛔ §一 里找不到 TAIL-201 行"
    lines.pop(idx)
    for k, ln in enumerate(lines):
        if ln.startswith("### 四、已销号"):
            for j in range(k, k + 6):
                if lines[j].startswith("| # | 事项 | 销号依据 | 日期 |"):
                    lines[j + 1:j + 1] = [ROW4]
                    break
            break
    plan = "\n".join(lines)
    print("   ✅ 计划 · 施工图 3 处 ＋ TAIL-64 行闸门 ＋ TAIL-201 销号（§一→§四）＋ 计数 A3/201")

    if dry:
        print("（干跑：⛔ 未写）")
        return 0
    DES.write_text(des.replace("\n", NL), encoding="utf-8", newline="")
    PLAN.write_text(plan.replace("\n", NL), encoding="utf-8", newline="")
    assert DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == des, "⛔ 施工图写回不一致"
    assert PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == plan, "⛔ 计划写回不一致"
    print("✅ 落纸完成（docs ×4 ＋ 判据 ×3 ＋ 施工图 ＋ 计划）")
    return 0


def _edit_str(t: str, pairs: list[tuple[str, str]], what: str) -> str:
    for old, new in pairs:
        n = t.count(old)
        assert n == 1, f"⛔ {what}：锚点命中 {n} 次（期望 1）—— {old[:70]!r}"
        t = t.replace(old, new, 1)
    return t


if __name__ == "__main__":
    raise SystemExit(main())
