"""油卡档案 API；写入身份与事务历史沿应用统一机制。"""
from typing import Literal
from uuid import UUID
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from sqlalchemy.exc import IntegrityError

from app.core.db import session_scope
from app.core.errors import DataConflictError
from app import export_registry
from . import service
from . import ledger
from . import transfers

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
