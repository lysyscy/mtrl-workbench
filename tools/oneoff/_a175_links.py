#!/usr/bin/env python
"""`TAIL-175` 顺手修交付面断链 · **第二轮**（2026-09-29 · 一次性）。

**为什么还有第二轮**（第一轮只补了 `tests/` 前缀 ⇒ 仍然 FAIL）：`demo/_links.js` 的口径是
**两道**都要满足 —— ① 命中 `KNOWN` 白名单（`/^tests\\//`）；② **同句**出现**声明措辞**
（`DECLARED = /未收录|不在本次交付|不收录|裁剪/`）⇒ 才从 **FAIL 降成 WARN**
（源码：`asWarn = !!hit && (legacyFile || (declared && hit.legacyOnly))`）。
⚠️ 交付面的既有先例 = 《材料科业务全流程说明书》§2383：「判据 = `ACC-USR-MGMT-001`（工程仓
`tests/test_acc_usr_i8.py`，**不在本次交付**）」⇒ 本件照同一写法改 `用例索引.md` 那一句。

用法：`… _a175_links.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
INDEX = FACE / "PRD" / "验收" / "用例索引.md"

OLD = "＋ `tests/test_tail04_pages.py` 把 `data-act=\"exp\" data-t=…` 名单钉在源码上）"
NEW = ("＋ **工程仓** `tests/test_tail04_pages.py`（**不在本次交付**）把 "
       "`data-act=\"exp\" data-t=…` 名单钉在源码上）")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = INDEX.read_text(encoding="utf-8", newline="")
    n = raw.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
    assert NEW not in raw, "新串已在 ⇒ 本脚本跑过了"
    print("  ✅ 锚点唯一（`用例索引.md` 那一句）")
    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    INDEX.write_text(raw.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    back = INDEX.read_text(encoding="utf-8", newline="")
    assert back.count(NEW) == 1 and back.count(OLD) == 0, "写回自校验不过"
    print("✅ 已写：补上**同句声明**（`_links` 的 FAIL ⇒ WARN）")
    print("   接着：`demo/_links.js` 复核（期望 `0 失败`）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
