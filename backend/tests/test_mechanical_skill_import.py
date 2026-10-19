"""Generated skill payloads exercise the real import/confirm contract in isolation."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
from pathlib import Path

import pytest

from app.mod06_proc import workbench as W
from tests.test_mechanical_workbench import session  # noqa: F401
from tests.acc_plugin import acc

SKILL = Path(__file__).resolve().parents[2] / 'skills/machinery-fee-consolidation'
spec = importlib.util.spec_from_file_location('mechanical_skill_import', SKILL / 'scripts/build_system_import.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / '原报.xlsx'
    source.write_bytes(b'read-only-source')
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    cell = lambda value: {'value': value, 'coordinate': 'B5', 'header': '原字段', 'format': 'General'}
    extraction = {'period': '2026-10', 'sources': [{'path': str(source), 'sheet': '零租',
                  'sha256_before': sha, 'sha256_after': sha}], 'issues': [], 'records': [
        {'period': '2026-10', 'project': '原报甲', 'kind': '零租',
         'source': {'path': str(source), 'sheet': '零租', 'row': 5},
         'fields': {'equipment': cell('升降车'), 'gross_amount': cell(113),
                    'rental_date': cell(8.21), 'remarks': cell('备注原文'), 'reported_net_amount': cell(100)},
         'tax': {'invoice': '专票', 'rate': '0.13'}, 'raw_cells': [cell('原字段')]}]}
    review = {'period': '2026-10', 'projects': {'原报甲': '甲'},
              'rows': [{'record': 0, 'id': 'source-row-a', 'reason': '原报项目与设备已核实'}]}
    return extraction, review, {'projects': [{'warehouse': '甲'}], 'details': []}


@acc()
def test_skill_payload_preview_confirm_revision_and_source_guard(session, inputs):
    extraction, review, state = inputs
    result = builder.build(*inputs)
    payload = result['detail_import']
    assert builder.build(*inputs) == result
    row = payload['batches'][0]['rows'][0]
    assert row['date'] == 8.21 and row['memo'] == '备注原文'
    assert Decimal(W.row_net(row)) == Decimal('100.00')
    assert row['source']['fields'] == extraction['records'][0]['fields']
    preview = W.action(session, 'import-preview', payload)
    assert W.effective(session, '甲', '2026-10')['values']['mech_2'] is None
    assert not W.read(session, W.key('details', '甲', '2026-10', 'zero'))[0]
    confirm = {'preview_id': preview['preview_id'], 'confirm_amounts': False}
    W.action(session, 'import-confirm', confirm)
    assert W.effective(session, '甲', '2026-10')['values']['mech_2'] is None
    assert W.action(session, 'import-confirm', confirm)['batches'][0]['revision'] == 1
    saved = W.read(session, W.key('details', '甲', '2026-10', 'zero'))[0]
    assert len(saved['rows']) == 1
    current = W.effective(session, '甲', '2026-10')
    W.action(session, 'amounts-confirm', {'warehouse': '甲', 'ym': '2026-10', 'category': 'zero',
             'revision': 1, 'effective_signature': current['signature'], 'columns': ['mech_2']})
    assert W.effective(session, '甲', '2026-10')['sources']['mech_2']['mode'] == 'detail'
    W.save_details(session, {'warehouse': '甲', 'ym': '2026-10', 'category': 'zero',
                   'revision': 2, 'rows': [{**row, 'plate': '人工补充车牌'}]})
    review['rows'][0]['values'] = {'amount': '226.00'}
    updated = builder.build(extraction, review, state)['detail_import']
    assert W.row_net(updated['batches'][0]['rows'][0]) == '200.00'
    preview = W.action(session, 'import-preview', updated)
    assert preview['batches'][0]['rows'][0]['plate'] == '人工补充车牌'
    assert len(preview['batches'][0]['rows']) == 1
    W.action(session, 'import-confirm', {'preview_id': preview['preview_id'], 'confirm_amounts': False})
    assert W.effective(session, '甲', '2026-10')['values']['mech_2'] == '113.00'


@acc()
def test_skill_rejects_unreviewed_changed_sources_and_unmatched_rows(inputs):
    extraction, review, state = inputs
    for mutate in (
        lambda e, r, s: r['rows'].clear(),
        lambda e, r, s: r['rows'].append(deepcopy(r['rows'][0])),
        lambda e, r, s: r['projects'].update({'原报甲': '未知仓库'}),
        lambda e, r, s: e['issues'].append({'reason': '票种待核'}),
        lambda e, r, s: s['details'].append({'warehouse': '甲', 'ym': '2026-10', 'category': 'zero', 'rows': [{'id': 'lost'}]}),
    ):
        args = deepcopy(inputs)
        mutate(*args)
        with pytest.raises(ValueError):
            builder.build(*args)
    Path(extraction['sources'][0]['path']).write_bytes(b'new-revision')
    with pytest.raises(ValueError, match='原报已更新'):
        builder.build(*inputs)
