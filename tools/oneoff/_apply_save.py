#!/usr/bin/env python
"""`TAIL-68`：6 处落盘 ⇒ 统一走 `app/report_export/save.py::save_workbook()`。

⭐ 抽它的**真理由不是省那 2~4 行**，而是：**"落盘前先 mkdir" 这一步没人兜** ——
   2026-09-21 普查当场抓到 `setl_export` **没有 mkdir**（换一个不存在的导出目录就崩）。
   ⇒ 收到一个出口之后，这一步**不可能再被漏**（本轮顺手修掉）。

⛔ **命名不抽**：`file_name` / `title_of` 那 7 处是**各报表的业务口径**，且期间标签
   `period_label` 已经是唯一主人 ⇒ 抽它就是"给同一规则找第二个主人"（见 `save.py` 模块头）。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
APP = ROOT / "backend" / "app"
BAK = ROOT / ".workbuddy" / "scratch"
BAK.mkdir(parents=True, exist_ok=True)

IMP = "from app.report_export.save import save_workbook"

# (相对路径, 旧块, 新块, 缩进)
EDITS: list[tuple[str, str, str]] = [
    ("mod05_flow/debt_export.py",
     "    out_dir = Path(out_dir)\n    out_dir.mkdir(parents=True, exist_ok=True)\n"
     "    out = out_dir / file_name(today)\n    wb.save(str(out))\n    wb.close()\n"
     "    return str(out.resolve())",
     "    out = save_workbook(wb, Path(out_dir) / file_name(today))\n    return str(out)"),
    ("report_export/big_export.py",
     "        Path(out).parent.mkdir(parents=True, exist_ok=True)\n        wb.save(str(out))",
     "        save_workbook(wb, out)"),
    ("report_export/ledger_export.py",
     "        Path(out).parent.mkdir(parents=True, exist_ok=True)\n        wb.save(str(out))",
     "        save_workbook(wb, out)"),
    ("report_export/process_export.py",
     "        Path(out).parent.mkdir(parents=True, exist_ok=True)\n        wb.save(str(out))",
     "        save_workbook(wb, out)"),
    ("report_export/tpl_fill.py",
     "        Path(out_path).parent.mkdir(parents=True, exist_ok=True)\n        wb.save(str(out_path))",
     "        save_workbook(wb, out_path)"),
    # ⭐ 这一处**原本没有 mkdir**（本轮修掉的隐患）
    ("report_export/setl_export.py",
     "    wb.save(out_path)",
     "    save_workbook(wb, out_path)          # ⭐ `TAIL-68`：这里原本**没有 mkdir**（换目录就崩）"),
]

for rel, old, new in EDITS:
    p = APP / rel
    t = p.read_text(encoding="utf-8")
    if old not in t:
        print(f"⚠️  {rel}: 找不到锚点")
        continue
    shutil.copy2(p, BAK / (p.name + ".bak-save"))
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
    print(f"✅ {rel}: 落盘改用 `save_workbook`")

# 补导入（⛔ 别整行替换已有导入，会丢名字 —— 本仓 2026-09-21 踩过）
for rel, *_ in EDITS:
    p = APP / rel
    t = p.read_text(encoding="utf-8")
    if IMP in t:
        continue
    lines = t.split("\n")
    # 插到最后一条**非多行**的 import 之后（⛔ 别插到 `import (` 后面，本仓踩过 SyntaxError）
    last = None
    for k, l in enumerate(lines):
        if l.startswith(("import ", "from ")) and not l.rstrip().endswith("("):
            last = k
    lines.insert(last + 1, IMP)
    p.write_text("\n".join(lines), encoding="utf-8", newline="")
    print(f"➕ {rel}: 导入 `{IMP}`")
print("完成 · 备份在 .workbuddy/scratch/*.bak-save")
