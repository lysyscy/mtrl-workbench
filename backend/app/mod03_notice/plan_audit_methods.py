"""Atomic notice planned-method updates; no payment or amount writes."""
import re
from app.core.money import to_money
from app.mod05_flow.models import PAY_METHODS


def validate_changes(preview):
    if not isinstance(preview, dict) or preview.get('schema') != 1 or not preview.get('changes'):
        raise ValueError('没有可回写的变更')
    if (not isinstance(preview.get('changes'), list)
            or not isinstance(preview.get('snapshot'), dict)
            or not re.fullmatch(r'[0-9a-f]{64}', str(preview.get('source_sha256', '')))
            or not re.fullmatch(r'[0-9a-f]{64}', str(preview['snapshot'].get('database_fingerprint', '')))):
        raise ValueError('回写清单缺少原表或系统快照凭据')
    seen = set()
    for c in preview['changes']:
        if (not isinstance(c, dict) or type(c.get('id')) is not int or c['id'] in seen
                or not isinstance(c.get('bill_no'), str) or not c['bill_no'].strip()):
            raise ValueError('回写清单定位无效或重复')
        seen.add(c['id'])
        if c.get('new') not in PAY_METHODS or c.get('old') not in ('', *PAY_METHODS):
            raise ValueError('回写清单含无效付款方式')
        if (type(c.get('ownership_id')) is not int or c['ownership_id'] <= 0
                or type(c.get('source_row')) is not int or c['source_row'] <= 0):
            raise ValueError('回写清单缺少归属或来源行')
        approved, paid, flow, planned = (to_money(c.get(k)) for k in
                                        ('approved', 'paid', 'flow_amount', 'planned_amount'))
        if approved < 0 or paid < 0 or flow != approved or planned <= 0 or planned > approved-paid:
            raise ValueError('回写清单不满足金额核对条件')


def apply_changes(conn, preview):
    from sqlalchemy import inspect, text
    from app.core.money import to_money
    if 'planned_pay_method' not in {c['name'] for c in inspect(conn).get_columns('payment_notice')}:
        raise ValueError('拟付款方式字段尚未迁移，未写入')
    # 单据号并非唯一约束；锁表防止检查与更新之间插入重号。
    if conn.dialect.name == 'postgresql':
        conn.exec_driver_sql('LOCK TABLE payment_notice, payment_flow IN SHARE ROW EXCLUSIVE MODE')
    for c in preview['changes']:
        rows = conn.execute(text(
            'SELECT id, ownership_id, planned_pay_method, excluded, i8_revoked, amount_approved, '
            "(SELECT COALESCE(SUM(amount),0) FROM payment_flow f WHERE f.notice_id=payment_notice.id "
            "AND f.status='effective') AS paid "
            'FROM payment_notice WHERE bill_no=:bill_no'), c).mappings().all()
        if len(rows) != 1 or rows[0]['id'] != c['id']:
            raise ValueError(f"单据已不唯一或不存在：{c['bill_no']}；整批未写入")
        n = rows[0]
        if (n['ownership_id'] != c['ownership_id'] or n['planned_pay_method'] != c['old']
                or n['excluded'] or n['i8_revoked']):
            raise ValueError(f"单据状态或原值已变化：{c['bill_no']}；整批未写入")
        if to_money(n['amount_approved']) != to_money(c['approved']) or to_money(n['paid']) != to_money(c['paid']):
            raise ValueError(f"审批或已付金额已变化：{c['bill_no']}；须重新核对，整批未写入")
    for c in preview['changes']:
        updated = conn.execute(text(
            'UPDATE payment_notice SET planned_pay_method=:new '
            'WHERE id=:id AND planned_pay_method=:old'), c)
        if updated.rowcount != 1:
            raise ValueError('写入期间原值变化，整批回滚')
