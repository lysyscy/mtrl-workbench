#!/usr/bin/env python
"""壳侧：m08 含透视导出撤销二次确认（导出不碰 i8 ⇒ 不需要 D9），回到普通 dlExport。"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
ACTS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
shutil.copy2(ACTS, ROOT / ".workbuddy" / "scratch" / "actions.js.bak-split2")

t = ACTS.read_text(encoding="utf-8", errors="replace")
s = t.find(" expPivot:async ()=>{")
e = t.find("',6400); },", s)
assert s > 0 and e > s, "expPivot 块定位失败"
NEW = (
  " expPivot:async ()=>{\n"
  "   /* ⭐ 2026-09-21 用户裁定「**抓取导出分开**」：这份导出只读**最近一次抓取的源文件缓存**\n"
  "      （⛔ 不现场登 i8 ⇒ 不再需要二次确认 / allow_kick —— D9 的确认都在「抓取」侧，与 m07 同一套心智）。\n"
  "      缓存没有（该月还没抓过）⇒ 后端回「请先抓取」，照样弹窗明说。 */\n"
  "   const url='/api/m08/inventory/export?period='+encodeURIComponent(fIvYm);\n"
  "   const fn=await dlExport(url,{name:'库存单据明细表.xlsx'});\n"
  "   if(!fn) return;\n"
  "   toast('已导出「库存单据明细（含数据透视表）」：<b>工作表 1</b> = 明细（<b>列随 i8 源文件</b>，与页面列不同）；"
  "<b>工作表 2</b> = <b>「过程资料」透视</b>（按仓 × 出入库方向 × 物料性质）；<b>工作表 3</b> = "
  "<b>「安全文明施工费」透视</b>（按仓 × 金额）<br>⭐ 用的是<b>最近一次抓取</b>的源文件 —— 若该月有新单据，先抓取再导出',6400); },"
)
ACTS.write_text(t[:s] + NEW + t[e + len("',6400); },"):], encoding="utf-8", newline="")
print("✅ actions.js: expPivot 回归普通导出（无确认 / 无 allow_kick）")
