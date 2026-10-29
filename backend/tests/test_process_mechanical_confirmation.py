"""Process amounts require an explicit decision whenever this month has any details."""
from copy import deepcopy
from decimal import Decimal
import pytest
from app.core.errors import MustReportError
from app.mod06_proc import workbench as W, repository as R
from tests.test_mechanical_source_protection import session, save_detail


def details(s, category='monthly', ym='2026-09'):
    return W.save_details(s, {'warehouse':'甲','ym':ym,'category':category,'revision':0,
        'rows':[{'id':'other','device':'升降车','amount':'103.00','tax':'3%专'}]})


def save(s, column='mech_2', value='77.00', **kwargs):
    return W.save_process_mech(s, warehouse='甲', ym='2026-09', values={column:None if value is None else Decimal(value)}, **kwargs)


def test_process_clear_is_unknown_and_explicit_zero_remains_a_real_value(session):
    save(session)
    save(session, value=None)
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] is None
    save(session, value='0')
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '0.00'


def test_clearing_previously_unrecorded_month_keeps_an_explicit_empty_override(session):
    assert R.mech_row(session, '甲', '2026-09') is None
    save(session, value=None)
    assert R.mech_row(session, '甲', '2026-09') is not None
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] is None


def test_clearing_detail_amount_requires_confirmation_and_keeps_details(session):
    state, _ = save_detail(session)
    original = deepcopy(W.read(session, W.key('details', '甲', '2026-09', 'zero')))
    with pytest.raises(MustReportError, match='明细'):
        save(session, value=None)
    save(session, value=None, confirmed=True, effective_signature=state['signature'],
         detail_signature=W.detail_signatures(session)['甲']['2026-09'])
    final = W.effective(session, '甲', '2026-09')
    assert final['values']['mech_2'] is None
    assert final['values']['mech_4'] == '100.00'
    assert final['sources']['mech_2']['mode'] == 'manual'
    assert W.read(session, W.key('details', '甲', '2026-09', 'zero')) == original
    stamp = R.mech_row(session, '甲', '2026-09').updated_at
    save(session, value=None)
    assert R.mech_row(session, '甲', '2026-09').updated_at == stamp


@pytest.mark.parametrize('zero', [0, '0'])
def test_postgresql_cell_clear_preserves_legacy_empty_as_zero(rollback_db, zero):
    from uuid import uuid4
    from app.core import db
    from app.mod06_proc import router
    from app.mod01_projects.models import Project
    wh = '清空入口-' + uuid4().hex
    with db.get_session_factory()() as s:
        s.add(Project(warehouse_name=wh)); s.commit()
        req = router.MechSaveRequest(warehouse=wh, ym='2026-09', values={'mech_2': ''})
        router.api_mech_save(req)
        assert router.api_mech()['effective_values'][wh]['2026-09']['mech_2'] == '0.00'
        router.api_mech_cell_save(req)
        assert router.api_mech()['effective_values'][wh]['2026-09']['mech_2'] is None
        router.api_mech_cell_save(router.MechSaveRequest(warehouse=wh, ym='2026-09', values={'mech_2': zero}))
        assert router.api_mech()['effective_values'][wh]['2026-09']['mech_2'] == '0.00'
        router.api_mech_cell_save(router.MechSaveRequest(warehouse=wh, ym='2026-09', values={'mech_2': None}))
        assert router.api_mech()['effective_values'][wh]['2026-09']['mech_2'] is None


@pytest.mark.parametrize('column',[f'mech_{i}' for i in range(6)])
def test_any_saved_details_require_confirmation_across_all_six_columns(session, column):
    details(session, 'monthly' if column in ('mech_2','mech_4') else 'zero')
    with pytest.raises(MustReportError, match='明细'):
        save(session,column)
    assert getattr(R.mech_row(session,'甲','2026-09'),column) != Decimal('77')


def test_other_month_does_not_require_confirmation(session):
    details(session, ym='2026-08')
    save(session)
    assert W.effective(session,'甲','2026-09')['values']['mech_2']=='77.00'


def test_confirmed_save_changes_one_cell_atomically_and_keeps_details_and_basis(session):
    state,_=save_detail(session)
    original=deepcopy(W.read(session,W.key('details','甲','2026-09','zero')))
    detail_signature=W.detail_signatures(session)['甲']['2026-09']
    save(session, confirmed=True,effective_signature=state['signature'],detail_signature=detail_signature,operator='实际操作者')
    final=W.effective(session,'甲','2026-09')
    assert final['values']['mech_2']=='77.00' and final['values']['mech_4']=='100.00'
    assert final['sources']['mech_2']['mode']=='manual' and final['sources']['mech_4']['mode']=='detail'
    assert final['sources']['mech_2']['basis']['rows'][0]['amount']=='103.00'
    assert final['sources']['mech_2']['history'][-1]['operator']=='实际操作者'
    assert W.read(session,W.key('details','甲','2026-09','zero'))==original
    with pytest.raises(MustReportError,match='明细'):save(session,value='78.00')
    # Repeating an unchanged amount makes no write or new confirmation.
    stamp=R.mech_row(session,'甲','2026-09').updated_at
    save(session)
    assert R.mech_row(session,'甲','2026-09').updated_at==stamp


@pytest.mark.parametrize('stale',['effective','details'])
def test_stale_confirmation_never_switches_source_or_writes_amount(session,stale):
    state,_=save_detail(session)
    signature=W.detail_signatures(session)['甲']['2026-09']
    before=deepcopy(W.effective(session,'甲','2026-09'))
    with pytest.raises(MustReportError,match='变化'):
        save(session,confirmed=True,effective_signature='stale' if stale=='effective' else state['signature'],
             detail_signature='stale' if stale=='details' else signature)
    assert W.effective(session,'甲','2026-09')==before



def test_postgresql_process_cell_api_keeps_legacy_contract_and_requires_new_confirmation(rollback_db):
    from uuid import uuid4
    from app.core import db
    from app.mod06_proc import router
    from app.mod01_projects.models import Project
    wh='确认入口-'+uuid4().hex
    with db.get_session_factory()() as s:
        s.add(Project(warehouse_name=wh));s.commit()
        W.save_details(s,{'warehouse':wh,'ym':'2026-09','category':'monthly','revision':0,
            'rows':[{'id':'row','device':'升降车','amount':'103','tax':'3%专'}]});s.commit()
        req=router.MechSaveRequest(warehouse=wh,ym='2026-09',values={'mech_0':'77'})
        with pytest.raises(MustReportError,match='明细'):router.api_mech_cell_save(req)
        assert R.mech_row(s,wh,'2026-09').mech_0 is None
        router.api_mech_save(req)
        fetched=router.api_mech()
        assert fetched['effective_values'][wh]['2026-09']['mech_0']=='77.00'
        with pytest.raises(MustReportError,match='明细'):
            router.api_mech_cell_save(router.MechSaveRequest(warehouse=wh,ym='2026-09',values={'mech_2':'88'}))
        router.api_mech_cell_save(router.MechSaveRequest(warehouse=wh,ym='2026-09',values={'mech_2':'88'},confirmed=True,
            effective_signature=fetched['effective_signatures'][wh]['2026-09'],detail_signature=fetched['detail_signatures'][wh]['2026-09']))
        s.expire_all()
        final=W.effective(s,wh,'2026-09')
        assert final['values']['mech_0']=='77.00' and final['values']['mech_2']=='88.00'
        assert W.read(s,W.key('details',wh,'2026-09','monthly'))[0]['rows'][0]['amount']=='103'



def test_skill_recording_holds_same_month_lock_as_process_amount_save(rollback_db):
    from uuid import uuid4
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    from app.core import db
    from app.mod01_projects.models import Project
    wh='明细串行-'+uuid4().hex
    with db.get_session_factory()() as s:
        s.add(Project(warehouse_name=wh));s.commit()
        W.record_details(s,{'request_id':wh,'batches':[{'warehouse':wh,'ym':'2026-09','category':'monthly','revision':0,
            'source':{'file':'测试原报'},'rows':[{'id':'row','device':'升降车','amount':'103','tax':'3%专'}]}]})
        with Session(rollback_db.engine) as other:
            other.execute(text("SET LOCAL lock_timeout='150ms'"))
            with pytest.raises(OperationalError):R.lock_mech_month(other,wh,'2026-09')
