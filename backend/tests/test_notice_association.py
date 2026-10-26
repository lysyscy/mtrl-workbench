"""Association drafts never save; contract authority and archived exits remain consistent."""
import pytest
from app.core.db import session_scope
from app.mod11_jc import service as S, repository as R
from app.mod03_notice.notice_api_router import api_jc_supplier, JcSupplierIn
from app.mod03_notice.list_view import build_rows
from tests.test_acc_jc_pay_link import _project, _contract, _notice


def test_draft_scope_and_contract_supplier_authority(rollback_db):
    with session_scope() as s:
        p = _project(s, '__关联两步__')
        a = _contract(s, project_id=p.id, supplier='甲')
        b = _contract(s, project_id=p.id, supplier='乙')
        n = _notice(s, ph='__关联两步__')
        n.ownership_id = p.id; n.jc_supplier = '甲'; s.flush()
        assert {r['id'] for r in S.link_recommendations(s, n.id)['rows']} == {a.id}
        assert {r['id'] for r in S.link_recommendations(s, n.id, supplier='')['rows']} == {a.id,b.id}
        assert S.link_recommendations(s, n.id, supplier='乙')['rows'][0]['id'] == b.id
        assert n.jc_supplier == '甲' and R.payment_of_notice(s, n.id) is None
        assert S.act_link_notice(s, notice_id=n.id, contract_id=b.id)['ok']
        s.flush()
        assert n.jc_supplier == '乙'
        assert not api_jc_supplier(JcSupplierIn(notice_id=n.id, supplier='甲'), s)['ok']
        n.jc_supplier = '历史旧值'; s.flush()
        row = build_rows(s, notice_ids=[n.id])[0]
        assert row.jc_supplier == '乙' and n.jc_supplier == '历史旧值'
        assert S.act_unlink_notice(s, notice_id=n.id)['ok']
        assert n.jc_supplier == '乙'
        assert api_jc_supplier(JcSupplierIn(notice_id=n.id, supplier='待关联丙'), s)['ok']


@pytest.mark.parametrize('state', ['excluded','i8_revoked','category'])
def test_archived_relation_can_be_viewed_and_removed_only(rollback_db, state):
    with session_scope() as s:
        p = _project(s, '__关联归档__')
        a = _contract(s, project_id=p.id, supplier='甲')
        b = _contract(s, project_id=p.id, supplier='乙')
        n = _notice(s, ph='__关联归档__')
        n.ownership_id = p.id; s.flush()
        assert S.act_link_notice(s, notice_id=n.id, contract_id=a.id)['ok']
        setattr(n, state, 'material' if state == 'category' else True); s.flush()
        data = S.link_recommendations(s, n.id, supplier='')
        assert data['ok'] and data['read_only'] and [r['id'] for r in data['rows']] == [a.id]
        assert not S.act_link_notice(s, notice_id=n.id, contract_id=b.id)['ok']
        assert not api_jc_supplier(JcSupplierIn(notice_id=n.id,supplier='乙'),s)['ok']
        assert R.payment_of_notice(s, n.id).contract_id == a.id
        assert S.act_unlink_notice(s, notice_id=n.id)['ok']
        assert n.jc_supplier == '甲'
        assert not S.link_recommendations(s, n.id, supplier='')['ok']


def test_wrong_or_missing_project_is_rejected_without_removing_current(rollback_db):
    with session_scope() as s:
        p = _project(s, '__关联项目甲__'); q = _project(s, '__关联项目乙__')
        a = _contract(s, project_id=p.id); b = _contract(s, project_id=q.id)
        n = _notice(s, ph='__关联项目__'); n.ownership_id = p.id; s.flush()
        assert S.act_link_notice(s, notice_id=n.id, contract_id=a.id)['ok']
        assert not S.act_link_notice(s, notice_id=n.id, contract_id=b.id)['ok']
        assert R.payment_of_notice(s, n.id).contract_id == a.id
        n.ownership_id=None; s.flush()
        assert not S.act_link_notice(s, notice_id=n.id, contract_id=b.id)['ok']
        assert R.payment_of_notice(s, n.id).contract_id == a.id
