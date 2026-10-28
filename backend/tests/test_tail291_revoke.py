"""291：真实测试库事务与壳两个撤销入口；样本全部回滚。"""
from contextlib import contextmanager
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_actions import apply_stat_change
from app.mod03_notice import repository as notices, domain as D
from app.mod05_flow import repository as flows, router as api
from app.mod05_flow.models import FlowRevokeLog
from app.mod11_jc import repository as jc, service as jcs
from tests.test_acc_jc_pay_link import _project


@pytest.fixture
def sample(monkeypatch):
    with session_scope() as s:
        @contextmanager
        def borrowed():
            with s.begin_nested():
                yield s
        monkeypatch.setattr(api, 'session_scope', borrowed)
        p = _project(s, '__自检仓_291__')
        c = jc.insert_contract(s, project_id=p.id, material_name='291材料')
        jc.insert_invoice(s, contract_id=c.id, kind='supplier', invoice_date='2026-10-01', amount=1000)
        n = PaymentNotice(ph_id='__291__', category='jc', ownership_id=p.id, amount_approved=1000, stat_paid=0)
        s.add(n); s.flush()
        assert jcs.act_link_notice(s, notice_id=n.id, contract_id=c.id)['ok']
        a = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=300)
        b = flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=200)
        apply_stat_change(s, notice_id=n.id, field='stat_paid', value='450', changed_by='291测试')
        yield s, n, p, c, a, b
        s.rollback()


def revoke(b, **kw):
    return api.api_revoke(b.id, reason='291撤销', changed_by='291测试', **kw)


def test_keep_manual(sample):
    s,n,p,c,a,b = sample
    revoke(b, stat_choice='keep')
    assert flows.effective_total_of(s,n.id)==300 and n.stat_paid==450
    d=jcs.build_detail(s,c.id)
    assert d['pay_sum']==450 and d['debt']==550 and d['payment_display_rows'][0]['mismatch']
    assert D.stat_paid_is_manual(notices.list_stat_traces(s,n.id),n.id)


def test_restore_follows_next_payment(sample):
    s,n,p,c,a,b = sample
    revoke(b, stat_choice='auto')
    assert n.stat_paid==300 and jcs.build_detail(s,c.id)['debt']==700
    flows.create_flow(s, notice_id=n.id, project_id=p.id, amount=100)
    assert n.stat_paid==400 and jcs.build_detail(s,c.id)['pay_sum']==400
    traces=notices.list_stat_traces(s,n.id)
    assert [(t.field,t.before,t.after) for t in traces]==[
        (D.F_STAT_PAID,Decimal('500'),Decimal('450')),
        (D.F_STAT_PAID_AUTO,Decimal('450'),Decimal('300'))]
    assert not D.stat_paid_is_manual(traces,n.id)
    apply_stat_change(s,notice_id=n.id,field='stat_paid',value='350',changed_by='291测试')
    assert D.stat_paid_is_manual(notices.list_stat_traces(s,n.id),n.id)
    revoke(a,stat_choice='auto')
    assert [t.field for t in notices.list_stat_traces(s,n.id)]==[D.F_STAT_PAID,D.F_STAT_PAID_AUTO,D.F_STAT_PAID,D.F_STAT_PAID_AUTO]


def test_equal_amount_still_manual_and_auto_no_choice(sample):
    s,n,p,c,a,b=sample
    apply_stat_change(s,notice_id=n.id,field='stat_paid',value='500',changed_by='291测试')
    assert api.api_revoke_info(b.id)['manual'] is True
    with pytest.raises(MustReportError): revoke(b)
    assert b.status=='effective' and n.stat_paid==500
    revoke(b,stat_choice='auto')
    assert api.api_revoke_info(a.id)['manual'] is False
    revoke(a)
    assert n.stat_paid==0
    fresh=PaymentNotice(ph_id='__291_auto__',amount_approved=1000,stat_paid=0)
    s.add(fresh);s.flush()
    f=flows.create_flow(s,notice_id=fresh.id,project_id=p.id,amount=100)
    assert not api.api_revoke_info(f.id)['manual']
    revoke(f)
    assert fresh.stat_paid==0


def facts(s,n,b):
    s.flush()
    return (b.status,b.revoke_reason,n.stat_paid,
            [(t.field,t.before,t.after) for t in notices.list_stat_traces(s,n.id)],
            len(s.execute(select(FlowRevokeLog).where(FlowRevokeLog.flow_id==b.id)).scalars().all()))


def test_invalid_and_duplicate_atomic(sample,monkeypatch):
    s,n,p,c,a,b=sample
    baseline=facts(s,n,b)
    for kwargs in [dict(reason='',stat_choice='auto'),dict(reason='撤销',stat_choice='invalid'),dict(reason='撤销')]:
        with pytest.raises(MustReportError): api.api_revoke(b.id,**kwargs)
        assert facts(s,n,b)==baseline
    expected=api.api_revoke_info(b.id)['expected']
    b.amount=210;s.flush()  # 另一编辑在窗口打开后改变事实，旧快照不能提交
    changed=facts(s,n,b)
    with pytest.raises(MustReportError): revoke(b,stat_choice='auto',expected=expected)
    assert facts(s,n,b)==changed
    with monkeypatch.context() as m:
        def fail(*args): raise MustReportError('模拟统计写入失败')
        m.setattr(flows,'sync_stat_paid',fail)
        with pytest.raises(MustReportError): revoke(b,stat_choice='auto')
        assert facts(s,n,b)==changed
    revoke(b,stat_choice='auto')
    done=facts(s,n,b)
    for _ in range(2):
        with pytest.raises(MustReportError): revoke(b,stat_choice='auto')
        assert facts(s,n,b)==done




def test_concurrent_edit_rejects_stale_snapshot():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from uuid import uuid4
    from sqlalchemy import delete
    from app.mod03_notice.models import NoticeStatLog
    from app.mod05_flow.models import PaymentFlow
    with session_scope() as s:
        n=PaymentNotice(ph_id='__291_concurrent_'+uuid4().hex,amount_approved=1000,stat_paid=0)
        s.add(n);s.flush();nid=n.id
        flows.create_flow(s,notice_id=nid,project_id=None,amount=300)
        b=flows.create_flow(s,notice_id=nid,project_id=None,amount=200);fid=b.id
        apply_stat_change(s,notice_id=nid,field='stat_paid',value='450',changed_by='并发测试')
    try:
        expected = api.api_revoke_info(fid)['expected']
        locked = Event()
        release = Event()
        started = Event()

        def editor():
            with session_scope() as s:
                f = flows.get_flow(s, fid, for_update=True)
                f.amount = 210
                s.flush()
                locked.set()
                assert release.wait(15)

        def revoker():
            started.set()
            return api.api_revoke(fid, reason='并发撤销', stat_choice='auto', expected=expected)
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit = pool.submit(editor)
            assert locked.wait(15)
            rev = pool.submit(revoker)
            assert started.wait(15)
            release.set()
            edit.result(timeout=15)
            with pytest.raises(MustReportError, match='已变化'):
                rev.result(timeout=15)
        with session_scope() as s:
            n = s.get(PaymentNotice, nid)
            b = flows.get_flow(s, fid)
            assert b.amount == 210 and b.status == 'effective' and (n.stat_paid == 450)
            assert flows.effective_total_of(s, nid) == 510
            assert [t.field for t in notices.list_stat_traces(s, nid)] == [D.F_STAT_PAID]
            assert not s.execute(select(FlowRevokeLog).where(FlowRevokeLog.flow_id == fid)).scalars().all()
    finally:
        with session_scope() as s:
            ids = select(PaymentFlow.id).where(PaymentFlow.notice_id == nid)
            s.execute(delete(FlowRevokeLog).where(FlowRevokeLog.flow_id.in_(ids)))
            s.execute(delete(NoticeStatLog).where(NoticeStatLog.notice_id == nid))
            s.execute(delete(PaymentFlow).where(PaymentFlow.notice_id == nid))
            s.execute(delete(PaymentNotice).where(PaymentNotice.id == nid))
