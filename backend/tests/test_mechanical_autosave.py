"""Saved detail amounts take effect without a separate adoption action."""
from decimal import Decimal
from copy import deepcopy
import pytest
from tests.test_mechanical_workbench import session, row, save
from app.mod06_proc import workbench as W
from app.mod06_proc.models import ProcMechManual
from app.core.errors import MustReportError


def test_amount_rows_apply_even_with_other_blank_or_incomplete_rows(session):
    saved = save(session, [row(device='', plate=''), row(id='blank', amount=None, tax='')])
    assert saved['totals'] == {'gross': '103.00', 'net': '100.00'}
    state = W.effective(session, '甲', '2026-09')
    assert state['values']['mech_2'] == '103.00'
    assert state['values']['mech_4'] == '100.00'
    assert state['values']['mech_3'] is None


def test_missing_tax_never_masquerades_as_zero_or_partial_net(session):
    save(session, [row(), row(id='unknown', amount='50', tax='')])
    state = W.effective(session, '甲', '2026-09')['values']
    assert state['mech_2'] == '153.00'
    assert state['mech_4'] is None
    from app.mod05_flow.service import mechanical_settlements
    assert '153.00' in {str(amount) for months in mechanical_settlements(session).values() for amount in months.values()}


def test_metadata_changes_keep_manual_override_until_amount_changes(session):
    saved = save(session)
    state = W.effective(session, '甲', '2026-09')
    W.save_process_mech(session, warehouse='甲', ym='2026-09', values={'mech_2': Decimal('120')},
        confirmed=True, effective_signature=state['signature'],
        detail_signature=W.detail_signatures(session)['甲']['2026-09'])
    changed = save(session, [row(plate='苏A12345', note='补备注')], revision=saved['revision'])
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '120.00'
    save(session, [row(amount='206', plate='苏A12345', note='补备注')], revision=changed['revision'])
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '206.00'


def test_last_amount_removed_clears_only_this_category(session):
    zero = save(session)
    save(session, cat='monthly')
    save(session, [], revision=zero['revision'])
    state = W.effective(session, '甲', '2026-09')
    assert state['values']['mech_2'] is None
    assert state['values']['mech_4'] is None
    assert state['values']['mech_3'] == '103.00'
    assert state['values']['mech_5'] == '100.00'
    assert state['sources']['mech_2']['mode'] == 'manual'
    from app.mod06_proc import domain
    matrix = domain.build_matrix(inv_rows=[], manual_rows=W.repo.load_mech(session), warehouse='甲', adjusted=True)
    assert matrix[0]['mech_2'] is None and matrix[0]['mech_4'] is None


def test_zero_is_an_amount_and_clearing_it_is_not_zero(session):
    saved = save(session, [row(amount='0')])
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '0.00'
    save(session, [row(amount=None)], revision=saved['revision'])
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] is None


def test_last_amount_clear_suppresses_annual_history_reference(session):
    from app.report_export.mechanical_export import annual_values
    W.write(session,W.key('history','甲'),{'warehouse':'甲','reference_months':{
        '2026-09':{'mech_2':'103'}}},0)
    saved=save(session)
    save(session,[],revision=saved['revision'])
    snapshot=W.snapshot(session,'2026-09',['甲'])
    assert annual_values(snapshot,'甲',snapshot['histories'][0],{},'zero')=={}


def legacy_details(session):
    for category, amount in (('zero', '103.00'), ('monthly', '206.00')):
        rows = [row(amount=amount)]
        W.write(session, W.key('details', '甲', '2026-09', category), {
            'warehouse': '甲', 'ym': '2026-09', 'category': category,
            'rows': rows, 'baseline_rows': deepcopy(rows),
            'source': {'file': '旧原报.xlsx'}, 'versions': [{'preview_id': 'old-import'}]}, 0)


def test_unchanged_legacy_save_restores_both_categories_when_month_is_absent(session):
    legacy_details(session)
    save(session, revision=1)
    effective = W.effective(session, '甲', '2026-09')
    assert effective['values'] == dict(mech_0=None, mech_1=None, mech_2='103.00',
                                     mech_3='206.00', mech_4='100.00', mech_5='200.00')
    assert effective['sources']['mech_3']['basis']['detail_revision'] == 1
    assert W.read(session, W.key('details', '甲', '2026-09', 'monthly'))[1] == 1


@pytest.mark.parametrize('amount', [None, Decimal('0')])
def test_legacy_metadata_save_keeps_existing_manual_month_including_empty_and_zero(session, amount):
    legacy_details(session)
    session.add(ProcMechManual(warehouse_name='甲', ym='2026-09', mech_2=amount))
    session.flush()
    save(session, [row(memo='补备注')], revision=1)
    expected = None if amount is None else '0.00'
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == expected
    assert W.effective(session, '甲', '2026-09')['values']['mech_3'] is None


def test_explicit_legacy_repair_preserves_details_and_rejects_changed_expectations(session):
    legacy_details(session)
    before = {cat: W.read(session, W.key('details', '甲', '2026-09', cat))
              for cat in W.CATEGORY_COLUMNS}
    signature = W.detail_signatures(session)['甲']['2026-09']
    with pytest.raises(MustReportError, match='明细已变化'):
        W.restore_missing_detail_month(session, '甲', '2026-09',
                                       expected_detail_signature='stale')
    assert W.repo.mech_row(session, '甲', '2026-09') is None
    restored = W.restore_missing_detail_month(session, '甲', '2026-09', '旧明细衔接修复',
                                              expected_detail_signature=signature)
    assert restored == ['zero', 'monthly']
    for cat, original in before.items():
        assert W.read(session, W.key('details', '甲', '2026-09', cat)) == original
    state = W.effective(session, '甲', '2026-09')
    for column in ('mech_2', 'mech_3', 'mech_4', 'mech_5'):
        assert state['sources'][column]['mode'] == 'detail'
        assert state['sources'][column]['basis']['detail_revision'] == 1
    assert state['values']['mech_3'] == '206.00'
    assert W.restore_missing_detail_month(session, '甲', '2026-09') == []
    with pytest.raises(MustReportError, match='月金额已存在'):
        W.restore_missing_detail_month(session, '甲', '2026-09',
                                       expected_detail_signature=signature)
    assert W.effective(session, '甲', '2026-09') == state
