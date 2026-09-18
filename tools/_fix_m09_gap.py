"""把 `V.m08` 与 `V.m09` 之间那段注释**逐字还原成原型原文**。

⚠️ 为什么必须还原：`ui_parity` 的 `U1` 按「行首 `V.x=` 起、到下一个 `V.`/`BIND.`/顶层 `const` 止」切片
   ⇒ 夹在两个切片之间的注释会被算进**前一个**切片（这里是 `m08`）逐行比对。
   我在那里扩写了 5 行注释 ⇒ `U1` 报 5 行漂移（`[m08 L68..L72]`，内容其实全是 m09 的面板说明）。

⭐ 做法（不是"登记漂移"，而是**把它恢复成原型原文**）：
   解释性文字搬到**切片之外**（数据容器区 `MOD-09` 段），切片内的注释**一字不改** ——
   这样 `U1` 保持零漂移，白名单也不需要多登记一行（登记簿**只准变短**）。
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
SHELL = ROOT / "backend" / "app" / "web" / "index.html"

PROTO_ANCHOR = '/* 「项目」**单选**面板'
PROTO_END = '变「未建档」。） */'
SHELL_END = "const awfPjPanel="

proto = PROTO.read_text(encoding="utf-8").split("\n")
i = next(k for k, ln in enumerate(proto) if ln.startswith(PROTO_ANCHOR))
j = next(k for k in range(i, len(proto)) if proto[k].rstrip().endswith(PROTO_END))
gap = "\n".join(proto[i:j + 1]) + "\n"
print(f"原型里的该段 = 第 {i + 1}..{j + 1} 行（{j - i + 1} 行）")

src = SHELL.read_text(encoding="utf-8")
lines = src.split("\n")
# ⚠️ 必须**按行首**找 —— 只搜子串会命中带缩进的那一处（`ACT` 里 `  /* 「项目」…` 同款文案）
hits = [k for k, ln in enumerate(lines) if ln.startswith(PROTO_ANCHOR)]
assert len(hits) == 1, f"⛔ 壳里行首锚命中 {len(hits)} 次 —— 不唯一"
s = sum(len(x) + 1 for x in lines[:hits[0]])
e = src.find(SHELL_END, s)
assert e > 0, "⛔ 壳里找不到 `const awfPjPanel=`"
old = src[s:e]
print(f"壳里待替换区间 = {len(old)} 字符 / {old.count(chr(10))} 行")

src = src[:s] + gap + src[e:]
SHELL.write_text(src, encoding="utf-8")
print(f"✅ 已逐字还原（新区间 {len(gap)} 字符）")
sys.exit(0)
