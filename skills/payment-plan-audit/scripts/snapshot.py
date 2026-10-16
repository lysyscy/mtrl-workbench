"""Load complete comparison facts through the authenticated workbench API."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def configure(repo=None):
    if repo:
        repo = Path(repo).resolve()
        if not (repo / 'backend/app/core/money.py').is_file():
            raise ValueError('工作台仓库路径不正确')
        runtime = repo / 'backend'
    else:
        runtime = Path(__file__).resolve().parents[1] / 'resources/audit-runtime.zip'
        if not runtime.is_file():
            raise ValueError('技能核对规则包缺失，请重新安装完整技能')
    sys.path.insert(0, str(runtime))
    return repo


def capture(repo=None, *, server=None, session_file=None):
    from remote import call
    return validate(call('/api/m03/plan-audit/snapshot', server=server, session_file=session_file))


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('complete') is not True:
        raise ValueError('快照缺少已确认的完整范围，不能据此判断单据查不到')
    if not data.get('captured_at') or not data.get('scope'):
        raise ValueError('快照必须记录时间和范围')
    ids = [n['id'] for n in data['notices']]
    if len(ids) != len(set(ids)):
        raise ValueError('快照通知书ID重复')
    for n in data['notices']:
        for key in ('bill_no', 'approved', 'paid', 'planned_pay_method', 'ownership_id',
                    'project_name', 'payee', 'excluded', 'i8_revoked'):
            if key not in n:
                raise ValueError(f'快照缺少字段：{key}')
        if type(n['excluded']) is not bool or type(n['i8_revoked']) is not bool:
            raise ValueError('快照剔除/撤单状态必须明确')
        if 'payments' in n:
            from app.core.money import sum_money, to_money
            if sum_money(p['amount'] for p in n['payments']) != to_money(n['paid']):
                raise ValueError('快照付款日期明细与已付合计不符')
    return data
