"""说明文字审计 · **只读盘点**（`TAIL-209` · 2026-10-01）—— 产出审计件要用的数字。

量三样：
  ① **说明块**（`class="tip"`）：件 / 行 / 字数（剥 `${…}` 与标签、折叠区不计）· 页内 vs **弹窗内**
  ② **口径说明块**（`CALIB`）15 页：各几**条**、条目正文合计多少字
  ③ 字数分布（分档计数）

⚠️ 只读（⛔ 不写任何业务文件）。判"是不是弹窗里的"用**启发式**：块前 600 字里出现 `modal({` ⇒ 判弹窗。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from tools.audit.shell_source import parts_text  # noqa: E402

TAG = re.compile(r"<[^>]+>")
JSX = re.compile(r"\$\{[\s\S]{0,600}?\}")
DET = re.compile(r"<details[\s\S]*?</details>")


def strip(s: str) -> str:
    return re.sub(r"\s+", "", TAG.sub("", DET.sub("", JSX.sub("…", s))))


def blocks() -> list[dict]:
    out = []
    for name, text in parts_text():
        for m in re.finditer(r'<div class="tip', text):
            seg, depth, i = text[m.start():m.start() + 4000], 0, 0
            while i < len(seg):
                op, cl = seg.find("<div", i), seg.find("</div>", i)
                if cl < 0:
                    break
                if 0 <= op < cl:
                    depth += 1
                    i = op + 4
                else:
                    depth -= 1
                    i = cl + 6
                    if depth == 0:
                        seg = seg[:i]
                        break
            txt = strip(seg)
            head = text[max(0, m.start() - 600):m.start()]
            out.append({"file": name, "line": text[:m.start()].count("\n") + 1,
                        "n": len(txt), "head": txt[:38],
                        "modal": ("modal({" in head and head.rfind("modal({") > head.rfind("}"))})
    return out


bs = blocks()
print(f"=== ① 说明块（`class=\"tip`）共 {len(bs)} 处 ===")
by = {}
for b in bs:
    by.setdefault(b["file"], [0, 0, 0])
    by[b["file"]][0] += 1
    by[b["file"]][1] += b["n"]
    by[b["file"]][2] += 1 if b["modal"] else 0
for f, (c, tot, mo) in sorted(by.items(), key=lambda kv: -kv[1][0]):
    print(f"   {c:3d} 处（弹窗 {mo:3d}）· 合计 {tot:5d} 字  {f}")

print("\n=== ② 口径说明块 `CALIB` 各几**条** ===")
for name, text in parts_text():
    for m in re.finditer(r"CALIB\(\{items:\[", text):
        seg = text[m.end():m.end() + 6000]
        cut = seg.find("]})}")
        seg = seg[:cut if cut > 0 else 3000]
        items = len(re.findall(r"\n\s+`", seg))
        print(f"   {items:2d} 条 · {len(strip(seg)):4d} 字  {name}:{text[:m.start()].count(chr(10)) + 1}")

print("\n=== ③ 字数分布（全站说明块）===")
for lo, hi in ((200, 9999), (150, 199), (120, 149), (80, 119), (0, 79)):
    k = [b for b in bs if lo <= b["n"] <= hi]
    print(f"   {lo:3d}–{hi if hi < 9999 else '∞'}: {len(k):3d} 处")

print("\n=== ④ 最长的 18 处（剥 JS 后）===")
for b in sorted(bs, key=lambda b: -b["n"])[:18]:
    tag = "弹窗" if b["modal"] else "页内"
    print(f"   {b['n']:4d} 字 [{tag}] {b['file']}:{b['line']}  {b['head']}")
