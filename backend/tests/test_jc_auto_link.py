"""应付来源批量关联：精确匹配、只补空缺、确认重验与分页完整性。"""
from contextlib import nullcontext
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.db import session_scope
from app.core.errors import ExternalServiceError
from app.mod11_jc import domain as D, service as S, repository as R, api
from app.mod02_i8.payable_source import fetch_payables
from tests.test_acc_jc_pay_link import _project, _contract, _notice


def source(no='CGHT1', amount='100.01'):
    return dict(id='P1',code='CGYF1',contract_no=no,project='项目全名',supplier='甲',amount=Decimal(amount))


def test_preview_confirm_recheck_and_existing_link(rollback_db, monkeypatch):
    with session_scope() as s:
        p=_project(s,'__应付批量__'); c=_contract(s,project_id=p.id,supplier='甲'); c.contract_no='CGHT1'
        other=_contract(s,project_id=p.id,supplier='甲'); other.contract_no='CGHT2'
        ns=[_notice(s,ph='__应付'+str(i),approved='100.01') for i in range(4)]
        for n in ns:
            n.ownership_id=p.id; n.project_name='项目全名'; n.jc_supplier='甲'; n.approve_status='已批'
        ns[0].jc_supplier=''
        ns[2].excluded=True; ns[3].approve_status='未批'
        s.flush(); ids=[n.id for n in ns]; cid=c.id; oldid=other.id
        S.act_link_notice(s,notice_id=ids[1],contract_id=oldid)
    monkeypatch.setattr(api, 'unified_i8_session', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(api,'_read_payables',lambda **kw:[source()])
    app=FastAPI(); app.include_router(api.router); client=TestClient(app)
    data=client.post('/api/m11/auto-link-preview',json={'notice_ids':ids, 'session_mode':'browser', 'device_id':'test'}).json()
    assert data['ready']==1
    ready=[r for r in data['rows'] if r['contract_id']]
    assert ready[0]['contract_id']==cid
    with session_scope() as s:
        assert R.payment_of_notice(s,ids[0]) is None
        ambiguous=S.auto_link_plan(s,[ids[0]],[source(),source('CGHT2')]); assert ambiguous['ready']==0
    # A changed amount/source after preview must not cause an unexpected association.
    body={'notice_ids':ids,'session_mode':'browser','device_id':'test','selections':[{k:r[k] for k in ('notice_id','contract_id','amount','payable_codes')} for r in ready]}
    monkeypatch.setattr(api,'_read_payables',lambda **kw:[source(amount='100.02')])
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==0
    monkeypatch.setattr(api,'_read_payables',lambda **kw:[source()])
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==1
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==0
    with session_scope() as s:
        assert R.payment_of_notice(s,ids[0]).contract_id==cid
        assert R.payment_of_notice(s,ids[1]).contract_id==oldid
        assert R.payment_of_notice(s,ids[2]) is None
        assert R.payment_of_notice(s,ids[3]) is None
        n=s.get(__import__('app.mod03_notice.models',fromlist=['PaymentNotice']).PaymentNotice,ids[0])
        assert n.jc_supplier == '甲'
        S.act_unlink_notice(s,notice_id=n.id)
        assert S.auto_link_plan(s,[n.id],[{**source(),'project':'其他项目'}])['ready']==0
        assert S.auto_link_plan(s,[n.id],[{**source(),'supplier':'其他供应商'}])['ready']==0


def test_title_supplier_narrows_exact_payables():
    contracts = [
        {'id': 1, 'project_key': '仓库', 'supplier': '甲方物资有限公司', 'contract_no': 'CGHT1', 'tag': D.TAG_IN},
        {'id': 2, 'project_key': '仓库', 'supplier': '乙方建材有限公司', 'contract_no': 'CGHT2', 'tag': D.TAG_IN},
    ]
    payables = [{**source(c['contract_no']), 'code': f"CGYF{c['id']}", 'supplier': c['supplier']} for c in contracts]
    inputs = dict(amount=Decimal('100.01'), project_key='仓库', supplier='', remark='',
                  contracts=contracts, payables=payables, prior_approved={})
    result = D.auto_link_evidence(**inputs, title='甲方物资/钢材')
    assert result['contract_id'] == 1 and result['payable_codes'] == ['CGYF1']
    assert 'contract_id' not in D.auto_link_evidence(**inputs, title='钢材')


def test_remark_mentions_take_priority_and_excluded_contract_blocks_fallback(rollback_db):
    with session_scope() as s:
        p = _project(s, '__合同号批量__')
        explicit = _contract(s, project_id=p.id, supplier='乙')
        explicit.contract_no = 'CGHTXX-20260101-2'
        exact = _contract(s, project_id=p.id, supplier='甲')
        exact.contract_no = 'CGHT1'
        excluded = _contract(s, project_id=p.id, supplier='乙')
        excluded.contract_no = 'CGHT202507040001'
        excluded.tag = D.TAG_OUT
        n = _notice(s, ph='__合同号备注__', approved='100.01')
        blocked = _notice(s, ph='__不纳入合同号__', approved='100.01')
        for notice in (n, blocked):
            notice.ownership_id = p.id
            notice.project_name = '项目全名'
            notice.approve_status = '已批'
        n.fields = {'BillName': '材料款', 'Remark': '扣除合同cghtxx-20260101-2质保金'}
        blocked.fields = {'BillName': '合同编号：202507040001 材料款'}
        s.flush()

        fallback = S.auto_link_plan(s, [n.id, blocked.id], [source()])['rows']
        assert fallback[0]['contract_id'] == explicit.id
        assert fallback[0]['payable_codes'] == [explicit.contract_no]
        assert fallback[0]['reason'] == '通知书明确提及本合同号'
        assert fallback[1]['contract_id'] is None
        assert fallback[1]['reason'] == '通知书提及的合同未纳入台账，保留人工处理'

        referenced_payable = {**source(explicit.contract_no, '125.00'), 'supplier': '乙', 'code': 'CGYF2'}
        with_payable = S.auto_link_plan(s, [n.id], [source(), referenced_payable])['rows'][0]
        assert with_payable['contract_id'] == explicit.id
        assert with_payable['payable_codes'] == ['CGYF2']

        n.jc_supplier = '甲'
        assert S.auto_link_plan(s, [n.id], [source()])['ready'] == 0


def test_split_payable_uses_valid_linked_approval_amounts(rollback_db):
    with session_scope() as s:
        p = _project(s, '__拆付批量__')
        contract = _contract(s, project_id=p.id, supplier='甲')
        contract.contract_no = 'CGHT1'
        n = _notice(s, ph='__本次尾款__', approved='75.01')
        n.ownership_id = p.id
        n.project_name = '项目全名'
        n.approve_status = '已批'
        for i, (amount, flags) in enumerate([
            ('20.00', {}), ('5.00', {'i8_revoked': True, 'revoked_joint': True}),
            ('80.00', {'excluded': True}), ('30.00', {'i8_revoked': True}), ('40.00', {'category': 'material'}),
        ]):
            previous = _notice(s, ph=f'__已关联拆付{i}__', approved=amount, paid='0')
            previous.ownership_id = p.id
            for key, value in flags.items():
                setattr(previous, key, value)
            R.insert_payment(s, contract_id=contract.id, pay_date='', amount=0, source='notice', notice_id=previous.id)
        s.flush()
        split_payable = source(amount='100.01')
        row = S.auto_link_plan(s, [n.id], [split_payable])['rows'][0]
        assert row['contract_id'] == contract.id
        assert row['amount'] == '75.01' and row['payable_codes'] == ['CGYF1']
        assert row['reason'] == '与已关联通知书合计对应唯一应付合同'
        assert R.payment_of_notice(s, n.id) is None

        direct = _contract(s, project_id=p.id, supplier='甲')
        direct.contract_no = 'CGHT2'
        exact = S.auto_link_plan(s, [n.id], [split_payable, source('CGHT2', '75.01')])['rows'][0]
        assert exact['contract_id'] == direct.id and exact['reason'] == '应付合同来源唯一'

        settled_notice = _notice(s, ph='__已有独立应付__', approved='60.00')
        settled_notice.ownership_id = p.id
        S.act_link_notice(s, notice_id=settled_notice.id, contract_id=contract.id)
        settled_payable = {**source(amount='60.00'), 'code': 'CGYF_SETTLED'}
        assert S.auto_link_plan(s, [n.id], [split_payable, settled_payable])['rows'][0]['contract_id'] == contract.id

        additional = _notice(s, ph='__另一笔未对平已关联拆付__', approved='60.00')
        additional.ownership_id = p.id
        S.act_link_notice(s, notice_id=additional.id, contract_id=contract.id)
        assert S.auto_link_plan(s, [n.id], [split_payable])['ready'] == 0


def test_source_pagination_and_money():
    class Client:
        calls=[]
        def post_json(self,path,**kw):
            self.calls.append(kw['data'])
            start=int(kw['data']['start'])
            return {'Success':True,'totalRows':'202','Record':[
                dict(PhId=str(i), BillNo='CGYF'+str(i), AsrFlag=0 if i == 200 else 1,
                     WfFlag=6 if i == 201 else 2, PhidFcur_EXName='人民币', ExchRate=1, AppAmtVatFc='0.10')
                for i in range(start, min(start+200, 202))
            ]}
    client=Client(); rows=fetch_payables(client)
    assert len(rows)==201 and rows[0]['amount']==Decimal('0.10')
    assert rows[-1]['code'] == 'CGYF200'
    assert 'CGYF201' not in {r['code'] for r in rows}
    assert [r['start'] for r in client.calls]==['0','200']
    class Broken:
        def post_json(self,*a,**kw):return {'Success':True,'totalRows':'3','Record':[]}
    with pytest.raises(ExternalServiceError):fetch_payables(Broken())
