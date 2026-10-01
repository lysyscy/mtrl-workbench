"""说明文字瘦身 · **定位靶**：把真机 ㉖ 报出的「默认展开的说明块」在源码里找出来（只读）。

㉖（`tools/probe/_shell_text.py`）量的是 `#view .tip` 且**不在 `<details>` 里**的那些块
（上限 200 字、≥120 字也打出来）⇒ 本件按它给的 13 个头去找源码行。
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PARTS = [ROOT / "backend" / "app" / "web" / "index.html"] + sorted(
    (ROOT / "backend" / "app" / "web" / "shell").glob("*.js"))

HEADS = [
    "这次同步报出的待人工里",
    "无效列处置口径",
    "看这两条就够",
    "这一块是「付款」侧",
    "默认看「当前核算月」",
    "列结构说明",
    "这张表按「项目一行」铺开",
    "大表中不得设「材料费」",
    "上次值带入",
    "自动项从哪来",
    "发票子表",
    "这页能看什么",
    "必须有「核算月」",
]

raw: dict[pathlib.Path, str] = {}
print("=== 每个靶在源码里的位置（⚠️ 字数按**渲染后**算，源串会含标签 ⇒ 这里只定位）===")
for h in HEADS:
    hits = []
    for f in PARTS:
        t = raw.setdefault(f, f.read_text(encoding="utf-8"))
        for i, ln in enumerate(t.splitlines(), 1):
            if h in ln:
                hits.append((f.name, i, ln.strip()[:96]))
    print(f"\n· 头＝「{h}」⇒ {len(hits)} 处")
    for name, i, s in hits:
        print(f"    {name}:{i}  {s}")

print("\n=== 全仓 `class=\"tip` 的分布（粗量）===")
for f in PARTS:
    t = raw.setdefault(f, f.read_text(encoding="utf-8"))
    n = len(re.findall(r'class="tip', t))
    if n:
        print(f"   {f.name}: {n} 处")
