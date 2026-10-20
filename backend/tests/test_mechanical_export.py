"""Protect original four-sheet layout, frozen values and truthful annual mapping."""

from copy import deepcopy
from decimal import Decimal
from openpyxl import load_workbook
import pytest

from app.report_export import mechanical_export as export
from app.core.errors import MustReportError


def sample():
    return {'ym': '2026-09', 'projects': [{'warehouse': '甲', 'name': '甲项目'}],
            'effective': [{'warehouse': '甲', 'ym': '2026-09', 'values': {'mech_2': '100.00', 'mech_3': '0.00'}}],
            'annual_effective': [{'warehouse': '甲', 'ym': '2026-09', 'values': {'mech_2': '100.00', 'mech_3': '0.00'}}],
            'summary': [{'warehouse': '甲', 'ym': '2026-09', 'cumulative': {'zero': '150.00', 'monthly': '0.00', 'internal': '0.00', 'company': None}}],
            'histories': [{'warehouse': '甲', 'i6': '10.00', 'annual_rows': [], 'meta_at': {'2026-09': {'year': 2025, 'month': 1}}}],
            'details': [{'warehouse': '甲', 'ym': '2026-09', 'category': 'zero', 'issues': [],
                         'totals': {'gross': '99.00', 'net': '96.1165048543689'},
                         'rows': [{'device': '=HYPERLINK("bad")', 'amount': '99.00', 'rate': '99.00', 'net': '96.1165048543689',
                                   'qty': '2小时', 'tax': '3%专票', 'date': '8.21', 'plate': '原文', 'memo': '备注'}]}],
            'i8': [], 'reconciliations': []}


def test_four_original_sheets_values_layout_and_missing_state(tmp_path):
    data = sample()
    wb, warnings = export.build(data)
    assert wb.sheetnames == ['工程公司汇总表', '零租设备月报表', '包月外租设备月报', '年度汇总']
    summary, zero, monthly, annual = wb.worksheets
    assert summary['J6'].value == Decimal('100.00')
    assert summary['E6'].value == Decimal('150.00')
    assert summary['C6'].value == '2025'
    assert zero['E6'].value == '2小时'
    assert zero['J6'].value == '8.21'
    assert zero['B6'].data_type == 's'
    assert zero['I6'].value == Decimal('96.1165048543689')
    assert monthly['O4'].value == '不含税价'
    assert monthly['A6'].value == '合计'
    assert any('未取得' in message for message in warnings)
    assert any('不同' in message for message in warnings)
    assert all(str(s.print_area) and s.print_title_rows for s in wb)
    assert all(not s.row_dimensions[row].hidden for s in wb for row in range(5 if s is zero or s is monthly else 2, s.max_row + 1))
    assert str(zero.freeze_panes) == 'C5'
    wb.close()


def test_preview_matches_frozen_file_and_next_export_does_not_modify_first(tmp_path):
    data = sample()
    preview = export.preview(data)
    path = export.export(data, tmp_path)
    before = path.read_bytes()
    changed = deepcopy(data)
    changed['effective'][0]['values']['mech_2'] = '200.00'
    second = export.export(changed, tmp_path)
    assert second != path and path.read_bytes() == before
    wb = load_workbook(path, data_only=True)
    assert Decimal(str(wb.worksheets[0]['J6'].value)) == Decimal('100.00')
    values = [cell['value'] for row in preview['sheets'][0]['rows'] for cell in row]
    assert '100.00' in values
    assert not any('忽略' in str(cell.value) for sheet in wb for row in sheet for cell in row)
    wb.close()


def test_monthly_hidden_net_column_survives_empty_template_cells():
    data = sample()
    data['details'].append({'warehouse': '甲', 'ym': '2026-09', 'category': 'monthly',
                            'totals': {'gross': '100.00', 'net': '100.00'}, 'issues': [],
                            'rows': [{'device': '升降平台', 'amount': '100', 'net': '100',
                                      'tax': '普票', 'memo': '原备注', 'date': '8月1日'}]})
    wb, _ = export.build(data)
    monthly = wb.worksheets[2]
    assert monthly['O6'].value == Decimal('100')
    assert monthly['M6'].value == '原备注'
    assert monthly['I6'].value == '8月1日'
    assert monthly['O4'].value == '不含税价'
    wb.close()


def annual_sample(year):
    data = sample()
    data['ym'] = f'{year}-01'
    data['histories'][0].update(base_month='2026-09', annual_rows=[{
        'category': 'zero', 'cells': {'C': '1000', 'D': '10', 'O': '20', 'P': '30', 'AA': '40', 'AH': '99'},
        'source': {'file': '原2026年度报表.xlsx', 'year': 2026}}])
    data['annual_effective'] = [{'warehouse': '甲', 'ym': '2027-01', 'values': {'mech_2': '50'}}]
    return data


@pytest.mark.parametrize('year', [2025, 2026, 2027])
def test_annual_columns_follow_real_year_without_relabeling_source_values(year):
    wb, _ = export.build(annual_sample(year))
    annual = wb['年度汇总']
    months = {c.value: annual.cell(2, c.column).value for c in annual[1]
              if isinstance(c.value, str) and '年' in c.value}
    assert months['2023年2月'] == Decimal('99')
    assert months['2025年1月'] == Decimal('10')
    assert ('2025年12月' in months) == (year >= 2026)
    assert ('2026年1月' in months) == (year >= 2026)
    assert ('2026年12月' in months) == (year >= 2027)
    if year == 2027:
        assert months['2026年1月'] == Decimal('30')
        assert months['2026年12月'] == Decimal('40')
        assert months['2027年1月'] == Decimal('50')
    assert '往年合计' not in [c.value for c in annual[1]]
    wb.close()


def test_rollover_older_total_uses_complete_previous_year_and_confirmed_revision_once():
    data = annual_sample(2027)
    cells = data['histories'][0]['annual_rows'][0]['cells']
    for month in range(1, 13):
        cells[export.get_column_letter(3 + month)] = str(month)
    data['annual_effective'].append({'warehouse': '甲', 'ym': '2025-01', 'values': {'mech_2': '2'}})
    wb, _ = export.build(data)
    annual = wb['年度汇总']
    col = next(c.column for c in annual[1] if c.value == '2025年1月')
    assert annual.cell(2, col).value == Decimal('2')
    # The opening lump sum is never silently allocated to a made-up month.
    assert annual['C2'].value == Decimal('99')
    wb.close()


def test_annual_source_without_reliable_year_is_rejected_before_mislabeling():
    data = annual_sample(2027)
    data['histories'][0].pop('base_month')
    data['histories'][0]['annual_rows'][0]['source'].pop('year')
    with pytest.raises(MustReportError, match='年份依据'):
        export.build(data)
