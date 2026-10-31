"""油卡档案业务出口；项目身份只通过项目域服务取得。"""
from hashlib import sha256
import json
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select, text

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import ZERO, sum_money
from app.core.references import project_references as collect_references
from app.mod01_projects import service as projects
from .models import OilAccount, OilAccountAssignment, OilCard, OilEntry, OilOpeningBalance, OilInvoiceAllocation, OilFeeCustom, OilBigCustom


def _lock(session):
    # 档案量小，串行校验主副卡关系，避免交叉修改形成非法关联。
    session.execute(text('SELECT pg_advisory_xact_lock(453, 13)'))


def _get(session, model, key):
    row = session.get(model, key, with_for_update=True, populate_existing=True)
    if row is None:
        raise MustReportError('这条油卡档案已不存在，请重读核对。')
    return row


def _check_version(row, version):
    if row.version != version:
        raise DataConflictError('这条档案已被修改，请重读核对后再保存。')


def _card_fields(session, values, row=None):
    card_no = values.get('card_no')
    if card_no is not None:
        card_no = card_no.strip() or None
    kind, parent_id = values['kind'], values['parent_card_id']
    if kind == 'primary' and parent_id is not None:
        raise MustReportError('主卡不能再选择所属主卡。')
    if parent_id is not None:
        parent = _get(session, OilCard, parent_id)
        if parent.kind != 'primary' or row is not None and parent.id == row.id:
            raise MustReportError('所属主卡请选择另一张主卡。')
        if parent.status == 'archived' and (row is None or row.parent_card_id != parent_id):
            raise MustReportError('这张主卡已归档，请选择在用主卡；已有关系可保留。')
    if row is not None and row.kind != kind:
        if session.scalar(select(OilCard.id).where(OilCard.parent_card_id == row.id).limit(1)):
            raise MustReportError('这张主卡仍有关联副卡，请先核对所属主卡。')
        if kind == 'primary' and session.scalar(select(OilAccount.id).where(OilAccount.card_id == row.id).limit(1)):
            raise MustReportError('这张副卡仍关联用卡账户，不能改成主卡。')
        if kind == 'primary' and any(session.scalar(select(model.id).where(model.card_id == row.id).limit(1))
                for model in (OilEntry, OilOpeningBalance, OilInvoiceAllocation)):
            raise MustReportError('这张副卡仍有历史账务，不能改成主卡。')
    if card_no is not None:
        duplicate = session.scalar(select(OilCard.id).where(OilCard.card_no == card_no))
        if duplicate is not None and (row is None or duplicate != row.id):
            raise MustReportError('完整卡号已建档，请选择已有卡片；尾号相同的不同卡可分别建档。')
    return {'card_no': card_no, 'kind': kind, 'parent_card_id': parent_id,
        'status': values.get('status', row.status if row is not None else 'active'), 'remark': values['remark']}


def _account_fields(session, values, row=None):
    name = values['name'].strip()
    if not name:
        raise MustReportError('请填写用卡账户名称。')
    project = projects.get_project(session, values['project_id'], for_update=True)
    if project is None or project.project_type == 'shell':
        raise MustReportError('请选择项目档案中的正式项目。')
    if values['card_id'] is not None:
        card = _get(session, OilCard, values['card_id'])
        if card.kind != 'secondary':
            raise MustReportError('用卡账户请选择副卡；主卡只维护管理信息。')
        if card.status == 'archived' and (row is None or row.card_id != card.id):
            raise MustReportError('这张副卡已归档，请选择在用副卡；已有账户关联可保留。')
    return {key: name if key == 'name' else values[key] for key in ('name', 'project_id', 'card_id', 'status', 'remark')}


def _assign(session, row):
    session.add(OilAccountAssignment(account_id=row.id, project_id=row.project_id,
        card_id=row.card_id, changed_by=current_operator()))


def save_card(session, values, *, key=None, version=''):
    _lock(session)
    if key is None:
        existing = session.scalar(select(OilCard).where(OilCard.request_id == values['request_id']))
        if existing is not None:
            return existing
        row = OilCard(request_id=values['request_id'], **_card_fields(session, values))
        session.add(row)
    else:
        row = _get(session, OilCard, key)
        _check_version(row, version)
        fields = _card_fields(session, values, row)
        if all(getattr(row, k) == v for k, v in fields.items()):
            return row
        for field, value in fields.items():
            setattr(row, field, value)
    row.version, row.updated_by = str(uuid4()), current_operator()
    session.flush()
    return row


def save_account(session, values, *, key=None, version=''):
    _lock(session)
    if key is None:
        existing = session.scalar(select(OilAccount).where(OilAccount.request_id == values['request_id']))
        if existing is not None:
            return existing
        row = OilAccount(request_id=values['request_id'], **_account_fields(session, values))
        session.add(row)
        changed = True
    else:
        row = _get(session, OilAccount, key)
        _check_version(row, version)
        fields = _account_fields(session, values, row)
        if all(getattr(row, k) == v for k, v in fields.items()):
            return row
        changed = any(getattr(row, k) != fields[k] for k in ('project_id', 'card_id'))
        for field, value in fields.items():
            setattr(row, field, value)
    row.version, row.updated_by = str(uuid4()), current_operator()
    session.flush()
    if changed:
        _assign(session, row)
    return row


def replace_card(session, account_id, values):
    """换卡只修改选定账户；新卡、关联事件与账户在同一历史事务中保存。"""
    _lock(session)
    fingerprint = sha256(json.dumps({'account_id': account_id, **values}, sort_keys=True).encode('utf-8')).hexdigest()
    existing = session.scalar(select(OilAccountAssignment).where(OilAccountAssignment.request_id == values['request_id']))
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise DataConflictError('这次换卡请求已保存且内容不同，请重读核对。')
        return _get(session, OilAccount, account_id), existing
    row = _get(session, OilAccount, account_id)
    _check_version(row, values['version'])
    if (values['card_id'] is None) == (values['new_card'] is None):
        raise MustReportError('请选择已有副卡或建立一张新副卡。')
    if values['new_card'] is not None:
        card = save_card(session, {**values['new_card'], 'kind': 'secondary',
            'request_id': str(uuid5(UUID(values['request_id']), 'replacement-card'))})
    else:
        card = _get(session, OilCard, values['card_id'])
    if card.kind != 'secondary' or card.id == row.card_id:
        raise MustReportError('换卡请选择另一张副卡；卡号录错请更正原卡号。')
    if card.status == 'archived':
        raise MustReportError('这张副卡已归档，换卡请选择在用副卡。')
    event = OilAccountAssignment(account_id=row.id, project_id=row.project_id, previous_card_id=row.card_id,
        card_id=card.id, change_kind='replacement', request_id=values['request_id'],
        request_fingerprint=fingerprint, changed_by=current_operator())
    session.add(event)
    row.card_id, row.version, row.updated_by = card.id, str(uuid4()), current_operator()
    session.flush()
    return row, event


def card_data(row):
    return {key: getattr(row, key) for key in ('id', 'request_id', 'card_no', 'kind', 'status', 'parent_card_id', 'remark', 'version')}


def account_data(row):
    return {key: getattr(row, key) for key in ('id', 'request_id', 'name', 'project_id', 'card_id', 'status', 'remark', 'version')}


def archives(session):
    return {'cards': [card_data(row) for row in session.scalars(select(OilCard).order_by(OilCard.id))],
            'accounts': [account_data(row) for row in session.scalars(select(OilAccount).order_by(OilAccount.id))]}


def assignments(session, account_id):
    if session.get(OilAccount, account_id) is None:
        raise MustReportError('用卡账户已不存在，请重读核对。')
    return [assignment_data(row) for row in session.scalars(
                 select(OilAccountAssignment).where(OilAccountAssignment.account_id == account_id)
                 .order_by(OilAccountAssignment.id))]


def total_export_snapshot(session):
    """全量台账的同一业务快照；域锁只持有到调用方读完并退出事务。"""
    from . import invoices, ledger

    _lock(session)
    archive = archives(session)
    accounts = {row['id']: row for row in archive['accounts']}
    cards = {row['id']: row for row in archive['cards']}
    project_names = {p.id: p.disp.strip() or '未设置展示名' for p in projects.all_projects(session)}

    def card_no(key):
        return (cards[key]['card_no'] or f'卡号待补 #{key}') if key is not None else '未关联卡片'

    def attribution(row):
        return {**row, 'project': project_names[row['project_id']],
            'account': accounts[row['account_id']]['name'], 'card': card_no(row['card_id'])}

    def account_status(key):
        return '在用' if accounts[key]['status'] == 'active' else '归档'

    reconciliation = ledger.reconciliation(session)
    reconciliation = {**reconciliation, 'rows': [{**attribution(row),
        'account_status': account_status(row['account_id']),
        'attribution': '当前归属' if row['current'] else '历史归属',
        'primary_card': card_no(row['primary_card_id']) if row['primary_card_id'] is not None else '未关联主卡',
        'account_remark': accounts[row['account_id']]['remark'],
        'primary_remark': cards[row['primary_card_id']]['remark'] if row['primary_card_id'] is not None else ''}
        for row in reconciliation['rows']]}
    reconciliation['recharge_amount'] = str(sum_money(row['recharge_amount'] for row in reconciliation['rows']))
    reconciliation['opening_amount'] = str(sum_money(row['opening_amount'] for row in reconciliation['rows']))
    invoice_snapshot = invoices.export_snapshot(session)
    allocation_rows = [{**attribution(allocation), 'invoice_id': invoice['id'],
        'invoice_no': invoice['invoice_no'], 'invoice_date': invoice['invoice_date'],
        'status': invoice['status'], 'kind': invoice['kind'],
        'registered_amount': allocation['amount'] if invoice['status'] == 'registered' else str(ZERO)}
        for invoice in invoice_snapshot['rows'] for allocation in invoice['allocations']]
    opening_rows = [attribution({'id': row.id, 'source_key': row.source_key,
        'source_note': row.source_note, 'account_id': row.account_id, 'project_id': row.project_id,
        'card_id': row.card_id, 'original_date_text': row.original_date_text, 'cutoff_ym': row.cutoff_ym,
        'status': '已确认' if row.confirmed else '待确认', 'amount': str(row.amount),
        'booked_amount': str(row.amount if row.confirmed else ZERO), 'remark': row.remark})
        for row in session.scalars(select(OilOpeningBalance).order_by(OilOpeningBalance.id))]
    account_rows = [{**attribution({**row, 'account_id': row['id']}),
        'status_label': account_status(row['id'])} for row in archive['accounts']]
    card_rows = [{**row, 'kind_label': '主卡' if row['kind'] == 'primary' else '副卡',
        'status_label': '在用' if row['status'] == 'active' else '归档',
        'parent_card': card_no(row['parent_card_id']) if row['parent_card_id'] is not None else ''}
        for row in archive['cards']]
    assignment_rows = [{**attribution(assignment_data(row)),
        'previous_card': card_no(row.previous_card_id) if row.previous_card_id is not None else '',
        'change_label': '换卡' if row.change_kind == 'replacement' else '关联变更'}
        for row in session.scalars(select(OilAccountAssignment).order_by(OilAccountAssignment.id))]
    # 两类自定义额各自保存原快照；大表截至值不能跨月份求和。
    custom_rows = [{'id': row.id, 'kind': label, 'project_id': row.project_id,
        'project': project_names[row.project_id], 'ym': row.ym,
        'amount': str(row.amount) if row.amount is not None else None, 'remark': row.remark}
        for model, label in ((OilFeeCustom, '特殊费用当月自定义额'), (OilBigCustom, '大表截至月额外快照'))
        for row in session.scalars(select(model).order_by(model.project_id, model.ym, model.id))]
    return {'reconciliation': reconciliation, 'ledger': ledger.export_snapshot(session),
        'invoices': invoice_snapshot, 'allocations': allocation_rows, 'openings': opening_rows,
        'accounts': account_rows, 'cards': card_rows, 'assignments': assignment_rows, 'customs': custom_rows}


def assignment_data(row):
    return {**{key: getattr(row, key) for key in ('id', 'account_id', 'project_id', 'card_id',
        'previous_card_id', 'change_kind', 'request_id', 'changed_by')}, 'changed_at': row.changed_at.isoformat()}


def project_references(session, project_id, warehouse_name, *, lock=False):
    return collect_references(session, ((OilAccount, '用卡账户'),
        (OilAccountAssignment, '油卡关联历史'), (OilEntry, '油卡充值与调整'),
        (OilOpeningBalance, '油卡期初依据'), (OilInvoiceAllocation, '油卡发票分配'),
        (OilFeeCustom, '用油自定义额'), (OilBigCustom, '大表用油额外值')), project_id, warehouse_name, lock=lock)


def fee_facts(session, *, project_id, end_ym):
    from .reporting import fee_facts as read
    return read(session, project_id=project_id, end_ym=end_ym)


def save_fee_custom(session, **values):
    from .reporting import save_fee_custom as save
    return save(session, **values)


def lock_reporting(session):
    _lock(session)


def big_oil_amount(session, *, project_id, ym):
    from .reporting import big_amount
    return big_amount(session, project_id=project_id, ym=ym)


def stage_big_custom(session, **values):
    from .reporting import stage_big_custom as stage
    return stage(session, **values)
