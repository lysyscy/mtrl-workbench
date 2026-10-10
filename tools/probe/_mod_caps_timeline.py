#!/usr/bin/env python
"""查「`MOD-*.md` 能力编号断档」的**成因**（`TAIL-168` · 2026-09-29）。

**为什么有它**：`tools/probe/_audit_face.py` 的尺子 `A` 报「能力编号 `1..N` 不连续」4 处，
但**没人知道那些号是怎么没的**（计划/台账里没有"退号"记录）⇒ ⛔ 不能瞎补号（补错 = 造一条假能力）。
本脚本用**交付面里历次快照**（`.workbuddy/_backup-*` ＋ 本仓 `.codebuddy/backups/交付面-*`）做**时间线**：
逐快照解析每个 `MOD-*.md` 的能力表编号 ⇒ 打印「哪一轮少了哪个号」⇒ 成因自然浮出来。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\probe\\_mod_caps_timeline.py [MOD-03 MOD-04 …]`
"""

from __future__ import annotations

import pathlib
import re
import sys

#: ⚠️ 2026-10-10：产品资料已迁入仓内 `delivery/`，**但历次快照仍在旧根的 `.workbuddy/` 里**
#:   （旧根 `D:\dev\PRD编写夹 - Workbuddy专用` 只剩这一处本机治理数据）⇒ 指针跟着它走。
FACE = pathlib.Path(r"D:\dev\PRD编写夹 - Workbuddy专用")
REPO = pathlib.Path(__file__).resolve().parents[2]
#: ⚠️ 旧根那份**仍叫 `.workbuddy`**（⛔ 别跟着仓内一起改名 —— 改了 ⇒ `not root.exists()` 静默扫空集）
ROOTS = (FACE / ".workbuddy", REPO / ".codebuddy" / "backups")

HEAD_RE = re.compile(r"^\|\s*#\s*\|\s*能力")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|(.*)$")


def snapshots() -> list[tuple[str, pathlib.Path]]:
    """(标签, MOD 目录) —— 标签按名字排序即可当时间线（备份目录名都带日期时分）。"""
    out: list[tuple[str, pathlib.Path]] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for d in sorted(root.glob("*")):
            if not d.is_dir() or not d.name.startswith(("_backup", "交付面-", "交付面_")):
                continue
            for cand in (d / "PRD" / "02-功能规格", d / "02-功能规格", d / "after-改动后"):
                if cand.is_dir():
                    out.append((f"{root.parent.name}/{d.name}", cand))
    return out


def caps(path: pathlib.Path) -> list[tuple[int, str]]:
    """→ [(编号, 能力文本前 26 字)]"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        if HEAD_RE.match(ln):
            for ln2 in lines[i + 1:]:
                if not ln2.startswith("|"):
                    break
                m = ROW_RE.match(ln2)          # ⚠️ 表头的 `|---|` 分隔行不算行，别拿它当结束
                if m:
                    rows.append((int(m.group(1)), m.group(2).strip()[:26]))
            break
    return rows


def main(argv: list[str]) -> int:
    want = argv or ["MOD-03", "MOD-04", "MOD-06", "MOD-10", "MOD-14"]
    snaps = snapshots()
    print(f"快照目录 {len(snaps)} 个：{', '.join(n for n, _ in snaps)}\n")
    for mod in want:
        print(f"══ {mod} ══")
        prev: list[int] | None = None
        for label, d in snaps:
            f = d / f"{mod}.md"
            if not f.exists():
                continue
            num = [n for n, _ in caps(f)]
            if not num:
                continue
            miss = sorted(set(range(1, max(num) + 1)) - set(num))
            flag = ""
            if prev is not None and prev != num:
                gone = sorted(set(prev) - set(num))
                add = sorted(set(num) - set(prev))
                flag = f"   ⟵ 变化：－{gone or '∅'} ＋{add or '∅'}"
            print(f"  {label:<42} {num}{'  缺 ' + str(miss) if miss else ''}{flag}")
            prev = num
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
