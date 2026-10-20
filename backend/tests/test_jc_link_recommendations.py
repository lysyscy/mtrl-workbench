"""合同推荐的金额边界、只读取数及人工选择保护。"""
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.core.db import session_scope
from app.mod11_jc.domain import recommend_link as recommend
from app.mod11_jc import api, repository as R
from app.mod11_jc.models import JcPayment
from tests.test_acc_jc_pay_link import _project, _contract, _notice
from tests.ui_helpers import ui_page  # noqa: F401


def invoice(i, amount, kind='supplier'):
    return {'id': i, 'amount': Decimal(amount), 'kind': kind, 'date': '2026-10-10'}


@pytest.mark.parametrize('amount,rows,prior,expected', [
    ('0.30', [invoice(1, '0.30')], [], 'invoice'),
    ('0.30', [invoice(1, '0.10'), invoice(2, '0.20'), invoice(3, '0.40')], [], 'invoice'),
    ('24311.25', [invoice(1, '1230931.50')], [{'code': 'OLD', 'amount': '1206620.25'}], 'combined_notices'),
    ('100', [], [], None),
    ('100', [invoice(1, '99.99')], [], None),
])
def test_exact_amounts_and_evidence(amount, rows, prior, expected):
    result = recommend(amount=amount, title='', contract_no='', trade_co='', invoices=rows, linked_notices=prior)
    assert [r['kind'] for r in result['reasons']] == ([expected] if expected else [])


def test_invoice_sides_and_contract_reference():
    rows = [invoice(1, '100'), invoice(2, '60', 'trade'), invoice(3, '40', 'trade')]
    result = recommend(amount='100', title='合同CGHT2026010001，非CGHT20260100012', contract_no='CGHT2026010001',
                       trade_co='贸易公司', invoices=rows, linked_notices=[])
    assert result['reasons'][0]['kind'] == 'contract_no'
    assert result['reasons'][1]['invoice_ids'] == [2, 3]
    result = recommend(amount='160', title='', contract_no='', trade_co='贸易公司', invoices=rows, linked_notices=[])
    assert not result['reasons']  # Never add supplier and trade invoices together.


def test_api_scopes_candidates_serializes_invoices_and_does_not_link(rollback_db):
    with session_scope() as s:
        p = _project(s, '__推荐甲__'); other = _project(s, '__推荐乙__')
        a = _contract(s, project_id=p.id, supplier='甲供应商')
        b = _contract(s, project_id=p.id, supplier='甲供应商')
        wrong = _contract(s, project_id=other.id, supplier='甲供应商')
        wrong_supplier = _contract(s, project_id=p.id, supplier='乙供应商')
        for c in (a, b, wrong, wrong_supplier):
            R.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-10-10', amount='100.01')
        n = _notice(s, ph='__推荐只读__', approved='100.01')
        n.ownership_id = p.id; n.jc_supplier = '甲供应商'; s.flush()
        ids = {a.id, b.id}; nid = n.id
        count = s.scalar(select(func.count()).select_from(JcPayment))
    app = FastAPI(); app.include_router(api.router)
    data = TestClient(app).get('/api/m11/link-recommendations', params={'notice_id': nid}).json()
    assert data['ok'] and {r['id'] for r in data['rows']} == ids
    assert all(r['invoices'][0]['amount'] == '100.01' for r in data['rows'])
    assert all(r['recommendation']['reasons'][0]['kind'] == 'invoice' for r in data['rows'])
    assert data['current_contract_id'] is None and 'selected_id' not in data
    with session_scope() as s:
        assert s.scalar(select(func.count()).select_from(JcPayment)) == count
        assert R.payment_of_notice(s, nid) is None


def test_dialog_shows_invoices_without_preselection_and_blocks_stale_choice(ui_page):
    p = ui_page
    p.evaluate('''() => {
      window.linkWrites=[];
      API.m11LinkRecommendations=async id=>({ok:true,notice_amount:'12345.67',project_key:'测试仓库',supplier:'供应商甲',current_contract_id:null,rows:[
        {id:2,project_seq:1,contract_no:'CGHT20260002',material:'钢材',supplier:'供应商甲',project_key:'测试仓库',contract_amt:'20000',
          invoices:[{id:9,kind:'supplier',date:'2026-10-10',amount:'12345.67'}],recommendation:{reasons:[{kind:'invoice',text:'单笔发票金额一致',invoice_ids:[9],amounts:['12345.67']}]}},
        {id:3,project_seq:2,contract_no:'CGHT20260003',material:'管材',supplier:'供应商甲',project_key:'测试仓库',trade_co:'贸易公司',
          invoices:[{id:10,kind:'trade',date:'2026-10-11',amount:'50.00'}],recommendation:{reasons:[]}}
      ]});
      API.m11Link=async body=>{linkWrites.push(body);return {ok:false,message:'隔离写出口'};};
    }''')
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert p.locator('#jcLinkCandidates').count() == 1, p.locator('#modalRoot').inner_text()
    assert p.locator('#jcLinkCandidates input:checked').count() == 0
    assert p.locator('[data-act="jcLinkOk"]').is_disabled()
    assert '供应商发票' in p.locator('#jcLinkCandidates').inner_text()
    assert '贸易公司发票' in p.locator('#jcLinkCandidates').inner_text()
    assert '2026-10-10' in p.locator('#jcLinkCandidates').inner_text()
    assert '12,345.67' in p.locator('#jcLinkCandidates').inner_text()
    p.evaluate("ACT.jcLinkOk({dataset:{id:'101'}})")
    assert p.evaluate('linkWrites.length') == 0
    p.locator('#jcLinkCandidates input[value="2"]').check()
    assert p.locator('[data-act="jcLinkOk"]').is_enabled()
    p.locator('[data-act="jcLinkOk"]').click()
    assert p.evaluate('linkWrites') == [{'notice_id': 101, 'contract_id': 2}]
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert p.locator('#jcLinkCandidates input:checked').count() == 0
    p.evaluate("() => {closeModal();API.m11LinkRecommendations=async()=>{throw new Error('网络失败')};}")
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert p.get_by_role('button', name='重试', exact=True).is_visible()
    assert p.locator('#jcLinkCandidates').count() == 0
