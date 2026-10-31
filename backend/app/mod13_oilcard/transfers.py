"""同一事务中的双边账务；共用现有金额、归属、版本和历史事务。"""
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import ZERO, sum_money
from .ledger import _amount, _attribution, _date
from .models import OilEntry
from .service import _check_version, _lock


def validate_pair(rows):
    pair = {row.kind: row for row in rows}
    if len(rows) != 2 or set(pair) != {'transfer_out', 'transfer_in'}:
        raise MustReportError('转账两端未能完整核对，请先重读，不重复登记。')
    outgoing, incoming = pair['transfer_out'], pair['transfer_in']
    if (not outgoing.transfer_id or outgoing.transfer_id != incoming.transfer_id or
            outgoing.version != incoming.version or outgoing.account_id == incoming.account_id or
            outgoing.date_text != incoming.date_text or outgoing.entry_date != incoming.entry_date or
            outgoing.amount >= ZERO or incoming.amount <= ZERO or sum_money(row.amount for row in rows) != ZERO):
        raise MustReportError('转账两端的金额、日期或关联不一致，请先核对。')
    return outgoing, incoming


def validate_transfers(rows):
    groups = {}
    for row in rows:
        if row.transfer_id is not None:
            groups.setdefault(row.transfer_id, []).append(row)
    for pair in groups.values():
        validate_pair(pair)


def _pair(session, transfer_id):
    return validate_pair(list(session.scalars(select(OilEntry).where(
        OilEntry.transfer_id == transfer_id).order_by(OilEntry.id).with_for_update()
        .execution_options(populate_existing=True))))


def create(session, values):
    _lock(session)
    transfer_id = values['request_id']
    existing = list(session.scalars(select(OilEntry).where(OilEntry.transfer_id == transfer_id).order_by(OilEntry.id).with_for_update()))
    amount = _amount(values['amount'])
    if amount <= ZERO:
        raise MustReportError('转账请填写大于0的金额，系统会分别记转出和转入。')
    if existing:
        outgoing, incoming = validate_pair(existing)
        matches = (outgoing.project_id == values['out_project_id'] and outgoing.account_id == values['out_account_id'] and
            incoming.project_id == values['in_project_id'] and incoming.account_id == values['in_account_id'] and
            incoming.amount == amount and outgoing.date_text == values['date_text'] and
            outgoing.remark == values['out_remark'] and incoming.remark == values['in_remark'])
        if not matches:
            raise DataConflictError('这次转账请求已登记且内容不同，请重读核对，勿重复转账。')
        return outgoing, incoming
    if values['out_account_id'] == values['in_account_id']:
        raise MustReportError('转出和转入请选择不同用卡账户；同项目的不同账户可以转账。')
    assignments = {}
    # 先稳定取得两个账户，再插入两端；任一端无效均不产生账务。
    for side in sorted(('out', 'in'), key=lambda side: values[f'{side}_account_id']):
        assignments[side] = _attribution(session, {'account_id': values[f'{side}_account_id'], 'project_id': values[f'{side}_project_id']})
    version = str(uuid4())
    rows = []
    for side, kind, signed in (('out', 'transfer_out', -amount), ('in', 'transfer_in', amount)):
        row = OilEntry(request_id=str(uuid5(UUID(transfer_id), kind)), transfer_id=transfer_id,
            kind=kind, amount=signed, date_text=values['date_text'], entry_date=_date(values['date_text']),
            remark=values[f'{side}_remark'], version=version, updated_by=current_operator(), **assignments[side])
        session.add(row); rows.append(row)
    session.flush()
    return validate_pair(rows)


def update_entry(session, row, values, *, version):
    if values['kind'] != row.kind:
        raise MustReportError('转入和转出类型固定，不能通过普通类型选择更改。')
    assignment = _attribution(session, values, row)
    outgoing, incoming = _pair(session, row.transfer_id)
    target = outgoing if row.kind == 'transfer_out' else incoming
    other = incoming if target is outgoing else outgoing
    _check_version(target, version)
    if assignment['account_id'] == other.account_id:
        raise MustReportError('转入和转出不能改为同一用卡账户。')
    amount = _amount(values['amount'])
    if target.kind == 'transfer_out' and amount >= ZERO or target.kind == 'transfer_in' and amount <= ZERO:
        raise MustReportError('转出记录请保持负数，转入记录请保持正数；两端会一起更新。')
    amount = abs(amount)
    fields = {**assignment, 'remark': values['remark']}
    changed = any(getattr(target, field) != value for field, value in fields.items()) or target.date_text != values['date_text'] or incoming.amount != amount
    if not changed:
        return target
    for field, value in fields.items():
        setattr(target, field, value)
    new_version = str(uuid4())
    for current in (outgoing, incoming):
        current.date_text, current.entry_date = values['date_text'], _date(values['date_text'])
        current.amount = -amount if current.kind == 'transfer_out' else amount
        current.version, current.updated_by = new_version, current_operator()
    session.flush()
    validate_pair((outgoing, incoming))
    return target
