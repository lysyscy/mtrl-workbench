#!/usr/bin/env python
"""列出台账 `§一`（**仍待办**）与 `§三`（待裁）里还剩什么 —— 只读（2026-09-29）。

**为什么要有它**：`§一` 的行都很长（每行带四问 / 落点 / 判据），直接 `grep` 会把整行糊一屏 ⇒
这里只取判断要用的几格；已销号从姊妹件读取，不再找主计划旧 §四。
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/status.md"
CLOSED = ROOT / "docs/archive/tickets/index.md"


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _brief(s: str, n: int = 78) -> str:
    s = re.sub(r"\*\*|`", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("…" if len(s) > n else "")


def read_tables(plan=PLAN, closed=CLOSED):
    text = plan.read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").split("\n")

    def block(header: str, source=lines) -> list[list[str]]:
        h = [i for i, ln in enumerate(source) if ln.strip() == header]
        assert len(h) == 1, f"表头命中 {len(h)} 行：{header}"
        out: list[list[str]] = []
        for ln in source[h[0] + 1:]:
            if ln.startswith("## ") or ln.startswith("### "):
                break
            if not ln.startswith('|'):
                continue
            cells = _cells(ln)
            if not cells[0] or cells[0]=='#' or set(cells[0]) <= {'-',':'}:
                continue
            out.append(cells)
        return out

    a = block("| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |")
    c = block("| # | 事项 | 现状 | 你只需说 | 阶段 / 时机 | 状态 |")
    d = block("| # | 事项 | 销号依据 | 日期 |", closed.read_text(encoding="utf-8").splitlines())
    return a, c, d


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        plan = pathlib.Path(temp)/'plan.md'; closed = pathlib.Path(temp)/'closed.md'
        plan.write_text('| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |\n| TAIL-2 | active | src | risk | dest | 随时 | 在办 |\n\n| # | 事项 | 现状 | 你只需说 | 阶段 / 时机 | 状态 |\n\n', encoding='utf-8')
        closed.write_text('| # | 事项 | 销号依据 | 日期 |\n| TAIL-1 | done | evidence | date |\n\n| TAIL-3 | done | evidence | date |\n', encoding='utf-8')
        a,c,d = read_tables(plan,closed)
        assert len(a)==1 and not c and len(d)==2 and d[0][0]=='TAIL-1', '两份台账必须分别读取，表内空行不截断'
        closed.unlink()
        try:
            read_tables(plan,closed)
        except OSError:
            pass
        else:
            raise AssertionError('缺少历史输入不能空扫放行')
    print('自测 两份票索引读取与缺失输入拒绝通过')
    return 0


def main() -> int:
    if '--selftest' in sys.argv: return selftest()
    a,c,d = read_tables()

    print(f"§一 · 仍待办（A 类）：{len(a)} 条")
    for r in a:
        print(f"  · {r[0]:<12} [{r[6]}] {_brief(r[1])}")
        print(f"     时机：{_brief(r[5], 60)}")
    print(f"\n§三 · 待裁（C 类）：{len(c)} 条")
    for r in c:
        print(f"  · {r[0]:<12} [{r[5]}] {_brief(r[1])}")
    print(f"\n姊妹件 · 已销号：{len(d)} 条（只报个数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
