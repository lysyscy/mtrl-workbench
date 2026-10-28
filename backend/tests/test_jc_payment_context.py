"""付款前上下文的真实API/PG回归；复用已有隔离事务夹具。"""
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core import db
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from app.mod11_jc.models import JcContract, JcInvoice, JcPayment
from app.mod11_jc import service as contracts
from tests.test_audit_payment_contract import http_case, _pay  # noqa: F401


@pytest.fixture
def context_case(http_case):
    client, ids, pid, key = http_case
    with db.session_scope() as s:
        c = JcContract(project_id=pid, contract_no='TERMS-CONTEXT', payment_term='90±10天', payment_method='承兑')
        s.add(c);s.flush()
        s.add_all([JcInvoice(contract_id=c.id, kind='supplier', invoice_date='2026-01-01', amount=200),
                   JcInvoice(contract_id=c.id, kind='supplier', invoice_date='2025-01-01', amount=100)])
        for nid in ids:
            s.get(PaymentNotice, nid).category = 'jc'
            assert contracts.act_link_notice(s, notice_id=nid, contract_id=c.id)['ok']
        cid = c.id
    return client, ids, cid


def _context(client, ids, day='2026-04-11'):
    response = client.post('/api/m03/payment-context', json={'ids': ids, 'pay_date': day})
    assert response.status_code == 200
    data = response.json()
    assert data['ok'], data
    return data['rows']


def test_boundary_and_defaults(context_case):
    client, ids, cid = context_case
    r = _context(client, ids)
    assert len(r) == 2 and r[0]['contract_id'] == cid
    assert r[0]['default_pay_method'] == '承兑' and r[0]['default_pay_method_source'] == 'contract'
    w = r[0]['term_warning']
    assert w['max_days'] == 100
    assert [v['invoice_date'] for v in w['invoices']] == ['2026-01-01']
    assert w['invoices'][0]['remind_through'] == '2026-04-11'
    assert _context(client, ids, '2026-04-12')[0]['term_warning'] is None
    with db.session_scope() as s:
        s.get(PaymentNotice, ids[0]).planned_pay_method = '供应链'
    assert _context(client, ids)[0]['default_pay_method'] == '供应链'
    assert _context(client, ids)[0]['default_pay_method_source'] == 'plan'


def test_trade_invoices_only_and_missing_terms(context_case):
    client, ids, cid = context_case
    with db.session_scope() as s:
        s.get(JcContract, cid).trade_co = '贸易公司'
        s.add(JcInvoice(contract_id=cid, kind='trade', invoice_date='2025-01-01', amount=200))
    assert _context(client, ids)[0]['term_warning'] is None
    with db.session_scope() as s:
        s.add(JcInvoice(contract_id=cid, kind='trade', invoice_date='2026-01-01', amount=200))
    assert _context(client, ids)[0]['term_warning']['invoice_side'] == 'trade'
    with db.session_scope() as s:
        s.get(JcContract, cid).payment_term = ''
    assert _context(client, ids)[0]['term_warning'] is None


def test_paid_contract_or_paid_notice_no_warning(context_case):
    client, ids, cid = context_case
    with db.session_scope() as s:
        s.add(JcPayment(contract_id=cid, pay_date='2026-01-02', amount=300, source='manual'))
    assert _context(client, ids)[0]['term_warning'] is None


def test_reminder_does_not_block_payment_and_history_keeps_actual_method(context_case):
    client, ids, cid = context_case
    assert _context(client, ids)[0]['term_warning']
    response = client.post('/api/m03/actions/batch-pay', json={'ids': [ids[0]], 'pay_date': '2026-04-11', 'request_id': 'terms-context-pay'})
    assert response.json()['ok'], response.text
    assert _context(client, ids)[0]['term_warning'] is None
    with db.session_scope() as s:
        actual = s.scalars(select(PaymentFlow).where(PaymentFlow.notice_id==ids[0])).one()
        assert actual.pay_method == '承兑'
        s.get(JcContract, cid).payment_method = '现汇'
    with db.session_scope() as s:
        assert s.scalars(select(PaymentFlow).where(PaymentFlow.notice_id==ids[0])).one().pay_method == '承兑'
    assert _context(client, ids)[1]['default_pay_method'] == '现汇'



def test_no_invoice_and_fallback_and_bad_date(context_case):
    from sqlalchemy import delete
    client, ids, cid = context_case
    with db.session_scope() as s:
        s.execute(delete(JcInvoice).where(JcInvoice.contract_id==cid))
        s.get(JcContract,cid).payment_method=''
    row=_context(client,ids)[0]
    assert row['term_warning'] is None
    assert (row['default_pay_method'],row['default_pay_method_source'])==('现汇','fallback')
    bad=client.post('/api/m03/payment-context',json={'ids':ids,'pay_date':''}).json()
    assert not bad['ok']


def test_read_only_order_unknown_ids_and_unlinked_fallback(context_case):
    client, ids, cid = context_case
    with db.session_scope() as s:
        before = [(p.id, p.amount) for p in s.scalars(select(JcPayment))]
        from app.mod01_projects.models import Project
        project = s.scalars(select(Project).where(Project.id == s.get(PaymentNotice, ids[0]).ownership_id)).one()
        notice = PaymentNotice(ph_id='TERMS-UNLINKED', bill_no='TERMS-UNLINKED',
                               ownership_id=project.id, amount_approved=100, approve_status='已批')
        s.add(notice)
        s.flush()
        unlinked = notice.id
    rows = _context(client, [ids[1], -1, unlinked, ids[0], ids[1]])
    assert [r['notice_id'] for r in rows] == [ids[1], unlinked, ids[0]]
    assert rows[1] == {'notice_id': unlinked, 'default_pay_method': '现汇',
                       'default_pay_method_source': 'fallback', 'term_warning': None}
    with db.session_scope() as s:
        assert [(p.id, p.amount) for p in s.scalars(select(JcPayment))] == before
        assert list(s.scalars(select(PaymentFlow))) == []
