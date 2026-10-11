#!/usr/bin/env python
r"""**第二轮定裁**落纸（2026-09-30 · 用户两问）：`§9.5 ①` 冻结口径**轻量化订正** ＋ `TAIL-188` 加
「说明书/验收基线进包」指示 ＋ 新尾巴 **`TAIL-200`**（`U1`/`U5` 基准要不要提前换掉）。

⚠️ 规矩同 `_p5c_docs.py` / `_decisions_docs.py`：逐处先断言命中数、写回后 round-trip 核一遍。
⚠️ 中文行文里的引号一律用「」——⛔ 别用半角双引号（会把 Python 字面量切断，本仓已踩多次）。

用法：`python tools/oneoff/_decisions2_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

# ── ① 冻结口径：把「功能」那条日历条件换掉（用户原话：BUG 和新需求未来任意时刻都可能再有）
OLD_FUNC = "**功能**（你**连续 3 个工作日不再报**新问题 · 侧栏无「原型态/暂缓」）·"
NEW_FUNC = (
    "**功能**（⭐ **2026-09-30 用户订正**：原写「你**连续 3 个工作日不再报**新问题」——"
    "用户原话「**BUG 和新需求，未来的任意时刻都可能再有**」⇒ 那条**日历条件作废**，"
    "改成「**你说冻就冻**」；「侧栏无『原型态/暂缓』」那半仍有效）·"
)

# ── ② 「变更单」那半：承认它对"全程逐批拍板"的实际状态**冗余**
OLD_FREEZE = ('冻结后进 `M8`；再往后任何改动**先写变更单**。⇒ 其中 `②④` 属 `M7-B`/`M8`，'
              '**等你说"功能可以冻了"再开工**。')
NEW_FREEZE = (
    "冻结后进 `M8`；⚠️ **2026-09-30 用户订正**：用户问「至于开工条件和变更单，**不冻结不也一样**？」"
    "⇒ 本仓实况 = **你全程逐批拍板** ⇒ 「**变更单**」这套对你**冗余** ⇒ 轻量化口径 = "
    "**冻前照旧每批报你拍板；冻后凡动结构先问一句**（⛔ 不引入正式变更单流程，除非你以后要求）。"
    "⚠️ 但「`②④` 等冻结再开工」这半**保留** —— 理由**不是手续，是「做早了会白做」**："
    "备份 / 日志保留 / 只许局域网 / **恢复演练** 都要**演练**，而结构还在动 ⇒ 今天演练通过、"
    "明天结构一变**就作废**。⇒ 其中 `②④` 属 `M7-B`/`M8`。"
)

# ── ③ 新尾巴 TAIL-200（§15 §一 · 7 列）
ROW200 = (
    "| `TAIL-200` | ⭐ **`U1`/`U5` 的基准要不要提前从「原型」换成「壳快照」**（＝ 提前执行 `D23`）—— "
    "用户 2026-09-30 原话：「原型在我看来就是 **1.0 版本**，我们现在的版本可能已经到 **6789** 了，"
    "那原型只是一个旧版本而已，为啥要在更新版本的时候，把改动**同步到 1.0**？」 | "
    "用户 2026-09-30 提问（记 `.codebuddy/memory/2026-09-30.md` §20） | 现状**改壳的公共件／切片 ⇒ "
    "要把同样的字节再写进 WPS 云里那份 demo**（＝双边同步）＋ 改交付面**必跑** `doc_audit --ui` ＋ "
    "⚠️ 交付面有**「云同步回退」实测前科**（`docs/delivery-surface.md` §三）⇒ 成本真实，而收益是什么值得算："
    "`U5` 比的是**源码**不是屏幕 ⇒ 它保的是「**原型不烂**／壳与规格同源」，⛔ 不是「用户看得见的东西」 | "
    "`tools/audit/ui_parity.py`（`U1`/`U5` 两把尺子）＋ `D23`（冻结那刻换基准的口径）＋ 交付面那侧说明 | "
    "随时 | ⏳ 待你定裁（你回一句：`A` 提前换基准 / `B` 维持到冻结） |"
)

ROW200_143 = (
    "| `TAIL-200` ⭐ **`U1`/`U5` 基准：提前换成「壳快照」？** | ⏳ **待你定裁**（`A` 提前换 / `B` 维持到冻结） | "
    "**落点** = `tools/audit/ui_parity.py` 的基准 ＋ `D23` 口径（⚠️ 换基准 = 动判据面 ⇒ 要同批改判据/变异） | "
    "触发 = 你回一句 |"
)

TAIL188_ADD = (
    "；⭐ **2026-09-30 用户指示**：《材料科业务全流程说明书.md》＋ `PRD/验收/验收基线.json` **放进包里**"
    "（包内留一份快照 ⇒ `.env` 的 `PRD_ACCEPTANCE_BASELINE` 默认**指包内**；⚠️ 口径：**云那份仍是真源**，"
    "落地后能连上云就改回 —— ⛔ 免得「两处副本必漂」） | 用户 2026-09-29 口述"
)


def _sub(t: str, old: str, new: str, what: str, n: int = 1) -> str:
    got = t.count(old)
    assert got == n, f"⛔ {what}：锚点命中 {got} 次（期望 {n}）"
    return t.replace(old, new, n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    plan = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")

    plan = _sub(plan, OLD_FUNC, NEW_FUNC, "§9.5 ①「功能」条件")
    plan = _sub(plan, OLD_FREEZE, NEW_FREEZE, "§9.5 ①「变更单」那半")
    print("   ✅ §9.5 ① · 冻结口径轻量化（功能条件作废 ＋ 变更单降级 ＋ 保留「做早了会白做」的理由）")

    a188 = "| `TAIL-188` | ⭐ **交付包与迁移**（本机 ⇒ 办公室电脑）"
    assert plan.count(a188) == 1, "⛔ §15 §一 里 TAIL-188 行锚点不唯一"
    plan = plan.replace(a188, ROW200 + "\n" + a188, 1)
    print("   ✅ §15 §一 · 新立 `TAIL-200`（`U1`/`U5` 基准）")

    a199 = "| ✅ `TAIL-199` ⚠️ **`P5-d` 剩下的两条口径**"
    assert plan.count(a199) == 1, "⛔ §14.3 里 TAIL-199 行锚点不唯一"
    plan = plan.replace(a199, ROW200_143 + "\n" + a199, 1)
    print("   ✅ §14.3 · 新立 `TAIL-200` 行")

    plan = _sub(plan, "（交付面定位 / node / Playwright） | 用户 2026-09-29 口述",
                "（交付面定位 / node / Playwright）" + TAIL188_ADD, "TAIL-188 行（进包指示）")
    print("   ✅ `TAIL-188` 行 · 加「说明书＋验收基线进包」指示")

    plan = _sub(plan, "A 类 **3** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **199** 条",
                "A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **199** 条", "§15 计数行")
    plan = _sub(plan, "A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **199**",
                "A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **199**", "§0 计数行")
    print("   ✅ 计数：A 类 3 → 4（新立 `TAIL-200`）")

    plan = _sub(plan, "（§15 §四））·",
                "（§15 §四）＋ 新尾巴 **`TAIL-200`**（`U1`/`U5` 基准要不要提前换成「壳快照」"
                "—— ⚠️ **待你定裁**））·", "口令 余量行")
    print("   ✅ 口令 · 余量行加 `TAIL-200`")

    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(plan.replace("\n", NL), encoding="utf-8", newline="")
    assert PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == plan, "⛔ 写回不一致"
    print("\n✅ 落纸完成（计划）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
