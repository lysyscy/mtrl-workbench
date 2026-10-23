"""Excel候选回写的合同关联/约定防过期保护；真实HTTP和任务专用PG schema。"""
from hashlib import sha256
import json
import pytest
from sqlalchemy import select
from app.core import db
from app.mod03_notice import plan_audit_api as API
from app.mod11_jc import service as JC
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from app.mod11_jc.models import JcContract
from app.mod11_jc import service as contracts
from tests.test_jc_payment_context import context_case  # noqa: F401
from tests.test_audit_payment_contract import http_case  # noqa: F401


@pytest.mark.parametrize('case',['normal','conflict','confirmed','stale_method','stale_link'])
def test_contract_method_write_and_stale_context(context_case,case):
    client,ids,cid=context_case
    client.app.dependency_overrides[API.audit_user]=lambda:'isolated-plan-test'
    with db.session_scope() as s:
        context=JC.plan_audit_contexts(s.connection())
        assert context[ids[0]]=={'id':cid,'contract_no':'TERMS-CONTEXT','payment_method':'承兑'}
        changes=[{'id':nid,'bill_no':s.get(PaymentNotice,nid).bill_no,'ownership_id':s.get(PaymentNotice,nid).ownership_id,
                  'source_row':index+3,'old':'','new':'承兑','approved':'100','paid':'0','flow_amount':'100','planned_amount':'10',
                  'jc_contract':context[nid],'method_exception_confirmed':False} for index,nid in enumerate(ids)]
    if case in ('conflict','confirmed'):
        changes[-1]['new']='供应链'
        changes[-1]['method_exception_confirmed']=case=='confirmed'
    with db.session_scope() as s:
        if case=='stale_method':s.get(JcContract,cid).payment_method='现汇'
        elif case=='stale_link':contracts.act_unlink_notice(s,notice_id=ids[-1])
    preview={'schema':1,'source_sha256':'a'*64,
             'snapshot':{'database_fingerprint':API.DATA.database_fingerprint(db.get_engine())},'changes':changes}
    raw=json.dumps(preview,ensure_ascii=False)
    response=client.post('/api/m03/plan-audit/methods',json={'preview_json':raw,'approved_sha256':sha256(raw.encode()).hexdigest()})
    success=case in ('normal','confirmed')
    assert response.status_code==(200 if success else 409),response.text
    with db.session_scope() as s:
        assert [s.get(PaymentNotice,nid).planned_pay_method for nid in ids]==([c['new'] for c in changes] if success else ['',''])
        assert not list(s.scalars(select(PaymentFlow).where(PaymentFlow.notice_id.in_(ids))))
        assert all(s.get(PaymentNotice,nid).amount_approved==100 for nid in ids)
    if case=='confirmed':
        context=client.post('/api/m03/payment-context',json={'ids':ids,'pay_date':'2026-04-11'}).json()['rows']
        assert context[-1]['default_pay_method']=='供应链'
        assert context[-1]['default_pay_method_source']=='plan'
