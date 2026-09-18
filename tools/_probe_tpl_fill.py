# -*- coding: utf-8 -*-
"""路径①（模板填充）取证：4 个模板的 sheet / 表头行 / `DATA_START` 标记格 / 现有数据行 / 列数。

只读。用法： backend/.venv/Scripts/python.exe tools/_probe_tpl_fill.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DEMO = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用") / "demo" / "模板"
FILES = ("模板-逐月欠款台账.xlsx", "模板-过程资料.xlsx", "模板-焊材气体.xlsx", "模板-开会大表.xlsx")


def main() -> int:
    for fn in FILES:
        p = DEMO / fn
        print("\n" + "#" * 78)
        print("# %s  (%s, %d B)" % (fn, "存在" if p.exists() else "缺", p.stat().st_size if p.exists() else 0))
        print("#" * 78)
        wb = openpyxl.load_workbook(p, data_only=True)
        for ws in wb.worksheets:
            print("\n  === sheet [%s]  dims=%s  max_row=%d max_col=%d" % (
                ws.title, ws.dimensions, ws.max_row, ws.max_column))
            print("      merged=%s" % (list(ws.merged_cells.ranges)[:6],))
            # 前 8 行全量单元格
            for r in range(1, min(ws.max_row, 8) + 1):
                vals = [ws.cell(row=r, column=c).value for c in range(1, min(ws.max_column, 26) + 1)]
                mark = ""
                for c, v in enumerate(vals, 1):
                    if isinstance(v, str) and "DATA_START" in v:
                        mark = "  <<< DATA_START 在 %s%d" % (openpyxl.utils.get_column_letter(c), r)
                print("      R%-3d %s%s" % (r, [("" if v is None else v) for v in vals][:14], mark))
        wb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
