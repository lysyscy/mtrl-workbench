"""说明文字瘦身 · **批 2 靶**：把所有 `class="tip"` 块的**估算字数**排出来（只读）。

⚠️ 真机 ㉖ 只覆盖 `#view .tip`（页内），**弹窗/别处不在它视野里** ⇒ 批 2 用它来定位。
字数 = 剥标签后的非空白字符数（**估算**，用于排序；精确值以真机/人工复核为准）。
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = [ROOT / "backend" / "app" / "web" / "index.html"] + sorted(
    (ROOT / "backend" / "app" / "web" / "shell").glob("*.js"))

TAG = re.compile(r"<[^>]+>")
#: ⭐ `\$\{…\}` = 模板里的 JS 表达式 ⇒ **不是给用户看的文字** ⇒ 剥掉再数（否则 `${a.map(...)}` 会被当成说明）
JSX = re.compile(r"\$\{[^}]*\}|\$\{[\s\S]{0,400}?\}(?=\s*</|\s*`)", re.S)


def tips(strip_js: bool = True) -> list[tuple[int, str, int, str]]:
    out: list[tuple[int, str, int, str]] = []
    for f in FILES:
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r'class="tip', t):
            start = m.start()
            seg = t[start:start + 1400]
            end = seg.find("</div>")
            seg = seg[:end if end > 0 else 500]
            if strip_js:
                seg = JSX.sub("…", seg)
            txt = re.sub(r"\s+", "", TAG.sub("", seg))
            out.append((len(txt), f.name, t[:start].count("\n") + 1, txt[:44]))
    return out


rows = sorted(tips(), reverse=True)
print(f"=== 所有 `class=\"tip` 块（**剥掉 ${{…}} 后的估算字数**）共 {len(rows)} 处 · 列 ≥80 字 ===")
for n, name, line, head in rows:
    if n < 80:
        break
    print(f"  {n:4d} 字  {name}:{line}  {head}")

print("\n=== 分布（剥 JS 后）===")
for thr in (200, 160, 120, 80):
    print(f"  ≥{thr} 字：{sum(1 for r in rows if r[0] >= thr)} 处")

