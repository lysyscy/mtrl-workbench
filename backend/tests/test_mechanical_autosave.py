"""Saved detail amounts take effect without a separate adoption action."""
from decimal import Decimal
from tests.test_mechanical_workbench import session, row, save
from app.mod06_proc import workbench as W


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
