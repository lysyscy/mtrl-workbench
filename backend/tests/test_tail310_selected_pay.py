"""310：所选付款事实、展示上限与整批事务；只写隔离测试库并回滚。"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.core.errors import MustReportError
from app.mod03_notice import repository as notices, list_view
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod03_notice.notice_pay_actions import apply_batch_pay
from app.mod05_flow import service as flows
from app.mod05_flow.models import PaymentFlow
from app.mod11_jc import repository as jc, service as contracts
from tests.test_acc_jc_pay_link import _project


@pytest.fixture
def sample():
    with Session(get_engine(), autoflush=False) as s:
        assert s.execute(text('select current_database()')).scalar_one() == 'mtrl_workbench_test'
        token = uuid4().hex
        a, b = [PaymentNotice(ph_id=f'__310_{token}_{i}', bill_no=f'310-{i}',
                             doc_date=date, approve_status='已批', category='',
                             amount_approved=Decimal('1000.00'), stat_paid=0)
                for i, date in enumerate(('2020-01-01', '2026-10-12'))]
        s.add_all([a, b]); s.flush()
        try:
            yield s, a, b
        finally:
            s.rollback()


def pay(s, ids, **kw):
    return apply_batch_pay(s, ids=ids, drafts=kw.pop('drafts', {}),
                           pay_date='2026-10-12', **kw)


def paid(s, ids):
    return s.execute(select(PaymentFlow).where(PaymentFlow.notice_id.in_(ids))
                     .order_by(PaymentFlow.id)).scalars().all()


def test_selected_beyond_display_cap_uses_actual_money(sample, monkeypatch):
    s, a, b = sample
    flows.create_flow(s, notice_id=a.id, project_id=None, amount=300)
    revoked = flows.create_flow(s, notice_id=a.id, project_id=None, amount=200)
    revoked.status = 'revoked'; s.flush()
    apply_stat_change(s, notice_id=a.id, field='stat_paid', value='50', changed_by='310测试')

    # SQL limit 反例：缩小展示 cap，无需造 5001 条；旧日期 a 不在展示行内。
    monkeypatch.setattr(notices, 'notice_rows', lambda session: session.execute(
        select(PaymentNotice).where(PaymentNotice.id.in_([a.id, b.id]))
        .order_by(PaymentNotice.doc_date.desc()).limit(1)).scalars().all())
    assert [n.id for n in notices.notice_rows(s)] == [b.id]

    def forbidden(*args, **kwargs):
        raise AssertionError('付款不得走展示/全量事实出口')
    for module, name in ((list_view, 'build_rows'), (notices, 'notice_rows'),
                         (notices, 'stat_trace_index'), (flows, 'list_flows')):
        monkeypatch.setattr(module, name, forbidden)
    seen = []
    for module, name in ((notices, 'get_notices_by_ids'), (flows, 'flows_of_notices'),
                         (contracts, 'links_by_notice')):
        original = getattr(module, name)
        def spy(session, ids=None, *, notice_ids=None, original=original, name=name):
            chosen = ids if notice_ids is None else notice_ids
            assert session is s and chosen == [a.id]
            seen.append(name)
            return original(session, chosen)
        monkeypatch.setattr(module, name, spy)
    a.planned_pay_method = '承兑'
    created, message = pay(s, [a.id])
    assert created == [a.id] and '700.00' in message
    assert len(seen) == 3
    row = paid(s, [a.id])[-1]
    assert row.amount == Decimal('700.00') and row.pay_method == '承兑'
    assert a.stat_paid == Decimal('50.00')


def test_order_duplicates_missing_and_archived_rows(sample, monkeypatch):
    s, a, b = sample
    original = notices.get_notices_by_ids
    selected = []
    def spy(session, ids):
        assert session is s
        selected.append(ids)
        return original(session, ids)
    monkeypatch.setattr(notices, 'get_notices_by_ids', spy)
    missing = -310
    created, _ = pay(s, [b.id, missing, a.id, b.id], drafts={
        a.id: {'amount': Decimal('10')}, b.id: {'amount': Decimal('20')}})
    assert created == [b.id, a.id]
    assert selected == [[b.id, missing, a.id]]
    assert [(f.notice_id, f.amount) for f in paid(s, [a.id, b.id])] == [
        (b.id, Decimal('20.00')), (a.id, Decimal('10.00'))]
    a.excluded = True; b.i8_revoked = True; s.flush()
    with pytest.raises(MustReportError, match='没有可付款的行'):
        pay(s, [b.id, missing, a.id])
    with pytest.raises(MustReportError, match='没有可付款的行'):
        pay(s, [])


def test_selected_links_and_default_full_query(sample, monkeypatch):
    s, a, b = sample
    p = _project(s, f'__自检仓_310_{uuid4().hex}__')
    c = jc.insert_contract(s, project_id=p.id, material_name='310材料')
    a.category = b.category = 'jc'; s.flush()
    contracts.act_link_notice(s, notice_id=a.id, contract_id=c.id)
    assert contracts.links_by_notice(s, [a.id, b.id]) == {a.id: [c.id]}
    assert contracts.links_by_notice(s)[a.id] == [c.id]
    with pytest.raises(MustReportError, match='整批未产生'):
        pay(s, [a.id, b.id])
    assert not paid(s, [a.id, b.id])
    assert pay(s, [a.id])[0] == [a.id]
    def no_query(*args, **kwargs):
        raise AssertionError('空集合不得查库')
    monkeypatch.setattr(s, 'execute', no_query)
    assert contracts.links_by_notice(s, []) == {}
    assert notices.get_notices_by_ids(s, []) == []
    assert flows.flows_of_notices(s, []) == []


@pytest.mark.parametrize('change,draft', [
    ('未批', {}), ('', {'amount': Decimal('1000.01')}),
    ('', {'amount': Decimal('0')}), ('', {'pay_method': '非法'}),
    ('', {'pay_method': '其他'}),
])
def test_entire_batch_validates_before_first_write(sample, change, draft):
    s, a, b = sample
    if change:
        b.approve_status = change; s.flush()
    with pytest.raises(MustReportError, match='整批未产生任何流水'):
        pay(s, [a.id, b.id], drafts={b.id: draft})
    assert not paid(s, [a.id, b.id])


def test_request_id_and_caller_rollback(sample, monkeypatch):
    s, a, b = sample
    original = flows.create_flow
    calls = []
    def fail_second(session, **kw):
        assert session is s
        calls.append(kw['notice_id'])
        if len(calls) == 2:
            raise RuntimeError('310模拟写入失败')
        return original(session, **kw)
    monkeypatch.setattr(flows, 'create_flow', fail_second)
    with pytest.raises(RuntimeError, match='模拟写入失败'):
        with s.begin_nested():
            pay(s, [a.id, b.id])
    assert calls == [a.id, b.id] and not paid(s, [a.id, b.id])
    assert a.stat_paid == 0
    monkeypatch.setattr(flows, 'create_flow', original)
    rid = f'310-{uuid4().hex}'
    pay(s, [a.id], drafts={a.id: {'amount': Decimal('10')}}, request_id=rid)
    with pytest.raises(MustReportError, match='重复提交'):
        pay(s, [a.id], drafts={a.id: {'amount': Decimal('10')}}, request_id=rid)
    assert len(paid(s, [a.id, b.id])) == 1
