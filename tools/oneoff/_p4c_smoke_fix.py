#!/usr/bin/env python
"""`TAIL-64` **P4-c 前哨**：改交付面 `demo/_smoke.js` 里那条**把手抄数字钉死**的断言（2026-09-30）。

**起因**：把 `m02` 的「口径说明 · 6 条」改成**真数 7 条**（`_p4c_fixcount.py`）之后，
`_smoke` 当场红 —— `X10｜MOD-02 口径说明为 6 条` 那条**钉的是那个数字本身**。
⭐ 这正是本仓的老课：**"改界面真相 ⇒ 那条 claim/守卫同时变成假话"** ⇒ 必须**同批改**。
⚠️ 而且它本来要证的是「**新增的定时抓取约束**确实写进了 MOD-02 的口径说明」——
   拿"条数 = 6"当替身是**脆的**（块里增删一条就假红）⇒ 改钉**意图**：
   **块在 ＋ 块里有那条约束 ＋ 标注的 N 与实际 `<li>` 数一致**（数字与内容同源）。
⚠️ 交付面注释里 ⛔ **不写工程仓的路径**（`_links` 会判断链 —— 本仓已踩两次）⇒ 只写"工程仓的测试里"。

用法：`python tools/oneoff/_p4c_smoke_fix.py`（干跑）· `… --write`
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import argparse
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
SMOKE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\_smoke.js")
BACKUPS = ROOT / _run_dir() / "delivery-backups"

OLD = """ck('X10｜MOD-02 口径说明为 6 条（新增定时抓取约束）', V.m02().indexOf('口径说明 · 6 条') >= 0 ? 1 : 0, 1);"""

NEW = """/* X10·3（⭐ 2026-09-30 改判 · `TAIL-64` P4-c 前哨）：原先钉的是「口径说明 · **6** 条」这个**手抄数字** ——
   ⚠️ 实测它**已经漂了**（该块实际有 **7** 条 `<li>`；原型与壳同一位点都写着 6）⇒ 那是**屏幕上的假数字**。
   本条本来要证的是「MOD-02 的**定时抓取约束**确实写进了它的口径说明」。
   ⇒ 改钉**意图**：块在 ＋ 块里有那条约束 ＋ **标注的 N 与实际 `<li>` 数一致**（数字与内容同源，不写死）。
   ⚠️ 壳侧同款守卫（**逐块 · 全站**）在工程仓的测试里（**不在本次交付**）。 */
ck('X10｜MOD-02 口径说明「定时抓取约束」在，且条数标注 = 实际 <li> 数', (function () {
  const b = (V.m02().match(/<details class="tip"><summary>口径说明 · \\d+ 条[\\s\\S]*?<\\/details>/) || [''])[0];
  if (!b) return 0;
  const stated = Number((b.match(/口径说明 · (\\d+) 条/) || [])[1]);
  const actual = (b.match(/<li>/g) || []).length;
  return stated === actual && b.indexOf('定时') >= 0 ? 1 : 0;
})(), 1);"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    text = SMOKE.read_text(encoding="utf-8")
    n = text.count(OLD)
    assert n == 1, f"⛔ 靶串在 {SMOKE.name} 里命中 {n} 次（必须恰好 1 次）"
    if not args.write:
        print("干跑 ✅ 命中 1 次（⛔ 未写）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / "_smoke.js-备份-20260930-P4c前哨.js"
    if not dst.exists():
        shutil.copy2(SMOKE, dst)
        print(f"  ✅ 备份 ⇒ {dst.relative_to(ROOT)}")
    out = text.replace(OLD, NEW, 1)
    assert len(out.split("\n")) == len(text.split("\n")) + len(NEW.split("\n")) - len(OLD.split("\n"))
    SMOKE.write_text(out, encoding="utf-8", newline="")
    assert SMOKE.read_text(encoding="utf-8") == out, "⛔ 写回自校验不过"
    print("  ✅ 已改（钉意图 ＋ 数字自洽；⛔ 不再钉 6 这个数字）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
