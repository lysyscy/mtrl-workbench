#!/usr/bin/env python
r"""`P5-b` 顺带新立一条尾巴 `TAIL-197`：**交付面四检失败时闸门不判红**（`T6` 要两处一致 ＋ 计数同改）。

**为什么立它**（本轮实测）：`tools/audit/doc_audit.py --ui` 会把交付面 `demo/*.js` 的**非零退出码照实打印**，
但**它自己不判红** —— 实测 `_smoke 退出码=1（606/1）` 的那一轮，`DOCUI_RC=0`、`_run_rulers` 的 `BAD: []`、
`acc_report` 全绿 ⇒ **交付面回归报得出来、却拦不住**（与"打印了红 ≠ 拦住了"同族）。

改 4 处：`①§15 §一 表加行` · `②§15 顶部计数 A4 → A5` · `③§0.2 同一计数 A4 → A5`（`T4` 两处都要对）·
`④§14.3 加排期行`（`T6` 要求每条尾巴在 §14.3 有一行）。

用法：`python tools/oneoff/_p5b_tail197.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

ROW15 = (
    "| `TAIL-197` | 🚧 **交付面四检失败时，闸门不判红** —— `tools/audit/doc_audit.py --ui` 会把 "
    "`demo/*.js` 的**非零退出码照实打印**，但**自己的 `rc` 仍是 0**（2026-09-30 实测：`_smoke` **606/1** 那一轮，"
    "`DOCUI_RC=0` · `BAD: []` · 四态全绿）⇒ 交付面回归**报得出来、却拦不住**（同族 = 「打印了红 ≠ 拦住了」） "
    "| `TAIL-64` `P5-b` 实测（出处 = `.codebuddy/memory/2026-09-30.md` §12） | 交付面一旦回归，"
    "**只有人眼读四检那 4 行**才发现 ⇒ 迟早漏 | `tools/audit/doc_audit.py` 的「交付面四检」那段"
    "（`subprocess.run(...).returncode` 那处）⇒ 非零要**并入 rc**（⛔ 不是只打印） | 随时 | 待做 |")

ROW143 = (
    "| `TAIL-197` 🚧 **交付面四检失败时闸门不判红**（只打印、不并入 `rc`） | ⏳ **随时**（几行退出码判法） | "
    "**四问**：① **不是别人的前置**；② **成本不随时间变贵**（一处判法）；③ **同域 = 审计工具那一层**"
    "（`doc_audit --ui`，与业务面不耦合）；④ **前置已查清**（本轮实测：`_smoke` 606/1 而 `BAD: []`） "
    "| 触发 = 谁空谁做；落点 = `tools/audit/doc_audit.py` 的「交付面四检」那段 |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    # ① §15 §一 表：插在 `TAIL-196` 那行**之前**（表是按编号降序排的）
    anchor15 = "| `TAIL-196` | 🔁 **「选时间」按钮"
    assert t.count(anchor15) == 1, f"⛔ ① §15 锚点命中 {t.count(anchor15)} 次"
    out = t.replace(anchor15, ROW15 + "\n" + anchor15, 1)
    # ② ③ 计数两处（`T4` 的计数锚点：§15 顶部 ＋ §0.2）
    for old, new in (("A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **195** 条",
                      "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **195** 条"),
                     ("A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **195**",
                      "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **195**")):
        n = out.count(old)
        assert n == 1, f"⛔ 计数锚点 `{old[:28]}…` 命中 {n} 次（期望 1）"
        out = out.replace(old, new, 1)
    # ④ §14.3：插在 `TAIL-196` 那行**之前**
    anchor143 = "| `TAIL-196` 🔁 **「选时间」按钮"
    assert out.count(anchor143) == 1, f"⛔ ④ §14.3 锚点命中 {out.count(anchor143)} 次"
    out = out.replace(anchor143, ROW143 + "\n" + anchor143, 1)

    if not args.write:
        print("干跑 ✅ 4 处锚点各命中 1 次")
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out, "⛔ 写回自校验不过"
    print("✅ 已写：`TAIL-197` 入台账（§15 ＋ §14.3）＋ 两处计数 → A5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
