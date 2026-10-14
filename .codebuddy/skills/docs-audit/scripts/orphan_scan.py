#!/usr/bin/env python
"""孤儿扫描（**只读**）—— 哪份文档"没人指它"。

用法：
    python .codebuddy/skills/docs-audit/scripts/orphan_scan.py
    python .codebuddy/skills/docs-audit/scripts/orphan_scan.py --min 3   # 只列引用数 < 3 的

口径（⛔ 别改）：
  · 引用判法 = 另一份文件的正文里出现**这份文件的文件名**或**仓内相对路径**。
  · ⭐ 按 `README.md` 的四层**分开报** —— **留痕档与产物档没人引用是正常的**（`journal/` 只追加不回读、
    `归档-*`/`D*` 是终点件）；**只有 ①② 层（注入档 / 按需档 = 口径·台账·地图·实测结论）的孤儿才是病**。
  · ⛔ 只读；⛔ 不是尺子（不进收工闸门、不判红）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKIP_PARTS = {"node_modules", ".venv", ".git", "__pycache__", ".pytest_cache"}

#: ② 层（按需档）里"必须有人指它"的落点前缀；① 层单列
CORE_PREFIXES = ("README.md", "ops/", "docs/architecture.md", "docs/architecture/",
                 "docs/agents/", "docs/guides/", "docs/reference/", "docs/adr/", "docs/status.md", "docs/requirements.md", "docs/requirements/", "tools/README.md",
                 ".codebuddy/memory/MEMORY.md", ".codebuddy/memory/细则.md",
                 #: ⭐ 2026-10-01（`TAIL-204` 第 6 步）：「给用户看的一页」= 根 `README.md`（已在上一行）
                 #:   —— 原 `.codebuddy/plans/执行情况-主文档.md` 已"只留待办"并进 `README.md` §〇，⛔ 旧路径不存在。
                 "docs/status.md",
                 "docs/guides/work-records.md")
#: 留痕档：只追加、不回读 ⇒ ⛔ 它们"没人引用"不是病
HISTORY_PREFIXES = ("docs/archive/", ".codebuddy/memory/journal/", ".codebuddy/plans/archive/归档-",
                    ".codebuddy/plans/archive/", ".codebuddy/memory/")


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for cand in (here, *here.parents):
        if (cand / "tools" / "audit" / "doc_audit.py").exists() and (cand / ".codebuddy").is_dir():
            return cand
    raise SystemExit("找不到仓库根（期望含 tools/audit/doc_audit.py 与 .codebuddy/）")


def main() -> int:
    ap = argparse.ArgumentParser(description="孤儿扫描（只读）")
    ap.add_argument("--min", type=int, default=1, help="只列出引用数小于该值的（默认 1 = 只报 0 引用）")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                             # noqa: BLE001
        pass

    root = repo_root()
    files = {}
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")

    rows = []
    for rel, _ in files.items():
        name = rel.rsplit("/", 1)[-1]
        refs = [o for o, text in files.items() if o != rel and (name in text or rel in text)]
        rows.append((rel, refs))

    def is_core(rel: str) -> bool:
        return any(rel == p or rel.startswith(p) for p in CORE_PREFIXES)

    core_orphans = [(r, f) for r, f in rows if is_core(r) and len(f) < args.min]
    hist_orphans = [(r, f) for r, f in rows if r.startswith(HISTORY_PREFIXES) and len(f) < args.min]
    other_weak = [(r, f) for r, f in rows
                  if not is_core(r) and not r.startswith(HISTORY_PREFIXES)
                  and len(f) < max(args.min, 1) and not r.startswith(".codebuddy/backups/")]

    print(f"扫描 {len(rows)} 份 md（跳过 node_modules/.venv/.git）")
    print(f"\n=== ⭐ ①② 层孤儿（**这才是病**，要修）{len(core_orphans)} 份 ===")
    for rel, _ in core_orphans:
        print(f"  ❌ {rel}")
    if not core_orphans:
        print("  （无 —— 口径/台账/地图/实测结论都有出处 ✓）")
    print(f"\n=== 留痕档（⛔ 没人引用**正常**，别当病）{len(hist_orphans)} 份 ===")
    for rel, _ in hist_orphans[:8]:
        print(f"  ·  {rel}")
    if len(hist_orphans) > 8:
        print(f"  ·  … 另 {len(hist_orphans) - 8} 份")
    print(f"\n=== 其它区（产物/决策/设计等，弱信号）{len(other_weak)} 份 ===")
    for rel, _ in other_weak[:12]:
        print(f"  ·  {rel}")
    if len(other_weak) > 12:
        print(f"  ·  … 另 {len(other_weak) - 12} 份")
    print("\n" + "-" * 70)
    print(" ⚠️ 判读：**只看第一段**；后两段是给你「要不要升档 / 归档」的线索，⛔ 不是待修清单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
