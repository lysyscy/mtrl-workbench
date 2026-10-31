"""油卡档案 API；写入身份与事务历史沿应用统一机制。"""
from typing import Literal
from uuid import UUID
from urllib.parse import quote

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from sqlalchemy.exc import IntegrityError

from app.core.db import session_scope
from app.core.errors import DataConflictError
from app import export_registry
from . import service
from . import ledger
from . import transfers
from . import invoices
from . import invoice_adjustments
from . import invoice_batches
from . import reporting
from .invoice_pdf import MAX_PDF_BYTES, recognize_pdf

router = APIRouter(prefix='/api/m13', tags=['oilcard'])


class CardFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    card_no: StrictStr | None = Field(default=None, max_length=128)
    kind: Literal['primary', 'secondary'] = 'secondary'
    parent_card_id: int | None = Field(default=None, gt=0)
    remark: StrictStr = ''


class CardCreate(CardFields):
    request_id: UUID


class CardUpdate(CardFields):
    version: UUID


class AccountFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: StrictStr = Field(min_length=1, max_length=255)
    project_id: int = Field(gt=0)
    card_id: int | None = Field(default=None, gt=0)
    status: Literal['active', 'archived'] = 'active'
    remark: StrictStr = ''


class AccountCreate(AccountFields):
    request_id: UUID


class AccountUpdate(AccountFields):
    version: UUID


def _write(action, serializer):
    try:
        with session_scope() as session:
            row = action(session)
            return {'ok': True, 'item': serializer(row)}
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, 'diag', None), 'constraint_name', '') != 'oil_card_card_no_key':
            raise
        raise DataConflictError('完整卡号已被其他操作保存，请重读后选择已有卡片。') from exc


@router.get('/archives')
def archives():
    with session_scope() as session:
        return service.archives(session)


@router.get('/accounts/{account_id}/assignments')
def assignments(account_id: int):
    with session_scope() as session:
        return service.assignments(session, account_id)


@router.post('/cards')
def create_card(req: CardCreate):
    return _write(lambda session: service.save_card(session, req.model_dump(mode='json')), service.card_data)


@router.put('/cards/{card_id}')
def update_card(card_id: int, req: CardUpdate):
    return _write(lambda session: service.save_card(session, req.model_dump(mode='json', exclude={'version'}),
        key=card_id, version=str(req.version)), service.card_data)


@router.post('/accounts')
def create_account(req: AccountCreate):
    return _write(lambda session: service.save_account(session, req.model_dump(mode='json')), service.account_data)


@router.put('/accounts/{account_id}')
def update_account(account_id: int, req: AccountUpdate):
    return _write(lambda session: service.save_account(session, req.model_dump(mode='json', exclude={'version'}),
        key=account_id, version=str(req.version)), service.account_data)


class ReplacementCard(BaseModel):
    model_config = ConfigDict(extra='forbid')
    card_no: StrictStr | None = Field(default=None, max_length=128)
    parent_card_id: int | None = Field(default=None, gt=0)
    remark: StrictStr = ''


class CardReplacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    version: UUID
    card_id: int | None = Field(default=None, gt=0)
    new_card: ReplacementCard | None = None


@router.post('/accounts/{account_id}/replace-card')
def replace_card(account_id: int, req: CardReplacement):
    with session_scope() as session:
        account, event = service.replace_card(session, account_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': service.account_data(account), 'assignment': service.assignment_data(event)}


class EntryFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['recharge', 'adjustment', 'refund', 'transfer_out', 'transfer_in'] = 'recharge'
    project_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    date_text: StrictStr = Field(default='', max_length=128)
    amount: StrictStr
    remark: StrictStr = ''


class EntryCreate(EntryFields):
    request_id: UUID


class EntryUpdate(EntryFields):
    version: UUID


class RefundCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    original_id: int = Field(gt=0)
    date_text: StrictStr = Field(default='', max_length=128)
    amount: StrictStr
    remark: StrictStr = ''


@router.get('/ledger')
def read_ledger():
    with session_scope() as session:
        return ledger.entries(session)


@router.get('/reconciliation')
def read_reconciliation():
    with session_scope() as session:
        return ledger.reconciliation(session)


@router.get('/linkage')
def read_linkage(ym: str):
    reporting.month_bounds(ym)
    with session_scope() as session:
        return {'ym': ym, 'rows': [reporting.fee_month(session, project_id=project.id, ym=ym)
            for project in service.projects.all_projects(session) if project.project_type != 'shell']}


class FeeCustomUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount: StrictStr | None = None
    remark: StrictStr = ''
    version: UUID | None = None


@router.put('/linkage/{project_id}/{ym}/fee')
def save_fee_custom(project_id: int, ym: str, req: FeeCustomUpdate):
    with session_scope() as session:
        reporting.save_fee_custom(session, project_id=project_id, ym=ym, amount=req.amount,
            remark=req.remark, version=str(req.version) if req.version else None)
        return {'ok': True, 'item': reporting.fee_month(session, project_id=project_id, ym=ym)}


@router.post('/linkage/{project_id}/enable')
def enable_empty_linkage(project_id: int):
    from app.mod09_fee import service as fees
    with session_scope() as session:
        return {'ok': True, **fees.enable_empty_oil_linkage(session, project_id=project_id)}


@router.get('/ledger/export')
def export_ledger():
    with session_scope() as session:
        snapshot = ledger.export_snapshot(session)
    filename = quote('油卡充值台账（全量）.xlsx')
    return Response(content=export_registry.get('oilcard').build(snapshot),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'X-Export-Filename': filename, 'Content-Disposition': f"attachment; filename*=UTF-8''{filename}",
                 'Cache-Control': 'no-store'})


@router.post('/ledger/entries')
def create_entry(req: EntryCreate):
    return _write(lambda session: ledger.save_entry(session, req.model_dump(mode='json')), ledger.entry_data)


@router.put('/ledger/entries/{entry_id}')
def update_entry(entry_id: int, req: EntryUpdate):
    return _write(lambda session: ledger.save_entry(session, req.model_dump(mode='json', exclude={'version'}),
        key=entry_id, version=str(req.version)), ledger.entry_data)


class AttributionCorrection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: UUID
    project_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    card_id: int | None = Field(default=None, gt=0)


@router.put('/ledger/entries/{entry_id}/attribution')
def correct_attribution(entry_id: int, req: AttributionCorrection):
    return _write(lambda session: ledger.correct_attribution(session, entry_id, req.model_dump(mode='json')), ledger.entry_data)


@router.post('/ledger/refunds')
def create_refund(req: RefundCreate):
    return _write(lambda session: ledger.refund(session, req.model_dump(mode='json')), ledger.entry_data)


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    out_project_id: int = Field(gt=0)
    out_account_id: int = Field(gt=0)
    in_project_id: int = Field(gt=0)
    in_account_id: int = Field(gt=0)
    amount: StrictStr
    date_text: StrictStr = Field(default='', max_length=128)
    out_remark: StrictStr = ''
    in_remark: StrictStr = ''


@router.post('/ledger/transfers')
def create_transfer(req: TransferCreate):
    with session_scope() as session:
        rows = transfers.create(session, req.model_dump(mode='json'))
        return {'ok': True, 'items': [ledger.entry_data(row) for row in rows]}


@router.get('/invoices')
def read_invoices():
    with session_scope() as session:
        return invoices.invoices(session)


@router.post('/invoices/receive')
def receive_invoice(file: UploadFile = File(...)):
    content = file.file.read(MAX_PDF_BYTES + 1)
    recognized = recognize_pdf(content)
    with session_scope() as session:
        original = invoices.receive_pdf(session, content, recognized)
        item = invoices.invoice_data(session, session.get(invoices.OilInvoice, original.invoice_id))
        return {'ok': True, 'original': next(o for o in item['originals'] if o['id'] == original.id),
                'item': item, **invoices.receipt_outcome(session, original)}


@router.get('/invoices/receipts/{digest}')
def invoice_receipt(digest: str):
    with session_scope() as session:
        return invoices.receipt(session, digest)


class InvoiceRemark(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: UUID
    remark: StrictStr


@router.put('/invoices/{invoice_id}/remark')
def invoice_remark(invoice_id: int, req: InvoiceRemark):
    with session_scope() as session:
        row = invoices.save_remark(session, invoice_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


@router.get('/invoices/originals/{original_id}')
def invoice_original(original_id: int, download: bool = False):
    with session_scope() as session:
        content, filename = invoices.original_file(session, original_id)
    name = quote(filename)
    return Response(content=content, media_type='application/pdf', headers={'X-Export-Filename': name,
        'Content-Disposition': f"{'attachment' if download else 'inline'}; filename*=UTF-8''{name}",
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/invoices/export')
def export_invoices():
    with session_scope() as session:
        snapshot = invoices.export_snapshot(session)
    name = quote('油卡发票台账（全量）.xlsx')
    return Response(content=export_registry.get('oilcard').build_invoices(snapshot),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'X-Export-Filename': name, 'Content-Disposition': f"attachment; filename*=UTF-8''{name}", 'Cache-Control': 'no-store'})


class InvoiceAllocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    amount: StrictStr


class InvoiceAllocationUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: UUID
    allocations: list[InvoiceAllocation] = Field(max_length=100)


class InvoiceCorrection(InvoiceAllocationUpdate):
    invoice_no: StrictStr = Field(max_length=32)
    invoice_date: StrictStr
    amount: StrictStr
    card_no: StrictStr | None = Field(default=None, max_length=128)
    note: StrictStr
    review_original_id: int | None = Field(default=None, gt=0)


class InvoiceCredit(InvoiceCorrection):
    related_invoice_id: int = Field(gt=0)


class InvoiceResolution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: UUID
    note: StrictStr


class InvoiceVoid(InvoiceResolution):
    date: StrictStr


@router.put('/invoices/{invoice_id}/correct')
def correct_invoice(invoice_id: int, req: InvoiceCorrection):
    with session_scope() as session:
        row = invoice_adjustments.correct(session, invoice_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


@router.put('/invoices/{invoice_id}/allocations')
def allocate_invoice(invoice_id: int, req: InvoiceAllocationUpdate):
    with session_scope() as session:
        row = invoice_adjustments.allocate(session, invoice_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


@router.put('/invoices/{invoice_id}/originals/{original_id}/resolve')
def resolve_invoice_original(invoice_id: int, original_id: int, req: InvoiceResolution):
    with session_scope() as session:
        row = invoice_adjustments.resolve_original(session, invoice_id, original_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


@router.post('/invoices/{invoice_id}/credit')
def credit_invoice(invoice_id: int, req: InvoiceCredit):
    with session_scope() as session:
        row = invoice_adjustments.correct(session, invoice_id, req.model_dump(mode='json'), credit=True)
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


@router.post('/invoices/{invoice_id}/void')
def void_invoice(invoice_id: int, req: InvoiceVoid):
    with session_scope() as session:
        row = invoice_adjustments.void(session, invoice_id, req.model_dump(mode='json'))
        return {'ok': True, 'item': invoices.invoice_data(session, row)}


class DeliveryBatchCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    links: StrictStr = Field(max_length=50000)


@router.post('/invoice-batches')
def create_delivery_batch(req: DeliveryBatchCreate):
    with session_scope() as session:
        batch = invoice_batches.create(session, str(req.request_id), req.links)
        return {'ok': True, 'batch': invoice_batches.batch_data(session, batch)}


@router.get('/invoice-batches')
def recent_delivery_batches():
    with session_scope() as session:
        return invoice_batches.recent(session)


@router.get('/invoice-batches/request/{request_id}')
def delivery_batch_request(request_id: UUID):
    with session_scope() as session:
        return invoice_batches.by_request(session, str(request_id))


@router.get('/invoice-batches/{batch_id}')
def read_delivery_batch(batch_id: int):
    with session_scope() as session:
        return invoice_batches.read(session, batch_id)


@router.post('/invoice-batches/{batch_id}/items/{item_id}/run')
def run_delivery_item(batch_id: int, item_id: int):
    return {'ok': True, 'batch': invoice_batches.run(batch_id, item_id)}
