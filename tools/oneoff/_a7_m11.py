#!/usr/bin/env python
"""`A7` 逐页（`m11` 集采台账）· 本批收口 · 一次性（2026-09-29）。

**本批只做一条**（其余见台账 `TAIL-180` 的待裁）：卡头那枚「抓取采购合同信息」**一个字提示都没有**
（守则 §2.4「操作后果提前说清」/ §4.4），而**同一件事**在别处都有提示 —— `m01` 的「同步仓库名单」
写「会登录 i8，需二次确认」· `m02` 两个同步同款；而集采抓取**还会顶号**（`D9`，确认弹窗里已经写了）。
⇒ 本批把这条提示补到按钮上（提示 = 与弹窗同一口径，⛔ 不新增口径）。

⚠️ 切片改动**行数不变**（只加一个 `title` 属性）⇒ `ui_parity` 的 `U1` 逐行对位只多 1 条漂移，不会级联。

用法：`… _a7_m11.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web" / "index.html"

OLD = '<button class="btn" data-act="jcFetch">抓取采购合同信息</button>'
NEW = ('<button class="btn" data-act="jcFetch" title="从 i8 抓采购合同 —— 会登录 i8、'
       '需二次确认；⚠️ 可能顶掉该账号其它在线会话（同事正在用 i8 时先择时）">抓取采购合同信息</button>')


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = INDEX.read_text(encoding="utf-8", newline="")
    if NEW in raw:
        print("⏭ 已应用（`jcFetch` 已有 title）⇒ 无事可做")
        return 0
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    print("  ✅ 锚点唯一：`m11` 卡头的「抓取采购合同信息」")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    INDEX.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = INDEX.read_text(encoding="utf-8", newline="")
    assert back.count(NEW) == 1 and back.count(OLD) == 0, "写回自校验不过"
    print("✅ 已写：抓取按钮补上后果提示（会登录 i8 / 二次确认 / 可能顶号）")
    print("   接着：`ui_parity`（登记 1 条漂移）⇒ 判据 ＋ 反向灵敏度 ⇒ 全闸门")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
