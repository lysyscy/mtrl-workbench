"""设备台账的三套打印表。输入是同一事务取出的普通数据快照。"""
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import to_excel

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
MAIN_HEADER = ["工机具编号", "名称", "规格型号", "单位", "信息化用购买日期", "购买日期", "购买项目",
               "购买价格", "当前状态", "当前所在项目", "备注", "在账", None, "列租赁表", "列资产账",
               "租赁底稿行", "盘点来源行", "来源", "接续所在项目", "数量", "核对说明"]
HISTORY_HEADER = "工机具编号 名称 规格型号 单位 购买日期 购买项目 购买价格".split()
RENT_HEADER = "序号 名称 规格型号 单位 数量 租赁单价（元） 金额（元） 类别 分布".split()
STATE = {"in_use": "在用", "damaged": "损坏", "pending_scrap": "待报废", "scrapped": "报废"}
SCOPE = {"current_asset": "是", "fixed_asset": "固定资产", "off_book": "否"}
BORDER = Side(style="thin", color="666666")


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


def grid(ws, first, end, width):
    for row in ws.iter_rows(min_row=first, max_row=end, max_col=width):
        for c in row:
            c.border = Border(left=BORDER, right=BORDER, top=BORDER, bottom=BORDER)
            c.alignment = Alignment(vertical="center", wrap_text=True)
            c.font = Font(name="宋体", size=10, bold=c.row == first)


def main_sheet(ws, items, turnover, transfer_sheet, scrap_sheet):
    widths = MAIN_WIDTH.copy()
    if turnover:
        widths[2], widths[12] = 16.85, 3
    sheet_setup(ws, widths, None if turnover else "portrait")
    ws.merge_cells("A1:K1")
    ws["A1"] = "四分公司周转材料分布台账" if turnover else "四分公司大型工机具分布台账"
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
    grid(ws, 2, ws.max_row, 21)


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
    sheet_setup(ws, widths, None if scrap else "portrait")
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
    grid(ws, 1, ws.max_row, len(headers))


def equipment_distribution_xlsx(snapshot):
    wb = Workbook()
    wb.remove(wb.active)
    for category, main, prefix in (("equipment", "工机具基础信息", ""), ("turnover", "周转材料", "周转材料")):
        transfer, scrap = prefix + "调拨记录", prefix + "报废记录"
        items = [r for r in snapshot["items"] if r["item_category"] == category]
        main_sheet(wb.create_sheet(main), items, bool(prefix), transfer, scrap)
        for key, title in (("transfers", transfer), ("scraps", scrap)):
            rows = [r for r in snapshot[key] if r["item_category"] == category]
            history_sheet(wb.create_sheet(title), rows, main, {i["id"]: i for i in items},
                          scrap=key == "scraps", turnover=bool(prefix))
    return workbook_bytes(wb)


def equipment_rental_xlsx(snapshot):
    wb = Workbook()
    ws = wb.active
    ws.title = "分公司租赁费"
    sheet_setup(ws, [4.375, 13.875, 10.25, 5.5, 5.375, 10.125, 11.25, 11, 9], "portrait")
    ws.page_setup.blackAndWhite = True
    ws.page_setup.horizontalDpi = 600
    ws.print_options.horizontalCentered = ws.print_options.verticalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = ws.page_setup.fitToHeight = 1
    first, totals, areas = 1, [], []
    for project in snapshot["projects"]:
        for offset, start, end in ((0, 1, 9), (1, 1, 4), (1, 5, 6), (1, 7, 9)):
            ws.merge_cells(start_row=first + offset, end_row=first + offset, start_column=start, end_column=end)
        ws.cell(first, 1, "租赁费明细（费用划转）")
        put(ws, first + 1, ["单位：" + project["project_name"]])
        ws.cell(first + 1, 5, "1012其他安装工程")
        ws.cell(first + 1, 7, date.fromisoformat(snapshot["month"] + "-01")).number_format = 'yyyy"年"m"月"'
        put(ws, first + 2, RENT_HEADER)
        for index, line in enumerate(project["lines"], 1):
            n = first + 2 + index
            put(ws, n, [index, line["name"], line["spec"], line["unit"], line["quantity"], line["unit_price"],
                        line["amount"], line["category_label"], line["distribution_note"]])
            if line["amount"] is not None:
                set_formula(ws[f"G{n}"], Formula(
                    f'=IF(COUNT(E{n}:F{n})=2,ROUND(E{n}*F{n},4),"")', line["amount"]))
        subtotal = first + 3 + len(project["lines"])
        put(ws, subtotal, [None, "合计"])
        span = f"G{first+3}:G{subtotal-1}"
        set_formula(ws[f"G{subtotal}"], Formula(f'=IF(COUNT({span}),SUM({span}),"")', project["subtotal"]))
        totals.append(f"G{subtotal}")
        ws.merge_cells(f"C{subtotal+1}:D{subtotal+1}")
        ws.merge_cells(f"G{subtotal+1}:I{subtotal+1}")
        ws.cell(subtotal + 1, 1, "制表")
        ws.cell(subtotal + 1, 5, "审核")
        grid(ws, first + 2, subtotal, 9)
        if (project["subtotal"] or 0) > 0:
            areas.append(f"A{first}:I{subtotal+1}")
        first = subtotal + 3
    put(ws, first, [None, "总计"])
    if totals and snapshot["grand_total"] is not None:
        set_formula(ws[f"G{first}"], Formula("=" + "+".join(f"N({ref})" for ref in totals), snapshot["grand_total"]))
    ws.print_area = areas or [f"A{first}:I{first}"]
    return workbook_bytes(wb)


def equipment_inventory_xlsx(items):
    wb = Workbook()
    cover = wb.active
    cover.title = "封皮"
    sheet_setup(cover, [9, 9, 9, 12.6416666666667, 9, 9, 9.35833333333333, 18.75, 9, 7.425, 9], "landscape")
    for address in ("C3:K3", "C4:K4", "C5:K5", "B6:D6", "E6:H6", "I6:J6", "C7:G7", "C8:G8",
                    "C9:K9", "C10:K10", "A13:K14"):
        cover.merge_cells(address)
    cover["C3"] = "流动资产盘点表"
    cover["C4"] = "第四工程公司"
    cover["B6"] = "合计"
    counted_totals = []
    for category, title, cover_row in (("tool", "流动资产盘点表", 7), ("turnover", "周转材料", 8)):
        ws = wb.create_sheet(title)
        sheet_setup(ws, INVENTORY_WIDTH, "landscape")
        ws.page_setup.scale = 92
        ws.page_setup.horizontalDpi, ws.page_setup.verticalDpi = 600, 180
        ws.page_margins.left, ws.page_margins.right = .551181102362205, .590551181102362
        ws.page_margins.top, ws.page_margins.bottom = .31496062992126, .748031496062992
        ws.page_margins.header = ws.page_margins.footer = .31496062992126
        for address in ("A1:L1", "A2:B2", "C2:E2", "F2:H2", "J2:L2", "F3:G3", "H3:I3",
                        "A3:A4", "B3:B4", "C3:C4", "D3:D4", "E3:E4", "K3:K4", "L3:L4"):
            ws.merge_cells(address)
        ws["A1"] = "流   动   资   产   盘   点   表"
        ws["A2"] = "类别：" + ("在用工具" if category == "tool" else title)
        for address, label in {"A3":"序          号", "B3":"名   称", "C3":"规   格", "D3":"单  位", "E3":"单价",
                               "F3":"帐面数", "H3":"盘点数", "J3":"盈亏      数量", "K3":"盈亏      金额", "L3":"盈亏原因",
                               "F4":"数量", "G4":"金额", "H4":"数量", "I4":"金额", "J4":"盈+        亏－      毁×"}.items():
            ws[address] = label
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
        ws.cell(n, 2, "合计")
        if n > 5:
            for col, values in amounts.items():
                span = f"{col}5:{col}{n-1}"
                set_formula(ws[f"{col}{n}"], Formula(f'=IF(COUNT({span}),SUM({span}),"")',
                                                    sum(values) if values else None))
        ws.print_area, ws.print_title_rows = f"A1:L{n}", "1:4"
        grid(ws, 3, n, 12)
        cover[f"C{cover_row}"] = title
        counted = sum(amounts["I"]) if amounts["I"] else None
        if counted is not None:
            counted_totals.append(counted)
        ref = f"'{title}'!I{n}"
        set_formula(cover[f"H{cover_row}"], Formula(f'=IF(ISNUMBER({ref}),{ref},"")', counted))
    overall = sum(counted_totals) if counted_totals else None
    set_formula(cover["I6"], Formula('=IF(COUNT(H7:H8),SUM(H7:H8),"")', overall))
    set_formula(cover["E6"], Formula('=IF(ISNUMBER(I6),I6,"")', overall))
    return workbook_bytes(wb)
