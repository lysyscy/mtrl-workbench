#!/usr/bin/env python
"""数**还剩多少张裸 `<table>`** —— 全壳（**含 `shell/*.js` 各拆件**）＋ 原型，`TAIL-64` 踏勘用。

**为什么需要它**：`TAIL-64` 的进度一直靠**手工数**，而 2026-09-29 第一次写本件时**只看 `index.html`** ⇒
把 modal 那批（住在 `shell/actions.js` 等拆件里）**整批漏掉**，当场报出"全仓只剩 3 张"的错数。
⇒ ⭐ **教训：壳是模块化的，任何"全仓"量测都必须先问"件被拆到哪儿去了"**（`tests/shell_src.py` 的
`SHELL_PARTS` 就是权威拆件清单）。

用法：`… _tbl_scan.py`（默认两侧）· `… _tbl_scan.py shell` / `proto` / `pages`（只看页切片）
"""

from __future__ import annotations

import pathlib
import re
import sys

FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
PROTO = FACE / "demo" / "材料报表自动化工作台-交互原型.html"
WEB = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "web"
TBL_DEF = re.compile(r"^\s*const TBL\s*=")
SLICE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=\s*\(\)\s*=>\s*\{")
KEY = re.compile(r'data-sort-key="([^"]+)"')
RAW = re.compile(r"<table\b")
TBL = re.compile(r"\bTBL\(\{")


def parts() -> list[pathlib.Path]:
    return [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))


def classify(line: str, in_tbl_kernel: bool, in_block: bool) -> str:
    s = line.strip()
    if in_tbl_kernel:
        return "内核"
    if in_block or s.startswith("//") or s.startswith("*") or s.startswith("/*"):
        return "注释"
    if ("<table" in s and (".match(" in s or ".replace(" in s)) or "<table\\b" in s:
        return "正则"
    return "裸表"


def walk(path: pathlib.Path) -> list[tuple[int, str, str, str]]:
    """逐行分类：块注释状态机 ＋ `TBL` 内核区间 ＋ 正则行。"""
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    rows: list[tuple[int, str, str, str]] = []
    in_kernel = in_block = False
    for i, l in enumerate(lines, 1):
        if TBL_DEF.match(l):
            in_kernel = True
        if in_kernel and l.startswith("};"):
            in_kernel = False
        head = l.split(RAW.pattern)[0]
        if head.count("/*") > head.count("*/"):
            in_block = True
        if RAW.search(l) and "TBL(" not in l:
            k = KEY.search(l)
            rows.append((i, classify(l, in_kernel, in_block), k.group(1) if k else "", l.strip()[:74]))
        if in_block and l.rstrip().endswith("*/"):
            in_block = False
    return rows


def scan(path: pathlib.Path) -> int:
    rows = walk(path)
    bad = [r for r in rows if r[1] == "裸表"]
    others = [r for r in rows if r[1] != "裸表"]
    print(f"  {path.name:<14} 裸表 {len(bad):>2} 处"
          + (f" · 另有 {len(others)} 处在内核/注释/正则里（不算）" if others else ""))
    for i, kind, key, txt in rows:
        print(f"      {'⛔' if kind == '裸表' else '· '} L{i:<5} [{kind}]"
              + (f" key={key}" if key else "") + f"  {txt}")
    return len(bad)


def report(tag: str, ps: list[pathlib.Path]) -> None:
    print(f"\n===== {tag} =====")
    tot = sum(scan(p) for p in ps)
    print(f"  —— **裸表合计 {tot} 处**")


def pages(tag: str, p: pathlib.Path) -> None:
    """只看页切片（`V.<页>=()=>{` 起、到下一个 `V.` 前）—— 与 §四 各批口径一致。"""
    lines = p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    hits = [(i, SLICE.match(l).group(1)) for i, l in enumerate(lines) if SLICE.match(l)]
    print(f"\n===== {tag} · 页切片 =====")
    for k, (i, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        body = lines[i:end]
        raw = sum(1 for x in body if RAW.search(x) and "TBL(" not in x)
        t = sum(1 for x in body if TBL.search(x))
        if raw or t:
            print(f"  V.{name:<6} 行 {len(body):>4} · 裸表 {raw:>2} · TBL {t:>2}")


def main(argv: list[str]) -> int:
    which = argv[0] if argv else "both"
    if which in {"both", "shell"}:
        report("壳（含全部拆件）", parts())
    if which == "pages":
        pages("壳", WEB / "index.html")
        pages("原型", PROTO)
    if which in {"both", "proto"}:
        report("原型", [PROTO])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
