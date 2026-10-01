#!/usr/bin/env python
"""一次性修补（2026-09-30 · `TAIL-203` 销号收尾 + 清掉我写坏的一行）。

三件事（都是"行级"精确操作，用脚本比多次 replace 稳）：
  1) 删掉 §14.3 里那行**残行** `| `TAIL-188``（我上一步误插的，它不是合法表行）；
  2) 删掉 §14.3 里的 `TAIL-203` 行（它已办 ⇒ 本表按 `T13` 只留「还没办」的）；
  3) 台账§15：把 `TAIL-203` 行**从 §一 移到 §四**（销号；⚠️ 计数已改成 A 2 / 已销号 204 ⇒
     本步不做的话 `ledger_counts()` 会与文字对不上 ⇒ `T4`/`T6` 必红）。

⚠️ 行尾：`read_bytes().decode()` ＋ `splitlines(keepends=True)`（本仓计划件 CRLF —— `read_text()` 会归一成 LF）。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
BT = chr(96)

SOLD_ROW = (
    f"| {BT}TAIL-203{BT} | 📄 **两份活文档腾余量**（计划/简略版贴 `T10`/`T13` 上限） | "
    f"**销号依据** = 用户 2026-09-30「P1-2/3/4 都做」⇒ 已办："
    f"① §14.3 **已办 74 行**逐字下沉 {BT}.workbuddy/plans/archive/归档-排期-已办尾巴-20260930.md{BT}"
    f"（计划 **1792 → 1719**，余 8 → **81**）· "
    f"② 简略版 §③-2 压成「人话 ＋ 指路」（**192 → 186**，余 8 → **14**）· "
    f"③ 工具 = {BT}tools/oneoff/_tail203_sink.py{BT}（先干跑；⛔ 三条红线：§15 §四 不许搬 / 只搬非 live / 逐字搬）| 2026-09-30 |"
)


def main() -> int:
    text = PLAN.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text[:2000] else "\n"
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    seen = {"dangling": 0, "sched203": 0, "live203": 0, "sec4": None}
    for l in lines:
        s = l.strip()
        if s == "| " + BT + "TAIL-188" + BT:                      # 1) 残行
            seen["dangling"] += 1
            continue
        if s.startswith("| " + BT + "TAIL-203" + BT):              # 2) §14.3 的 203 行 / 3) §一 的 203 行
            if "两份活文档腾余量" in s and ("立刻" in s or "销号依据" in s):
                if "销号依据" in s:
                    continue                                       # 已是 §四 形态（幂等）
                seen["sched203"] += 1
                continue
        if s.startswith("| # | 事项 | 销号依据 | 日期 |"):
            seen["sec4"] = len(out)
        out.append(l)

    # 3) §15 §一 里那条 203 行（形态 = 首格编号 ＋ 事项里含「两份活文档腾余量」）
    out2: list[str] = []
    for l in out:
        s = l.strip()
        if s.startswith("| " + BT + "TAIL-203" + BT) and "两份活文档腾余量" in s:
            seen["live203"] += 1
            continue
        if s.startswith("| # | 事项 | 销号依据 | 日期 |"):
            seen["sec4"] = len(out2)
        out2.append(l)

    if seen["sec4"] is None:
        print("⛔ 找不到 §四 表头 ⇒ 停手"); return 1
    out2.insert(seen["sec4"] + 2, SOLD_ROW + nl)      # 表头 ＋ 分隔行之后
    shutil.copy2(PLAN, PLAN.with_name(PLAN.name + ".pre-fix"))
    PLAN.write_bytes("".join(out2).encode("utf-8"))
    print(f"残行删除 {seen['dangling']} · §14.3 的 203 行删除 {seen['sched203']} · §一 的 203 行删除 {seen['live203']}")
    print(f"§四 已插入销号行（表头在第 {seen['sec4'] + 1} 行）· 现 {len(out2)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
