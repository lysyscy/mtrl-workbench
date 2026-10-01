#!/usr/bin/env python
r"""`TAIL-201`（**退场** · 用户 2026-09-30 裁定）**定死**：把这一条从 §15 §三（待你一句话）
挪进 **§一（我认领的活）**，状态 = 「⏳ 待施工」，并把**施工图**（19 处活引用）钉在它的落点上。

⚠️ 为什么只落纸、不这轮开拆：⛔ 判据面（尺子/变异/文档）要动 19 处 ⇒ 必须留足「改 ＋ 全闸门」的**整轮预算**
   （本仓纪律，见口令「⛔ 开工要留足整轮预算」）。⇒ 施工图 = `.codebuddy/memory/2026-09-30.md` §23。
用法：`python tools/oneoff/_tail201_plan.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

ROW1 = (
    "| `TAIL-201` | ⭐ **`U1`/`U5` 退场**（`ui_parity` 只留 `U2`/`U3`/`U4`）—— 用户 2026-09-30 裁定「退场」（出处 = "
    "`.codebuddy/memory/2026-09-30.md` §22/§23）；来由 = `TAIL-200` 换了基准后发现 `U1`/`U5` 与 `shell_verify` "
    "**同一个基准、一事两套账** | 用户 2026-09-30 口述 | 留着 = 每批盖一次章 ＋ 每批登一次记"
    "（登记条目**盖完章就成幽灵**）⇒ 一事两写 | **施工图**（19 处活引用逐条列出 · ⚠️ 它要**整轮预算**）"
    "= `.codebuddy/memory/2026-09-30.md` **§23**；落点 = `tools/audit/ui_parity.py` ＋ `audit_drift.py` 的 `T4` "
    "锚点 ＋ `_mut_shell`/`_mut_countanchors` ＋ 两份 `docs/` ＋ 计划 | 随时 | ⏳ **待施工**（裁定已下 · 施工图已备） |"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dry = not a.write
    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    lines = t.split("\n")

    # ① 删掉 §三 里那行
    idx = next((i for i, l in enumerate(lines) if l.startswith("| `TAIL-201` | ⭐ **`U1`/`U5` 与 ")), None)
    assert idx is not None, "⛔ §三 里找不到 TAIL-201 那行"
    lines.pop(idx)

    # ② 放进 §一（表头 `| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |` 之后）
    for k, ln in enumerate(lines):
        if ln.startswith("### 一、A 类"):
            for j in range(k, k + 8):
                if lines[j].startswith("| # | 事项 | 来源 | 不做会怎样 |"):
                    lines[j + 1:j + 1] = [ROW1]
                    break
            else:
                raise AssertionError("⛔ §一 里找不到表头行")
            break
    else:
        raise AssertionError("⛔ 找不到 §一 段")
    t = "\n".join(lines)

    # ③ 计数：A 3 → 4 · C 1 → 0
    for old, new in (("A 类 **3** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **200** 条",
                      "A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **200** 条"),
                     ("A 类 **3** 条 · B 类 0 · C 类 **1** · 已销号 **200**",
                      "A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **200**")):
        assert t.count(old) == 1, f"⛔ 计数锚点命中 {t.count(old)} 次：{old[:40]!r}"
        t = t.replace(old, new, 1)

    # ④ 口令 · 余量行：`TAIL-201` 从「立了待你定」改成「已裁 · 待施工」
    old_hint = ("＋ 立 **`TAIL-201`**（C 类：`U1`/`U5` 与 `shell_verify` **重叠**，要不要索性退场 —— "
                "⚠️ 待你一句话））·")
    new_hint = ("＋ **`TAIL-201`**（**已裁：`U1`/`U5` 退场** · ⏳ **待施工** —— ⚠️ 要**整轮预算**，施工图 = "
                "`.codebuddy/memory/2026-09-30.md` **§23**））·")
    assert t.count(old_hint) == 1, f"⛔ 口令余量行锚点命中 {t.count(old_hint)} 次"
    t = t.replace(old_hint, new_hint, 1)
    print("   ✅ §三 → §一（TAIL-201 待施工）＋ 计数 A 4 / C 0 ＋ 口令余量行")

    if dry:
        print("（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
    assert PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == t, "⛔ 写回不一致"
    print("✅ 落纸完成（计划）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
