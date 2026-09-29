"""`P2-a` 量测（**只读**）：把 `index.html` 内联 JS 切成"段"，给出**非切片段清单**。

## 段的口径（⛔ 刻意与 `tools/audit/ui_parity.py` 同一套，别新立一套）

`ui_parity` 的 `END_RE` = `^(V\\.<名>\\s*=|BIND\\.|const |function |let |var )`；
`U1` 的切片 = 行首 `V.<名> =` 起点 ＋ 直到下一个命中 `END_RE` 的行为止。
⇒ 本件用**同一个** `BOUNDARY` 切段，所以：

- **段边界与 `U1` / `U5` 看到的完全一致** ⇒ "某段搬走会不会引 `U1` 漂移"可以据此**预判**；
- ⚠️ 一段的**起点行本身**（`function foo(){` 那行）不是上一段的尾巴，而**它前面的注释块**算**上一段的尾巴**
  （`slices()` 把它们并进上一个 `V.` 切片）⇒ 搬走注释块**会**改上一段的内容（若上一段是 `V.*` ⇒ `U1` 漂移）。

## 跑法

    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_measure.py          # 人读
    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_measure.py --csv    # 机读
    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_measure.py --all    # 连 V.* 切片一起列
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "backend" / "app" / "web" / "index.html"

# ⛔ 与 `ui_parity.END_RE` 同一套（复制是**有意的**：那边一改，本件要跟着改；已在文件头写明）
BOUNDARY = r"^(V\.[A-Za-z0-9_]+\s*=|BIND\.|const |function |let |var )"
NAME = r"^(?:V\.([A-Za-z0-9_]+)\s*=|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|function\s+([A-Za-z_$][\w$]*)\s*\()"

import re  # noqa: E402

B_RE = re.compile(BOUNDARY)
N_RE = re.compile(NAME)


def inline_script_span(lines: list[str]) -> tuple[int, int]:
    """内联 `<script>` 的**脚本体**行号区间（0 基左闭右开）。"""
    starts = [i for i, l in enumerate(lines) if l.strip() == "<script>"]
    ends = [i for i, l in enumerate(lines) if l.strip() == "</script>"]
    if not starts or not ends:
        raise SystemExit("⛔ 找不到内联 <script> 块 —— index.html 结构变了？")
    return starts[0] + 1, ends[-1]


def segments(lines: list[str], lo: int, hi: int) -> list[tuple[int, int, str]]:
    """返回 `(起始行号 1 基, 行数, 名字)`；段尾切在下一个 `BOUNDARY` 行。"""
    starts = [i for i in range(lo, hi) if B_RE.match(lines[i])]
    out: list[tuple[int, int, str]] = []
    for k, i in enumerate(starts):
        j = starts[k + 1] if k + 1 < len(starts) else hi
        m = N_RE.match(lines[i])
        name = (m.group(1) or m.group(2) or m.group(3)) if m else lines[i][:40]
        out.append((i + 1, j - i, name))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-a 段量测（只读）")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--all", action="store_true", help="连 V.* 切片一起列")
    ap.add_argument("--md", default=None, help="把全清单写进这个文件（⛔ 只写量测产物）")
    a = ap.parse_args()

    lines = INDEX.read_text(encoding="utf-8").splitlines()
    lo, hi = inline_script_span(lines)
    segs = segments(lines, lo, hi)
    v = [s for s in segs if lines[s[0] - 1].startswith("V.")]
    nv = [s for s in segs if not lines[s[0] - 1].startswith("V.")]
    js_lines = hi - lo

    def head() -> str:
        return (f"index.html 全文件 {len(lines)} 行 · 内联 <script> 体 {lo + 1}–{hi} 行（{js_lines} 行）\n"
                f"段 {len(segs)} 个 = V.* 切片 {len(v)} 个 / {sum(s[1] for s in v)} 行 ＋ "
                f"非切片 {len(nv)} 个 / {sum(s[1] for s in nv)} 行")

    if a.md:
        out = [head(), "", f"── V.* 切片（{len(v)} 个）──"]
        out += [f"  L{st:>4} ({n:>4} 行)  V.{nm}" for st, n, nm in v]
        out += ["", f"── 非切片段（{len(nv)} 个 · 按出现顺序）──"]
        out += [f"  {i:>3}. L{st:>4} ({n:>4} 行)  {nm}" for i, (st, n, nm) in enumerate(nv, 1)]
        Path(a.md).write_text("\n".join(out) + "\n", encoding="utf-8")
        print(head())
        print(f"⇒ 已写入 {a.md}")
        return 0

    print(head())
    print()
    if a.csv:
        print("kind,start,lines,name")
        for s in segs:
            kind = "V" if lines[s[0] - 1].startswith("V.") else "nonV"
            print(f"{kind},{s[0]},{s[1]},{s[2]}")
        return 0

    print("── 非切片段（按出现顺序）──")
    for i, (st, n, nm) in enumerate(nv, 1):
        print(f"  {i:>3}. L{st:>4}({n:>3} 行)  {nm}")
    if a.all:
        print("\n── V.* 切片 ──")
        for st, n, nm in v:
            print(f"  L{st:>4}({n:>3} 行)  V.{nm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
