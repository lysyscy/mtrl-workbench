"""TAIL-400 fixed external responses; actual routes, ownership, writes and records."""
from contextvars import ContextVar
import json
import time


def create_app():
    from tools.dev.frontend_preview import create_preview_app
    app = create_preview_app()
    from app.core.db import session_scope
    from app.core.errors import ExternalServiceError
    from app.core.session import current_name
    from app.mod02_i8 import client as clients, cookie_store
    from app.mod02_i8.login import LoginResult
    from app.mod02_i8.models import RunRecord
    from app.mod03_notice.models import PaymentNotice
    from sqlalchemy import select
    import httpx

    calls = []
    active_month = ContextVar('fixed_month', default='')
    def no_external(*args, **kwargs):
        raise AssertionError('TAIL-400 forbids real external I/O')
    def fixed_login(*, user, password, allow_kick):
        assert user.startswith('synthetic-') and password == 'synthetic-password'
        if active_month.get() == '2026-02' and not allow_kick:
            return LoginResult(ok=False, conflict=True, detail='fixed online conflict')
        return LoginResult(ok=True, cookie='fixed-cookie', kicked_online=allow_kick)
    def fixed_response(client, path, **kwargs):
        assert 'PaymentBill' in path
        form = kwargs['data']
        dates = json.loads(json.loads(form['queryfilter'])['queryFilter'])
        month = dates['BillDt*date*ge*1'][:7]
        user, _ = client._creds()
        assert user.startswith('synthetic-')
        calls.append({'month': month, 'allow_kick': client._allow_kick, 'account': str(current_name())})
        token = active_month.set(month)
        try:
            client._login()
        finally:
            active_month.reset(token)
        time.sleep(2 if month in ('2026-01', '2026-04', '2026-06') else .25)
        if month in ('2026-03', '2026-09'):
            raise ExternalServiceError('fixed i8 failure: no real request')
        rows = [{'PhId': 'TAIL400-' + month, 'BillNo': 'TAIL400-' + month,
                 'PhidPc_EXName': '隔离验收项目', 'BillName': '合成材料款',
                 'BillDt': month + '-10', 'ApproveAmt': '100.25'}]
        if month == '2026-05':
            rows.append({'PhId': 'TAIL400-UNRESOLVED', 'BillNo': 'TAIL400-UNRESOLVED',
                         'PhidPc_EXName': '合成待归属壳', 'BillName': '未命中项目材料款',
                         'BillDt': month + '-10', 'ApproveAmt': '12.50'})
        return {'Record': rows}
    clients.http_login = fixed_login
    clients.I8Client.post_json = fixed_response
    clients.I8Client.request = no_external
    cookie_store.save = lambda *args, **kwargs: None
    httpx.Client.send = no_external
    httpx.AsyncClient.send = no_external
    from app.mod03_notice.router import get_batch_executor
    def blocked_batch():
        raise AssertionError('TAIL-400 forbids print dispatch')
    app.dependency_overrides[get_batch_executor] = blocked_batch
    from app.mod03_notice.print import dispatch
    dispatch.dispatch_pdf = no_external

    @app.get('/__test__/i8')
    def snapshot():
        with session_scope() as session:
            notices = session.scalars(select(PaymentNotice).where(PaymentNotice.ph_id.like('TAIL400-%'))).all()
            runs = session.scalars(select(RunRecord).order_by(RunRecord.id.desc())).all()
            return {'calls': list(calls), 'notices': [{'ph_id': row.ph_id, 'owner': row.ownership_id, 'amount': str(row.amount_approved)} for row in notices],
                    'runs': [{'target': row.target, 'operator': row.triggered_by, 'status': row.status,
                              'duration': (row.finished_at - row.started_at).total_seconds() if row.finished_at else None} for row in runs]}
    return app
