#!/usr/bin/env python
"""`TAIL-59` 量测（**只读** · 2026-09-29）：规则/阈值现在散在哪、有多少处是「同一件事的第二份」。

⭐⭐ **为什么先量测**：`TAIL-59` 台账自己写着「⚠️ **只在"规则数继续涨"时才值得做**（⛔ **别为形式搬**）」
⇒ 先取证"**副本债**有多少、哪些**没有机器眼**"，再决定要不要上 `rules.toml` 那种形式。

三个面：
  A. 各「规则面」的条数与体量（注入档 / 阈值表 / 尺子常量 / 前端守则 / 运维索引）；
  B. `docs/reference/thresholds.md` 每行的**复述清单** —— 该行的数字在哪些**复述面**里又出现了一次
     （⭐ 复述面 = 每会话**必读/注入**的那些档 ⇒ 它漂了最贵：读它的人最多、而 `T4④` 只校"表 vs 真源"、**不校别处复述**）；
  C. 结论行：有几处复述**没有机器眼**。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail59_measure.py`
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / "docs/reference/thresholds.md"

#: 「复述面」= 每会话**注入 / 必读**的档（⭐ 定义见根 `README.md` §二 的四层：①②层）
FACES: tuple[str, ...] = (
    "docs/agents/project-rules.md",
    "docs/guides/implementation-constraints.md",
    "README.md",
    "docs/status.md",
    "docs/guides/operations.md",
)
#: 「真源面」——数字出现**在这里是对的**（那是它的主人）
SOURCES: tuple[str, ...] = (
    "docs/reference/thresholds.md",
    "tools/audit/audit_meta.py",
    "tools/audit/audit_common.py",
    "tools/audit/audit_work.py",
    "tools/audit/shell_verify.py",
    "tools/audit/sticky_probe.py",
    "backend/tests/test_theme.py",
    "backend/tests/test_router_refs.py",
    "backend/tests/test_wiring_guards.py",
    "backend/app/core/session.py",
)
_PLAN = "docs/status.md"

#: 阈值表第一格里的数字（`| **400** |` / `| **±2 行** |` / `| **200px / 30 行** |`）
_CELL_RE = re.compile(r"^\|\s*\*{0,2}([^|]+?)\*{0,2}\s*\|")
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([A-Za-z%份天小时件套行类个]*)")


def rule_rows() -> list[tuple[int, str, list[str]]]:
    """阈值表的每个数据行 → (行号, 数字单元格, [出现的数字])。"""
    out: list[tuple[int, str, list[str]]] = []
    for i, line in enumerate(TABLE.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        if set(line) <= set("|-: "):
            continue
        m = _CELL_RE.match(line)
        if not m:
            continue
        cell = m.group(1).strip()
        if cell in ("数字",):
            continue
        nums = [n for n, _u in _NUM_RE.findall(cell)]
        if nums:
            out.append((i, cell, nums))
    return out


def occurrences(num: str) -> list[tuple[str, int, str]]:
    """`num` 在各「复述面」里的出现（避开真源面）。"""
    hits: list[tuple[str, int, str]] = []
    pat = re.compile(r"(?<![\d.])" + re.escape(num) + r"(?![\d.])")
    for rel in FACES + (_PLAN,):
        f = ROOT / rel
        if not f.exists():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pat.search(line):
                hits.append((rel, i, line.strip()[:150]))
    return hits


def face_inventory() -> list[tuple[str, int, int]]:
    """各面：行数 / `- ` 条目数（`MEMORY.md §八` 那种"纪律条目"的规模代理指标）。"""
    out = []
    for rel in FACES:
        f = ROOT / rel
        if not f.exists():
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        out.append((rel, len(lines), sum(1 for x in lines if x.startswith("- "))))
    return out


def main() -> int:
    rows = rule_rows()
    print("=" * 92)
    print(f" TAIL-59 量测（只读）· 阈值表 {len(rows)} 个数据行 · 复述面 {len(FACES)} 个 ＋ 计划主文档")
    print("=" * 92)

    print("\n【面 A】各「规则面」体量（行数 / `- ` 条目数）")
    for rel, n, bullets in face_inventory():
        print(f"  {n:>5} 行 / {bullets:>3} 条目   {rel}")
    print(f"  {len(rows):>5} 行 /   数据行   docs/reference/thresholds.md（⚠️ 只数表格数据行）")

    print("\n【面 B】阈值表每个数字在「复述面」里的出现（⭐ 每次出现 = 一个**候选副本**）")
    dup_rows = 0
    for lineno, cell, nums in rows:
        found: list[tuple[str, int, str]] = []
        for n in dict.fromkeys(nums):
            found += occurrences(n)
        if not found:
            continue
        dup_rows += 1
        print(f"\n  ◆ 阈值表:{lineno}  「{cell}」  （数字 {', '.join(dict.fromkeys(nums))}）")
        for rel, i, text in found[:12]:
            print(f"      {rel}:{i}  {text}")
        if len(found) > 12:
            print(f"      … 另有 {len(found) - 12} 处")

    print("\n【面 C】结论")
    print(f"  · 阈值表 {len(rows)} 个数据行里，**{dup_rows} 行**的数字在复述面里出现过 ⇒ 候选副本 {dup_rows} 处")
    print("  · ⚠️ 机器眼现状：`T4④` 只校「阈值表 vs **它自称的真源**」，**不校「别处的复述」** ⇒")
    print("    注入档（`MEMORY.md`）里那句「`T13`（行数预算 1700）」就是这样漂掉的：真源已 1800，**没有任何尺子看得见**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
