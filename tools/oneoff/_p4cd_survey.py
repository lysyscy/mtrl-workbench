#!/usr/bin/env python
"""`TAIL-64` **`P4-c`（口径说明）/ `P4-d`（项目选择）踏勘量测**（2026-09-30 · 只读 · ⛔ 不改任何文件）。

**为什么要它**：施工图 §8.3 写着「`P4-c`/`P4-d` ⛔ **没定义不许开工**」——
而 §四 原来那两个数（口径说明 `11x` · 项目选择 `10x`）**量不出来**（同"`fbar` 115 处"那次教训）。
⇒ 本件把两者**按形态分类**数清楚，好让"哪些算"这件事**有数据可裁**。

**它量什么**：
 1. `class="tip`（139 处）按**形态**分：折叠块 `<details class="tip">` / 行内条 `<div class="tip…">` / 语义色（`ok`/`wn`/`dg`）；
 2. ⭐ **页首「口径说明 · N 条」那块的 N 是手写的** —— 逐块_比对「声明的 N」与「实际 `<li>` 数」，
    不比不知道：**手抄的数字会不会已经漂了**（守则 §2.6「能算出来的别让人自己数」＋ §4.2「状态必须真实」）；
 3. `pjwrap` / `projPanel(` 的处数与分布，以及「项目选择按钮」那串重复标记的**形态方差**
    （`min-width` 有几种 · `▼` 与 `gap` 是否逐字同款）—— 守则 §4.4「相似元素不制造歧义」/ §5.12「只走一个出口」。

用法：`python tools/oneoff/_p4cd_survey.py`
"""

from __future__ import annotations

import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PARTS = [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))

TIP = re.compile(r'class="tip([^"]*)"')
DETAILS_TIP = re.compile(r'<details class="tip"')
SUMMARY = re.compile(r"<summary>([^<]{0,40})")
LI = re.compile(r"<li>")
PJWRAP = re.compile(r'class="fi pjwrap"')
PROJPANEL = re.compile(r"projPanel\(")
MINW = re.compile(r'data-act="(\w*[Pp]j\w*Toggle)"[^>]*style="([^"]*)"')


def text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def main() -> int:
    joined = {p.name: text(p) for p in PARTS}
    all_txt = "\n".join(joined.values())

    print("=" * 78)
    print(" `P4-c` · 口径说明 —— `class=\"tip` 按形态分（壳全部件）")
    print("=" * 78)
    kinds: Counter = Counter()
    for m in TIP.finditer(all_txt):
        kinds[m.group(1).strip() or "（无后缀）"] += 1
    for k, v in kinds.most_common():
        print(f"   {v:>4}  tip [{k}]")
    print(f"   —— 合计 {sum(kinds.values())} 处")
    print(f"   其中**折叠块** `<details class=\"tip\">` = {len(DETAILS_TIP.findall(all_txt))} 处"
          f"（`<summary>` 以「口径说明」起头的见下）")

    print("\n" + "=" * 78)
    print(" ⭐ 页首「口径说明 · N 条」：**声明的 N** ⇄ **实际 `<li>` 数**（手抄数字会不会漂）")
    print("=" * 78)

    def where(idx: int) -> str:
        """`idx` 落在**哪一页**（最近的前一个 `V.<页>=`）—— ⚠️ 别只报件名（那样找不着）。"""
        cur, head = "（切片外）", 0
        for m in re.finditer(r"(?m)^V\.([A-Za-z0-9_]+)\s*=", all_txt[:idx]):
            cur, head = m.group(1), m.start()
        return f"{cur} 第 {all_txt.count(chr(10), head, idx) + 1} 行"

    bad = 0
    n_blocks = 0
    for m in re.finditer(r"<details class=\"tip\"><summary>口径说明 · (\d+) 条", all_txt):
        n_blocks += 1
        seg = all_txt[m.start(): m.start() + 4000]
        end = seg.find("</details>")
        seg = seg[:end if end > 0 else len(seg)]
        n_decl, n_real = int(m.group(1)), len(LI.findall(seg))
        flag = "✅" if n_decl == n_real else "⛔ **已漂**"
        if n_decl != n_real:
            bad += 1
        print(f"   {flag}  声明 {n_decl} 条 / 实际 {n_real} 个 <li>   （{where(m.start())}）")
    print(f"   ⇒ 共 {n_blocks} 块，**已漂 {bad} 块**")

    print("\n" + "=" * 78)
    print(" `P4-d` · 项目选择 —— `pjwrap` / `projPanel(` 分布")
    print("=" * 78)
    for k, v in joined.items():
        w, p = len(PJWRAP.findall(v)), len(PROJPANEL.findall(v))
        if w or p:
            print(f"   {k:<16} pjwrap={w:>2} · projPanel(={p:>2}")
    print(f"   —— 合计 pjwrap **{len(PJWRAP.findall(all_txt))}** 处 · projPanel( **{len(PROJPANEL.findall(all_txt))}** 处")
    print("\n   「项目选择按钮」那串重复标记的形态方差（`min-width` 有几种）：")
    widths = Counter(m.group(2).split(";")[0] for m in MINW.finditer(all_txt))
    for k, v in widths.most_common():
        print(f"     {v:>3}  {k}")
    tail = Counter(m.group(2) for m in MINW.finditer(all_txt))
    print(f"   ⇒ **不同的 `style` 串** 共 {len(tail)} 种（⛔ 不是 1 种 = 同一个选择长出了 {len(tail)} 个形态）")

    print("\n===== 读法（给「哪些算」这件事定裁用）=====")
    print("  · `P4-c` 可定义成三档：① 只做**页首那个折叠「口径说明 · N 条」块**（**先把 N 变成算出来的**）；")
    print("    ② 所有折叠块 `<details class=\"tip\">`；③ 全部 `class=\"tip\"`（139 处，含行内提示条）。")
    print("  · `P4-d` 可定义成两档：① 只做 **`pjwrap` 那一层外壳**（控件留在原地，同 `FBAR` 的做法）：")
    print("    ② 连**项目选择按钮**一起收（那串 `min-width`/`▼`/`gap` 现在是逐处手写）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
