#!/usr/bin/env python
"""`§13.6` 那行「本次交接 = …」跟上新编号（`HANDOFF-20260929-01`）· 一次性（2026-09-29）。

**为什么不用编辑器工具改**：本批实测过一次「**外部脚本写完 ⇒ 编辑器里的旧副本又把它盖回去**」
（`_handoff_20260929.py` 那次：主文档明明写了，回读却是旧内容）⇒ 凡这条链路，
一律**用脚本读盘 → 改 → 写回 → 再读盘校验**，⛔ 中间不混用编辑器。

用法：`… _fix_handoff_lead.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"

OLD = "> ⭐ **本次交接 = `HANDOFF-20260928-01`（下面「★ 当前交接材料」一节 · ⛔ 别按 `-20260927-02` 及更早的接续）**。"
NEW = "> ⭐ **本次交接 = `HANDOFF-20260929-01`（下面「★ 当前交接材料」一节 · ⛔ 别按 `-20260928-01` 及更早的接续）**。"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n")
    n = t.count(OLD)
    if n == 0 and t.count(NEW) == 1:
        print("已经是新编号 ⇒ 无需改（幂等）")
        return 0
    if n != 1:
        print(f"⛔ 那行命中 {n} 次（期望 1）⇒ ⛔ 别写")
        return 1
    out = t.replace(OLD, NEW, 1)
    print(f"改 1 行：{OLD[:40]}… ⇒ {NEW[:40]}…")
    if args.write:
        PLAN.write_text(out.replace("\n", nl) if nl == "\r\n" else out, encoding="utf-8", newline="")
        back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
        print(f"   回读校验：新编号 {back.count('本次交接 = `HANDOFF-20260929-01`')} 处 · "
              f"旧编号残留 {back.count('本次交接 = `HANDOFF-20260928-01`')} 处 · 行数 {len(back.splitlines())}")
    else:
        print("（`--check`：⛔ 未写）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
