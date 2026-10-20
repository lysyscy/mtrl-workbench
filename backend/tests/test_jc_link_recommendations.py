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
        blank = _contract(s, project_id=p.id, supplier='甲供应商')
        a.contract_date = '2026-10-01'; b.contract_date = '2025-01-01'; blank.contract_date = ''
        a.contract_amt = Decimal('150.02'); b.contract_amt = Decimal('90.00')
        b.trade_co = '贸易公司'; b.trade_contract_amt = Decimal('200.02')
        R.insert_invoice(s, contract_id=b.id, kind='trade', invoice_date='2026-10-10', amount='100.01')
        wrong = _contract(s, project_id=other.id, supplier='甲供应商')
        wrong_supplier = _contract(s, project_id=p.id, supplier='乙供应商')
        for c in (a, b, wrong, wrong_supplier):
            R.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-10-10', amount='100.01')
        n = _notice(s, ph='__推荐只读__', approved='100.01')
        n.ownership_id = p.id; n.jc_supplier = '甲供应商'; s.flush()
        ids = {a.id, b.id, blank.id}; ordered = [b.id, a.id, blank.id]; nid = n.id
        count = s.scalar(select(func.count()).select_from(JcPayment))
    app = FastAPI(); app.include_router(api.router)
    data = TestClient(app).get('/api/m11/link-recommendations', params={'notice_id': nid}).json()
    assert data['ok'] and {r['id'] for r in data['rows']} == ids
    assert [r['id'] for r in data['rows']] == ordered
    by_id = {r['id']: r for r in data['rows']}
    assert by_id[ordered[0]]['supplier_uninvoiced'] == '-10.01'
    assert by_id[ordered[0]]['trade_uninvoiced'] == '100.01'
    assert by_id[ordered[1]]['supplier_uninvoiced'] == '50.01'
    assert by_id[ordered[1]]['trade_uninvoiced'] is None
    assert by_id[ordered[2]]['supplier_uninvoiced'] == '100.00'
    assert all(r['recommendation']['reasons'][0]['kind'] == 'invoice' for r in data['rows'] if r['invoices'])
    assert data['current_contract_id'] is None and 'selected_id' not in data
    with session_scope() as s:
        assert s.scalar(select(func.count()).select_from(JcPayment)) == count
        assert R.payment_of_notice(s, nid) is None


def test_dialog_shows_invoices_without_preselection_and_blocks_stale_choice(ui_page):
    p = ui_page
    p.evaluate('''() => {
      window.linkWrites=[];
      API.m11LinkRecommendations=async id=>({ok:true,notice_amount:'12345.67',notice_title:'支付12345.67元',project_key:'测试仓库',supplier:'供应商甲',current_contract_id:2,rows:[
        {id:2,project_seq:1,contract_no:'CGHT20260002',material:'钢材',supplier:'供应商甲',project_key:'测试仓库',contract_amt:'20000',supplier_uninvoiced:'7654.33',pay_sum:'50.00',settle:'1000.00',debt:'950.00',
          invoices:[{id:9,kind:'supplier',date:'2026-10-10',amount:'12345.67'}],recommendation:{reasons:[{kind:'invoice',text:'单笔发票金额一致',invoice_ids:[9],amounts:['12345.67']}]}},
        {id:3,project_seq:2,contract_no:'CGHT20260003',material:'管材',supplier:'供应商甲',project_key:'测试仓库',trade_co:'贸易公司',supplier_uninvoiced:'-20',trade_uninvoiced:null,
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
    assert '未开票金额 7,654.33' in p.locator('#jcLinkCandidates').inner_text()
    assert '超开票金额 20.00' in p.locator('#jcLinkCandidates').inner_text()
    assert '未开票金额未确定' in p.locator('#jcLinkCandidates').inner_text()
    assert p.locator('.jc-link-money').count() >= 7
    assert p.locator('.jc-link-money').filter(has_text='12345.67').count() == 1
    p.evaluate("ACT.jcLinkOk({dataset:{id:'101'}})")
    assert p.evaluate('linkWrites.length') == 0
    p.locator('#jcLinkCandidates input[value="2"]').check()
    assert '金额按本条通知书未关联时计算' in p.locator('#modalRoot').inner_text()
    assert '关联前欠款 950.00' in p.locator('#modalRoot').inner_text()
    assert p.locator('[data-act="jcLinkOk"]').is_enabled()
    p.locator('[data-act="jcLinkOk"]').click()
    assert p.evaluate('linkWrites') == [{'notice_id': 101, 'contract_id': 2}]
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert p.locator('#jcLinkCandidates input:checked').count() == 0
    p.evaluate("() => {closeModal();API.m11LinkRecommendations=async()=>{throw new Error('网络失败')};}")
    p.evaluate("ACT.jcLink({dataset:{id:'101'}})")
    assert p.get_by_role('button', name='重试', exact=True).is_visible()
    assert p.locator('#jcLinkCandidates').count() == 0


@pytest.mark.parametrize('stat_paid,trade', [('80.01', False), ('0', False), ('80.01', True)])
def test_change_link_uses_unlinked_amounts_without_mutating_relation(rollback_db, stat_paid, trade):
    from app.mod11_jc import service as S
    with session_scope() as s:
        p = _project(s, '__更改基准__')
        c = _contract(s, project_id=p.id, supplier='甲')
        if trade:
            c.trade_co = '贸易公司'; c.trade_contract_amt = Decimal('2000')
        R.insert_invoice(s, contract_id=c.id, kind='trade' if trade else 'supplier',
                         invoice_date='2026-10-01', amount='1000')
        n = _notice(s, ph='__更改当前__', approved='100', paid=stat_paid)
        prior = _notice(s, ph='__更改其他__', approved='30', paid='30')
        n.ownership_id = prior.ownership_id = p.id
        n.jc_supplier = prior.jc_supplier = '甲'
        S.act_link_notice(s, notice_id=n.id, contract_id=c.id)
        S.act_link_notice(s, notice_id=prior.id, contract_id=c.id)
        R.insert_payment(s, contract_id=c.id, pay_date='2026-10-01', amount='20', source='manual', notice_id=None)
        link_id = R.payment_of_notice(s, n.id).id
        live = next(r for r in S.build_list(s)['rows'] if r['id'] == c.id)
        assert live['pay_sum'] == Decimal(stat_paid) + Decimal('50')
        data = S.link_recommendations(s, n.id)
        row = next(r for r in data['rows'] if r['id'] == c.id)
        assert data['current_contract_id'] == c.id
        assert row['pay_sum'] == Decimal('50.00') and row['debt'] == Decimal('950.00')
        assert row['notice_ids'] == [prior.id]
        assert row['settle'] == Decimal('1000.00')
        assert row['recommendation']['reasons'] == []
        assert R.payment_of_notice(s, n.id).id == link_id
        again = next(r for r in S.build_list(s)['rows'] if r['id'] == c.id)
        assert again['pay_sum'] == live['pay_sum'] and again['debt'] == live['debt']
