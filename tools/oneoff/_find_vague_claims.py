"""找「**空口承诺判据**」：写了"有判据 / 有断言 / 盯着 / 会红"之类，却**没给指向**（测试文件名 或 `ACC-*`）。

⭐ 背景（2026-09-26）：刚立了「引用的 `test_*.py` **必须真存在**」（`tests/test_wiring_guards.py`），
   但那只管**给了文件名**的。"只说有判据、不说是哪一个"这一形态**机器判不了**
   ⇒ ⛔ 别先立规矩：**先量**有多少、长什么样，再决定是立契约还是靠人。

⚠️ 只报"**承诺存在**"的措辞（`有判据` / `有断言` / `盯着` / `会红`…）；
   `判据不变` / `判据不删` 这类**不是承诺**，⛔ 不许算进来（否则天天误报，规矩就没人看了）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 「承诺存在」的措辞（⚠️ 宁可少报、不可错报 —— 这是"先量"不是"先判"）
PROMISE = re.compile(r"有(?:机器)?判据|有断言|有测试|有结构性断言|会被?红|当场红|必然红|必红|盯着|守着|守住|测试守")
#: 「指向」= 真能点的东西：测试文件名，或 `ACC-*` 用例号
POINTER = re.compile(r"test_[\w]+\.py|ACC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
SCAN_DIRS = ("backend/app", "backend/tests", "tools")
SKIP_PARTS = (".venv", "__pycache__", "node_modules", ".git", "backups")
EXTS = (".py", ".js", ".html")

hits: list[tuple[str, int, str]] = []
for d in SCAN_DIRS:
    for p in (ROOT / d).rglob("*"):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        if any(s in p.parts for s in SKIP_PARTS):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            if not PROMISE.search(line) or POINTER.search(line):
                continue
            hits.append((str(p.relative_to(ROOT)), i, line.strip()[:110]))

print(f"空口承诺判据：{len(hits)} 行（措辞真命中 ∧ 同一行没有任何指向）")
for rel, ln, txt in hits[:30]:
    print(f"  {rel}:{ln}\n      {txt}")

# ---------------- ② 代码 / 壳里引用的 `ACC-*` 必须真在册（这一半**能机器判**）----------------
# 真源 = 验收基线（与 `doc_audit` 的 `T1` 同一份）；⚠️ `T1` 只扫**文档** ⇒ 代码注释此前没人管。
sys.path.insert(0, str(ROOT / "tools" / "audit"))
import acc_report as ar                                                # noqa: E402

known = set(ar.load_json(ar.resolve_baseline(None)).get("cases") or {})
ACC_REF = re.compile(r"ACC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
miss: list[tuple[str, int, str, str]] = []
for d in SCAN_DIRS:
    for p in (ROOT / d).rglob("*"):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        if any(s in p.parts for s in SKIP_PARTS):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            for m in ACC_REF.finditer(line):
                cid = m.group(0).rstrip("-")
                if cid not in known:
                    miss.append((str(p.relative_to(ROOT)), i, cid, line.strip()[:80]))

print(f"\n代码/壳里引用 `ACC-*` 却不在册：{len(miss)} 处（真源 = 验收基线 {len(known)} 条用例）")
for rel, ln, cid, txt in miss[:30]:
    print(f"  {rel}:{ln}  {cid}\n      {txt}")
sys.exit(0)
