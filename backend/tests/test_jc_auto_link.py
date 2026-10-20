"""应付来源批量关联：精确匹配、只补空缺、确认重验与分页完整性。"""
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.db import session_scope
from app.core.errors import ExternalServiceError
from app.mod11_jc import service as S, repository as R, api
from app.mod02_i8.payable_source import fetch_payables
from tests.test_acc_jc_pay_link import _project, _contract, _notice
from tests.ui_helpers import ui_page  # noqa: F401


def source(no='CGHT1', amount='100.01'):
    return dict(id='P1',code='CGYF1',contract_no=no,project='项目全名',supplier='甲',amount=Decimal(amount))


def test_preview_confirm_recheck_and_existing_link(rollback_db, monkeypatch):
    with session_scope() as s:
        p=_project(s,'__应付批量__'); c=_contract(s,project_id=p.id,supplier='甲'); c.contract_no='CGHT1'
        other=_contract(s,project_id=p.id,supplier='甲'); other.contract_no='CGHT2'
        ns=[_notice(s,ph='__应付'+str(i),approved='100.01') for i in range(4)]
        for n in ns:
            n.ownership_id=p.id; n.project_name='项目全名'; n.jc_supplier='甲'; n.approve_status='已批'
        ns[2].excluded=True; ns[3].approve_status='未批'
        s.flush(); ids=[n.id for n in ns]; cid=c.id; oldid=other.id
        S.act_link_notice(s,notice_id=ids[1],contract_id=oldid)
    monkeypatch.setattr(api,'_read_payables',lambda:[source()])
    app=FastAPI(); app.include_router(api.router); client=TestClient(app)
    data=client.post('/api/m11/auto-link-preview',json={'notice_ids':ids}).json()
    assert data['ready']==1
    ready=[r for r in data['rows'] if r['contract_id']]
    assert ready[0]['contract_id']==cid
    with session_scope() as s:
        assert R.payment_of_notice(s,ids[0]) is None
        ambiguous=S.auto_link_plan(s,[ids[0]],[source(),source('CGHT2')]); assert ambiguous['ready']==0
    # A changed amount/source after preview must not cause an unexpected association.
    body={'notice_ids':ids,'selections':[{k:r[k] for k in ('notice_id','contract_id','amount','payable_codes')} for r in ready]}
    monkeypatch.setattr(api,'_read_payables',lambda:[source(amount='100.02')])
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==0
    monkeypatch.setattr(api,'_read_payables',lambda:[source()])
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==1
    assert client.post('/api/m11/auto-link',json=body).json()['linked']==0
    with session_scope() as s:
        assert R.payment_of_notice(s,ids[0]).contract_id==cid
        assert R.payment_of_notice(s,ids[1]).contract_id==oldid
        assert R.payment_of_notice(s,ids[2]) is None
        assert R.payment_of_notice(s,ids[3]) is None
        n=s.get(__import__('app.mod03_notice.models',fromlist=['PaymentNotice']).PaymentNotice,ids[0])
        S.act_unlink_notice(s,notice_id=n.id)
        assert S.auto_link_plan(s,[n.id],[{**source(),'project':'其他项目'}])['ready']==0
        assert S.auto_link_plan(s,[n.id],[{**source(),'supplier':'其他供应商'}])['ready']==0


def test_source_pagination_and_money():
    class Client:
        calls=[]
        def post_json(self,path,**kw):
            self.calls.append(kw['data'])
            start=int(kw['data']['start'])
            return {'Success':True,'totalRows':'201','Record':[dict(PhId=str(i),BillNo='CGYF'+str(i),AsrFlag=1,WfFlag=2,PhidFcur_EXName='人民币',ExchRate=1,AppAmtVatFc='0.10') for i in range(start,min(start+200,201))]}
    client=Client(); rows=fetch_payables(client)
    assert len(rows)==201 and rows[0]['amount']==Decimal('0.10')
    assert [r['start'] for r in client.calls]==['0','200']
    class Broken:
        def post_json(self,*a,**kw):return {'Success':True,'totalRows':'3','Record':[]}
    with pytest.raises(ExternalServiceError):fetch_payables(Broken())


def test_button_previews_before_batch_write(ui_page):
    p=ui_page
    p.evaluate("""() => {
      window.autoWrites=[];
      API.m11AutoLinkPreview=async b=>{window.previewIds=b.notice_ids;return {ok:true,rows:[{notice_id:101,code:'DOC-101',contract_id:2,contract_no:'CGHT1',amount:'12345.67',payable_codes:['CGYF1']}],ready:1};};
      API.m11AutoLink=async b=>{autoWrites.push(b);return {ok:false,message:'隔离写出口'};};
    }""")
    p.get_by_role('button',name='一键关联集采合同',exact=True).click()
    assert p.evaluate('previewIds')==[101]
    assert p.evaluate('autoWrites.length')==0
    assert 'CGYF1' in p.locator('#modalRoot').inner_text()
    p.get_by_role('button',name='关联这 1 条',exact=True).click()
    assert len(p.evaluate('autoWrites'))==1
    assert p.evaluate('autoWrites[0].selections[0].contract_id')==2
