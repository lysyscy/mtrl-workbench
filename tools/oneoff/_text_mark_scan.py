"""只读盘点：壳里**说明文字**（`class="tip` 块内）残留的 `**` —— 那是"加粗"标记，⛔ 不该原样上屏。

⚠️ 为什么要单列：`**` 不许上屏那条判据（真机 ㉙）**只扫 `#view`** ⇒ **弹窗里的 `**` 没人守**
（与"弹窗说明块长度"是同一类缺口）。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from tools.audit.shell_source import parts_text  # noqa: E402

n = 0
for name, text in parts_text():
    for m in re.finditer(r'<div class="tip', text):
        seg, depth, i = text[m.start():m.start() + 4000], 0, 0
        while i < len(seg):
            op, cl = seg.find("<div", i), seg.find("</div>", i)
            if cl < 0:
                break
            if 0 <= op < cl:
                depth += 1
                i = op + 4
            else:
                depth -= 1
                i = cl + 6
                if depth == 0:
                    seg = seg[:i]
                    break
        if "**" not in seg:
            continue
        n += 1
        hits = [x.strip()[:60] for x in seg.splitlines() if "**" in x]
        print(f"\n── {name}:{text[:m.start()].count(chr(10)) + 1}（{len(hits)} 行含 `**`）")
        for h in hits[:3]:
            print(f"   {h}")

print(f"\n=== 共 {n} 个说明块含 `**` ===")
