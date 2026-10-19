"""Frozen mechanical reports using the approved four-sheet company template."""
from copy import copy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import column_index_from_string, get_column_letter

from app.core.errors import MustReportError
from app.report_export.resources import MECHANICAL_TEMPLATE, require_template
from app.report_export.save import save_workbook

MONEY_FIELDS = {'amount', 'rate', 'net', 'qty', 'plan', 'used'}
ZERO_FIELDS = ('device', 'spec', 'unit', 'qty', 'rate', 'amount', 'tax', 'net',
               'date', 'use', 'team', 'reviewer', 'vendor', 'plate', 'memo')
MONTHLY_FIELDS = ('device', 'spec', 'unit', 'plan', 'used', 'rate', 'amount',
                  'date', 'vendor', 'reviewer', 'tax', 'memo')
CATEGORY_COLUMNS = {'zero': 'mech_2', 'monthly': 'mech_3', 'internal': 'mech_1'}


def numeric(value):
    if value in (None, ''):
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError) as exc:
        raise MustReportError('报表含有无效金额，请回编辑页核对') from exc


def put(sheet, row, col, value, *, number=False):
    cell = sheet.cell(row, col)
    if number:
        cell.value = numeric(value)
    else:
        cell.value = '' if value is None else str(value)
        cell.data_type = 's'
    return cell


def append_row(sheet, row, values, styles, numeric_cols=()):
    for col, value in enumerate(values, 1):
        cell = put(sheet, row, col, value, number=col in numeric_cols)
        cell._style = copy(styles[col - 1])
    sheet.row_dimensions[row].height = 22.5
    sheet.row_dimensions[row].hidden = False
    sheet.row_dimensions[row].outlineLevel = 0


def amount(data, wh, ym, column):
    return next((r['values'].get(column) for r in data.get('annual_effective', data['effective'])
                 if r['warehouse'] == wh and r['ym'] == ym), None)


def history(data, wh):
    return next((h for h in data['histories'] if h['warehouse'] == wh), {})


def cumulative(data, wh, column, ym):
    """Consume the same confirmed cumulative used by the workbench."""
    category = {'mech_0': 'company', 'mech_1': 'internal', 'mech_2': 'zero', 'mech_3': 'monthly'}.get(column)
    summary = next((r for r in data.get('summary', []) if r['warehouse'] == wh and r['ym'] == ym), None)
    return numeric(summary['cumulative'].get(category)) if summary else None


def annual_values(data, wh, hist, source, year, category):
    """Rebase the two calendar-year blocks without changing the dates of source facts."""
    cells = source.get('cells', {})
    if not cells:
        source_year = None
    else:
        source_year = source.get('source', {}).get('year') or str(hist.get('base_month') or '')[:4]
        if not str(source_year).isdigit() or len(str(source_year)) != 4:
            raise MustReportError('年度历史缺少年份依据，请补齐来源年份后再导出')
        source_year = int(source_year)
    source_months = {}
    if source_year:
        for month in range(1, 13):
            source_months[f'{source_year - 1}-{month:02d}'] = cells.get(get_column_letter(3 + month))
            source_months[f'{source_year}-{month:02d}'] = cells.get(get_column_letter(15 + month))

    def monthly(ym):
        adopted = amount(data, wh, ym, CATEGORY_COLUMNS[category]) if category in CATEGORY_COLUMNS else None
        return numeric(adopted if adopted is not None else source_months.get(ym))

    values = dict(cells)
    for month in range(1, 13):
        values[get_column_letter(3 + month)] = monthly(f'{year - 1}-{month:02d}')
        values[get_column_letter(15 + month)] = monthly(f'{year}-{month:02d}')
    if source_year == year:
        values['C'] = numeric(cells.get('C'))
    elif source_year and year > source_year:
        earlier = [numeric(cells.get('C'))] + [monthly(f'{old_year}-{month:02d}')
                   for old_year in range(source_year - 1, year - 1) for month in range(1, 13)]
        values['C'] = sum(earlier, Decimal(0)) if all(v is not None for v in earlier) else None
    else:
        # The old opening total cannot be split into earlier years without source evidence.
        values['C'] = None
    return values


def build(data):
    ym = data.get('ym', '')
    if len(ym) != 7 or not data.get('projects'):
        raise MustReportError('请选择报表月份和至少一个项目')
    wb = load_workbook(require_template(MECHANICAL_TEMPLATE))
    warnings = []
    styles = [[copy(sheet.cell(first, col)._style) for col in range(1, width + 1)]
              for sheet, first, width in zip(wb, (6, 5, 5, 2), (15, 17, 15, 56))]
    for sheet in wb:
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str) and '2026年9月' in cell.value:
                    cell.value = cell.value.replace('2026年9月', f'{ym[:4]}年{int(ym[5:])}月')
    summary = wb.worksheets[0]
    summary.row_dimensions[5].height = 33
    for i, project in enumerate(data['projects'], 6):
        wh = project['warehouse']
        values = [i - 5, project['name'], None, None,
                  cumulative(data, wh, 'mech_2', ym), cumulative(data, wh, 'mech_3', ym),
                  None, cumulative(data, wh, 'mech_1', ym), cumulative(data, wh, 'mech_0', ym),
                  amount(data, wh, ym, 'mech_2'), amount(data, wh, ym, 'mech_3'), None,
                  amount(data, wh, ym, 'mech_1'), amount(data, wh, ym, 'mech_0'), None]
        metadata = history(data, wh).get('meta_at', {}).get(ym, {})
        values[2:4] = [metadata.get('year'), metadata.get('month')]
        append_row(summary, i, values, styles[0], range(5, 15))
    total_row = summary.max_row + 1
    append_row(summary, total_row, [None] * 15, styles[0])
    put(summary, total_row, 1, '合计')
    summary.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=2)
    for col in range(5, 15):
        values = [numeric(summary.cell(r, col).value) for r in range(6, total_row)]
        put(summary, total_row, col, sum(values, Decimal(0)) if all(v is not None for v in values) else None, number=True)
    for sheet_index, category, fields, total_col, net_col in (
            (1, 'zero', ZERO_FIELDS, 7, 9), (2, 'monthly', MONTHLY_FIELDS, 8, 15)):
        sheet = wb.worksheets[sheet_index]
        row_no = 5
        for group_no, project in enumerate(data['projects'], 1):
            wh = project['warehouse']
            detail = next((r for r in data['details'] if r['warehouse'] == wh and r['category'] == category), None)
            rows = detail['rows'] if detail else []
            gross = detail['totals']['gross'] if detail else None
            net = detail['totals']['net'] if detail else None
            append_row(sheet, row_no, [None] * sheet.max_column, styles[sheet_index])
            put(sheet, row_no, 1, group_no, number=True)
            put(sheet, row_no, 2, project['name'])
            sheet.merge_cells(start_row=row_no, start_column=2, end_row=row_no, end_column=3)
            put(sheet, row_no, total_col, gross, number=True)
            put(sheet, row_no, net_col, net, number=True)
            for cell in sheet[row_no]:
                cell.fill = PatternFill('solid', fgColor='E8EEF5')
                cell.font = Font(name=cell.font.name or '宋体', size=cell.font.sz or 10, bold=True, color='223B54')
            row_no += 1
            for n, row in enumerate(rows, 1):
                values = [n] + [row.get(field) for field in fields]
                if category == 'monthly':
                    # M preserves the original report note; plate remains separate in the system.
                    values += [None, row.get('net')]
                numeric_cols = [1] + [i + 2 for i, field in enumerate(fields) if field in {'amount', 'rate', 'net'}]
                for i, field in enumerate(fields, 2):
                    if field in {'qty', 'plan', 'used'} and row.get(field) not in (None, ''):
                        try:
                            numeric(row[field])
                            numeric_cols.append(i)
                        except MustReportError:
                            pass
                if category == 'monthly':
                    numeric_cols += [15]
                append_row(sheet, row_no, values, styles[sheet_index], numeric_cols)
                row_no += 1
            if not rows:
                warnings.append(f'{project["name"]}：{"零租" if category == "zero" else "包月"}明细未取得')
            if detail and detail.get('issues'):
                warnings.append(f'{project["name"]}：{len(detail["issues"])}行字段待补')
            effective = amount(data, wh, ym, CATEGORY_COLUMNS[category])
            if numeric(effective) != numeric(gross):
                warnings.append(f'{project["name"]}：{"零租" if category == "zero" else "包月"}明细合计与已采用金额不同')
    annual = wb.worksheets[3]
    annual.page_setup.orientation = 'landscape'
    annual.page_setup.paperSize = '8'
    annual.row_dimensions[1].height = 33
    year = int(ym[:4])
    for month in range(1, 13):
        put(annual, 1, 3 + month, f'{year - 1}年{month}月')
        put(annual, 1, 15 + month, f'{year}年{month}月')
    row_no = 2
    for project in data['projects']:
        wh, hist = project['warehouse'], history(data, project['warehouse'])
        start = row_no
        for category, label in [('zero', '当月零租费'), ('monthly', '当月包月费'),
                                ('weekly', '当月周材费'), ('internal', '当月内租费'), ('total', '合计')]:
            append_row(annual, row_no, [None] * 56, styles[3])
            put(annual, row_no, 1, project['name'])
            put(annual, row_no, 2, label)
            source = next((r for r in hist.get('annual_rows', []) if r['category'] == category), {})
            for col, value in annual_values(data, wh, hist, source, year, category).items():
                put(annual, row_no, column_index_from_string(col), value, number=True)
            if category in CATEGORY_COLUMNS:
                put(annual, row_no, 28, cumulative(data, wh, CATEGORY_COLUMNS[category], ym), number=True)
            if category == 'total':
                for col in list(range(3, 29)) + list(range(34, 57)):
                    values = [numeric(annual.cell(r, col).value) for r in range(start, row_no)]
                    put(annual, row_no, col, sum(values, Decimal(0)) if all(v is not None for v in values) else None, number=True)
                snapshot = next((r for r in data['i8'] if r['warehouse'] == wh), {})
                usage = numeric(snapshot.get('totals', {}).get('usage'))
                i6 = numeric(hist.get('i6'))
                put(annual, row_no, 30, i6, number=True)
                put(annual, row_no, 31, usage, number=True)
                right = i6 + usage if i6 is not None and usage is not None else None
                left = numeric(annual.cell(row_no, 28).value)
                put(annual, row_no, 29, right, number=True)
                put(annual, row_no, 32, left - right if left is not None and right is not None else None, number=True)
                parts = [numeric(snapshot.get('totals', {}).get(k)) for k in ('project', 'team')]
                put(annual, row_no, 33, sum(parts, Decimal(0)) if all(v is not None for v in parts) else None, number=True)
            row_no += 1
    # Earlier archival month columns AH:BD remain in the workbook, outside the current annual print view.
    for sheet, max_col in zip(wb, (15, 16, 15, 33)):
        sheet.print_area = f'A1:{get_column_letter(max_col)}{sheet.max_row}'
    return wb, warnings


def preview(data):
    wb, warnings = build(data)
    sheets = []
    for sheet in wb.worksheets[:3]:
        merged_starts, hidden = {}, set()
        for item in sheet.merged_cells.ranges:
            merged_starts[(item.min_row, item.min_col)] = (item.max_row - item.min_row + 1, item.max_col - item.min_col + 1)
            hidden.update((r, c) for r in range(item.min_row, item.max_row + 1) for c in range(item.min_col, item.max_col + 1)
                          if (r, c) != (item.min_row, item.min_col))
        rows = []
        for row in sheet:
            cells = []
            for cell in row:
                if (cell.row, cell.column) in hidden:
                    continue
                rs, cs = merged_starts.get((cell.row, cell.column), (1, 1))
                value = cell.value
                cells.append({'value': '' if value is None else str(value), 'rowspan': rs, 'colspan': cs})
            rows.append(cells)
        sheets.append({'name': sheet.title, 'rows': rows})
    wb.close()
    return {'ok': True, 'ym': data['ym'], 'projects': data['projects'], 'sheets': sheets, 'warnings': warnings}


def export(data, output_dir):
    wb, _ = build(data)
    return save_workbook(wb, Path(output_dir) / f'机械费报表-{data["ym"]}-{uuid4().hex[:12]}.xlsx')
