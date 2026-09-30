#!/usr/bin/env python
"""`TAIL-185`（`A` 案 · 摘掉 `m08` 那枚空转的朴素导出）的**文书收口** · 一次性（2026-09-29）。

**它改什么**（⚠️ 每处写前断言**恰好命中一次**；台账行手术排在字符串编辑**之前**、每步重定位下标）：
  1. 计划 `§15`：**`TAIL-185` 从 `§三` 移到 `§四`（销号 · `A` 案）**；计数 `C 1 → 0` · 已销号 `182 → 183`；
  2. `§14.3`：`TAIL-185` 那行标 ✅ 已办；
  3. `§13.6`：状态行 / 入门口令下一步 / 接手核验续记；
  4. 守则 `§10` 记一笔（⭐ 含本批最硬的一条：**改壳同批改契约** —— claim 与守卫一起动）；
  5. 逐页计划 `§三` 进度块补一句。
  ⚠️ **四态计数本批不动**（判据点总数**不变** —— 改的是既有 claim 的文字）。

用法：`… _a9b_docs.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
RULE = REPO / "ops" / "前端设计守则-以使用用户为中心.md"
PAGEPLAN = REPO / ".workbuddy" / "work" / "10-designs" / "设计-前端逐页推进计划-20260929.md"

STAMP = "20260929-1250"
SRC = "出处 = §13.6 接手核验续记 ＋ `.codebuddy/memory/2026-09-29.md`"

ROW_DONE = (
    "| `TAIL-185` | 🧾 **摘掉 `m08` 卡头那枚「点了必然空转」的朴素导出**（`A` 案 · 2026-09-29 "
    "**用户裁定** · " + SRC + "）：`m08` 卡头并排两枚导出 —— 「导出 Excel」（朴素 · `data-act=\"exp\"` · "
    "走 `EXP_ROUTES` 兜底 ⇒ 点了只会说「这一页还没有导出功能」）＋「导出（含数据透视表）」（`expPivot` · "
    "**真下载**）⇒ 两枚并排、其中一枚必然空转 ＝ **让用户以为坏了**（守则 §4.6）；同族先例 = `m06` 那枚"
    "（`TAIL-173` · 同日用户裁定 `A` ⇒ 已摘）。⭐ 做法 = **`BIND.m08` 渲染后摘除**（⛔ **零切片改动** —— "
    "`V.m08` 是 `U1` 逐行对位原件，删行会让它后面所有行报漂移；`test_tail04_pages.py` 还把 "
    "`data-act=\"exp\" data-t=…` 的名单钉在源码上）；⚠️ **同批改了契约**：`ACC-INV-001/001-12` 的 claim "
    "由「朴素导出与含透视那份**并存互不影响**」改成「**卡头只留真入口**：朴素那枚渲染后摘除」"
    "（⛔ 只改壳不改 claim = 守则 §4.1「说了不做」）；`EXP_ROUTES` 上方那段裁定注释同批订正 | "
    "判据 = **改既有守卫**（`tests/test_tail04_export.py` 的 `001-12`：切片里两枚仍在 ＋ **渲染后朴素那枚"
    "必须被 `BIND.m08` 摘掉**；判据点**总数不变**）＋ **反向灵敏度** `tools/mut/_mut_a7.py` **9/9** ＋ "
    "全套 pytest **100%** ＋ 四态**仍 641** ＋ `ui_parity` **零漂移**（没碰切片）＋ **交付面**改前已备份"
    "（`交付面-20260929-1247-A9b/`）＋ **盖章** `" + STAMP + "` | 2026-09-29 |"
)

EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    (PLAN, "§0.2 的尾巴计数（C 1 → 0 · 已销号 182 → 183）",
     "A 类 **5** 条 · B 类 0 · C 类 **1** · 已销号 **182**",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **183**"),
    (PLAN, "§15 计数行（`T6` 按实际条数核）",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **182** 条",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **183** 条"),
    (PLAN, "§14.3：`TAIL-185` 那行标 ✅ 已办",
     "| ⏳ **待用户一句话**（⚠️ 只牵「要不要动既有契约」，不影响本页可用） |",
     "| ✅ **已办（`A` 案 · 2026-09-29）** ⇒ 见 §15 §四（⚠️ 同批改了 `ACC-INV-001/001-12` 的 claim 文字） |"),
    (PLAN, "§13.6 状态行：`TAIL-185` 已按 `A` 案办",
     "⚠️ 同批查出 `m08` 那枚朴素导出"
     "与既有契约 `ACC-INV-001/001-12`「并存互不影响」**有张力** ⇒ 立 `TAIL-185` 待你裁）⇒ ",
     "⭐ 同批查出 `m08` 那枚朴素导出与既有契约 `ACC-INV-001/001-12`「并存互不影响」**有张力** ⇒ 立 "
     "`TAIL-185`，**用户已裁定 `A`**：**摘掉它**（`BIND.m08` 渲染后摘除 · 零切片改动 · 同 `m06` 那次；"
     "⚠️ **同批把那条 claim 的文字改成「卡头只留真入口」** ⇒ 见 §15 §四）⇒ "),
    (PLAN, "§13.6 入门口令的下一步：`TAIL-185` 已办",
     "⏳ 新立 `TAIL-185`（`m08` 朴素导出：与 `001-12` 有张力 · 待你裁）；",
     "⭐ `TAIL-185` **用户已裁定 `A`**：`m08` 那枚朴素导出**渲染后摘除**（`BIND.m08` · 零切片改动 · 同 "
     "`m06`）＋ **同批改 `ACC-INV-001/001-12` 的 claim 文字**（改壳不改 claim = 「说了不做」）；"),
    (PLAN, "§13.6 接手核验续记：`TAIL-185` 已办",
     "＋ 新立 `TAIL-185`（朴素导出的待裁）⇒ 四态**仍 641**（本批不新增判据点）；⏳ 下一步 = `A10`",
     "＋ `TAIL-185`（朴素导出的待裁）—— **用户裁定 `A` ⇒ 已办**：`BIND.m08` 摘掉它 ＋ **同批改 "
     "`ACC-INV-001/001-12` 的 claim**（判据点总数**不变**）⇒ 四态**仍 641**；⏳ 下一步 = `A10`"),
    (RULE, "守则 §10 变更记录：记一笔 `TAIL-185`（`A` 案）",
     "{nl}---{nl}{nl}## 附录 A · 原始口述对照",
     "{nl}| 2026-09-29 | ⭐⭐ **`TAIL-185`（`A` 案）：摘掉「点了必然空转」的导出按钮 —— 且改壳要同批改契约** "
     "—— `m08` 卡头并排两枚导出（朴素那枚走兜底 ⇒ 点了只会说「这一页还没有导出功能」；含透视那枚是真下载）"
     "⇒ 用户裁定 `A`：**摘掉朴素那枚**（守则 §4.6）。做法 = `BIND.m08` **渲染后摘除**，⛔ **零切片改动**"
     "（`V.m08` 是 `U1` 逐行对位原件；`test_tail04_pages.py` 还把 `data-act=\"exp\" data-t=…` 名单钉在源码上） "
     "| §4.6 §4.1 | `tests/test_tail04_export.py` 的 `001-12`（**同批改守卫**：切片两枚仍在 ＋ 渲染后朴素那枚"
     "必须被摘）＋ `tools/mut/_mut_a7.py` **9/9** · 四态**仍 641** · 盖章 `" + STAMP + "` | "
     "用户 2026-09-29「185：A，继续」 | ⭐⭐ **可复用**：**契约与实现是一对** —— 用户裁定改了**界面真相**，"
     "那条说「两者并存互不影响」的 claim 就**同时变成假话** ⇒ 必须**同批**改 claim 文字 ＋ 改守卫断言"
     "（⛔ 只改壳不改 claim = 守则 §4.1「说了不做」；本项目最忌「界面与契约互相矛盾」—— 前例见 `TAIL-125`） |" +
     "{nl}{nl}---{nl}{nl}## 附录 A · 原始口述对照"),
    (PAGEPLAN, "逐页计划 §三 进度块：补 `TAIL-185` 已办",
     "⇒ **没擅自改**；张力来自 `m06` 那次（`TAIL-173` · 用户裁定 `A` 摘掉同款按钮）。",
     "⇒ **没擅自改**；张力来自 `m06` 那次（`TAIL-173` · 用户裁定 `A` 摘掉同款按钮）。"
     "{nl}> ✅ **`TAIL-185` 已按 `A` 案办（2026-09-29 · 用户裁定）**：`m08` 那枚朴素导出**渲染后摘除**"
     "（`BIND.m08` · ⛔ **零切片改动** —— `U1` 逐行对位原件 ＋ `test_tail04_pages.py` 把名单钉在源码上）；"
     "⚠️ **同批把 `ACC-INV-001/001-12` 的 claim 文字改成「卡头只留真入口」**（改壳不改 claim = 「说了不做」）"
     "＋ 守卫同批改在 `tests/test_tail04_export.py`（判据点**总数不变**）；`EXP_ROUTES` 上方那段裁定注释同批订正。"),
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    plan: list[tuple[pathlib.Path, str, str, str]] = []
    for path, label, old_t, new_t in EDITS:
        raw = path.read_text(encoding="utf-8", newline="")
        nl = "\r\n" if "\r\n" in raw else "\n"
        old, new = old_t.replace("{nl}", nl), new_t.replace("{nl}", nl)
        if old == new:
            raise AssertionError(f"{label}：新旧串相同（空操作 ⇒ 本脚本写错了）")
        n = raw.count(old)
        assert n == 1, f"{label}：锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
        assert new not in raw, f"{label}：新串已在 ⇒ 本脚本跑过了"
        plan.append((path, label, old, new))
        print(f"  ✅ 锚点唯一：{label}（{path.name}）")

    txt = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in txt else "\n"
    lines = txt.replace("\r\n", "\n").split("\n")
    drop = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-185` |")]
    assert len(drop) == 1, f"§三 的 `TAIL-185` 行命中 {len(drop)} 行"
    print(f"  ✅ 命中：§三 第 {drop[0] + 1} 行 = `TAIL-185`（转销号 ⇒ 删）")

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；逐处 {len(plan)} 处 ＋ §三 −1 / §四 ＋1）")
        return 0

    lines.pop(drop[0])
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "删行后 §四 表头不唯一"
    lines.insert(hD[0] + 1, ROW_DONE)
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    print("✅ 已写：§15（§三 −1 `TAIL-185` · §四 ＋1 销号）")

    for path, label, old, new in plan:
        raw = path.read_text(encoding="utf-8", newline="")     # ⚠️ 每处写前重读盘
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        path.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{label}")

    print("\n接着：全套 pytest ＋ 12 把尺子 ＋ `claim_audit`（`T4`/`T6` 会盯计数与排期）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
