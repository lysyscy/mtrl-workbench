"""只读盘点（`TAIL-209` 余项 ② · 第 2 版）：壳里**所有会原样上屏的 `**`**，带件名:行号。

## 为什么要有第 2 版

第 1 版 `_text_mark_scan.py` 只扫 `class="tip` 块 ⇒ 报「6 个说明块含 `**`」。
但 `**` 上屏的条件不是"在 tip 里"，而是"这串 HTML **走没走 `lgMd`**"：
`modal({body})`（`base.js` 直插 `innerHTML`）· `toast(msg)`（`innerHTML`）· 拼出来的卡片 HTML
⇒ **块外的 `**` 同样上屏**（如 `<span class="mut sm">**一个字节都不写库**</span>`），第 1 版看不见。
（实测：第 1 版报 6 处，第 2 版报 **49 行 / 7 件**。）

## 与判据的关系（⛔ 别搞混）

- **判据** = `backend/tests/test_ux_text.py::test_壳源码里不许有_双层星号_加粗标记`（`TAIL-209`）
  —— 它只管"有没有"，⛔ 不报位置；
- **本件** = 出**位置清单**（改之前先知道要动哪些行）。
两者**共用**同一个剥注释器（`tools/audit/shell_source.py::strip_comments`）⇒ 口径只有一处。

⚠️ 本件是**只读量测**：不进收工闸门、不判红。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.audit.shell_source import parts_text, strip_comments  # noqa: E402

total = 0
files = 0
for name, text in parts_text():
    clean = strip_comments(text, html=name.endswith(".html"))
    hits = [(i, ln.strip()) for i, ln in enumerate(clean.splitlines(), 1) if "**" in ln]
    if not hits:
        continue
    files += 1
    total += len(hits)
    print(f"\n── {name}（{len(hits)} 行）")
    for i, ln in hits:
        print(f"   :{i}  {ln[:150]}")

print(f"\n=== {files} 件 · 共 {total} 行含 `**`（注释已剥）===")
