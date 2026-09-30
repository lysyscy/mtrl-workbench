#!/usr/bin/env python
"""`A11` 逐页（`home` 看板）· 本批收口 · 一次性（2026-09-29）。

**本批只做一条**（⛔ 零行为改动）：`V.home` 里那段「看板清账」注释写「**保留**：归属待指定 / 付款计划未匹配 /
占位行待扶正 / 本月抓取」（**4 项**），而实际 `todoTiles` 有 **6** 项 —— 同一天随后又加了
「**集采未关联合同**」与「**撤单但有牵涉**」（它们各自那段注释就在上面几行）⇒ 这段**没跟上**，
读代码的人会以为"保留 4 项"与 6 个瓦片**互相矛盾**。
⚠️ 本仓这类"同一处留痕被后续增删甩下"已出现过（`A8` 的 `lgSteps` 过期注释）⇒ 本批只订正**这一句**、
⛔ 不动任何代码与判定，也⛔ 不加注释行（切片是 `U1` 逐行对位原件 —— 只改**同一行内**的字）。

用法：`… _a11_home.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web" / "index.html"

OLD = "    保留：归属待指定 / 付款计划未匹配 / 占位行待扶正 / 本月抓取。"
NEW = ("    保留：归属待指定 / 付款计划未匹配 / 占位行待扶正 / 本月抓取；"
       "⭐ 同日**随后又加了 2 项**（集采未关联合同 / 撤单但有牵涉 —— 见上面 `nNoLink` / `nVoidJ` 那段），"
       "本行原先只写了前 4 项 ⇒ 2026-09-29（`A11` 逐页）订正。")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = INDEX.read_text(encoding="utf-8", newline="")
    if NEW in raw and OLD not in raw:
        print("⏭ 已应用（那句已订正）⇒ 无事可做")
        return 0
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    print("  ✅ 锚点唯一：`V.home` 那段「保留 4 项」的注释")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    INDEX.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = INDEX.read_text(encoding="utf-8", newline="")
    assert back.count(NEW) == 1 and back.count(OLD) == 0, "写回自校验不过"
    print("✅ 已写：那段注释订正为「4 项 ＋ 随后又加 2 项」（⛔ 零行为改动、⛔ 没加行）")
    print("   接着：`ui_parity --write-expected` 登记 1 条漂移 ⇒ 消号幽灵")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
