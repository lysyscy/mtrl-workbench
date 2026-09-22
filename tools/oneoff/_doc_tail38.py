# -*- coding: utf-8 -*-
"""收尾：把 `TAIL-38` 销号写进**开发计划**（§15 台账 ＋ §14.3 排期 ＋ §15 顶部计数 ＋ `TAIL-27` 状态）。

⚠️ 幂等：已是目标状态就直接退出 0（防「一条命令被跑两次」把第二遍误读成失败）。
⚠️ 按**行首标记**定位、整行替换（长中文行不做精确全文匹配 —— 太脆）。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

raw = PLAN.read_bytes()
CRLF = b"\r\n" in raw
lines = raw.decode("utf-8").splitlines(keepends=True)


def _nl(i: int) -> str:
    return "\r\n" if lines[i].endswith("\r\n") else "\n"


def find_one(prefix: str) -> int:
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 行首标记 `{prefix}` 命中 {len(hit)} 次（应 1）")
    return hit[0]


TODAY = dt.datetime.now().strftime("%Y-%m-%d")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

if "TAIL-38` 两件都做完" in raw.decode("utf-8"):
    print("已是目标状态（TAIL-38 已销号）—— 无需重复执行")
    sys.exit(0)

# ---- ① §15 A 类：删掉 TAIL-38 行
i = find_one("| `TAIL-38` |")
del lines[i]
print("① §15 A 类：删除 TAIL-38 行")

# ---- ② §15 四、已销号：在表头分隔行之后插入销号行
j = find_one("### 四、已销号")
k = next(idx for idx in range(j, j + 6) if lines[idx].startswith("|---|---|"))
lines.insert(k + 1, (
    "| `TAIL-38` | **`m06` 机械 6 列缺壳侧录入入口 ＋ `m07` 整页未接线** | **两件都做完**（" + TODAY + "）："
    "① **`m07` 收发结存与活动大表已接线** —— 新增 `mod07_setl/api.py`（7 个 JSON 端点：`settlement` / `extract` / "
    "`big` / `big/cell` / `big/selection` / `fetch`），壳侧删演示容器 `WHM`/`EXTM`/`BIGVAL`（＋已失效的 `EXTRACT` 别名）、"
    "`BIGSET` 改后端填充；⚠️ **判定一律留后端**（对平 / 提取口径 / 手填校验 / 选题校验，⛔ 前端不复写）。"
    "② **录机械费入口**（`TAIL-38` 本体）—— 新增 `POST /api/m06/mech`（复用 `mech_ui.parse_mech_values` ＋ `save_mech`）；"
    "⛔ **不改 `V.m06` 一行**：走原型自己的 `BIND` 钩子在渲染后注入工具栏。"
    "**真机**：`m07` 三张表全通（表内渲染 == 后端行数 ＋ 合计行 · 大表行数 == 后端选题数 10）；"
    "录机械费「写 → 回读 `[0,1234.56,0,0,0,0]` → 负数 / 非法月份双 400 拒 → **复原**」全通。"
    "断言 **19 ＋ 4** 条（`test_wired_m07.py` · `test_wired_m06.py`）· 反向灵敏度 **15/15**（**首跑抓出 4 处假绿**，已改紧）· "
    "MD5 逐字节复原 · 四态 **487 不变** · 六把尺子全 0 | " + TODAY + " |"
) + "\n")
print("② §15 已销号：插入 TAIL-38 行")

# ---- ③ §15 顶部计数
c = find_one("> **当前状态（")
lines[c] = (
    f"> **当前状态（{NOW}）**：A 类 **9** 条 · B 类 **1** 条 · C 类 **1** 条 · 已销号 **30** 条。\n"
)
print("③ §15 顶部计数：A 类 10 → 9 · 已销号 29 → 30")

# ---- ④ §14.3 排期表：TAIL-38 行改为「已做」
m = find_one("| `TAIL-38` **`m06` 机械录入缺壳侧入口")
lines[m] = (
    "| `TAIL-38` **`m06` 机械录入缺壳侧入口 ＋ `m07` 整页未接线** | ✅ **已做**（" + TODAY + "） "
    "| ① **是不是别人的前置？是** —— 机械欠款要真数就得有人录机械费；② **同 `TAIL-27` 一族**，分开做会把同一页的文件来回进出 "
    "| 已完成（`m07` 整页接线 ＋ 录机械费入口），见交接 §⑥ ＋ §15 已销号 |\n"
)
print("④ §14.3 排期表：TAIL-38 标「已做」")

# ---- ⑤ §15 TAIL-27 行：补 m07
t = find_one("| `TAIL-27` |")
lines[t] = lines[t].replace(
    "| 立刻 | 进行中（**壳已建 · `m03`/`m01`/`m04`/`m05` 已接**） |",
    "| 立刻 | 进行中（**壳已建 · `m03`/`m01`/`m04`/`m05`/`m06`/`m08`/`m07` 已接**） |",
)
if "`m06`/`m08`/`m07` 已接" not in lines[t]:
    raise SystemExit("⛔ TAIL-27 行的状态列没改成（锚不匹配）")
print("⑤ §15 TAIL-27：状态列补上 m06/m08/m07")

PLAN.write_bytes("".join(lines).encode("utf-8"))
print(f"\n写好：{PLAN.name} · {len(raw)} → {PLAN.stat().st_size} 字节")
print("下一步：跑 tools/doc_audit.py 复核（T6 会查台账栏位 / 计数 / 与 §14.3 一致）")
