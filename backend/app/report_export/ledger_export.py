# -*- coding: utf-8 -*-
"""逐月欠款台账：辅材、机械和特殊费用共用一本工作簿及截止月。

费用矩阵由MOD09按项目组装，列布局与字段映射见docs/reference/template-export.md。
本模块只负责模板布局、标题和数字格式；金额及行集合由业务服务提供。
沿用模板标记定位、尾块位移和成品逐格回读，清除全部样例值。
"""

from __future__ import annotations

import re
import zipfile
from copy import copy
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.errors import MustReportError
from app.core.money import sum_money
from app.mod07_setl.domain import period_label
from app.report_export import resources, tpl_fill
from app.report_export.save import save_workbook

#: 类别（**内部值 = 英文**，见 `mod05_flow.models`：`material` / `mechanical`）→ 模板里的 sheet 名
#: （`模板清单` §二 登记；⛔ 不在这里另起名字。⚠️ 别把「显示名（辅材/机械）」当键 —— 那是 `label`）
SHEET_OF_CATEGORY: dict[str, str] = {"material": "辅材", "mechanical": "机械"}
SHEET_FEE = "特殊费用月报表"

#: 标题后缀（**照模板**；前缀 = 项目**展示名**）
TITLE_SUFFIX: dict[str, str] = {"辅材": "辅材欠款", "机械": "机械费欠款", SHEET_FEE: "费用汇总表"}

#: 成品命名（**唯一出口**）：`{展示名}欠款台账_{期间标签}.xlsx`（原型：文件名含项目展示名与当前年月）
FILE_SUFFIX = "欠款台账"

#: 台账列映射（`模板清单` §5.1：模板 6 列 = 页面 7 列去掉「操作」）
LEDGER_COL = {"seq": "A", "month": "B", "other": "C", "pay": "D", "debt": "E", "remark": "F"}

#: 期初占位行的月份文本（**照原型** `ledCutLabel`：空格与「年月」写法一字不差）
CUT_MONTH_FMT = "截止 {y} 年 {m} 月底"
#: 写文本前先设的**数字格式**（唯一主人 = 引擎 `tpl_fill.TEXT_FMT`；此处只为兼容既有引用而转发）
TEXT_FMT = tpl_fill.TEXT_FMT

#: 月份表头的识别（`3月份` / `9月份` …）—— 认**结构**，⛔ 不抄列字母
_MONTH_HEADER = re.compile(r"^\d+月份$")


def money(value) -> Decimal | None:
    """金额列的值：**空 ⇒ `None`**（留白），其余归一到 `Decimal`（2 位小数口径 = `core.money`）。

    ⚠️ 台账的 `0` 是**合法值**（空月记 0，§4.5.4）⇒ **照写 0**，⛔ 不按"焊材结余"那套留空。
    """
    if value in (None, ""):
        return None
    return sum_money([value])


# ---------------------------------------------------------------- 台账两 sheet


def title_of(display: str, sheet: str) -> str:
    """标题 = **展示名 ＋ 模板后缀**（用户 2026-09-18 裁：不带「项目」二字）。"""
    return f"{display or ''}{TITLE_SUFFIX[sheet]}"


def month_text(row: dict, *, sheet: str = '') -> str:
    """「月份」列的**页面文本**：期初占位行 = `截止 YYYY 年 M 月底`，其余 = `YYYY-MM`。"""
    ym = str(row.get("month") or "")
    if sheet == '辅材' and str(row.get('month_label') or ym) == '2025-11':
        return '2025-11及之前'
    if row.get("month_label"):
        return str(row["month_label"])
    if row.get("is_opening") and len(ym) >= 7 and ym[4] == "-":
        return CUT_MONTH_FMT.format(y=int(ym[:4]), m=int(ym[5:7]))
    return ym


def ledger_spec(sheet: str, side: dict, *, display: str) -> dict:
    """一侧台账 → 引擎 `spec`（`label` = 序号；「合计行」进 `tail` 的偏移 0）。"""
    rows = list(side.get("display_rows", side.get("rows")) or ())
    data = [
        (r.get("seq"), {
            LEDGER_COL["month"]: month_text(r, sheet=sheet),
            LEDGER_COL["other"]: money(r.get("other_expense")),
            LEDGER_COL["pay"]: money(r.get("payment")),
            LEDGER_COL["debt"]: money(r.get("debt")),
            # ⚠️ 空备注给 `None`（⛔ 不给 `""`）：空串存回 Excel 会变成"有格无值"，
            #    与 `verify_filled` 期望的 `None` 不符 ⇒ 对账会**误报**（实测踩到，8 条）。
            LEDGER_COL["remark"]: (str(r.get("remark") or "").strip() or None),
        })
        for r in rows
    ]
    tail = {0: (None, {
        LEDGER_COL["other"]: sum_money([r.get("other_expense") for r in rows]),
        LEDGER_COL["pay"]: sum_money([r.get("payment") for r in rows]),
        LEDGER_COL["debt"]: sum_money([r.get("debt") for r in rows]),
    })}
    return {"sheet": sheet, "rows": data, "tail": tail, "title": title_of(display, sheet),
            "months_col": LEDGER_COL["month"]}


# ---------------------------------------------------------------- 特殊费用月报表


def fee_spec(fee: dict, *, display: str, ym: str) -> dict:
    """已组装的逐月费用矩阵 → 模板列；金额及合计由业务服务提供。"""
    total_col = get_column_letter(len(fee['months']) + 2)
    data = []
    for item in fee['rows']:
        cells = {get_column_letter(col): money(value) for col, value in enumerate(item['months'], 2)}
        cells[total_col] = money(item['total'])
        data.append((str(item.get('item') or '').strip() or None, cells))
    return {"sheet": SHEET_FEE, "rows": data, "tail": {}, "title": title_of(display, SHEET_FEE)}


def layout_fee_months(ws, months: list[str]) -> None:
    """以模板标题、月列及合计样式生成动态列，随后仍由填充引擎写数据行。"""
    cols = [c for c in range(1, ws.max_column + 1)
            if _MONTH_HEADER.match(str(ws.cell(row=2, column=c).value or "").strip())]
    if not cols:
        raise MustReportError("模板的 `特殊费用月报表` 第 2 行找不到「N月份」列 ⇒ 形态不认识，拒绝产出。")
    data_start = tpl_fill.locate_data_area(ws)['data_start']
    styles = {r: [copy(ws.cell(r, col)._style) for col in (cols[0], ws.max_column)]
              for r in range(1, data_start + 1)}
    for merged in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(merged))
    ws.delete_rows(data_start + 1, ws.max_row - data_start)
    ws.delete_cols(2, ws.max_column - 1)
    for col in list(ws.column_dimensions):
        if col != 'A':
            del ws.column_dimensions[col]
    ws.column_dimensions['A'].width = max(ws.column_dimensions['A'].width, 36)
    for col, label in enumerate([*months, '合计'], 2):
        ws.column_dimensions[get_column_letter(col)].width = 12
        for row in range(1, data_start + 1):
            ws.cell(row, col)._style = copy(styles[row][int(col == len(months) + 2)])
        ws.cell(2, col).value = label
        ws.cell(data_start, col).number_format = '#,##0.00'
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(months) + 2)


# ---------------------------------------------------------------- 组装


def file_name(display: str, ym: str) -> str:
    """成品文件名（**唯一出口**）。"""
    return "%s%s_%s.xlsx" % (display or "", FILE_SUFFIX, period_label(str(ym or "").strip()))


def _set_text_fmt(ws, plan: dict, months_col: str) -> None:
    """把「月份」列的**数据行**格设为文本格式（`模板清单` §四-4）。

    ⚠️ 本条实现在 `TAIL-04` 片 4a 时**提到了引擎**（`tpl_fill.set_text_format`）—— 那是同一个坑的
       **第二次**出现（台账「月份」列 ＋ 过程资料「时间」列）⇒ 口径归引擎，这里只做转发。
    ⚠️ `months_col` 从 **spec** 传进来（`fill_sheet` 返回的对账计划里**没有**它 ——
       它只回引擎自己认得的键）。
    """
    tpl_fill.set_text_format(ws, plan, months_col)


def build_xlsx(sections: dict, out_dir, *, display: str, ym: str) -> str:
    """三个 sheet → 一本 xlsx ⇒ 返回**成品绝对路径**。

    `sections` = `{"material": side, "mechanical": side, "特殊费用月报表": fee}`
    （`side` 由 `mod05_flow.service.build_ledger` 给、`fee` 由 `mod09_fee.service.build_export_data` 给）。

    - 模板走 `resources.require_template`（缺失 / 被回退 ⇒ **显式拒做**）；
    - ⚠️ 三个 sheet **要么都填、要么不产出** —— 只填两个就交付，第三张会把模板里**别的项目**的
      示例数据整张留给用户（`TAIL-43` 同族）；
    - 产物一律过 `tpl_fill.verify_filled`（逐格 / 尾块以下残留 / 值覆盖不彻底）。
    """
    ym = str(ym or "").strip()
    if len(ym) != 7 or ym[4] != "-":
        raise MustReportError("导出台账：拿不到**报告月**（当前筛选下没有可导出的数据）——"
                              "请先在页面上把项目 / 止月选到有数据的那一档。")
    template = resources.require_template(resources.LEDGER_TEMPLATE)
    out = Path(out_dir) / file_name(display, ym)
    wb = openpyxl.load_workbook(str(template))
    try:
        fee_ws = wb[SHEET_FEE]
        layout_fee_months(fee_ws, sections[SHEET_FEE]['months'])
        for sheet in (SHEET_FEE, *SHEET_OF_CATEGORY.values()):
            wb[sheet]["A1"] = title_of(display, sheet)    # 标题里写着别的项目名 ⇒ 整格替换
        specs = [ledger_spec(sheet, sections.get(cat) or {}, display=display)
                 for cat, sheet in SHEET_OF_CATEGORY.items()]
        specs.append(fee_spec(sections.get(SHEET_FEE) or {}, display=display, ym=ym))
        plan = []
        for sp in specs:
            ws = wb[sp["sheet"]]
            sheet_plan = tpl_fill.fill_sheet(ws, sp)
            if sp.get('months_col'):
                _set_text_fmt(ws, sheet_plan, sp["months_col"])
            if ws.title == SHEET_FEE:
                ws.print_area = f'A1:{get_column_letter(ws.max_column)}{ws.max_row}'
            plan.append(sheet_plan)
        save_workbook(wb, out)
    finally:
        wb.close()
    problems = tpl_fill.verify_filled(out, {"path": str(out), "sheets": plan})
    if problems:
        raise MustReportError(
            "台账成品**显示区对账未通过** ⇒ 已中止，未交付："
            + "；".join(problems[:5]) + ("" if len(problems) <= 5 else "（等共 %d 条）" % len(problems)))
    return str(out)


def build_zip(paths, out_dir, name: str) -> str:
    """把**每个项目一本**的工作簿打成一个 zip（≥2 个项目时的交付形态）⇒ 返回 zip 路径。"""
    out = Path(out_dir) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(str(p), Path(p).name)
    return str(out)


__all__ = ["SHEET_OF_CATEGORY", "SHEET_FEE", "TITLE_SUFFIX", "FILE_SUFFIX", "LEDGER_COL",
           "CUT_MONTH_FMT", "TEXT_FMT", "money", "title_of", "month_text", "ledger_spec",
           "fee_spec", "layout_fee_months", "file_name", "build_xlsx",
           "build_zip"]
