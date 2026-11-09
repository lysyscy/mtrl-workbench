"""Protect field placement and audit handoff for the two project layouts."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.dom.minidom import parseString
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
import pytest

from audit import read_plan
from expense_dates import MONTH_FORMAT, format_file
from append_plan import append_plan
from merge import SHEET, merge, with_formula_cache
from snapshot import configure


HEADERS = ['科目', '费用日期', '单据号', '收款单位', '该流程金额', '已付款金额',
           '本月预付款金额', '剩余付款金额', '付款时间', '付款方式', '备注']


def write_plan(path, title, headers, rows, name='材机付款计划'):
    book = Workbook()
    sheet = book.active
    sheet.title = name
    sheet.append([title])
    sheet.append(headers)
    sheet.append([None, None, '外租机械：付款通知书（编号）'])
    for row in rows:
        sheet.append(row)
    book.save(path)


def test_merge_preserves_submitted_details_and_opens_in_audit(tmp_path):
    configure(Path(__file__).resolve().parents[3])
    template, short, long, output = (tmp_path / f'{name}.xlsx'
                                     for name in ('template', 'short', 'long', 'output'))
    write_plan(template, '乙项目10月付款计划（账面数：70万，本月一期+二期预计回款：30万）',
               HEADERS + [None, '核对说明'], [
        ['旧分类', None, '旧单据', '旧单位', 10, 0, 10, 0, None, '现汇', None, None, '旧说明'],
        ['甲  项目10月付款计划（账面数：10万，本月预计回款：20万）'],
    ], SHEET)
    with_template = load_workbook(template)
    with_template[SHEET].sheet_format.defaultRowHeight = 30
    with_template[SHEET].row_dimensions[4].height = 40
    with_template.save(template)
    with_template.close()
    short_headers = [title for title in HEADERS if title not in ('已付款金额', '剩余付款金额')]
    write_plan(short, '甲项目10月付款计划', short_headers, [
        ['集采', '2026.10.06', 'FKTZS1234567890', '甲单位', 120, 35.25, '承兑', None, '原备注'],
        [None, None, None, '项目负责人（签字）：'],
    ])
    write_plan(long, '乙项目11月付款计划', HEADERS, [
        ['外租', None, 'FKTZS1234567890', '乙单位', 90, 0, 12.75, 77.25, None, '现汇'],
        [None, None, None, None, None, None, 2, None, None, None, '原报无编号'],
    ])
    original = {p: p.read_bytes() for p in (short, long, template)}

    with pytest.raises(ValueError, match='标题月份'):
        merge([short, long], template, '2026-11', output)
    assert not output.exists()
    assert merge([short, long], template, '2026-11', output, [short])['rows'] == 3
    with pytest.raises(ValueError, match='尚不存在'):
        merge([short, long], template, '2026-11', output, [short])
    assert all(path.read_bytes() == data for path, data in original.items())

    plan = read_plan(output, '2026-11')
    assert plan['source_warnings'] == []
    assert [row['doc_no'] for row in plan['rows']] == ['FKTZS1234567890', '', 'FKTZS1234567890']
    assert [row['planned_amount'] for row in plan['rows']] == ['12.75', '2.00', '35.25']
    assert plan['structures'][-1]['kind'] == '全表总计'
    book = load_workbook(output, data_only=True)
    try:
        sheet = book[SHEET]
        assert book.sheetnames == [SHEET]
        titles = [sheet[f"A{row['row']}"].value for row in plan['structures'] if row['kind'] == '项目标题']
        assert titles == [
            '乙项目2026年11月份付款计划（账面数：　万，本月一期+二期预计回款：　万）',
            '甲项目2026年11月份付款计划（账面数：　万，本月预计回款：　万）',
        ]
        short_row = plan['rows'][-1]['row']
        assert [sheet[f'{col}{short_row}'].value for col in 'BFHIJKM'] == [
            datetime(2026, 10, 6), None, None, None, '承兑', '原备注', None]
        assert sheet[f'B{short_row}'].number_format == MONTH_FORMAT
        assert sheet[f'G{sheet.max_row}'].value == 50
        assert all(sheet.row_dimensions[row].height == 32 for row in range(1, sheet.max_row + 1))
    finally:
        book.close()


def test_expense_month_changes_only_detail_dates_and_keeps_other_cells(tmp_path):
    configure(Path(__file__).resolve().parents[3])
    path = tmp_path / 'plan.xlsx'
    write_plan(path, '甲项目11月付款计划', HEADERS, [
        ['集采', 2026.1, 'A', '甲单位', 100, 0, 10],
        ['集采', '2026.09.25', 'B', '乙单位', 100, 0, 10],
        ['集采', 46320, 'C', '丙单位', 100, 0, 10],
        ['集采', datetime(2026, 10, 30), 'D', '丁单位', 100, 0, 10],
        ['集采', None, 'E', '戊单位', 100, 0, 10],
    ])
    wb = load_workbook(path)
    wb.active['K4'] = '=SUM(G4:G8)'
    wb.active['L4'] = '人工附注'
    wb.active['M4'] = '已有核对说明'
    wb.create_sheet('其他')['B4'] = '保留文字'
    wb.save(path)
    wb.close()
    before = path.read_bytes()
    with pytest.raises(ValueError, match='B4.*1 月或 10 月'):
        format_file(path, '2026-11', None, tmp_path / 'backups')
    assert path.read_bytes() == before
    wb = load_workbook(path)
    wb.active['B4'].number_format = '0.00_ '
    wb.save(path)
    wb.close()
    before = path.read_bytes()

    receipt = format_file(path, '2026-11', None, tmp_path / 'backups')
    assert Path(receipt['backup']).read_bytes() == before
    with ZipFile(path) as saved, ZipFile(receipt['backup']) as original:
        sheet_name = 'xl/worksheets/sheet1.xml'
        assert all(saved.read(name) == original.read(name) for name in original.namelist()
                   if name not in {sheet_name, 'xl/styles.xml'})
        def other_cells(archive):
            return {cell.getAttribute('r'): cell.toxml()
                    for cell in parseString(archive.read(sheet_name)).getElementsByTagName('c')
                    if cell.getAttribute('r') not in {'B4', 'B5', 'B6', 'B7'}}
        assert other_cells(saved) == other_cells(original)
    wb = load_workbook(path)
    try:
        dates = [wb.active[f'B{i}'] for i in range(4, 9)]
        assert [cell.value for cell in dates] == [
            datetime(2026, 10, 1), datetime(2026, 9, 25), datetime(2026, 10, 25),
            datetime(2026, 10, 30), None]
        assert all(cell.number_format == MONTH_FORMAT for cell in dates[:4])
    finally:
        wb.close()
    assert format_file(path, '2026-11', None, tmp_path / 'backups')['changed'] == 0


def test_append_to_summary_preserves_edited_blocks_and_recomputes_one_total(tmp_path):
    configure(Path(__file__).resolve().parents[3])
    template, original, summary, submitted, output = (tmp_path / f'{name}.xlsx'
                                                     for name in ('layout', 'project', 'summary', 'late', 'new'))
    write_plan(template, '甲项目11月付款计划', HEADERS, [], SHEET)
    write_plan(original, '甲项目11月付款计划', HEADERS, [
        ['集采', '2026年9月', 'A', '甲单位', 100, 0, 15],
    ])
    write_plan(submitted, '内蒙项目10月付款计划', HEADERS, [
        ['机械', '2026.10.25', 'B', '乙单位', 100, 0, 28.5],
    ])
    merge([original], template, '2026-11', summary)
    saved = load_workbook(summary, data_only=True)
    old_sheet = saved[SHEET]
    final_row = old_sheet.max_row
    cached = {f'{letter}{row}': Decimal(str(old_sheet[f'{letter}{row}'].value))
              for row in (final_row - 2, final_row - 1) for letter in 'EG'}
    cached[f'G{final_row}'] = Decimal(15)
    saved.close()

    book = load_workbook(summary)
    sheet = book[SHEET]
    sheet['A1'] = '甲项目2026年11月份付款计划（账面数：18万）'
    sheet['B4'] = datetime(2026, 8, 19)
    sheet['M4'] = '原有人工说明'
    sheet.print_area = f'A1:M{final_row}'
    book.create_sheet('另一张业务表')['B2'] = '=2+3'
    book.create_sheet('__付款核对标记')['A1'] = 'payment-plan-audit:v1'
    book['__付款核对标记'].sheet_state = 'veryHidden'
    content = BytesIO()
    book.save(content)
    book.close()
    summary.write_bytes(with_formula_cache(content, cached))
    before, late = summary.read_bytes(), submitted.read_bytes()
    with pytest.raises(ValueError, match='标题月份'):
        append_plan([submitted], summary, '2026-11', output)
    assert not output.exists()
    append_plan([submitted], summary, '2026-11', output, [submitted])
    assert summary.read_bytes() == before and submitted.read_bytes() == late

    plan = read_plan(output, '2026-11')
    assert not plan['source_warnings']
    assert [(row['project'], row['doc_no']) for row in plan['rows']] == [('甲', 'A'), ('内蒙', 'B')]
    assert [item['kind'] for item in plan['structures']].count('全表总计') == 1
    out = load_workbook(output, data_only=True)
    try:
        sheet = out[SHEET]
        assert sheet['B4'].value == datetime(2026, 8, 19)
        assert sheet['A1'].value.endswith('（账面数：18万）')
        assert sheet['M4'].value == '原有人工说明'
        assert sheet[f'A{final_row}'].value.startswith('内蒙项目2026年11月')
        new_detail = plan['rows'][-1]['row']
        assert sheet[f'B{new_detail}'].value == datetime(2026, 10, 25)
        assert sheet[f'B{new_detail}'].number_format == MONTH_FORMAT
        assert sheet[f'G{sheet.max_row}'].value == 43.5
        assert sheet.print_area.endswith(f'$M${sheet.max_row}')
    finally:
        out.close()
    sheet_path = 'xl/worksheets/sheet1.xml'
    with ZipFile(BytesIO(before)) as old, ZipFile(output) as new:
        assert set(old.namelist()) == set(new.namelist())
        assert all(old.read(name) == new.read(name) for name in old.namelist()
                   if name not in {sheet_path, 'xl/styles.xml', 'xl/workbook.xml'})
        def prior_rows(archive):
            return [row.toxml() for row in parseString(archive.read(sheet_path)).getElementsByTagName('row')
                    if int(row.getAttribute('r')) < final_row]
        assert prior_rows(old) == prior_rows(new)
    another = output.with_name('duplicate.xlsx')
    with pytest.raises(ValueError, match='项目已存在'):
        append_plan([submitted], output, '2026-11', another, [submitted])
    assert not another.exists()

    book = load_workbook(summary)
    book['另一张业务表']['A1'] = f"='{SHEET}'!G{final_row}"
    content = BytesIO()
    book.save(content)
    book.close()
    summary.write_bytes(with_formula_cache(content, cached))
    with pytest.raises(ValueError, match='另一张业务表!A1'):
        append_plan([submitted], summary, '2026-11', another, [submitted])
    assert not another.exists()
