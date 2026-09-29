#!/usr/bin/env python
"""列出台账 `§一`（**仍待办**）与 `§三`（待裁）里还剩什么 —— 只读（2026-09-29）。

**为什么要有它**：`§一` 的行都很长（每行带四问 / 落点 / 判据），直接 `grep` 会把整行糊一屏 ⇒
这里只取**判断要用的那几格**：编号 · 状态 · 事项的头一句 · 建议时机；`§四`（已销号）只数个数。
"""

from __future__ import annotations

import pathlib
import re
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _brief(s: str, n: int = 78) -> str:
    s = re.sub(r"\*\*|`", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("…" if len(s) > n else "")


def main() -> int:
    text = PLAN.read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").split("\n")

    def block(header: str) -> list[list[str]]:
        h = [i for i, ln in enumerate(lines) if ln.strip() == header]
        assert len(h) == 1, f"表头命中 {len(h)} 行：{header}"
        out: list[list[str]] = []
        for ln in lines[h[0] + 1:]:
            if not ln.startswith("|"):
                break
            if set(ln) <= set("|-: "):
                continue
            out.append(_cells(ln))
        return out

    a = block("| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |")
    c = block("| # | 事项 | 现状 | 你只需说 | 阶段 / 时机 | 状态 |")
    d = block("| # | 事项 | 销号依据 | 日期 |")

    print(f"§一 · 仍待办（A 类）：{len(a)} 条")
    for r in a:
        print(f"  · {r[0]:<12} [{r[6]}] {_brief(r[1])}")
        print(f"     时机：{_brief(r[5], 60)}")
    print(f"\n§三 · 待裁（C 类）：{len(c)} 条")
    for r in c:
        print(f"  · {r[0]:<12} [{r[5]}] {_brief(r[1])}")
    print(f"\n§四 · 已销号：{len(d)} 条（只报个数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
