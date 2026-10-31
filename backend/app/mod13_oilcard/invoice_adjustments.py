"""Explicit invoice correction, whole allocation and local credit/void transactions."""
from datetime import date
import json
import re
from uuid import uuid4

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import ZERO, sum_money
from .ledger import _amount, _attribution
from .invoices import number_owner
from .models import OilInvoice, OilInvoiceAllocation, OilInvoiceNumber, OilInvoiceOriginal
from .service import _check_version, _get, _lock


def validate_credits(session):
    rows = {r.id: r for r in session.scalars(select(OilInvoice))}
    credited = {}
    for row in rows.values():
        if row.status != 'registered':
            continue
        if row.kind == 'normal':
            if row.amount is None or row.amount <= ZERO or row.related_invoice_id is not None:
                raise MustReportError('原票金额或关联未能核对，请先核对发票。')
            continue
        original = rows.get(row.related_invoice_id)
        if row.amount is None or row.amount >= ZERO or original is None or original.status != 'registered' or original.kind != 'normal':
            raise MustReportError('红票须关联有效原票，金额填负数。')
        credited.setdefault(original.id, []).append(-row.amount)
    for key, amounts in credited.items():
        if sum_money(amounts) > rows[key].amount:
            raise MustReportError('本台账累计红冲金额超过原票金额，请一起核对原票和红票。')


def _touch(row):
    row.version, row.updated_by = str(uuid4()), current_operator()


def _parent_touch(session, ids):
    # Credits and their parent share an aggregate version in normal history.
    # A later credit by another actor must block undoing an older parent value.
    for key in sorted(x for x in set(ids) if x is not None):
        _touch(_get(session, OilInvoice, key))


def _alias(session, row, number):
    owner = number_owner(session, number)
    if owner is not None and owner != row.id:
        raise DataConflictError('此票号已属于另一张发票（含原件识别号），请先核对，不能重复登记。')
    existing = session.scalar(select(OilInvoiceNumber).where(OilInvoiceNumber.number == number))
    if existing is not None:
        if existing.invoice_id != row.id:
            raise DataConflictError('此票号已属于另一张发票（含原识别票号），请先核对，不能重复登记。')
    else:
        session.add(OilInvoiceNumber(invoice_id=row.id, number=number))


def _facts(values, kind):
    number = values['invoice_no'].strip()
    if not re.fullmatch(r'(?:\d{8}|\d{20})', number):
        raise MustReportError('请按票面填写完整的8位或20位发票号码。')
    try:
        issued = date.fromisoformat(values['invoice_date'])
    except (ValueError, TypeError) as exc:
        raise MustReportError('请填写明确的开票日期。') from exc
    amount = _amount(values['amount'])
    if kind == 'normal' and amount <= ZERO or kind == 'credit' and amount >= ZERO:
        raise MustReportError('普通发票填正数；实际红冲请使用“登记红冲”填写负数并关联原票。')
    card = (values.get('card_no') or '').strip() or None
    if card is not None and not re.fullmatch(r'(?:\d{16}|\d{19})', card):
        raise MustReportError('卡号请填写完整16位或19位；无法确认时留空，人工明确选择账户。')
    return {'invoice_no': number, 'invoice_date': issued, 'amount': amount, 'card_no': card}


def _replace_allocations(session, row, values):
    existing = {a.account_id: a for a in session.scalars(select(OilInvoiceAllocation).where(OilInvoiceAllocation.invoice_id == row.id))}
    fields = []
    seen = set()
    for value in values:
        if value['account_id'] in seen:
            raise MustReportError('同一用卡账户请合并成一项分配。')
        seen.add(value['account_id'])
        current = existing.get(value['account_id'])
        amount = _amount(value['amount'])
        if amount == ZERO or row.amount is None or (amount > ZERO) != (row.amount > ZERO):
            raise MustReportError('每项分配须与票面金额同号且不为0。')
        fields.append({**_attribution(session, value, current), 'amount': amount})
    if fields and (row.amount is None or sum_money(a['amount'] for a in fields) != row.amount):
        raise MustReportError('分配合计必须严格等于票面价税合计，请核对后整体保存。')
    for account_id, allocation in existing.items():
        if account_id not in seen:
            session.delete(allocation)
    for field in fields:
        current = existing.get(field['account_id'])
        if current:
            for key, value in field.items():
                setattr(current, key, value)
        else:
            session.add(OilInvoiceAllocation(invoice_id=row.id, **field))
    row.status = 'registered' if fields else 'pending'
    row.reason = '' if fields else '票面已核对，请确认用卡账户和金额分配。'


def _review(session, row, original_id, decision, note):
    source = _get(session, OilInvoiceOriginal, original_id)
    if source.invoice_id != row.id:
        raise MustReportError('请选择这张发票的原件。')
    if not note.strip():
        raise MustReportError('请填写核对结论，保留本次处理依据。')
    reviews = json.loads(row.review_json)
    reviews[source.sha256] = {'decision': decision, 'note': note.strip()}
    row.review_json = json.dumps(reviews, ensure_ascii=False, sort_keys=True)


def correct(session, key, values, *, credit=False):
    _lock(session)
    row = _get(session, OilInvoice, key)
    _check_version(row, values['version'])
    if row.status == 'voided':
        raise MustReportError('这张票已登记作废，请先通过操作历史核对并撤销作废。')
    if not values['note'].strip():
        raise MustReportError('请填写更正或红冲说明。')
    previous_parent = row.related_invoice_id
    kind = 'credit' if credit else row.kind
    facts = _facts(values, kind)
    parent_id = values.get('related_invoice_id') if credit else row.related_invoice_id
    if kind == 'credit':
        parent = _get(session, OilInvoice, parent_id) if parent_id else None
        if parent is None or parent.id == row.id or parent.kind != 'normal' or parent.status != 'registered':
            raise MustReportError('红票请选择另一张已登记且未作废的普通原票。')
    _alias(session, row, facts['invoice_no'])
    for field, value in facts.items():
        setattr(row, field, value)
    row.kind, row.related_invoice_id, row.change_note = kind, parent_id, values['note'].strip()
    _replace_allocations(session, row, values['allocations'])
    if values.get('review_original_id'):
        _review(session, row, values['review_original_id'], 'corrected', values['note'])
    _touch(row)
    _parent_touch(session, (previous_parent, parent_id))
    session.flush()
    validate_credits(session)
    return row


def allocate(session, key, values):
    _lock(session)
    row = _get(session, OilInvoice, key)
    _check_version(row, values['version'])
    if row.status == 'voided':
        raise MustReportError('作废票保留原分配，请先核对作废记录。')
    if not row.invoice_no or not row.invoice_date or row.amount is None or row.kind == 'normal' and row.amount <= ZERO:
        raise MustReportError('请先更正完整票面信息；负数红票使用“登记红冲”。')
    if not values['allocations']:
        raise MustReportError('请填写完整分配，至少选择一个用卡账户。')
    _replace_allocations(session, row, values['allocations'])
    _touch(row)
    _parent_touch(session, (row.related_invoice_id,))
    session.flush(); validate_credits(session)
    return row


def resolve_original(session, key, original_id, values):
    _lock(session)
    row = _get(session, OilInvoice, key)
    _check_version(row, values['version'])
    _review(session, row, original_id, 'keep', values['note'])
    _touch(row); session.flush()
    return row


def void(session, key, values):
    _lock(session)
    row = _get(session, OilInvoice, key)
    _check_version(row, values['version'])
    if row.kind != 'normal' or row.status != 'registered':
        raise MustReportError('请选择有效的普通原票登记作废；录错请使用更正。')
    if session.scalar(select(OilInvoice.id).where(OilInvoice.related_invoice_id == row.id, OilInvoice.status == 'registered').limit(1)):
        raise MustReportError('原票已有有效红冲，不能在本台账再次作废冲减，请先核对关联红票。')
    try:
        row.void_date = date.fromisoformat(values['date'])
    except ValueError as exc:
        raise MustReportError('请填写实际作废日期。') from exc
    if not values['note'].strip():
        raise MustReportError('请填写作废依据。')
    row.status, row.change_note, row.reason = 'voided', values['note'].strip(), '已登记作废'
    _touch(row); session.flush()
    return row
