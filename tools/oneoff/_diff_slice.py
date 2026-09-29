#!/usr/bin/env python
"""看**某一页切片**在「壳 ⇄ 原型」之间到底差哪几行（`A4` 用 · 一次性）。

**为什么需要它**：`ui_parity` 的 `U1` 是**逐行对位**比较 —— 只要壳的切片里**多/少一行**，
它后面**所有行**都会报"未登记漂移"（本批实测：加了两行注释 ⇒ 一下子 101 条 ＋ 42 条幽灵）。
它的报告只列**原型那侧**的行，所以"到底是我改的那行，还是后面被顶偏了"要另看一眼。

用法：`… _diff_slice.py m06`
"""

from __future__ import annotations

import difflib
import pathlib
import re
import sys

FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
PROTO = FACE / "demo" / "材料报表自动化工作台-交互原型.html"
SHELL = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web" / "index.html"
SLICE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=")


def slabs(p: pathlib.Path) -> dict[str, list[str]]:
    lines = p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    hits = [(i, SLICE.match(l).group(1)) for i, l in enumerate(lines) if SLICE.match(l)]
    out: dict[str, list[str]] = {}
    for k, (i, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        out.setdefault(name, lines[i:end])
    return out


def main(argv: list[str]) -> int:
    page = argv[0] if argv else "m06"
    a = slabs(PROTO).get(page)
    b = slabs(SHELL).get(page)
    if a is None or b is None:
        print(f"⛔ 切片刻不到：原型 {a is not None} · 壳 {b is not None}")
        return 1
    print(f"`V.{page}`：原型 {len(a)} 行 ⇄ 壳 {len(b)} 行  ⇒ 差 {len(b) - len(a)} 行")
    n = 0
    for line in difflib.unified_diff([x.rstrip() for x in a], [x.rstrip() for x in b],
                                     "原型", "壳", lineterm="", n=1):
        print("  " + line[:170])
        n += 1
        if n > 60:
            print("  …（截断）")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
