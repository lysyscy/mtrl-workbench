"""油卡档案 API；写入身份与事务历史沿应用统一机制。"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from sqlalchemy.exc import IntegrityError

from app.core.db import session_scope
from app.core.errors import DataConflictError
from . import service

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
