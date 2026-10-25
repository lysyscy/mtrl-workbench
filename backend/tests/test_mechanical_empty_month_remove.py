"""Remove a cleared mechanical month without restoring its former cumulative amount."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, select

from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod06_proc import domain as D, repository as R, workbench as W
from app.mod06_proc.models import ProcHistoryBatch, ProcHistorySnapshot, ProcMechImportChange
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord
from app.mod08_inv.models import InvDetail, InvAdjustment
from tests.test_mechanical_source_protection import session as source_session  # noqa: F401


@pytest.fixture
def session(source_session):
    metadata = MetaData()
    for model in (Project, InvDetail, InvAdjustment):
        table = model.__table__.to_metadata(metadata)
        for column in table.columns:
            column.server_default = None
    metadata.create_all(source_session.bind)
    return source_session


def prepare(s, wh='甲'):
    prior = dict(zip(D.MECH_KEYS, ('9748.83', '0.00', '64000.00', '189000.00', '62135.92', '183649.51')))
    september = dict(zip(D.MECH_KEYS, ('13046.19', '0.00', '107500.00', '225000.00', '104368.93', '220995.15')))
    history = {'warehouse': wh, 'base_month': '2026-09', 'report_total': '3333293.94',
               'category_totals': {'company': '135800.26', 'internal': '18209.00', 'zero': '1446375.00',
                                   'monthly': '1868709.94', 'weekly': '0.00'},
               'cumulative_at': {'2025-01': {'company': '9748.83', 'internal': '0.00', 'zero': '64000.00',
                                             'monthly': '189000.00', 'weekly': '0.00'},
                                  '2026-09': {'company': '135800.26', 'internal': '18209.00', 'zero': '1446375.00',
                                              'monthly': '1868709.94', 'weekly': '0.00'}},
               'reference_months': {'2025-01': prior, '2026-09': september},
               'effective_base': {'2025-01': prior, '2026-09': september},
               'original_months': {'2025-01': prior, '2026-09': september},
               'source': {'file': 'original.xlsx', 'sha256': 'source-version'},
               'annual_rows': [{'source': {'row': 71}, 'raw': 'original annual fact'}]}
    W.write(s, W.key('history', wh), history, 0)
    R.save_mech(s, warehouse=wh, ym='2025-01', values={column: 0 for column in D.MECH_KEYS})
    R.save_mech(s, warehouse=wh, ym='2026-09', values={**september, 'mech_3': '227700.00'})
    batch_no = 'REMOVE-' + uuid4().hex
    s.add(ProcHistoryBatch(batch_no=batch_no, warehouse_name=wh, row_count=2, status='active', cutoff_ym='2026-08'))
    s.add(ProcHistorySnapshot(batch_no=batch_no, warehouse_name=wh, ym='2025-01', material_present=True, **prior))
    s.add(ProcHistorySnapshot(batch_no=batch_no, warehouse_name=wh, ym='2026-09', material_present=True))
    for column in D.MECH_KEYS:
        s.add(ProcMechImportChange(batch_no=batch_no, warehouse_name=wh, ym='2025-01', column_key=column,
                                  before_amount=0, before_batch=''))
    s.flush()
    return history, batch_no


def remove(s, wh='甲', **options):
    request = {'warehouse': wh, 'ym': '2025-01', 'confirmed': True,
               'effective_signature': W.effective(s, wh, '2025-01')['signature'], **options}
    return W.action(s, 'empty-month-remove', request, '宿主操作者')


def matrix(s, wh, adjusted):
    return D.build_matrix(inv_rows=R.load_inv_rows(s), manual_rows=R.load_mech(s), history_rows=R.load_history(s),
                          warehouse=wh, adjusted=adjusted, cutoff_ym='2026-08')


def test_remove_cleared_month_preserves_total_categories_and_other_manual_edit(session):
    original, batch_no = prepare(session)
    before_total = W.report_total(session, '甲')
    before = {ym: W.cumulative(session, '甲', ym) for ym in ('2025-01', '2026-09', '2026-10')}
    assert before_total == '3082993.94'
    assert '2025-01' in {r['ym'] for r in matrix(session, '甲', False)}
    result = remove(session, operator='伪造操作者')
    assert result['removed'] is True
    assert R.mech_row(session, '甲', '2025-01') is None
    assert W.report_total(session, '甲') == before_total
    assert {ym: W.cumulative(session, '甲', ym) for ym in before} == before
    assert W.effective(session, '甲', '2026-09')['values']['mech_3'] == '227700.00'
    assert all('2025-01' not in {r['ym'] for r in matrix(session, '甲', mode)} for mode in (False, True))
    history, _ = W.read(session, W.key('history', '甲'))
    for field in ('source', 'original_months', 'annual_rows'):
        assert history[field] == original[field]
    assert history['reference_months']['2025-01'] == dict.fromkeys(D.MECH_KEYS, '0.00')
    assert '2025-01' not in history['effective_base']
    assert R.load_batches(session)[0].row_count == 1
    assert len(list(session.scalars(select(ProcMechImportChange)))) == 6
    audit = session.get(MechanicalWorkbenchRecord, result['audit_key']).payload
    assert audit['operator'] == '宿主操作者'
    assert audit['history_before'] == original
    assert audit['snapshots'][0]['mech_3'] == '189000.00'
    assert audit['batches_before'][0]['row_count'] == 2
    assert len(audit['import_changes']) == 6


def test_new_revisions_after_removal_only_add_the_changed_amount(session):
    prepare(session)
    remove(session)
    before = Decimal(W.report_total(session, '甲'))
    R.save_mech(session, warehouse='甲', ym='2026-09', values={'mech_3': '228700.00'})
    assert Decimal(W.report_total(session, '甲')) == before + 1000
    R.save_mech(session, warehouse='甲', ym='2026-10', values={'mech_2': '50.00'})
    assert Decimal(W.report_total(session, '甲')) == before + 1050
    R.save_mech(session, warehouse='甲', ym='2025-01', values={'mech_2': '25.00'})
    assert Decimal(W.report_total(session, '甲')) == before + 1075
    assert W.cumulative(session, '甲', '2025-01')['zero'] == '25.00'


def test_dated_annual_reference_and_cumulative_adoption_are_preserved(session):
    prepare(session)
    history, revision = W.read(session, W.key('history', '甲'))
    history['reference_at'] = {'2026-09': {'2025-01': {'mech_0': '100', 'mech_1': '0',
                                                       'mech_2': '6400', 'mech_3': '18900'}}}
    W.write(session, W.key('history', '甲'), history, revision)
    W.mark_adoption(session, '甲', '2026-09', ['mech_3'])
    adopted = W.read(session, W.key('adoption', '甲', '2026-09'))
    before = {ym: W.cumulative(session, '甲', ym) for ym in ('2026-09', '2026-10')}
    remove(session)
    assert {ym: W.cumulative(session, '甲', ym) for ym in before} == before
    assert W.read(session, W.key('adoption', '甲', '2026-09')) == adopted


def test_removal_failure_rolls_back_audit_history_snapshots_and_batch(session, monkeypatch):
    original, _ = prepare(session)
    write = W.write
    def fail_history(s, record_key, payload, revision):
        if record_key == W.key('history', '甲'):
            raise MustReportError('模拟历史并发修改')
        return write(s, record_key, payload, revision)
    monkeypatch.setattr(W, 'write', fail_history)
    with pytest.raises(MustReportError, match='并发修改'):
        remove(session)
    assert R.mech_row(session, '甲', '2025-01') is not None
    assert W.read(session, W.key('history', '甲'))[0] == original
    assert R.load_batches(session)[0].row_count == 2
    assert len(list(session.scalars(select(ProcHistorySnapshot)))) == 2
    assert not list(session.scalars(select(MechanicalWorkbenchRecord).where(
        MechanicalWorkbenchRecord.key.like('empty-month-removal:%'))))


@pytest.mark.parametrize('reason', ['nonzero', 'detail', 'draft', 'material', 'inventory', 'stale', 'unconfirmed'])
def test_removal_rejects_nonempty_linked_or_stale_month_without_changes(session, reason):
    prepare(session)
    extra = {}
    if reason == 'nonzero':
        R.save_mech(session, warehouse='甲', ym='2025-01', values={'mech_3': '1.00'})
    elif reason == 'detail':
        row = R.mech_row(session, '甲', '2025-01')
        row.source_batches = {'__detail_sources': {'mech_2': {'mode': 'detail'}}}
    elif reason == 'draft':
        W.save_details(session, {'warehouse': '甲', 'ym': '2025-01', 'category': 'zero', 'revision': 0,
                                 'rows': [{'id': 'draft', 'device': '升降车', 'amount': '0.00', 'tax': '普票'}]})
    elif reason == 'material':
        snapshot = session.scalar(select(ProcHistorySnapshot).where(ProcHistorySnapshot.ym == '2025-01'))
        snapshot.in_0 = Decimal('1.00')
    elif reason == 'inventory':
        session.add(InvDetail(warehouse_name='甲', ym='2025-01', amount=0))
    elif reason == 'stale':
        extra['effective_signature'] = 'old-signature'
    elif reason == 'unconfirmed':
        extra['confirmed'] = False
    session.flush()
    before = deepcopy(W.read(session, W.key('history', '甲')))
    with pytest.raises(MustReportError):
        remove(session, **extra)
    assert R.mech_row(session, '甲', '2025-01') is not None
    assert W.read(session, W.key('history', '甲')) == before
    assert R.load_batches(session)[0].row_count == 2
    assert len(list(session.scalars(select(ProcHistorySnapshot)))) == 2
    assert not list(session.scalars(select(MechanicalWorkbenchRecord).where(
        MechanicalWorkbenchRecord.key.like('empty-month-removal:%'))))


def test_postgresql_empty_month_removal_persists_audit_and_removes_both_matrix_rows(rollback_db):
    from app.core import db
    assert rollback_db.dialect.name == 'postgresql'
    wh = '删除空月PG-' + uuid4().hex
    with db.get_session_factory()() as s:
        s.add(Project(warehouse_name=wh))
        s.flush()
        prepare(s, wh)
        before = W.report_total(s, wh)
        result = remove(s, wh)
        s.commit()
        s.expire_all()
        assert R.mech_row(s, wh, '2025-01') is None
        assert W.report_total(s, wh) == before
        assert all('2025-01' not in {r['ym'] for r in matrix(s, wh, mode)} for mode in (False, True))
        assert s.get(MechanicalWorkbenchRecord, result['audit_key']).payload['operator'] == '宿主操作者'
