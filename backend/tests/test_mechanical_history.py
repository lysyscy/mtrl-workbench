"""History adapters preserve independent facts before any business adoption."""
from copy import deepcopy
from decimal import Decimal
import hashlib

import pytest

from app.mod06_proc.workbench_history import build_history_payload, exact_projects, verify_source_hashes, yuan
from tests.acc_plugin import acc


def sample():
    names = ['已配项目', '未配历史项目']
    record = {'zero': 0, 'monthly': None, 'company': 1304618.63, 'internal': 1400000,
              'zeroNet': None, 'monthlyNet': None}
    row = {'id': 'r1', 'project': 0, 'month': '2026-02', 'cat': 'zero',
           'device': '吊车', 'rate': 3508333.33333333, 'amount': 485000, 'original': 485000,
           'sourceNet': None, 'source': '原表.xlsx / 零租设备月报表 / 第6行'}
    data = {'records': {f'{i}|2026-02': deepcopy(record) for i in range(2)},
            'saved': [row, {**row, 'id': 'r2', 'project': 1}], 'working': [row, row],
            'latestMonthly': {'0|2026-02|zero': 485000},
            'baseMonth': ['2026-09', '2026-09'], 'feeBase': [500000, 100000],
            'cumulativeAt': {'2026-02': [{'zero': 485000}, {'zero': None}]},
            'latestCats': [{'zero': 485000}, {'zero': None}],
            'metaAt': {'2026-02': [{'year': '2024', 'month': '2', 'source': '原表'}, {}]},
            'feeBaseSource': ['年度合计'] * 2, 'i8': [{'i6': None}, {'i6': 0}],
            'quality': [{'project': 0, 'detail': 485000, 'adopted': 0}],
            'monthConflicts': [{'project': 0, 'original_month_report': 0,
                                'latest_annual_reference': 485000}],
            'issues': [{'project': 0, 'amount': 50000, 'note': '已约定，尚未执行'}]}
    seed = {'names': names, 'months': ['2026-02'], 'data': data}
    verification = {'hashes': {'D:/原件/原表.xlsx': {'before': 'hash', 'after': 'hash'}}}
    system = {'projects': [{'warehouse_name': '仓库', 'disp': '显示名'}],
              'rules': [{'warehouse_name': '仓库', 'aliases': ['已配项目']}], 'effective': []}
    workbooks = [{'path': 'D:/原件/原表.xlsx', 'sheets': [{'name': '年度汇总', 'cells': [
        {'row': 2, 'col': 1, 'cell': 'A2', 'cache': '已配项目'},
        {'row': 2, 'col': 2, 'cell': 'B2', 'cache': '当月零租费'},
        {'row': 2, 'col': 3, 'cell': 'C2', 'cache': 4850, 'value': '=BD2', 'type': 'f'},
        {'row': 2, 'col': 56, 'cell': 'BD2', 'cache': None, 'value': None, 'type': 'n'}]}]}]
    return seed, verification, system, workbooks


@acc("ACC-RPT-MECH-001", "001-06")
@acc("ACC-RPT-MECH-001", "001-05")
def test_history_preserves_adopted_annual_precision_and_unknown_identity():
    inputs = sample()
    before = deepcopy(inputs)
    result = build_history_payload(*inputs)
    assert inputs == before
    assert sum(len(b['rows']) for b in result['detail_import']['batches']) == 1
    row = result['detail_import']['batches'][0]['rows'][0]
    assert row['rate'] == '35083.3333333333'
    assert row['sourceNet'] is None
    assert row['source_evidence']['row'] == 6
    project = result['history_import']['projects'][0]
    assert project['months'][0]['values']['mech_2'] == '0.00'
    assert project['months'][0]['values']['mech_0'] == '13046.19'
    assert project['history']['original_months']['2026-02']['mech_0'] == '13046.1863'
    assert project['history']['cumulative_at']['2026-02']['zero'] == '4850'
    assert project['history']['meta_at']['2026-02']['year'] == '2024'
    assert project['history']['reference_months']['2026-02']['mech_2'] == '4850'
    assert project['history']['i6'] is None
    assert project['history']['annual_rows'][0]['cells']['C'] == '4850'
    assert project['history']['annual_rows'][0]['source_cells']['C']['value'] == '=BD2'
    assert project['history']['issues'][0]['amount'] == '500'
    assert result['unmapped'][0]['detail_count'] == 1
    assert result['unmapped'][0]['history_project']['warehouse'] is None
    assert '未配历史项目' not in exact_projects(inputs[2])


@acc("ACC-RPT-MECH-001", "001-05")
def test_explicit_mapping_is_a_new_preview_and_ambiguous_alias_stays_unmapped():
    args = sample()
    system = args[2]
    system['projects'].append({'warehouse_name': '另一仓库', 'disp': '另一显示名'})
    system['rules'].append({'warehouse_name': '另一仓库', 'aliases': ['已配项目']})
    assert '已配项目' not in exact_projects(system)
    original = build_history_payload(*args)
    mapped = build_history_payload(*args, mappings={'未配历史项目': '隔离历史档案'})
    assert original['detail_import']['request_id'] != mapped['detail_import']['request_id']
    assert len(mapped['unmapped']) == 1
    assert mapped['history_import']['projects'][0]['warehouse'] == '隔离历史档案'


@pytest.mark.parametrize('value', [True, 'NaN', 'Infinity', 'bad'])
@acc("ACC-RPT-MECH-001", "001-03")
def test_invalid_history_money_is_not_zero(value):
    with pytest.raises(ValueError):
        yuan(value)


@acc("ACC-RPT-MECH-001", "001-03")
def test_decimal_conversion_preserves_source_fractional_cents():
    assert Decimal(yuan('1304618.63')) == Decimal('13046.1863')
    assert yuan(None) is None
    assert yuan(0) == '0'


@acc("ACC-RPT-MECH-001", "001-06")
def test_changed_source_file_blocks_history_verification(tmp_path):
    source = tmp_path / 'source.xlsx'
    source.write_bytes(b'reviewed source')
    hashes = {str(source): hashlib.sha256(source.read_bytes()).hexdigest()}
    assert verify_source_hashes(hashes) == 1
    source.write_bytes(b'later revision')
    with pytest.raises(ValueError, match='来源文件已变化'):
        verify_source_hashes(hashes)
