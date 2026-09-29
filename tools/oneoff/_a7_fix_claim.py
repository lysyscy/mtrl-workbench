#!/usr/bin/env python
"""补 `TAIL-178` 两行的**裁定出处**（`claim_audit` 的 `C2` 当场抓到）· 一次性（2026-09-29）。

**为什么**：本仓铁律「用户裁定必须**指得出日期与出处**」（`claim_audit` = 真闸门 · 2026-09-24 用户裁定 `A`）
—— 我写「用户 2026-09-29 裁定」时只写了日期、**没写出处** ⇒ 哨报 `C2` 2 处。
⇒ 补上两个**可核**的位置：`§13.6` 的接手核验续记 ＋ 本会话 `memory` 日志（用户原话在那里）。

用法：`… _a7_fix_claim.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

SRC = "出处 = §13.6 接手核验续记 ＋ `.codebuddy/memory/2026-09-29.md`"

EDITS: tuple[tuple[str, str, str], ...] = (
    (
        "§14.3 的 `TAIL-178` 行（补出处）",
        "⛔ **不做（2026-09-29 · 用户裁定：本系统没有触屏用户）** ⇒ 已销号 |",
        f"⛔ **不做（2026-09-29 · 用户裁定：本系统没有触屏用户 · {SRC}）** ⇒ 已销号 |",
    ),
    (
        "§15 §四 的 `TAIL-178` 行（补出处）",
        "⛔ **用户裁定不做**（本系统没有触屏用户 ⇒ 该缺口不成立）；",
        f"⛔ **用户裁定不做**（本系统没有触屏用户 ⇒ 该缺口不成立 · {SRC}）；",
    ),
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    plan: list[tuple[str, str, str]] = []
    for label, old, new in EDITS:
        n = raw.count(old)
        if new in raw and n == 0:
            print(f"  ⏭ 已应用：{label}")
            continue
        assert n == 1, f"{label}：锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
        plan.append((label, old, new))
        print(f"  ✅ 锚点唯一：{label}")
    if not plan:
        print("\n（全部已应用 ⇒ 无事可做）")
        return 0
    if not args.write:
        print(f"\n（`--check`：⛔ 未写；要改 {len(plan)} 处）")
        return 0
    for label, old, new in plan:
        raw = PLAN.read_text(encoding="utf-8", newline="")     # ⚠️ 每处写前重读盘
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        PLAN.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{label}")
    print("\n接着：`claim_audit`（期望 `C1` 0 ＋ `C2` 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
