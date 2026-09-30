#!/usr/bin/env python
"""`A9` 逐页（`m08` 库存单据）· 本批收口 · 一次性（2026-09-29）。

**本批只做一条**（其余见台账 `TAIL-185` 的待裁）：`V.m08` 结尾那句
`<div class="tip ok">`**已验证：**重新抓取 i8 数据后——原始金额回到 i8 值，但**调整单依然保留**…`
**挂了成功绿，而它是一句「机制说明」**（讲系统会怎么表现），不是"这一步已经做完"的结果回执 ——
守则 `§4.5` 的判法原文：**预告 / 机制说明 / 空态指路 / 安抚 一律普通 `tip`**。
⚠️ 批次 0 已经为**同款**改过两处（「交付形态」「上次值带入」都从 `tip ok` 降成普通 `tip`）⇒ 这处是漏网。

⚠️ 切片改动**同一行内**（只动 `class`），⛔ 不在切片里加注释行（那会多出 1 行、`U1` 逐行对位会连锁）。
   理由写进：`tests/test_ux_colors.py` 的墓碑 ＋ 台账 `§四`。

用法：`… _a9_m08.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web" / "index.html"

OLD = '<div class="tip ok" style="margin:0"><b>已验证：</b>'
NEW = '<div class="tip" style="margin:0"><b>已验证：</b>'


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = INDEX.read_text(encoding="utf-8", newline="")
    if NEW in raw and OLD not in raw:
        print("⏭ 已应用（那句已是普通 `tip`）⇒ 无事可做")
        return 0
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    print("  ✅ 锚点唯一：`V.m08` 的「已验证」那句（`tip ok` ⇒ `tip`）")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    INDEX.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = INDEX.read_text(encoding="utf-8", newline="")
    assert back.count(NEW) == 1 and back.count(OLD) == 0, "写回自校验不过"
    print("✅ 已写：那句机制说明降为普通 `tip`（守则 §4.5：绿只给「已经做完」的回执）")
    print("   接着：`test_ux_colors.py` 加墓碑 ⇒ `ui_parity --write-expected` 登记 1 条漂移 ⇒ 消号幽灵")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
