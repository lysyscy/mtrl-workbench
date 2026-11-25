"""设备台账的三套打印表。输入是同一事务取出的普通数据快照。"""
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import to_excel
from openpyxl.worksheet.pagebreak import Break

from app.report_export.save import Formula, TextFormula, set_formula, workbook_bytes


MAIN_WIDTH = [23.675, 18.3416666666667, 22.325, 8.675, 28.25, 13.0083333333333, 15.0083333333333,
              13.3416666666667, 12.3416666666667, 16.0083333333333, 8.675, 8.675, 33.9666666666667,
              12, 12, 14, 16, 24, 20, 11, 48]
TRANSFER_WIDTH = [23.675, 18.3416666666667, 43.0083333333333, 8.675, 14.4833333333333,
                  15.0083333333333, 15.0083333333333, 15.0083333333333, 12.3416666666667,
                  13.0083333333333, 8.675, 8.675, 18.375]
INVENTORY_WIDTH = [4.64166666666667, 19.6416666666667, 14.6416666666667, 6.70833333333333,
                   11.6416666666667, 7.85833333333333, 14.1416666666667, 7.64166666666667,
                   14.5, 6.64166666666667, 5.64166666666667, 22.7083333333333]
RENT_WIDTH = [4.375, 13.875, 10.25, 5.5, 5.375, 10.125, 11.25, 11, 13]
MAIN_HEADER = ["工机具编号", "名称", "规格型号", "单位", "信息化用购买日期", "购买日期", "购买项目",
               "购买价格", "当前状态", "当前所在项目", "备注", "在账", None, "列租赁表", "列资产账",
               "租赁底稿行", "盘点来源行", "来源", "接续所在项目", "数量", "核对说明"]
HISTORY_HEADER = "工机具编号 名称 规格型号 单位 购买日期 购买项目 购买价格".split()
RENT_HEADER = "序号 名称 规格型号 单位 数量 租赁单价（元） 金额（元） 类别 分布".split()
STATE = {"in_use": "在用", "damaged": "损坏", "pending_scrap": "待报废", "scrapped": "报废"}
SCOPE = {"current_asset": "是", "fixed_asset": "固定资产", "off_book": "否"}
BORDER = Side(style="thin", color="000000")
GRID_BORDER = Border(left=BORDER, right=BORDER, top=BORDER, bottom=BORDER)
HEADER_FILL = PatternFill("solid", fgColor="E9EFF5")
NUMBER_FORMAT = "General"
INVENTORY_MONEY = "#,##0.00##"


def sheet_setup(ws, widths, orientation=None):
    ws.sheet_format.defaultColWidth = 9
    ws.sheet_format.defaultRowHeight = 14.25
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    if orientation:
        ws.page_setup.orientation = orientation
        ws.page_setup.paperSize = ws.PAPERSIZE_A4


def put(ws, r, values):
    for i, value in enumerate(values, 1):
        cell = ws.cell(r, i)
        cell.value = value
        if isinstance(value, str):
            cell.data_type = "s"  # Workbook text never becomes an Excel expression.


def style_cell(cell, size=12, *, bold=False, horizontal="center", shrink=False):
    cell.font = Font(name="宋体", size=size, bold=bold)
    cell.alignment = Alignment(horizontal=horizontal, vertical="center", wrap_text=not shrink, shrink_to_fit=shrink)


def grid(ws, first, end, width, *, size=12, bold=False, fill=None, money=(), right=()):
    for row in ws.iter_rows(min_row=first, max_row=end, max_col=width):
        for c in row:
            c.border = GRID_BORDER
            style_cell(c, size, bold=bold, horizontal="right" if c.column in right else "center")
            if fill:
                c.fill = fill
            if c.column in money:
                c.number_format = INVENTORY_MONEY


def distribution_layout(ws, widths, header, count):
    sheet_setup(ws, widths, "portrait")
    ws.sheet_format.defaultRowHeight = 22.5
    ws.freeze_panes = f"A{header + 1}"
    ws.print_title_rows = f"1:{header}"
    ws.print_area = f"A1:{get_column_letter(count)}{ws.max_row}"
    grid(ws, header, header, count, size=11, bold=True, fill=HEADER_FILL)
    grid(ws, header + 1, ws.max_row, count, size=10)


def main_sheet(ws, items, turnover, transfer_sheet, scrap_sheet):
    widths = MAIN_WIDTH.copy()
    if turnover:
        widths[2], widths[12] = 16.85, 3
    ws.merge_cells("A1:K1")
    ws["A1"] = "四分公司周转材料分布台账" if turnover else "四分公司大型工机具分布台账"
    style_cell(ws["A1"], 22, bold=True)
    ws.row_dimensions[1].height = 31
    put(ws, 2, MAIN_HEADER)
    for n, r in enumerate(items, 3):
        dt = r["purchase_date"]
        date_text = r["purchase_date_text"] or (dt.strftime("%Y%m%d") if dt else None)
        lists_inventory = r.get("source_lists_inventory")
        if lists_inventory is None:
            lists_inventory = r["inventory_item_id"] is not None
        put(ws, n, [r["code"], r["name"], r["spec"], r["unit"], dt,
                    date_text, r["purchase_project"], r["purchase_price"],
                    STATE[r["status"]], r["current_project"], r["remark"], SCOPE[r["asset_scope"]],
                    None, {"yes": "是", "no": "否", "pending": "待核"}[r["in_rental"]],
                    "是" if lists_inventory else "否", r["rental_source_row"], r["inventory_source_row"],
                    r["source_info"], r["current_project"], r["quantity"], None])
        # Stable identifiers may contain a sequence suffix or an earlier name/date.
        if dt and date_text == dt.strftime("%Y%m%d") and r["code"] == f"{r['name']}-{date_text}":
            set_formula(ws[f"A{n}"], TextFormula(f'=CONCATENATE(B{n},"-",F{n})', r["code"]))
        status = STATE[r["status"]]
        set_formula(ws[f"I{n}"], TextFormula(f'=IF(COUNTIF(\'{scrap_sheet}\'!A:A,A{n})>=1,"报废","{status}")', status))
        lookup = f"=_xlfn.XLOOKUP(A{n},'{transfer_sheet}'!A:A,'{transfer_sheet}'!I:I,S{n},0,-1)"
        set_formula(ws[f"J{n}"], TextFormula(lookup, r["current_project"]))
    distribution_layout(ws, widths, 2, 21)


def history_sheet(ws, rows, main, equipment, *, scrap, turnover):
    widths = TRANSFER_WIDTH.copy()
    if scrap or turnover:
        widths[4] = 13.0083333333333
    if scrap:
        widths[9] = 24.3916666666667
        headers = HISTORY_HEADER + ["报废项目", "报废日期", "报废原因", "数量"]
        widths = widths[:11]
    else:
        headers = HISTORY_HEADER + ["调出项目", "调入项目", "调拨日期", "备注", "来源" if turnover else "在账"]
        if turnover:
            widths = widths[:12]
            widths[-1] = 24
    put(ws, 1, headers)
    for n, r in enumerate(rows, 2):
        tail = [r["original_project"], r["scrap_date"], r["reason"], r["quantity"]] if scrap else [
            r["from_project"], r["to_project"], r["transfer_date"], r["remark"], None]
        put(ws, n, [r["code"], None, None, None, None, None, r.get("purchase_price"), *tail])
        item = equipment[r["equipment_id"]]
        for col, source, key in (("B", 2, "name"), ("C", 3, "spec"), ("D", 4, "unit"),
                                 ("E", 5, "purchase_date"), ("F", 7, "purchase_project"), ("G", 8, "purchase_price")):
            if col == "G" and scrap:
                continue
            lookup = f"VLOOKUP(A{n},'{main}'!A:U,{source},FALSE)"
            expr = f'=IFERROR(IF(ISBLANK(INDEX(\'{main}\'!A:U,MATCH(A{n},\'{main}\'!A:A,0),{source})),"",{lookup}),"")'
            value = item[key]
            if key == "purchase_date" and isinstance(value, date):
                value = to_excel(value)
                ws[f"E{n}"].number_format = "yyyy-mm-dd"
            formula = TextFormula(expr, value) if isinstance(value, str) else Formula(expr, value)
            set_formula(ws[f"{col}{n}"], formula)
        if not scrap and not turnover:
            expr = f'=IFERROR(VLOOKUP(A{n},\'{main}\'!A:L,12,FALSE),"")'
            set_formula(ws[f"L{n}"], TextFormula(expr, SCOPE[item["asset_scope"]]))
    distribution_layout(ws, widths, 1, len(headers))


def equipment_distribution_xlsx(snapshot):
    wb = Workbook()
    wb.remove(wb.active)
    for category, main, prefix in (("equipment", "工机具基础信息", ""), ("turnover", "周转材料", "周转材料")):
        transfer, scrap = prefix + "调拨记录", prefix + "报废记录"
        items = [r for r in snapshot["items"] if r["item_category"] == category]
        main_sheet(wb.create_sheet(main), items, bool(prefix), transfer, scrap)
        for key, title in (("transfers", transfer), ("scraps", scrap)):
            rows = [r for r in snapshot[key] if r["item_category"] == category]
            if key == "transfers":
                # XLOOKUP searches from the bottom, with undated history below dated rows in priority.
                rows.sort(key=lambda row: (row["transfer_date"] is not None, row["transfer_date"] or date.min, row["id"]))
            history_sheet(wb.create_sheet(title), rows, main, {i["id"]: i for i in items},
                          scrap=key == "scraps", turnover=bool(prefix))
    return workbook_bytes(wb)


def rental_page_setup(ws, *, fit_height=0):
    sheet_setup(ws, RENT_WIDTH, "portrait")
    ws.page_setup.blackAndWhite = True
    ws.page_setup.horizontalDpi = 600
    ws.page_margins.left = ws.page_margins.right = .5
    ws.page_margins.top = ws.page_margins.bottom = .6
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = fit_height


def rental_row_height(count):
    if count <= 3:
        return 36
    if count <= 12:
        return 30
    if count <= 28:
        return max(18, min(29, 510 // count))
    return max(15.5, 510 / count)


def rental_table(ws, first, period, project):
    count = len(project["lines"])
    data_row = first + 3
    subtotal = data_row + (4 if count < 3 else count)
    footer = subtotal + 1
    ws.merge_cells(f"A{first}:I{first}")
    style_cell(ws.cell(first, 1, "租赁费明细（费用划转）"), 16, bold=True)
    info = first + 1
    ws.merge_cells(f"A{info}:D{info}")
    ws.merge_cells(f"E{info}:F{info}")
    ws.merge_cells(f"G{info}:I{info}")
    put(ws, info, ["单位：" + project["project_name"]])
    style_cell(ws.cell(info, 1), horizontal="left", shrink=True)
    style_cell(ws.cell(info, 5, "1012其他安装工程"), shrink=True)
    style_cell(ws.cell(info, 7, period))
    ws.cell(info, 7).number_format = 'yyyy"年"m"月"'
    for col in (*range(1, 5), *range(7, 10)):
        ws.cell(info, col).border = Border(bottom=BORDER)
    put(ws, first + 2, RENT_HEADER)
    grid(ws, first + 2, first + 2, 9, bold=True)
    grid(ws, data_row, subtotal - 1, 9, size=10.5 if count > 28 else 12, right=(6, 7))
    grid(ws, subtotal, subtotal, 9, bold=True, right=(7,))
    for row, height in ((first, 21), (info, 21), (first + 2, 34.5), (subtotal, 30), (footer, 43)):
        ws.row_dimensions[row].height = height
    for n in range(data_row, subtotal):
        ws.row_dimensions[n].height = rental_row_height(count)
    for index, line in enumerate(project["lines"], 1):
        n = data_row + index - 1
        put(ws, n, [index, line["name"], line["spec"], line["unit"], line["quantity"], line["unit_price"],
                    line["amount"], line["category_label"], line["distribution_note"]])
        if line["amount"] is not None and line["quantity"] is not None and line["unit_price"] is not None:
            set_formula(ws[f"G{n}"], Formula(
                f'=IF(COUNT(E{n}:F{n})=2,ROUND(E{n}*F{n},4),"")', line["amount"]))
    put(ws, subtotal, [None, "合计："])
    span = f"G{data_row}:G{subtotal-1}"
    set_formula(ws[f"G{subtotal}"], Formula(f'=IF(COUNT({span}),SUM({span}),"")', project["subtotal"]))
    ws.merge_cells(f"C{footer}:D{footer}")
    ws.merge_cells(f"G{footer}:I{footer}")
    style_cell(ws.cell(footer, 2, "审核人："), horizontal="right")
    style_cell(ws.cell(footer, 7, "制表人："))
    for cell in ws[footer][:9]:
        cell.border = Border(top=BORDER)
    return subtotal, footer


def rental_pages(projects):
    batch, fit_height, has_printable = [], 0, False
    for project in projects:
        count = len(project["lines"])
        printable = bool(project["subtotal"])
        # A4 less the margins and fixed rows leaves about 606 pt for the body at 100%.
        oversized = printable and count * rental_row_height(count) > 590
        if printable and has_printable and (fit_height or oversized):
            yield batch, fit_height, has_printable
            batch, has_printable = [], False
        if printable:
            fit_height, has_printable = int(oversized), True
        batch.append(project)
    yield batch, fit_height, has_printable


def equipment_rental_xlsx(snapshot):
    wb = Workbook()
    ws = wb.active
    ws.title = "分公司租赁费"
    period = date.fromisoformat(snapshot["month"] + "-01")
    totals, total_row = [], 3
    for index, (projects, fit_height, has_printable) in enumerate(rental_pages(snapshot["projects"])):
        title = "租赁长表" if fit_height else "租赁续表"
        page = wb.create_sheet(f"{title} {index}") if index else ws
        rental_page_setup(page, fit_height=fit_height)
        first, areas = (1 if has_printable else 3), []
        for project in projects:
            subtotal, footer = rental_table(page, first, period, project)
            totals.append(f"'{page.title}'!G{subtotal}" if index else f"G{subtotal}")
            if project["subtotal"]:
                areas.append(f"A{first}:I{footer}")
                if not fit_height:
                    page.row_breaks.append(Break(id=footer))
            # Non-adjacent print areas keep each project on its own page.
            first = footer + 2
        page.print_area = areas or ["A1:I1"]
        if not index:
            total_row = first
    first = total_row
    put(ws, first, [None, "总计"])
    style_cell(ws.cell(first, 2), bold=True)
    style_cell(ws.cell(first, 7), bold=True, horizontal="right")
    if totals and snapshot["grand_total"] is not None:
        set_formula(ws[f"G{first}"], Formula("=" + "+".join(f"N({ref})" for ref in totals), snapshot["grand_total"]))
    return workbook_bytes(wb)


def inventory_cover(cover):
    cover.title = "封皮"
    sheet_setup(cover, [9, 13, 13, 12.6416666666667, 9, 13, 9.35833333333333, 18.75, 9, 7.425, 9, 13], "landscape")
    cover.print_options.horizontalCentered = True
    for address in ("C3:K3", "C4:K4", "C5:K5", "B6:D6", "E6:H6", "I6:J6", "C7:G7", "C8:G8",
                    "C9:K9", "C10:K10", "A13:K14"):
        cover.merge_cells(address)
    for column in cover.column_dimensions.values():
        column.font = Font(name="宋体", charset=134, size=12)
        column.alignment = Alignment(vertical="center")
    for row, height in ((3, 62.15), (4, 36), (5, 36), (6, 36), (7, 36), (8, 27), (9, 27), (10, 27)):
        cover.row_dimensions[row].height = height
        cover.row_dimensions[row].font = Font(name="宋体", charset=134, size=12)
    cells = {
        "C3": ("河南省安装集团有限责任公司", 24, "center"),
        "C4": ("第四工程公司", 20, "center"),
        "C5": ("流动资产盘点表", 20, "center"),
        "B6": ("流动资产金额总计（原值）：", 14, "center"),
        "C7": ("其     中：大型工机具：", 14, "right"),
        "C8": ("周转材料：", 14, "right"),
        "A13": ("单位主管：             财务主管：               资产主管：              制表人：   ", 16, None),
    }
    for address in ("K6", "I7", "I8"):
        cells[address] = ("元", 14, None)
    for address in ("J7", "K7", "J8", "K8", "C9", "C10"):
        cells[address] = (None, 14, None)
    for address in ("E6", "I6", "H7", "H8"):
        cells[address] = (None, 14, "center")
    for address, (value, size, align) in cells.items():
        cell = cover[address]
        cell.value = value
        cell.font = Font(name="宋体", charset=134, size=size, bold=address == "C3")
        cell.alignment = Alignment(horizontal=align, vertical="center")
    cover["E6"].number_format = '[DBNum2][$RMB]General;[Red][DBNum2][$RMB]General'
    cover["I6"].number_format = r'"￥"#,##0.00;[Red]"￥"\-#,##0.00'
    for address in ("H7", "H8"):
        cover[address].number_format = r'"￥"#,##0.00_);[Red]\("￥"#,##0.00\)'
    cover.print_area = "A1:K14"


def equipment_inventory_xlsx(items):
    wb = Workbook()
    cover = wb.active
    inventory_cover(cover)
    counted_totals = []
    for category, title, cover_row in (("tool", "流动资产盘点表", 7), ("turnover", "周转材料", 8)):
        ws = wb.create_sheet(title)
        inventory_page_setup(ws, category)
        n = 5
        amounts = {"G": [], "I": [], "K": []}
        for r in items:
            if r["category"] != category or not r["is_active"]:
                continue
            put(ws, n, [n-4, r["name"], r["spec"], r["unit"], r["unit_price"], r["book_qty"], r["book_amount"],
                        r["count_qty"], r["count_amount"], r["diff_qty"], r["diff_amount"], r["diff_reason"]])
            for col, qty, quantity, key in (("G", "F", "book_qty", "book_amount"),
                                           ("I", "H", "count_qty", "count_amount"),
                                           ("K", "J", "diff_qty", "diff_amount")):
                if r[key] is not None:
                    amounts[col].append(r[key])
                    if r["unit_price"] is not None and r[quantity] is not None:
                        expr = f'=IF(COUNT({qty}{n},E{n})=2,ROUND({qty}{n}*E{n},4),"")'
                        set_formula(ws[f"{col}{n}"], Formula(expr, r[key]))
            n += 1
        ws.cell(n, 2, "合计：")
        if n > 5:
            for col, values in amounts.items():
                span = f"{col}5:{col}{n-1}"
                set_formula(ws[f"{col}{n}"], Formula(f'=IF(COUNT({span}),SUM({span}),"")',
                                                    sum(values) if values else None))
        ws.print_area = f"A1:L{n}"
        money = (5, 7, 9, 11)
        grid(ws, 5, n - 1, 12, money=money)
        grid(ws, n, n, 12, bold=True, money=money)
        ws.row_dimensions[n].height = 20.05 if category == "tool" else 23.05
        counted = sum(amounts["I"]) if amounts["I"] or n == 5 else None
        if counted is not None:
            counted_totals.append(counted)
        ref = f"'{title}'!I{n}"
        set_formula(cover[f"H{cover_row}"], Formula(f'={ref}', counted))
    overall = sum(counted_totals) if counted_totals else None
    # A populated detail sheet can have no known amounts, so its total formula returns empty text.
    total_formula = '=H7+H8' if len(counted_totals) == 2 else '=IF(COUNT(H7:H8),SUM(H7:H8),"")'
    set_formula(cover["I6"], Formula(total_formula, overall))
    set_formula(cover["E6"], Formula('=I6', overall))
    return workbook_bytes(wb)


def inventory_page_setup(ws, category):
    sheet_setup(ws, INVENTORY_WIDTH, "landscape")
    ws.page_setup.horizontalDpi, ws.page_setup.verticalDpi = 600, 180
    ws.page_margins.left, ws.page_margins.right = .551, .591
    ws.page_margins.top, ws.page_margins.bottom = .315, .748
    ws.page_margins.header = ws.page_margins.footer = .315
    ws.print_title_rows = "1:4"
    tool = category == "tool"
    ws.sheet_format.defaultRowHeight = 17.5 if tool else 23.05
    for row, height in enumerate((33, 18, 17.5, 17.5) if tool else (22.5, 18.75, 30, 45.75), 1):
        ws.row_dimensions[row].height = height
    grid(ws, 3, 4, 12)
    for address in ("A1:L1", "A2:B2", "C2:E2", "F2:H2", "J2:L2", "F3:G3", "H3:I3",
                    "A3:A4", "B3:B4", "C3:C4", "D3:D4", "E3:E4", "K3:K4", "L3:L4"):
        ws.merge_cells(address)
    ws["A1"] = "流   动   资   产   盘   点   表"
    style_cell(ws["A1"], 18, bold=True)
    ws["A2"] = "类别：" + ("在用工具" if tool else "周转材料")
    style_cell(ws["A2"], 12 if tool else 14, horizontal="left")
    if tool:
        for cell in ws[2][:2]:
            cell.border = Border(bottom=BORDER)
        ws.freeze_panes = "A5"
    for address, label in {
        "A3": "序          号", "B3": "名   称", "C3": "规   格", "D3": "单  位", "E3": "单价",
        "F3": "帐面数", "H3": "盘点数", "J3": "盈亏      数量", "K3": "盈亏      金额", "L3": "盈亏原因",
        "F4": "数量", "G4": "金额", "H4": "数量", "I4": "金额", "J4": "盈+        亏－      毁×",
    }.items():
        ws[address] = label
