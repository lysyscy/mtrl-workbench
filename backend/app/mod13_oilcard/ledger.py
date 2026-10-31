"""充值/调整/退款与期初核对；归属快照不随档案关系改变。"""
from datetime import date
from decimal import Decimal
import re
from uuid import uuid4

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import ZERO, amount_text, sum_money, to_money
from app.mod01_projects import service as projects
from .models import OilAccount, OilAccountAssignment, OilCard, OilEntry, OilOpeningBalance
from .service import _check_version, _get, _lock


def _amount(raw):
    try:
        result = to_money(amount_text(raw))
        if abs(result) >= Decimal('10000000000000000'):
            raise ValueError()
        return result
    except (ValueError, ArithmeticError) as exc:
        raise MustReportError('请填写有效金额，最多16位整数和两位小数。') from exc


def _date(raw):
    # 原文保持；无法明确识别的日期/文字/空白都不摊入某个核算月。
    try:
        return date.fromisoformat(raw) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw) else None
    except ValueError:
        return None


def _attribution(session, values, row=None):
    if row is not None and (row.project_id, row.account_id) == (values['project_id'], values['account_id']):
        return {'project_id': row.project_id, 'account_id': row.account_id, 'card_id': row.card_id}
    account = _get(session, OilAccount, values['account_id'])
    if account.project_id != values['project_id']:
        raise MustReportError('项目与用卡账户不对应，请重新选择账户后一起保存。')
    return {'project_id': account.project_id, 'account_id': account.id, 'card_id': account.card_id}


def _fields(session, values, row=None):
    kind, amount = values['kind'], _amount(values['amount'])
    if row is not None and row.kind == 'refund':
        if kind != 'refund' or (row.project_id, row.account_id) != (values['project_id'], values['account_id']):
            raise MustReportError('退款保留原充值的归属与关联，请只更正日期、金额或备注。')
    elif kind not in ('recharge', 'adjustment'):
        raise MustReportError('普通记录请选择充值或调整；退款、转账请使用对应操作。')
    if kind == 'recharge' and amount <= ZERO:
        raise MustReportError('充值金额必须大于0；增减调账请选择调整。')
    if kind == 'refund' and amount >= ZERO:
        raise MustReportError('退款记录显示冲减金额，请填写负数。')
    if row is not None and row.kind == 'recharge' and kind != row.kind and session.scalar(
            select(OilEntry.id).where(OilEntry.related_entry_id == row.id).limit(1)):
        raise MustReportError('这笔充值已有退款关联，不能改为其他类型。')
    return {**_attribution(session, values, row), 'kind': kind, 'amount': amount,
            'date_text': values['date_text'], 'entry_date': _date(values['date_text']), 'remark': values['remark']}


def save_entry(session, values, *, key=None, version=''):
    _lock(session)
    if key is None:
        existing = session.scalar(select(OilEntry).where(OilEntry.request_id == values['request_id']))
        if existing is not None:
            fields = _fields(session, values, existing)
            if any(getattr(existing, k) != v for k, v in fields.items()):
                raise DataConflictError('这次充值请求已登记且内容不同，请重读核对，勿重复入账。')
            return existing
        row = OilEntry(request_id=values['request_id'], **_fields(session, values))
        session.add(row)
    else:
        current = session.get(OilEntry, key, populate_existing=True)
        if current is not None and current.transfer_id is not None:
            from .transfers import update_entry
            return update_entry(session, current, values, version=version)
        row = _get(session, OilEntry, key)
        _check_version(row, version)
        fields = _fields(session, values, row)
        if all(getattr(row, k) == v for k, v in fields.items()):
            return row
        for field, value in fields.items():
            setattr(row, field, value)
    row.version, row.updated_by = str(uuid4()), current_operator()
    session.flush()
    return row


def refund(session, values):
    _lock(session)
    existing = session.scalar(select(OilEntry).where(OilEntry.request_id == values['request_id']))
    if existing is not None:
        if existing.kind != 'refund' or existing.related_entry_id != values['original_id'] or existing.amount != -_amount(values['amount']) or existing.date_text != values['date_text'] or existing.remark != values['remark']:
            raise DataConflictError('这次退款请求已登记且内容不同，请重读核对，勿重复办理。')
        return existing
    original = _get(session, OilEntry, values['original_id'])
    if original.kind != 'recharge':
        raise MustReportError('请选择原充值记录办理实际退款。')
    amount = _amount(values['amount'])
    if amount <= ZERO:
        raise MustReportError('办理退款时请填写大于0的退款金额。')
    row = OilEntry(request_id=values['request_id'], kind='refund', related_entry_id=original.id,
        project_id=original.project_id, account_id=original.account_id, card_id=original.card_id,
        date_text=values['date_text'], entry_date=_date(values['date_text']), amount=-amount,
        remark=values['remark'], updated_by=current_operator())
    session.add(row); session.flush()
    return row


def correct_attribution(session, key, values):
    """明确更正单笔历史快照，不改变账户当前关系或其他旧账。"""
    _lock(session)
    account = _get(session, OilAccount, values['account_id'])
    project = projects.get_project(session, values['project_id'], for_update=True)
    if project is None or project.project_type == 'shell':
        raise MustReportError('请选择项目档案中的正式项目。')
    current = session.get(OilEntry, key, populate_existing=True)
    if current is None:
        raise MustReportError('这条账务已不存在，请重读核对。')
    historical = (current.account_id, current.project_id) == (account.id, project.id) or session.scalar(select(
        OilAccountAssignment.id).where(OilAccountAssignment.account_id == account.id,
        OilAccountAssignment.project_id == project.id).limit(1))
    if account.project_id != project.id and not historical:
        raise MustReportError('项目与账户没有当前或历史关联，请核对后成对选择。')
    if values['card_id'] is not None and _get(session, OilCard, values['card_id']).kind != 'secondary':
        raise MustReportError('账务关联请选择副卡；主卡只维护管理信息。')
    if current.transfer_id:
        from .transfers import _pair
        rows = _pair(session, current.transfer_id)
        row = next(item for item in rows if item.id == key)
        if any(item.id != key and item.account_id == account.id for item in rows):
            raise MustReportError('转入和转出不能改为同一用卡账户。')
    else:
        row = _get(session, OilEntry, key)
        rows = (row,)
    _check_version(row, values['version'])
    fields = {field: values[field] for field in ('project_id', 'account_id', 'card_id')}
    if all(getattr(row, field) == value for field, value in fields.items()):
        return row
    for field, value in fields.items():
        setattr(row, field, value)
    version = str(uuid4())
    for item in rows:
        item.version, item.updated_by = version, current_operator()
    session.flush()
    return row


def entry_data(row):
    return {**{key: getattr(row, key) for key in ('id', 'request_id', 'kind', 'account_id', 'project_id',
        'card_id', 'date_text', 'remark', 'related_entry_id', 'transfer_id', 'version')}, 'amount': str(row.amount),
        'entry_date': row.entry_date.isoformat() if row.entry_date else None}


def _saved_rows(session):
    rows = list(session.scalars(select(OilEntry).order_by(OilEntry.id)))
    from .transfers import validate_transfers
    validate_transfers(rows)
    return rows


def entries(session):
    rows = _saved_rows(session)
    return {'entries': [entry_data(row) for row in rows], 'total_amount': str(sum_money(row.amount for row in rows))}


def export_snapshot(session):
    """全量已保存充值台账；不接受页面筛选，也不把期初当明细重复导出。"""
    data = entries(session)
    project_names = {p.id: p.disp.strip() or '未设置展示名' for p in projects.all_projects(session)}
    accounts = {a.id: a.name for a in session.scalars(select(OilAccount))}
    cards = {c.id: c.card_no or f'卡号待补 #{c.id}' for c in session.scalars(select(OilCard))}
    kinds = {'recharge': '充值', 'adjustment': '调整', 'refund': '退款', 'transfer_out': '转出', 'transfer_in': '转入'}
    return {'total_amount': data['total_amount'], 'rows': [{**row,
        'project': project_names[row['project_id']], 'account': accounts[row['account_id']],
        'card': cards[row['card_id']] if row['card_id'] is not None else '未关联卡片',
        'kind_label': kinds[row['kind']]} for row in data['entries']]}


def stage_opening(session, *, source_key, source_note, account_id, project_id, amount,
                  original_date_text='', cutoff_ym=None, confirmed=False, remark=''):
    """接续业务的小接口；仅供明确来源及确认状态的后续接续流程，不自动推定期初。"""
    _lock(session)
    if not source_key.strip() or not source_note.strip():
        raise MustReportError('期初需要保留来源标识和依据。')
    if confirmed and not (isinstance(cutoff_ym, str) and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', cutoff_ym)):
        raise MustReportError('确认期初前请明确截至月份。')
    fields = {**_attribution(session, {'account_id': account_id, 'project_id': project_id}),
        'source_note': source_note, 'amount': _amount(amount), 'original_date_text': original_date_text,
        'cutoff_ym': cutoff_ym, 'confirmed': confirmed, 'remark': remark}
    existing = session.scalar(select(OilOpeningBalance).where(OilOpeningBalance.source_key == source_key))
    if existing is not None:
        if any(getattr(existing, k) != v for k, v in fields.items()):
            raise MustReportError('这份期初来源已登记且内容不同，请先核对，不重复接续。')
        return existing
    row = OilOpeningBalance(source_key=source_key, updated_by=current_operator(), **fields)
    session.add(row); session.flush()
    return row


def reconciliation(session):
    accounts = list(session.scalars(select(OilAccount).order_by(OilAccount.id)))
    cards = {card.id: card for card in session.scalars(select(OilCard))}
    groups = {}
    def group(account_id, project_id, card_id):
        key = (account_id, project_id, card_id)
        if key not in groups:
            groups[key] = {'account_id': account_id, 'project_id': project_id, 'card_id': card_id,
                          'recharge': [], 'opening': []}
        return groups[key]
    for account in accounts:
        group(account.id, account.project_id, account.card_id)
    for entry in _saved_rows(session):
        group(entry.account_id, entry.project_id, entry.card_id)['recharge'].append(entry.amount)
    for opening in session.scalars(select(OilOpeningBalance).where(OilOpeningBalance.confirmed.is_(True))):
        group(opening.account_id, opening.project_id, opening.card_id)['opening'].append(opening.amount)
    current = {a.id: (a.project_id, a.card_id) for a in accounts}
    rows = []
    for item in groups.values():
        card = cards.get(item['card_id'])
        recharge, opening = sum_money(item.pop('recharge')), sum_money(item.pop('opening'))
        rows.append({**item, 'primary_card_id': card.parent_card_id if card else None,
            'current': current.get(item['account_id']) == (item['project_id'], item['card_id']),
            'recharge_amount': str(recharge), 'opening_amount': str(opening), 'total_amount': str(sum_money((recharge, opening)))})
    return {'rows': rows, 'total_amount': str(sum_money(row['total_amount'] for row in rows))}
