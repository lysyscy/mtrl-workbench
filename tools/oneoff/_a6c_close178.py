#!/usr/bin/env python
"""`TAIL-178` **销号**（用户 2026-09-29 裁定「没有触屏用户，不需要」）· 一次性（2026-09-29）。

**为什么不是"删掉"**：本仓对"不做"的尾巴一律**销号 ＋ 写明依据**（`§15 §四` 留痕、不释放编号），
⛔ 不是静默删掉 —— 否则下一个人会把同一个议题再提一遍。

**它改什么**：
  1. `§15`：`§一` 删 `TAIL-178` 行 ⇒ `§四` 加一行（依据 = 用户裁定）；计数 `A 6 → 5` · `已销号 176 → 177`；
  2. `§14.3`：那一行的「建议时机」格改成 `⛔ 不做（2026-09-29 · 用户裁定：本系统没有触屏用户）`
     （⚠️ 行**保留**：`T6` 要求"登记即排期"两表一致，删行会让 §四 的编号在排期表里悬空）；
  3. `§13.6`：状态行 / 下一步里那两处「⏳ 待做」改成「⛔ 用户裁定不做」；
  4. 守则 `§10`：在 `A6b` 那一行末尾**追一句订正**（那条引出的复核不做 ＋ `m01` 可见理由保留）。

⚠️ 行手术纪律（本会话同族踩过两次）：**先做行手术、且每步改完重新定位下标**；
⛔ 别拿"改动前算出的下标"去改"改动后的数组"。

用法：`… _a6c_close178.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
RULE = REPO / "ops" / "前端设计守则-以使用用户为中心.md"

ROW_DONE = (
    "| `TAIL-178` | ⛔ **不做（用户 2026-09-29 裁定：「没有触屏用户，不需要」）** —— 原议题 = 全站约 27 处"
    "字面 `disabled` 只挂 `title`（`A6b` 真机实测：置灰元素 `matches(':hover')` **仍成立** ⇒ 鼠标用户看得到、"
    "键盘 / 触屏看不到）⇒ 要不要逐处把理由挪上屏 | ⛔ **用户裁定不做**（本系统没有触屏用户 ⇒ 该缺口不成立）；"
    "⚠️ `m01` 删除确认那处**已上屏的可见理由保留**（它同时说明「这一项还没打通」，与悬停无关） | 2026-09-29 |"
)

EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    (PLAN, "§0.2 尾巴计数（A 6 → 5 · 已销号 176 → 177）",
     "A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **176**",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **177**"),
    (PLAN, "§15 计数行（`T6` 按实际条数核）",
     "A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **176** 条",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **177** 条"),
    (PLAN, "§14.3：`TAIL-178` 那行的「建议时机」改成 ⛔ 不做",
     "| 随时（**自主推进**：不阻塞主线，按页顺路做） |",
     "| ⛔ **不做（2026-09-29 · 用户裁定：本系统没有触屏用户）** ⇒ 已销号 |"),
    (PLAN, "§13.6 状态行：`TAIL-178` 改「用户裁定不做」",
     "⏳ 新立 `TAIL-178` 待做：全站「置灰写理由」的可达性复核）",
     "⛔ `TAIL-178` 经用户裁定**不做**（2026-09-29：本系统没有触屏用户）⇒ 已销号）"),
    (PLAN, "§13.6 入门口令下一步：同上",
     "⏳ 新立 `TAIL-178`（置灰理由可达性复核）；",
     "⛔ `TAIL-178` 用户裁定**不做**（2026-09-29：没有触屏用户）；"),
    (RULE, "守则 §10：`A6b` 那行末尾追一句订正",
     "＋ 反向灵敏度专打这一点 |",
     "＋ 反向灵敏度专打这一点；⚠️ **订正（同日）**：第 ① 条引出的 `TAIL-178`（全站「置灰写理由」可达性复核）"
     "经**用户裁定不做**（「**没有触屏用户，不需要**」）⇒ 已销号；`m01` 那处**已上屏的可见理由保留**"
     "（它同时说明「这一项还没打通」，与悬停无关） |"),
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    plan: list[tuple[pathlib.Path, str, str, str]] = []
    for path, label, old, new in EDITS:
        raw = path.read_text(encoding="utf-8", newline="")
        assert raw.count(old) == 1, f"{label}：锚点命中 {raw.count(old)} 次（要**恰好 1 次**）—— 先核再改"
        assert new not in raw, f"{label}：新串已在 ⇒ 本脚本跑过了"
        plan.append((path, label, old, new))
        print(f"  ✅ 锚点唯一：{label}（{path.name}）")

    # ── §15 行手术（⚠️ 先做，且每步重新定位下表）─────────────────────────
    txt = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in txt else "\n"
    lines = txt.replace("\r\n", "\n").split("\n")
    hA = [i for i, ln in enumerate(lines)
          if ln.strip() == "| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |"]
    assert len(hA) == 1, f"§一 表头命中 {len(hA)} 行"
    drop = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-178` |")]
    assert len(drop) == 1, f"§一 的 `TAIL-178` 行命中 {len(drop)} 行"
    print(f"  ✅ 命中：§一 第 {drop[0] + 1} 行 = `TAIL-178`（待删）")

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；逐处 {len(plan)} 处 ＋ §一 −1 / §四 ＋1）")
        return 0

    lines.pop(drop[0])                                    # ① 先删（删完再找 §四 表头 —— ⛔ 别用旧下标）
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "删行后 §四 表头不唯一"
    lines.insert(hD[0] + 1, ROW_DONE)                     # ② 紧跟表头（§四 无 `|---|`）
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    print("✅ 已写：§15（§一 −1 `TAIL-178` · §四 ＋1 销号行）")

    for path, label, old, new in plan:
        raw = path.read_text(encoding="utf-8", newline="")   # ⚠️ 每处写前重读盘
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        path.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{label}")

    print("\n接着：`audit_meta`（`T6`：编号/计数/排期两表一致）⇒ `doc_audit`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
