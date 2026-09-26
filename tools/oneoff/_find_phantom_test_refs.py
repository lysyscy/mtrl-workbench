"""找「**幽灵判据**」：代码 / 工具里的注释引用了**不存在**的 `test_*.py`（2026-09-26 立）。

⭐ 为什么值得单跑一次：`index.html` 里那条注释白纸黑字承诺「这条**有机器判据**：
   `backend/tests/test_proj_panel.py`」—— 而该文件**根本不存在**。
   ⚠️ **承诺一个不存在的检查，比不承诺更糟**：下一个人会放心把活交给一个不存在的东西
   （那正是用户今天问的"还有哪些是**靠自觉**的"——这是它更隐蔽的一种变体：**假装有检查**）。

⚠️ 为什么此前没有任何尺子看得见：`doc_audit` 的 `T1` 只管**文档里的 `ACC-*` 用例号**；
   代码注释里引用的**测试文件名**没人管（`T3` 管的是文档里的**路径**，也扫不到 `.js`/`.py` 的注释）。

⛔ 一次性（看清事实就够）；若值得常驻，再把它的核心搬进 `tests/` 当判据。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 引用形态：`tests/test_x.py` / `test_x.py` / 反引号里的裸名都算
REF = re.compile(r"[\w./\\-]*test_[\w]+\.py")
SCAN_DIRS = ("backend/app", "tools", "ops", "backend/tests")
SKIP_PARTS = (".venv", "__pycache__", "node_modules", ".git", "backups")
EXTS = (".py", ".js", ".html", ".ps1", ".md", ".txt")

existing = {p.name for p in (ROOT / "backend" / "tests").rglob("test_*.py")}
bad: list[tuple[str, int, str, str]] = []
scanned = 0

for d in SCAN_DIRS:
    base = ROOT / d
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        if any(s in p.parts for s in SKIP_PARTS):
            continue
        scanned += 1
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.split("\n"), 1):
            for m in REF.finditer(line):
                name = Path(m.group(0).replace("\\", "/")).name
                if name not in existing:
                    bad.append((str(p.relative_to(ROOT)), i, name, line.strip()[:88]))

print(f"扫描 {scanned} 个文件；`backend/tests/` 里现有 {len(existing)} 个测试件")
if not bad:
    print("OK 没有幽灵判据：所有被引用的 test_*.py 都真实存在")
for rel, ln, name, txt in sorted(set(bad)):
    print(f"PHANTOM {rel}:{ln}  引用不存在的 {name}")
    print(f"        {txt}")
sys.exit(1 if bad else 0)
