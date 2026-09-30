#!/usr/bin/env python
"""`TAIL-62`：**朴素导出三件（fl / jc / pj）下沉到 `naive_export`** —— 机械改写。

⭐ 为什么能这么改：`naive_export.build_xlsx` 本来就是这三件的**通用化版本**
   （它自己的模块头写着"`jc_export` / `fl_export` / `pj_export` 是它的前身…要拆另开一轮"）。
   本轮把它需要的三个差异（`seq_key` 序号列 · `int_keys` 整数列 · `width_max` 列宽上限）
   作为**可选参数**加进内核（默认值与旧行为一致 ⇒ 现有调用方零影响），再让三件**薄委托**。

⛔ 纪律：`COLUMNS` / `MONEY_KEYS` / `SEQ_KEY` **留在各自那件**（那是**该页的口径**），
   下沉的只有"怎么写成 xlsx"这一件事 —— ⛔ 别把列定义也搬走（搬了就是"口径搬家"，必漂）。
⛔ 判据：输出必须与下沉前**逐格一致** ⇒ `artifacts/golden/_golden_naive_before.json`（母本）比对。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BAK = ROOT / ".workbuddy" / "scratch"

BODIES = {
    "fl_export.py": (62, 110, '''def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⭐ `TAIL-62`（2026-09-21）：**实现已下沉到 `naive_export`**（本件是它的前身之一）⇒
      这里只留一层**薄委托**。⛔ 列定义 / 金额键**仍在本件**（那是**付款流水页的口径**），
      下沉的只有"怎么写成 xlsx"这一件事 ⇒ 现在**只有一个主人**。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ 金额列写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接求和/排序。
    """
    from app.report_export import naive_export as N
    return N.build_xlsx(rows, columns=COLUMNS, sheet_name=SHEET_NAME,
                        money_keys=MONEY_KEYS, total_keys=MONEY_KEYS)'''),
    "jc_export.py": (71, 122, '''def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⭐ `TAIL-62`（2026-09-21）：**实现已下沉到 `naive_export`**（本件是它的前身之一）⇒ 薄委托。
      ⛔ 两个**本页口径**必须照旧带给内核：① `SEQ_KEY` = 「序号」列写**行号**；
      ② 列宽上限 **28**（不是内核默认的 32 —— ⛔ 统一成 32 会**改掉本页导出形态**，
      本轮是"换实现"，**不是"改口径"**）。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ 金额列写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接求和/排序
       —— 写成 `"1234.56"` 那种"看着是数、其实是文本"的表，是本项目最讨厌的一类假象。
    """
    from app.report_export import naive_export as N
    return N.build_xlsx(rows, columns=COLUMNS, sheet_name=SHEET_NAME,
                        money_keys=MONEY_KEYS, total_keys=MONEY_KEYS,
                        seq_key=SEQ_KEY, width_max=28)'''),
    "pj_export.py": (56, 97, '''def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⭐ `TAIL-62`（2026-09-21）：**实现已下沉到 `naive_export`**（本件是它的前身之一）⇒ 薄委托。
      ⚠️ 本页**没有合计行** ⇒ 不传 `total_keys`（⛔ 别"顺手"给它补一个合计 —— 页面没有，导出就**不能**有）。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ `ord` 写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接排序
       —— 写成 `"3"` 那种"看着是数、其实是文本"的表，是本项目最讨厌的一类假象。
    """
    from app.report_export import naive_export as N
    return N.build_xlsx(rows, columns=COLUMNS, sheet_name=SHEET_NAME,
                        int_keys=NUMBER_KEYS)'''),
}

for name, (start, end, body) in BODIES.items():
    p = ROOT / "backend" / "app" / "report_export" / name
    BAK.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, BAK / (name + ".bak-naive"))
    t = p.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    L = t.replace("\r\n", "\n").split("\n")
    old = L[start - 1:end]
    assert old[0].startswith("def build_xlsx"), f"{name}: 起点不是 build_xlsx ⇒ {old[0][:60]}"
    assert "return buf.getvalue()" in old[-1], f"{name}: 终点不对 ⇒ {old[-1][:60]}"
    L[start - 1:end] = body.split("\n")
    p.write_text(nl.join(L), encoding="utf-8", newline="")
    print(f"{name}: 替换 L{start}–L{end}（{end - start + 1} 行 ⇒ {len(body.split(chr(10)))} 行）")
print("完成 · 备份在 .workbuddy/scratch/*.bak-naive")
