# -*- coding: utf-8 -*-
"""`MOD-07` **焊材 / 气体提取**的成品导出（`TAIL-04` **路径① = 模板填充**）。

## 分工

| 管什么 | 主人 |
|---|---|
| 形态（两个 sheet · 表头 · `DATA_START` · 列映射） | 交付面 `demo/模板/模板清单.md`（§二 登记表 · §5.4 列映射） |
| 行为（认标记文字定位数据区 · 尾块随行数派生） | 《材料科业务全流程说明书》**§7.1** |
| 取数（项目集合 / 各月金额 / 结余） | `mod07_setl/extract.py`（**纯函数**）＋ `service.build_extract_export` |
| 摆位（写哪一格 · 清残留 · 尾块偏移） | `report_export/tpl_fill.py`（中立引擎） |

⚠️ **本模块只做一件事**：把域内核给的**网格**映射到**列**，交给引擎 + 对账。
   ⛔ 不在这里算金额、不筛项目、不拼路径（路径唯一出口 = `resources`）。

⚠️ 与**路径②**（`setl_export` / `kcdj_export` · `zip` 字节替换）**是两类做法**，⛔ 别混：
   路径① 用 `openpyxl` 读模板再填数（模板里带示例数据 ⇒ **必须清干净**）。

## 列映射（`模板清单` §5.4 · 两个 sheet 结构相同 · 15 列）

| 列 | A | B | C…N | O |
|---|---|---|---|---|
| 含义 | 项目 | 结余 | `1月`…`12月` | 合计 |

⚠️ 模板 `A1` 表头写的是**类别名**（「焊材」/「气」）、取值其实是**项目名**（清单 §5.4 的备注）
   —— 本模块**按位置**写、不按列名找列，所以那条坑不吃；表头文字**照模板保留**（改动它 = 改用户的外观）。
"""

from __future__ import annotations

from pathlib import Path

from openpyxl.utils import column_index_from_string, get_column_letter

from app.core.errors import MustReportError
from app.mod07_setl.domain import period_label
from app.report_export import resources, tpl_fill
from app.report_export.save import save_workbook

#: 类别 → 模板里的 sheet 名（`模板清单` §二 登记：`焊材` / `气`）
SHEET_OF_KIND: dict[str, str] = {"焊材": "焊材", "气体": "气"}

#: 模板里的列（`模板清单` §5.4）
COL_LABEL = "A"          # 第 1 列 = 项目
COL_BALANCE = "B"        # 结余
COL_FIRST_MONTH = "C"    # `1月` ⇒ C…N = 1…12 月
COL_TOTAL = "O"          # 合计

#: 成品名（**唯一出口**；⛔ 不让壳自己拼 —— 命名规则两处各写一份必然走形）
FILE_PREFIX = "焊材气体提取表"


def _month_letters(count: int) -> list[str]:
    """月份列字母（`C` 起连续 `count` 个）。"""
    first = column_index_from_string(COL_FIRST_MONTH)
    return [get_column_letter(first + i) for i in range(count)]


def cells_of_row(grid: dict, row: dict) -> dict:
    """一行的网格值 → `{列字母: 值}`。

    - `结余`：**缺 ⇒ `None`**（该月该仓库没有命中行 ⇒ 留空，⛔ 不写 0）；
    - 月份格：该月**无数据 ⇒ `None`**（同上）；
    - `合计`：**总是写** —— 模板里它本来就是每行的 `=SUM(B:N)`（空行 = 0，与模板同表现）。
    """
    letters = _month_letters(len(grid["months"]))
    cells: dict = {COL_BALANCE: row.get("balance"), COL_TOTAL: row.get("total")}
    for letter, value in zip(letters, row.get("cells") or []):
        cells[letter] = value
    return cells


def sum_cells(grid: dict) -> dict:
    """合计行（模板尾块那一行）= 各月列之和 ＋ 合计列之和；`结余` 列**照模板留空**。"""
    letters = _month_letters(len(grid["months"]))
    sums = grid.get("sum_row") or []
    cells: dict = {}
    for letter, value in zip(letters, sums):
        cells[letter] = "" if value is None else value
    if sums:
        cells[COL_TOTAL] = sums[-1]
    return cells


def build_specs(grids: dict) -> list[dict]:
    """网格 → 引擎的 `spec` 列表（一个模板 sheet 一份）。"""
    specs: list[dict] = []
    for kind, sheet in SHEET_OF_KIND.items():
        grid = (grids or {}).get(kind)
        if grid is None:
            continue
        specs.append({
            "sheet": sheet,
            "rows": [(r["warehouse"], cells_of_row(grid, r)) for r in grid["rows"]],
            # 尾块 = 模板那一行合计（偏移 0）；它下面若还有别的东西，由引擎按文本原样保留
            "tail": {0: (None, sum_cells(grid))},
        })
    return specs


def file_name(report_ym: str) -> str:
    """成品文件名（**唯一出口**）。"""
    return "%s_%s.xlsx" % (FILE_PREFIX, period_label(str(report_ym or "").strip()))


def build_xlsx(grids: dict, root, report_ym: str, *, annual_grids: dict | None = None) -> str:
    """两个 sheet → 一个 xlsx ⇒ 返回**成品绝对路径**。

    - 模板一律走 `resources.require_template`（缺失 / 被回退 ⇒ **显式拒做**）；
    - 落点 = `<root>/焊材气体提取表/<期间标签>/<成品名>`（与另两条导出的命名规矩一致）；
    - ⚠️ 产物一律过 **`tpl_fill.verify_filled`**：显示区 ≠ 期望 / 尾块以下有残留 / 值覆盖不彻底
      ⇒ **抛 `MustReportError`**（⛔ 宁可不出文件，也不出一份"看着正常、数是旧的"）。
    """
    ym = str(report_ym or "").strip()
    if len(ym) != 7:
        raise MustReportError("导出焊材 / 气体提取：拿不到**报告月**（当前筛选下没有可导出的数据）——"
                              "请先在页面上把时间范围选到有数据的月份。")
    template = resources.require_template(resources.WELD_TEMPLATE)
    out = Path(root) / FILE_PREFIX / period_label(ym) / file_name(ym)
    plan = tpl_fill.fill_workbook(template, out, build_specs(grids))
    problems = tpl_fill.verify_filled(out, plan)
    if problems:
        raise MustReportError(
            "成品**显示区对账未通过** ⇒ 已中止，未交付："
            + "；".join(problems[:5]) + ("" if len(problems) <= 5 else "（等共 %d 条）" % len(problems)))
    if annual_grids is not None:
        from openpyxl import load_workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = load_workbook(out)
        for kind, grid in annual_grids.items():
            sheet = wb.create_sheet(kind + '年度汇总')
            sheet.append(['项目', '往年金额', *grid['months'], '合计', '2025-11及之前'])
            for row in grid['rows']:
                sheet.append([row['warehouse'], row['prior'], *row['cells'], row['total'], row['balance']])
            sheet.append(['合计', *grid['sum_row'], None])
            sheet.freeze_panes = 'C2'
            sheet.column_dimensions['A'].width = 36
            for cell in sheet[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill('solid', fgColor='E8EEF4')
            for col in range(2,17):
                sheet.column_dimensions[get_column_letter(col)].width = 16
                for cell in list(sheet.columns)[col-1][1:]:
                    cell.number_format = '#,##0.00'
            for cell in sheet['A']:
                cell.alignment = Alignment(wrap_text=True, vertical='center')
        save_workbook(wb, out)
        check = load_workbook(out, data_only=True)
        for kind, grid in annual_grids.items():
            actual = list(check[kind+'年度汇总'].values)
            expected = [['项目','往年金额',*grid['months'],'合计','2025-11及之前'],
                        *[[row['warehouse'],row['prior'],*row['cells'],row['total'],row['balance']] for row in grid['rows']],
                        ['合计',*grid['sum_row'], None]]
            from decimal import Decimal
            def comparable(value):
                if isinstance(value, (int, float, Decimal)):
                    return Decimal(str(value)).quantize(Decimal('0.01'))
                return value
            if [[comparable(value) for value in row] for row in actual] != [
                    [comparable(value) for value in row] for row in expected]:
                check.close()
                raise MustReportError('年度汇总导出对账失败，请重试')
        check.close()
    return str(out)


__all__ = ["SHEET_OF_KIND", "COL_LABEL", "COL_BALANCE", "COL_FIRST_MONTH", "COL_TOTAL",
           "FILE_PREFIX", "cells_of_row", "sum_cells", "build_specs", "file_name", "build_xlsx"]
