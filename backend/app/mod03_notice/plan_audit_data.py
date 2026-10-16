"""Complete comparison facts, in a PostgreSQL read-only snapshot."""
from datetime import datetime
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

def database_fingerprint(engine):
    url = engine.url
    identity = [url.drivername, url.host, url.port, url.database]
    return sha256(json.dumps(identity).encode()).hexdigest()


def capture():
    from app.core.db import get_engine
    from app.core.money import sum_money
    from sqlalchemy import inspect, text

    engine = get_engine()
    if engine.dialect.name != 'postgresql':
        raise ValueError('实时快照仅使用工作台PostgreSQL只读事务；测试请提供离线快照')
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one() == 'on'
            columns = {c['name'] for c in inspect(conn).get_columns('payment_notice')}
            method = 'planned_pay_method' if 'planned_pay_method' in columns else "'' AS planned_pay_method"
            notices = [dict(r) for r in conn.execute(text(
                'SELECT id, bill_no, ownership_id, project_name, payee, amount_approved, '
                f'approve_status, excluded, i8_revoked, fetched_at, {method} '
                'FROM payment_notice ORDER BY id')).mappings()]
            flows = {}
            for r in conn.execute(text('SELECT notice_id,amount,pay_date FROM payment_flow '
                                       "WHERE status='effective' ORDER BY pay_date,id")).mappings():
                flows.setdefault(r['notice_id'], []).append({'amount': str(r['amount']), 'pay_date': r['pay_date']})
            projects = [dict(r) for r in conn.execute(text(
                'SELECT id, disp, warehouse_name, name_full, match_keywords, status, project_type FROM project ORDER BY id'
            )).mappings()]
            for n in notices:
                n['approved'] = str(n.pop('amount_approved'))
                n['payments'] = flows.get(n['id'], [])
                n['paid'] = str(sum_money(f['amount'] for f in n['payments']))
                n['fetched_at'] = n['fetched_at'].isoformat() if n['fetched_at'] else None
    return {
        'schema': 1, 'captured_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'scope': '全部月份通知书（含剔除/撤单）及全部生效付款流水；不访问i8',
        'complete': True, 'database_fingerprint': database_fingerprint(engine),
        'method_column_available': 'planned_pay_method' in columns,
        'notices': notices, 'projects': projects,
    }
