#!/usr/bin/env python
"""补 `TAIL-180` 销号行的**裁定出处**（`claim_audit` 的 `C2` 当场抓到 · 一次性 2026-09-29）。

⚠️ 这是**同一个坑的第二次**（上一次是 `TAIL-178` 那两行）：写「用户裁定 ＋ 日期」时**忘了写可核的出处**。
⇒ 本仓纪律：**"用户裁定"必须同时写 日期 ＋ 出处**（去得着核原话的地方）。
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

SRC = "出处 = §13.6 接手核验续记 ＋ `.codebuddy/memory/2026-09-29.md`"
OLD = "（`B` 案 · 2026-09-29 **用户裁定**）"
NEW = f"（`B` 案 · 2026-09-29 **用户裁定** · {SRC}）"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    raw = PLAN.read_text(encoding="utf-8", newline="")
    if NEW in raw:
        print("⏭ 已应用（出处已在）⇒ 无事可做")
        return 0
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    print(f"  ✅ 锚点唯一：`TAIL-180` 销号行（`{OLD[:28]}…`）")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    PLAN.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    print("✅ 已写：补上裁定出处")
    print("   接着：`claim_audit`（期望 `C1` 0 ＋ `C2` 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
