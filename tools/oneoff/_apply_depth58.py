#!/usr/bin/env python
"""`TAIL-58` 收尾：搬家后深度 +1 ⇒ `parents[2]`（原=仓根）全站改 `parents[2]`。

⭐ 例外：`parents[1] / "audit"` 是**搬运同批特意写成深度 2** 的（mut/oneoff 的引导行）⇒ 不动。
⛔ 判据：改完全站 `compile()` ＋ 13 把尺子（新路径）＋ pytest 全套。
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
PAT = re.compile(r"(parents\[1\])(?! / \"audit\")")
n = 0
for p in sorted((ROOT / "tools").rglob("*.py")):
    t = p.read_text(encoding="utf-8", errors="replace")
    t2 = PAT.sub("parents[2]", t)
    if t2 != t:
        p.write_text(t2, encoding="utf-8", newline="")
        n += 1
        print(f"✅ {p.relative_to(ROOT)}")
print(f"共修 {n} 件")
