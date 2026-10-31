"""One receipt service for uploads and delivery adapters; money comes from allocations."""
from datetime import date
from hashlib import sha256
import json
import re
from uuid import uuid4

from sqlalchemy import select

from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.core.money import sum_money
from app.mod01_projects import service as projects
from .models import OilAccount, OilCard, OilInvoice, OilInvoiceAllocation, OilInvoiceOriginal
from .service import _check_version, _get, _lock


def original_data(row):
    return {key: getattr(row, key) for key in ('id', 'sha256', 'invoice_id', 'byte_size', 'outcome', 'reason')}


def _allocations(session, invoice_id):
    return list(session.scalars(select(OilInvoiceAllocation).where(OilInvoiceAllocation.invoice_id == invoice_id).order_by(OilInvoiceAllocation.id)))


def allocation_data(row):
    return {**{key: getattr(row, key) for key in ('id', 'account_id', 'project_id', 'card_id')}, 'amount': str(row.amount)}


def invoice_data(session, row):
    allocations = _allocations(session, row.id)
    if row.status == 'registered' and (row.amount is None or not allocations or sum_money(a.amount for a in allocations) != row.amount):
        raise MustReportError('发票分配合计未能核对，请核对票面和分配后再继续。')
    originals = list(session.scalars(select(OilInvoiceOriginal).where(OilInvoiceOriginal.invoice_id == row.id).order_by(OilInvoiceOriginal.id)))
    return {**{key: getattr(row, key) for key in ('id', 'invoice_no', 'card_no', 'status', 'reason', 'remark', 'version')},
        'invoice_date': row.invoice_date.isoformat() if row.invoice_date else None,
        'amount': str(row.amount) if row.amount is not None else None,
        'allocations': [allocation_data(a) for a in allocations], 'originals': [original_data(o) for o in originals]}


def receive_pdf(session, content, recognized):
    """Caller extracts first. Hash + invoice number are cross-batch identities.

    Receipt evidence is immutable and deliberately not undoable. Later changes
    to notes, facts and allocations use the existing operation history.
    """
    _lock(session)
    digest = sha256(content).hexdigest()
    existing = session.scalar(select(OilInvoiceOriginal).where(OilInvoiceOriginal.sha256 == digest))
    if existing is not None:
        return existing
    number = recognized['invoice_no']
    invoice = session.scalar(select(OilInvoice).where(OilInvoice.invoice_no == number)) if number else None
    outcome, reason = 'received', recognized['reason']
    if invoice is not None:
        first = session.scalar(select(OilInvoiceOriginal).where(OilInvoiceOriginal.invoice_id == invoice.id).order_by(OilInvoiceOriginal.id).limit(1))
        original_facts = json.loads(first.recognized_json) if first else {}
        same = bool(recognized.get('text_sha256') and recognized['text_sha256'] == original_facts.get('text_sha256')) and all(
            recognized[key] == original_facts.get(key) for key in ('invoice_no', 'invoice_date', 'amount', 'card_no'))
        outcome = 'duplicate' if same else 'conflict'
        reason = '同票号票面一致，原件已补档，未重复记金额。' if same else '同票号内容不同，原件已保留待核；原已确认金额保持。'
    else:
        invoice = OilInvoice(invoice_no=number, invoice_date=date.fromisoformat(recognized['invoice_date']) if recognized['invoice_date'] else None,
            amount=recognized['amount'], card_no=recognized['card_no'], reason=reason, updated_by=current_operator())
        session.add(invoice); session.flush()
        if recognized['reliable']:
            candidates = list(session.scalars(select(OilAccount).join(OilCard, OilAccount.card_id == OilCard.id).where(
                OilCard.card_no == recognized['card_no'], OilCard.kind == 'secondary', OilAccount.status == 'active')))
            if len(candidates) == 1:
                account = candidates[0]
                invoice.status, invoice.reason = 'registered', ''
                session.add(OilInvoiceAllocation(invoice_id=invoice.id, account_id=account.id,
                    project_id=account.project_id, card_id=account.card_id, amount=invoice.amount))
            else:
                invoice.reason = '完整卡号有多个在用账户，请确认归属。' if candidates else '完整卡号没有在用账户，请确认归属。'
    source = OilInvoiceOriginal(sha256=digest, invoice_id=invoice.id, content=content, byte_size=len(content),
        outcome=outcome, reason=reason, recognized_json=json.dumps(recognized, ensure_ascii=False, sort_keys=True), received_by=current_operator())
    session.add(source); session.flush()
    return source


def receipt(session, digest):
    source = session.scalar(select(OilInvoiceOriginal).where(OilInvoiceOriginal.sha256 == digest))
    return {'received': source is not None, 'original': original_data(source) if source else None}


def invoices(session):
    rows = [invoice_data(session, row) for row in session.scalars(select(OilInvoice).order_by(OilInvoice.id))]
    return {'invoices': rows, 'total_amount': str(sum_money(a['amount'] for row in rows if row['status'] == 'registered' for a in row['allocations']))}


def save_remark(session, invoice_id, values):
    _lock(session)
    row = _get(session, OilInvoice, invoice_id)
    _check_version(row, values['version'])
    if row.remark != values['remark']:
        row.remark, row.version, row.updated_by = values['remark'], str(uuid4()), current_operator()
        session.flush()
    return row


def registered_allocations(session):
    # Validate whole invoices before exposing any money to reconciliation.
    rows = list(session.scalars(select(OilInvoice).where(OilInvoice.status == 'registered')))
    result = []
    for invoice in rows:
        allocations = _allocations(session, invoice.id)
        if invoice.amount is None or not allocations or sum_money(a.amount for a in allocations) != invoice.amount:
            raise MustReportError('发票分配合计未能核对，请核对后再继续。')
        result.extend(allocations)
    return result


def _safe_name(value):
    return re.sub(r'[\x00-\x1f\\/:*?"<>|]', '_', value).strip(' .')[:70] or '待确认'


def original_file(session, original_id):
    source = session.get(OilInvoiceOriginal, original_id)
    if source is None:
        raise MustReportError('这份发票原件不存在，请重读核对。')
    invoice = _get(session, OilInvoice, source.invoice_id)
    allocations = _allocations(session, invoice.id)
    project_ids = {a.project_id for a in allocations}
    names = {p.id: p.disp.strip() or '未设置展示名' for p in projects.all_projects(session)}
    project = '多项目' if len(project_ids) > 1 else names.get(next(iter(project_ids)), '待确认') if project_ids else '待确认'
    tail = invoice.card_no[-5:] if invoice.card_no else '卡号待核'
    amount = str(invoice.amount) if invoice.amount is not None else '金额待核'
    number = invoice.invoice_no or f'待核-{invoice.id}'
    if source.outcome == 'conflict':
        # A conflicting PDF is evidence awaiting confirmation, not the main
        # invoice's facts or attribution. Its filename must describe its bytes.
        recognized = json.loads(source.recognized_json)
        tail = recognized['card_no'][-5:] if recognized['card_no'] else '卡号待核'
        amount = recognized['amount'] or '金额待核'
        number = recognized['invoice_no'] or f'待核-{source.id}'
        project = '待确认'
    suffix = f' 待核原件-{source.id}' if source.outcome == 'conflict' else ''
    filename = f'{_safe_name(tail)} {_safe_name(project)} {amount} {_safe_name(number)}{suffix}.pdf'
    content = source.content
    if len(content) != source.byte_size or sha256(content).hexdigest() != source.sha256:
        raise MustReportError('发票原件完整性未能核对，请联系维护人员检查备份。')
    return content, filename


def export_snapshot(session):
    data = invoices(session)
    names = {p.id: p.disp.strip() or '未设置展示名' for p in projects.all_projects(session)}
    accounts = {a.id: a.name for a in session.scalars(select(OilAccount))}
    return {**data, 'rows': [{**row, 'project': '、'.join(dict.fromkeys(names[a['project_id']] for a in row['allocations'])) or '待确认',
        'account': '、'.join(accounts[a['account_id']] for a in row['allocations']) or '待确认'} for row in data['invoices']]}
