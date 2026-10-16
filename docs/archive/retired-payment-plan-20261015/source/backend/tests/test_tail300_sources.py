"""300取数迁移的金额、批量与事务后果；测试库事务全部回滚。"""
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import event
from sqlalchemy import update

from app.core.db import session_scope
from app.mod03_notice import service as notices
from app.mod03_notice.models import PaymentNotice
from app.mod04_plan import service as plans
from app.mod05_flow import repository as flows
from app.mod05_flow.models import PaymentFlow
from app.mod08_inv import service as inventory
from app.mod08_inv.models import InvDetail, InvAdjustment
from app.mod09_fee import repository as fees
from app.mod11_jc import repository as jc, service as contracts
from tests.acc_plugin import acc
from tests.test_acc_jc_pay_link import _project


@acc()
def test_fee_original_excludes_adjustment():
    with session_scope() as s:
        row = InvDetail(ym='2026-08', warehouse_name='__300原单__',
                        direction='出库', cbs_name='CBS-安文费', amount=100)
        other = InvDetail(ym='2026-09', warehouse_name='__300原单__', amount=200)
        s.add_all([row, other]); s.flush()
        s.add(InvAdjustment(row_id=row.id, before_amount=100, amount=900,
                            remark='300隔离调整')); s.flush()
        original = [r for r in fees.inv_rows(s, ym='2026-08') if r['warehouse']=='__300原单__']
        assert original == [{'ym':'2026-08', 'warehouse':'__300原单__',
                             'direction':'出库', 'cbs':'CBS-安文费', 'amount':Decimal('100')}]
        adjusted = next(r for r in inventory.load_rows(s, ym='2026-08') if r['id']==row.id)
        assert adjusted['adj_amount'] == Decimal('900')
        s.rollback()


@acc()
def test_jc_batch_facts_and_query_count():
    with session_scope() as s:
        project = _project(s, '__自检仓_300__')
        made = []
        for i in range(4):
            c = jc.insert_contract(s, project_id=project.id, material_name=f'300材料{i}')
            n = PaymentNotice(ph_id=f'__300_{i}__', bill_no=f'__300_{i}__',
                              amount_approved=1000, stat_paid=Decimal(i*100))
            s.add(n); s.flush()
            contracts.act_link_notice(s, notice_id=n.id, contract_id=c.id)
            s.add_all([PaymentFlow(flow_no=f'__300_e{i}__', notice_id=n.id, amount=10,
                                   status='effective', pay_date='2026-08-01'),
                       PaymentFlow(flow_no=f'__300_r{i}__', notice_id=n.id, amount=999,
                                   status='revoked', pay_date='2026-09-30')])
            made.append((c,n))
        manual = jc.insert_payment(s, contract_id=made[0][0].id, pay_date='2026-07-01', amount=33)
        s.flush()
        calls=[]
        def count(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                calls.append(statement)
        engine=s.get_bind()
        event.listen(engine, 'before_cursor_execute', count)
        try:
            one=jc.payments_of_many(s, [made[0][0].id]); small=len(calls); calls.clear()
            many=jc.payments_of_many(s, [c.id for c,n in made]); large=len(calls); calls.clear()
            assert jc.payments_of_many(s, []) == {} and not calls
        finally:
            event.remove(engine, 'before_cursor_execute', count)
        assert small == large == 3  # 本包子表＋通知书批量＋流水批量，与行数无关。
        for c,n in made:
            linked=next(r for r in many[c.id] if r['source']=='notice')
            assert linked['amount']==n.stat_paid and linked['date']=='2026-08-01'
            assert linked['notice_id']==n.id
        assert next(r for r in one[made[0][0].id] if r['id']==manual.id)['amount']==33
        assert next(r for r in one[made[0][0].id] if r['id']==manual.id)['date']=='2026-07-01'
        amounts=plans.notice_amounts(s)
        assert [(amounts[n.bill_no].approved, amounts[n.bill_no].paid) for c,n in made]==[(1000,10)]*4
        s.rollback()


@acc()
def test_notice_full_input_and_lock_parameters(monkeypatch):
    class Session:
        def __init__(self): self.calls=[]
        def get(self, model, ident, **kw):
            self.calls.append((model,ident,kw)); return SimpleNamespace(id=ident)
        def execute(self, stmt):
            assert stmt._limit_clause is None
            assert str(stmt).endswith('ORDER BY payment_notice.id ASC')
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(id=1),SimpleNamespace(id=5001)]))
        def flush(self): pass
    s=Session()
    assert [n.id for n in flows.notice_rows(s)]==[1,5001]
    row=notices.get_notice(s, 23, with_for_update={'key_share':True}, populate_existing=True)
    assert row.id==23
    monkeypatch.setattr(notices, 'list_stat_traces', lambda session, nid: [])
    monkeypatch.setattr(flows, 'effective_total_of', lambda session, nid: Decimal('75'))
    assert flows.sync_stat_paid(s,23)==75
    assert s.calls==[(PaymentNotice,23,{'with_for_update':{'key_share':True},'populate_existing':True})]*2


@acc()
def test_jc_stat_reads_database_fact_not_cached_notice():
    with session_scope() as s:
        p=_project(s, '__自检仓_300_cache__')
        c=jc.insert_contract(s, project_id=p.id, material_name='300统计事实')
        n=PaymentNotice(ph_id='__300_cache__', amount_approved=1000, stat_paid=10)
        s.add(n); s.flush()
        contracts.act_link_notice(s, notice_id=n.id, contract_id=c.id)
        # 保留本会话旧对象，模拟事实已变而identity map仍旧；原标量join必须读到新事实。
        s.execute(update(PaymentNotice).where(PaymentNotice.id==n.id).values(stat_paid=75)
                  .execution_options(synchronize_session=False))
        assert n.stat_paid==10
        assert jc.payments_of_many(s,[c.id])[c.id][0]['amount']==75
        s.rollback()
