"""批量付款真实事务回归：仅backend_verify临时schema中的合成HTTP请求。"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.core import db, session as identity
from app.core.errors import MustReportError
from app.mod03_notice import domain
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_pay_actions import apply_batch_pay
from app.mod05_flow.models import PaymentFlow


@pytest.fixture(scope='module')
def payment_app():
    from app.main import create_app
    from app.mod15_user.models import UserAccount
    engine = db.get_engine()
    with engine.connect() as connection:
        database, schema = connection.execute(text('select current_database(), current_schema()')).one()
        assert database == 'mtrl_workbench_test' and schema.startswith('backend_verify_'), '需要backend_verify专用临时schema'
    app = create_app()
    accounts = [f'__pay_concurrency_{uuid4().hex}_{i}' for i in range(2)]
    with Session(engine) as session, session.begin():
        session.add_all([UserAccount(account=a, name=a, role='user', password='') for a in accounts])
    return engine, app, accounts


@pytest.fixture(autouse=True)
def bounded_transactions(payment_app):
    engine = payment_app[0]
    def timeout(session, transaction, connection):
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
    event.listen(Session, 'after_begin', timeout)
    try:
        yield
    finally:
        event.remove(Session, 'after_begin', timeout)


def notices(engine, count=1):
    with Session(engine) as session, session.begin():
        rows = [PaymentNotice(ph_id=f'__pay_{uuid4().hex}', bill_no='合成并发验证',
            doc_date='2026-10-28', approve_status='已批', category='material',
            amount_approved=Decimal('100'), stat_settle=Decimal('100'), stat_paid=0,
            excluded=False, i8_revoked=False, fields={}) for _ in range(count)]
        session.add_all(rows); session.flush()
        return [row.id for row in rows]


def post(app, account, ids, rid):
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(identity.COOKIE_NAME, identity.make(account))
        response = client.post('/api/m03/actions/batch-pay', json={
            'ids': ids, 'drafts': {str(n): {'pay_method': '现汇', 'amount': '100.00'} for n in ids},
            'pay_date': '2026-10-28', 'remark': '专用schema合成验证', 'request_id': rid})
        return response.status_code, response.json() if response.status_code == 200 else {}


def facts(engine, ids):
    with Session(engine) as session:
        rows = list(session.scalars(select(PaymentFlow).where(PaymentFlow.notice_id.in_(ids)).order_by(PaymentFlow.id)))
        totals = {n: sum((f.amount for f in rows if f.notice_id == n and f.status == 'effective'), Decimal('0')) for n in ids}
        stats = {n.id: n.stat_paid for n in session.scalars(select(PaymentNotice).where(PaymentNotice.id.in_(ids)))}
        return rows, totals, stats


def waiting_on(engine, waiter, blocker):
    with engine.connect() as connection:
        return blocker in connection.execute(text('select pg_blocking_pids(:pid)'), {'pid': waiter}).scalar_one()


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.01)
    return False


@pytest.mark.parametrize('count', [1, 2], ids=['same-notice', 'reversed-batch'])
def test_two_accounts_cannot_pay_the_same_balance(payment_app, monkeypatch, count):
    engine, app, accounts = payment_app
    ids = notices(engine, count); first_order = list(reversed(ids))
    first_ready = threading.Event(); release_first = threading.Event(); second_confirmed = threading.Event()
    pids = {}; original = domain.confirm_batch
    def confirm(*args, **kwargs):
        result = original(*args, **kwargs)
        actor = identity.current_name()
        if actor == accounts[0]:
            first_ready.set()
            assert release_first.wait(8), '第一请求控制门未释放'
        elif actor == accounts[1]:
            second_confirmed.set()
        return result
    def observe(connection, cursor, statement, parameters, context, executemany):
        actor = identity.current_name()
        if actor in accounts and statement.lstrip().lower().startswith('select') and 'payment_notice' in statement:
            pids[actor] = connection.connection.driver_connection.info.backend_pid
    monkeypatch.setattr(domain, 'confirm_batch', confirm)
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(post, app, accounts[0], first_order, uuid4().hex)
            try:
                assert first_ready.wait(4)
                second = pool.submit(post, app, accounts[1], ids, uuid4().hex)
                # 旧实现可在A暂停时直接confirm；新实现必须在真实Postgres锁等待。
                blocked = False
                def interleaved():
                    nonlocal blocked
                    if len(pids) == 2:
                        blocked = waiting_on(engine, pids[accounts[1]], pids[accounts[0]])
                    return blocked or second_confirmed.is_set()
                assert wait_for(interleaved), '未观察到第二请求执行或锁等待'
            finally:
                release_first.set()
            responses = [first.result(timeout=12), second.result(timeout=12)]
        rows, totals, stats = facts(engine, ids)
        assert [status for status, _ in responses] == [200, 200]
        assert [data['ok'] for _, data in responses] == [True, False]
        assert responses[0][1]['created'] == first_order
        assert responses[1][1]['created'] == []
        assert [row.notice_id for row in rows] == first_order
        assert totals == stats == {nid: Decimal('100') for nid in ids}
        assert blocked, '成功结果须来自实际行锁串行，不能只依靠线程偶然顺序'
    finally:
        release_first.set()
        event.remove(engine, 'before_cursor_execute', observe)


@pytest.mark.parametrize('field,value', [
    ('amount_approved', Decimal('50')), ('approve_status', '未批'),
    ('excluded', True), ('i8_revoked', True),
])
def test_lock_wait_refreshes_cached_notice_before_validation(payment_app, field, value):
    engine = payment_app[0]; nid = notices(engine)[0]
    cached = threading.Event(); start = threading.Event(); pids = {}
    def pay_cached():
        with Session(engine, autoflush=False) as session:
            row = session.get(PaymentNotice, nid)
            assert row.amount_approved == Decimal('100') and not row.excluded and not row.i8_revoked
            pids['payment'] = session.connection().connection.driver_connection.info.backend_pid
            cached.set(); assert start.wait(8)
            try:
                with pytest.raises(MustReportError):
                    apply_batch_pay(session, ids=[nid], drafts={nid: {'amount': Decimal('100')}}, pay_date='2026-10-28')
                assert getattr(row, field) == value
            finally:
                session.rollback()
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(pay_cached)
        try:
            assert cached.wait(4)
            with Session(engine) as update:
                row = update.get(PaymentNotice, nid, with_for_update={'key_share': True})
                setattr(row, field, value); update.flush()
                blocker = update.connection().connection.driver_connection.info.backend_pid
                start.set()
                assert wait_for(lambda: waiting_on(engine, pids['payment'], blocker)), '未观察到真实行锁等待'
                update.commit()
        finally:
            start.set()
        worker.result(timeout=12)
    rows, totals, stats = facts(engine, [nid])
    assert rows == [] and totals[nid] == stats[nid] == 0


def test_http_batch_exception_rolls_back_and_releases_locks(payment_app, monkeypatch):
    from app.mod05_flow import service as flows
    engine, app, accounts = payment_app; ids = notices(engine, 2)
    original = flows.create_flow; calls = []
    def fail_second(session, **kwargs):
        calls.append(kwargs['notice_id'])
        if len(calls) == 2:
            raise RuntimeError('合成整批回滚验证')
        return original(session, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(flows, 'create_flow', fail_second)
        assert post(app, accounts[0], ids, uuid4().hex)[0] == 500
    rows, totals, stats = facts(engine, ids)
    assert calls == ids and rows == [] and totals == stats == {nid: 0 for nid in ids}
    status, data = post(app, accounts[1], list(reversed(ids)), uuid4().hex)
    assert status == 200 and data['ok'] and data['created'] == list(reversed(ids))
    assert facts(engine, ids)[1:] == ({nid: Decimal('100') for nid in ids}, {nid: Decimal('100') for nid in ids})
