#!/usr/bin/env python
"""`P4` 踏勘量测（筛选栏 `fbar` ＋ 口径说明 ＋ 项目选择）—— 2026-09-30 · `TAIL-64`。

**为什么要它**：施工图 §四 把 `P4` 写成「**筛选栏 `fbar` 配置化（115 处）** ＋ 口径说明 `11x` ＋ 项目选择 `10x`」，
但那三个数字**量不出来**（现测 `class="fbar` 只有 36 处；且 `115` 不知当初数的是什么）
⇒ ⭐ 按本仓规矩：**先定义量法，再定批**（同 09-29「全仓只剩 3 张裸表」那次教训）。

**它量什么**（只读，⛔ 不改任何文件）：
 1. `class="fbar`  —— **筛选栏的调用点**（＝真正要收进统一出口的那些"处"），按件分开数；
 2. 每个调用点**后面 6 行**里的子件类型（`label`/`select`/`input`/`button`/`data-act`）—— 看形态方差；
 3. `class="tip`（口径说明的候选）与 `pjwrap`/`projPanel`（项目选择的候选）—— 给另两个数字一个**定义**。

用法：`python tools/oneoff/_p4_survey.py`
"""

from __future__ import annotations

import pathlib
import re
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

FBAR = re.compile(r'class="fbar')
TIP = re.compile(r'class="tip')
PJ = re.compile(r"pjwrap|projPanel")
CHILD = re.compile(r"<(label|select|input|button|datalist)\b|data-act=")


def lines(p: pathlib.Path) -> list[str]:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def survey(name: str, path: pathlib.Path) -> tuple[int, int, int, Counter]:
    ls = lines(path)
    fbar = tip = pj = 0
    kids: Counter = Counter()
    for i, l in enumerate(ls):
        if FBAR.search(l):
            fbar += 1
            for k in CHILD.findall("\n".join(ls[i + 1: i + 7])):
                kids[k or "data-act"] += 1
        tip += len(TIP.findall(l))
        pj += len(PJ.findall(l))
    print(f"  {name:<16} fbar={fbar:>3} · tip={tip:>3} · pjwrap/projPanel={pj:>3}")
    return fbar, tip, pj, kids


def main() -> int:
    print("===== 壳（index.html ＋ shell/*.js）=====")
    tf = tt = tp = 0
    kids: Counter = Counter()
    parts = [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))
    for p in parts:
        f, t, j, k = survey(p.name, p)
        tf += f
        tt += t
        tp += j
        kids += k
    print(f"  —— 壳合计：**fbar {tf} 处** · tip {tt} · pjwrap/projPanel {tp}")
    print("\n===== 原型 =====")
    pf, pt, pp, _ = survey("原型", PROTO)

    print("\n===== `fbar` 调用点的子件类型分布（壳 · 每个调用点后 6 行）=====")
    for k, v in kids.most_common():
        print(f"  {k:<10} {v}")
    print("\n===== 读法（给下一批定批用）=====")
    print(f"  · 「筛选栏配置化」的真实规模 = **壳 {tf} 处**（原型 {pf} 处）—— ⛔ 别再用「115 处」那个来源不明的数")
    print(f"  · 「口径说明」的真实规模 = 壳 `class=\"tip` {tt} 处（⚠️ 它**不等于**筛选栏说明 ⇒ 需要先定义哪些算）")
    print(f"  · 「项目选择」的真实规模 = 壳 `pjwrap|projPanel` {tp} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
