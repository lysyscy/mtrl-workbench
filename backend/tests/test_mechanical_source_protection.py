"""Mechanical source protection on a private in-memory database."""
from copy import deepcopy
from decimal import Decimal

import pytest
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod06_proc import repository as R, workbench as W
from app.mod06_proc.models import (ProcMechManual, ProcCutoff, ProcHistoryBatch,
                                   ProcHistorySnapshot, ProcMechImportChange, ProcMechMatchRule)
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord, MechanicalWorkbenchPreview
from tests.acc_plugin import acc


@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()
    for model in (Project, ProcMechManual, ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot,
                  ProcMechImportChange, ProcMechMatchRule, MechanicalWorkbenchRecord, MechanicalWorkbenchPreview):
        table = model.__table__.to_metadata(metadata)
        for column in table.columns:
            column.server_default = None  # PostgreSQL casts are irrelevant to this private schema.
    metadata.create_all(engine)
    with Session(engine, autoflush=False, expire_on_commit=False) as s:
        s.add(Project(warehouse_name='甲', name_full='甲项目'))
        s.flush()
        yield s
    engine.dispose()


@acc('ACC-RPT-MECH-001', '001-02')
def test_plain_save_cannot_overwrite_detail_confirmed_cell(session):
    item = ProcMechManual(warehouse_name='甲', ym='2026-09', mech_2=Decimal('103.00'),
                          source_batches={'__detail_sources': {'mech_2': {'mode': 'detail'}}})
    session.add(item)
    session.flush()
    before = deepcopy(item.source_batches)
    with pytest.raises(MustReportError, match='明细'):
        R.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_2': '999.00'})
    assert item.mech_2 == Decimal('103.00')
    assert item.source_batches == before


@acc('ACC-RPT-MECH-001', '001-02')
def test_effective_keeps_unknown_cells_distinct_from_explicit_zero():
    row = ProcMechManual(warehouse_name='甲', ym='2026-09', mech_2=Decimal('0.00'), mech_3='')
    state = R.mech_effective(row, '甲', '2026-09')
    assert state['values']['mech_2'] == '0.00'
    assert state['values']['mech_4'] is None
    assert state['values']['mech_3'] is None


@pytest.mark.parametrize('columns', [[], ['other'], [{}], 'mech_2'])
@acc('ACC-RPT-MECH-001', '001-02')
def test_manual_switch_rejects_invalid_column_payload(session, columns):
    with pytest.raises(MustReportError, match='金额格'):
        W.action(session, 'source-manual', {'warehouse': '甲', 'ym': '2026-09', 'columns': columns,
                                          'confirmed': True}, '宿主操作者')


def confirm(s, *, columns=None, tax='3%专', amount='103.00', ym='2026-09', operator='审核人'):
    saved = W.save_details(s, {'warehouse': '甲', 'ym': ym, 'category': 'zero', 'revision': 0,
                              'rows': [{'id': 'row-1', 'device': '升降车', 'amount': amount,
                                        'tax': tax, 'plate': ''}]})
    request = {'warehouse': '甲', 'ym': ym, 'category': 'zero', 'revision': saved['revision'],
               'effective_signature': W.effective(s, '甲', ym)['signature']}
    if columns is not None:
        request['columns'] = columns
    return W.action(s, 'amounts-confirm', request, operator), request


def to_manual(s, state, columns, *, operator='宿主操作者', **extra):
    return W.action(s, 'source-manual', {'warehouse': '甲', 'ym': state['ym'], 'columns': columns,
                                       'effective_signature': state['signature'], 'confirmed': True, **extra}, operator)


@acc('ACC-RPT-MECH-001', '001-02')
def test_gross_and_net_have_independent_confirmation_and_validation(session):
    state, _ = confirm(session, columns=['mech_2'], tax='')
    assert state['sources']['mech_2']['mode'] == 'detail'
    assert state['sources']['mech_4']['mode'] == 'manual'
    detail, revision = W.read(session, W.key('details', '甲', '2026-09', 'zero'))
    view = W.detail_view(session, detail, revision)
    assert not view['blocked_columns']['mech_2']
    assert view['blocked_columns']['mech_4'] == [{'id': 'row-1', 'fields': ['票种／税率']}]
    with pytest.raises(MustReportError, match='字段待补'):
        W.confirm_amounts(session, {'warehouse': '甲', 'ym': '2026-09', 'category': 'zero',
                                   'columns': ['mech_4'], 'revision': revision,
                                   'effective_signature': state['signature']})
    R.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_4': '99.00'})
    assert W.effective(session, '甲', '2026-09')['values']['mech_4'] == '99.00'


@acc('ACC-RPT-MECH-001', '001-02')
def test_same_value_save_retains_signature_source_and_timestamp(session):
    state, _ = confirm(session)
    row = R.mech_row(session, '甲', '2026-09')
    stamp, origins = row.updated_at, deepcopy(row.source_batches)
    R.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_2': '103.00', 'mech_4': '100.00'})
    assert row.updated_at == stamp and row.source_batches == origins
    assert W.effective(session, '甲', '2026-09')['signature'] == state['signature']


@acc('ACC-RPT-MECH-001', '001-02')
def test_explicit_manual_switch_preserves_evidence_and_does_not_replay_confirmation(session):
    state, request = confirm(session)
    adopted = W.read(session, W.key('adoption', '甲', '2026-09'))
    with pytest.raises(MustReportError, match='明确确认'):
        to_manual(session, state, ['mech_2'], confirmed=False)
    manual = W.action(session, 'source-manual', {'warehouse': '甲', 'ym': '2026-09', 'columns': ['mech_2'],
                       'effective_signature': state['signature'], 'confirmed': True, 'operator': '伪造操作者'}, '实际操作者')
    assert manual['sources']['mech_2']['mode'] == 'manual'
    assert manual['sources']['mech_4']['mode'] == 'detail'
    source = manual['sources']['mech_2']
    assert source['basis']['rows'][0]['amount'] == '103.00'
    assert source['history'][-1]['operator'] == '实际操作者'
    assert source['basis']['operator'] == '审核人'
    assert W.read(session, W.key('adoption', '甲', '2026-09')) == adopted
    with pytest.raises(MustReportError, match='已变化'):
        to_manual(session, state, ['mech_4'])
    with pytest.raises(MustReportError, match='已变化'):
        W.confirm_amounts(session, request)
    R.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_2': '104.00'})
    with pytest.raises(MustReportError, match='明细'):
        R.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_4': '101.00'})


@acc('ACC-RPT-MECH-001', '001-06')
def test_process_import_preflights_all_months_before_batch_changes(session):
    from app.mod06_proc import imp_spec
    R.import_snapshot(session, warehouse='甲', rows=[{'ym': '2026-08', 'mech_1': '7'}],
                      batch_no='old', operator='导入人')
    confirm(session, columns=['mech_2'])
    before = W.effective(session, '甲', '2026-09')
    with pytest.raises(MustReportError, match='明细'):
        imp_spec.commit(session, [{'_row': 2, '核算月': '2026-08', '外租零租含税': '22'},
                                  {'_row': 3, '核算月': '2026-09', '外租零租含税': '999'}], {}, '导入人',
                        {'warehouse': '甲', 'batch': 'new'})
    assert [(b.batch_no, b.status) for b in R.load_batches(session)] == [('old', 'active')]
    assert R.mech_row(session, '甲', '2026-08').mech_2 == Decimal('0.00')
    assert W.effective(session, '甲', '2026-09')['signature'] == before['signature']


@acc('ACC-RPT-MECH-001', '001-06')
def test_same_detail_process_import_skips_without_a_fake_batch_or_cutoff(session):
    from app.mod06_proc import imp_spec
    state, _ = confirm(session, columns=['mech_2'])
    out = imp_spec.commit(session, [{'_row': 2, '核算月': '2026-09', '外租零租含税': '103'}], {}, '导入人',
                          {'warehouse': '甲', 'batch': 'same'})
    assert out['rows'] == 0 and out['batch'] == ''
    assert not R.load_batches(session)
    assert not list(session.scalars(select(ProcHistorySnapshot)))
    assert not list(session.scalars(select(ProcMechImportChange)))
    assert not R.load_cutoffs(session)
    assert W.effective(session, '甲', '2026-09')['signature'] == state['signature']


@acc('ACC-RPT-MECH-001', '001-06')
def test_mixed_import_keeps_detail_ownership_and_imports_only_other_column(session):
    state, _ = confirm(session, columns=['mech_2'])
    R.import_snapshot(session, warehouse='甲', rows=[{'ym': '2026-09', 'mech_2': '103', 'mech_4': '99'}],
                      batch_no='mixed', operator='导入人')
    row = R.mech_row(session, '甲', '2026-09')
    assert row.mech_2 == Decimal('103') and row.mech_4 == Decimal('99')
    assert 'mech_2' not in row.source_batches
    assert row.source_batches['mech_4'] == 'mixed'
    assert R.mech_sources(row)['mech_2'] == state['sources']['mech_2']
    assert [c.column_key for c in session.scalars(select(ProcMechImportChange))] == ['mech_4']
    R.rollback_batch(session, batch_no='mixed')
    assert R.mech_sources(row)['mech_2']['mode'] == 'detail'
    assert row.mech_2 == Decimal('103') and row.mech_4 == Decimal('0')


@acc('ACC-RPT-MECH-001', '001-02')
def test_report_import_blocks_other_project_writes_and_skips_same_sources(session):
    from app.mod06_proc import mech_report_spec
    session.add_all([Project(warehouse_name='乙'), ProcMechMatchRule(warehouse_name='甲', aliases=[]),
                     ProcMechMatchRule(warehouse_name='乙', aliases=[])])
    session.flush()
    state, _ = confirm(session, columns=['mech_2'])
    records = [{'核算月': '2026-09', '报表项目名': '乙', '外租零租含税': '5'},
               {'核算月': '2026-09', '报表项目名': '甲', '外租零租含税': '999'}]
    with pytest.raises(MustReportError, match='明细'):
        mech_report_spec.commit(session, records, {}, '导入人', {'year_month': '2026-09', 'confirmed': True})
    assert R.mech_row(session, '乙', '2026-09') is None
    records[1]['外租零租含税'] = '103'
    result = mech_report_spec.commit(session, records, {}, '导入人', {'year_month': '2026-09', 'confirmed': True})
    assert result['rows'] == 1
    assert W.effective(session, '甲', '2026-09')['signature'] == state['signature']


@acc('ACC-RPT-MECH-001', '001-06')
def test_history_incoming_decision_cannot_override_detail_mode(session):
    state, _ = confirm(session, columns=['mech_2'])
    p = W.history_preview(session, {'projects': [{'warehouse': '甲', 'history': {'source': {'file': '原表'}},
                                                  'months': [{'ym': '2026-08', 'values': {'mech_2': '5'}},
                                                             {'ym': '2026-09', 'values': {'mech_2': '999'}}]}]})
    with pytest.raises(MustReportError, match='明细'):
        W.history_confirm(session, {'preview_id': p['preview_id'],
                                    'resolutions': {'甲|2026-09|mech_2': 'incoming'}})
    assert R.mech_row(session, '甲', '2026-08') is None
    assert not W.read(session, W.key('history', '甲'))[0]
    assert W.effective(session, '甲', '2026-09')['signature'] == state['signature']


@acc('ACC-RPT-MECH-001', '001-06')
def test_detail_confirmation_survives_original_import_rollback_even_when_zero(session):
    R.import_snapshot(session, warehouse='甲', rows=[{'ym': '2026-09', 'mech_2': '10'}],
                      batch_no='old', operator='导入人')
    confirm(session, columns=['mech_2'], amount='0.00')
    R.rollback_batch(session, batch_no='old')
    row = R.mech_row(session, '甲', '2026-09')
    assert row is not None and row.mech_2 == 0
    assert R.mech_sources(row)['mech_2']['mode'] == 'detail'


@acc('ACC-RPT-MECH-001', '001-06')
def test_rollback_preflights_inconsistent_detail_ownership_before_other_restores(session):
    R.import_snapshot(session, warehouse='甲', rows=[{'ym': '2026-08', 'mech_2': '5'},
                                                   {'ym': '2026-09', 'mech_2': '10'}],
                      batch_no='old', operator='导入人')
    row = R.mech_row(session, '甲', '2026-09')
    row.source_batches = {**row.source_batches, '__detail_sources': {'mech_2': {'mode': 'detail'}}}
    session.flush()
    with pytest.raises(MustReportError, match='明细'):
        R.rollback_batch(session, batch_no='old')
    assert R.mech_row(session, '甲', '2026-08').mech_2 == Decimal('5')
    assert R.load_batches(session)[0].status == 'active'


@acc('ACC-RPT-MECH-001', '001-02')
def test_process_get_exposes_same_source_and_signature_as_workbench(session, monkeypatch):
    from contextlib import contextmanager
    from app.mod06_proc import router
    @contextmanager
    def scope():
        yield session
    monkeypatch.setattr(router, 'session_scope', scope)
    state, _ = confirm(session, columns=['mech_2'])
    data = router.api_mech()
    assert data['sources']['甲']['2026-09'] == state['sources']
    assert data['effective_signatures']['甲']['2026-09'] == state['signature']
    manual = R.load_mech(session)[0]
    assert manual['sources'] == state['sources'] and manual['effective_signature'] == state['signature']
    with pytest.raises(MustReportError, match='明细'):
        router.api_mech_save(router.MechSaveRequest(warehouse='甲', ym='2026-09', values={'mech_2': '999'}))


@acc('ACC-RPT-MECH-001', '001-02')
def test_postgresql_action_api_sources_switch_and_independent_net(rollback_db):
    """Exercise PostgreSQL JSON persistence and the real session-scope API boundary."""
    from uuid import uuid4
    from app.core import db
    from app.mod06_proc import router
    assert rollback_db.dialect.name == 'postgresql'
    warehouse = '来源保护PG-' + uuid4().hex
    factory = db.get_session_factory()
    with factory() as s:
        s.add(Project(warehouse_name=warehouse))
        s.commit()
        draft = W.action(s, 'details-save', {'warehouse': warehouse, 'ym': '2026-09', 'category': 'zero',
                          'revision': 0, 'rows': [{'id': 'pg-row', 'device': '升降车', 'amount': '103.00', 'tax': '3%专'}]})
        state = W.action(s, 'amounts-confirm', {'warehouse': warehouse, 'ym': '2026-09', 'category': 'zero',
                          'revision': draft['revision'], 'columns': ['mech_2'],
                          'effective_signature': W.effective(s, warehouse, '2026-09')['signature']}, 'PG审核人')
        detail, revision = W.read(s, W.key('details', warehouse, '2026-09', 'zero'))
        state = W.action(s, 'amounts-confirm', {'warehouse': warehouse, 'ym': '2026-09', 'category': 'zero',
                          'revision': revision, 'columns': ['mech_4'], 'effective_signature': state['signature']}, 'PG审核人')
        s.commit()
        fetched = router.api_mech()
        assert fetched['sources'][warehouse]['2026-09']['mech_2']['mode'] == 'detail'
        assert fetched['sources'][warehouse]['2026-09']['mech_4']['mode'] == 'detail'
        assert fetched['effective_signatures'][warehouse]['2026-09'] == state['signature']
        router.api_mech_save(router.MechSaveRequest(warehouse=warehouse, ym='2026-09', values={'mech_2': '103'}))
        with pytest.raises(MustReportError, match='明细'):
            router.api_mech_save(router.MechSaveRequest(warehouse=warehouse, ym='2026-09', values={'mech_2': '999'}))
        with pytest.raises(MustReportError, match='已变化'):
            W.action(s, 'source-manual', {'warehouse': warehouse, 'ym': '2026-09', 'columns': ['mech_2'],
                      'effective_signature': 'stale', 'confirmed': True}, 'PG操作者')
        manual = W.action(s, 'source-manual', {'warehouse': warehouse, 'ym': '2026-09', 'columns': ['mech_2'],
                          'effective_signature': state['signature'], 'confirmed': True, 'operator': '伪造'}, 'PG操作者')
        assert manual['sources']['mech_2']['history'][-1]['operator'] == 'PG操作者'
        s.commit()
        router.api_mech_save(router.MechSaveRequest(warehouse=warehouse, ym='2026-09', values={'mech_2': '104'}))
        with pytest.raises(MustReportError, match='明细'):
            router.api_mech_save(router.MechSaveRequest(warehouse=warehouse, ym='2026-09', values={'mech_4': '101'}))
        s.expire_all()
        final = W.effective(s, warehouse, '2026-09')
        assert final['values']['mech_2'] == '104.00' and final['values']['mech_4'] == '100.00'
        assert final['sources']['mech_2']['mode'] == 'manual' and final['sources']['mech_4']['mode'] == 'detail'
        assert final['sources']['mech_2']['basis']['rows'][0]['amount'] == '103.00'
