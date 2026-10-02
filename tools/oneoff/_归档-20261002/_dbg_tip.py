"""诊断：判据到底读到了哪些件、`index.html` 里有多少 tip 块、`_tip_blocks()` 数的对不对。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from tools.audit.shell_source import INDEX_HTML, parts_text  # noqa: E402

print("INDEX_HTML =", INDEX_HTML)
ps = parts_text()
print("parts =", [n for n, _ in ps])
for name, txt in ps:
    n = txt.count('class="tip')
    print(f"  {name}: class=\"tip 共 {n} 处 · {len(txt)} 字节")

sys.path.insert(0, str(ROOT / "backend" / "tests"))
from test_ux_text import TIP_LIMIT, _tip_blocks  # noqa: E402

rows = sorted(_tip_blocks(), key=lambda r: -r[2])
print(f"\n_tip_blocks() 共 {len(rows)} 块 · 上限 {TIP_LIMIT}")
for name, ln, c, head in rows[:6]:
    print(f"   {c:4d} 字  {name}:{ln}  {head}")
m04 = [r for r in rows if "欠款 = 其他支出金额" in r[3]]
print("m04 那块 =", m04)
