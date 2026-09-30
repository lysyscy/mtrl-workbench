#!/usr/bin/env python
"""`A10` 逐页（`m13` / `m14` / `set` / `m15`）· 本批收口 · 一次性（2026-09-29）。

**本批只做一条**：`V.m14` 里「**分类只有三类**…」那句挂的是 **`tip dg`（危险红）**，而它是**口径说明**
（陈述"只有三类、没有其他类"这个事实），不是"危险 / 错误" ⇒ 守则 §4.5：**红只给危险 / 错**；
⚠️ 同一页 1545 那条**禁止项**（"不得配置收款单位 = 资产处集中采购"）用的是 `tip wn`（黄）—— 那才是对的形态。
⇒ 改成**普通 `tip`**（守则 §4.5 判法：说明一律普通）。

⚠️ 又一处**颜色闸门的盲区**（本批顺带发现）：`tests/test_ux_colors.py` 的墓碑**只覆盖 `tip ok` / `tip wn`**
（批次 0 数的就是这两类共 38 处）⇒ **`tip dg` 从没被审过**。本批把这一类也纳入那个闸门（加墓碑 ＋ 改文件头口径）。

⚠️ 切片改动**同一行内**（只动 `class`），⛔ 不在切片里加注释行（那会多出 1 行、`U1` 逐行对位会连锁）。

用法：`… _a10_m14.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web" / "index.html"

OLD = '<div class="tip dg" style="margin:0"><b>分类只有三类</b>'
NEW = '<div class="tip" style="margin:0"><b>分类只有三类</b>'


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
    print("  ✅ 锚点唯一：`V.m14` 的「分类只有三类」那句（`tip dg` ⇒ `tip`）")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    INDEX.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = INDEX.read_text(encoding="utf-8", newline="")
    assert back.count(NEW) == 1 and back.count(OLD) == 0, "写回自校验不过"
    print("✅ 已写：那句口径说明降为普通 `tip`（守则 §4.5：红只给危险 / 错）")
    print("   接着：`test_ux_colors.py` 加墓碑 ⇒ `ui_parity --write-expected` 登记 1 条漂移")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
