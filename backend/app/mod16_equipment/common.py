"""设备台账（mod16）共用辅助：守卫十进制金额计算、状态校验与冲突错误转换。"""

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text

from app.core.errors import DataConflictError
from app.core.money import MoneyError, ledger_product


def ledger_lock(db):
    # Code allocation, month creation and cross-ledger writes share a transaction lock.
    db.execute(text("SELECT pg_advisory_xact_lock(16261123)"))


def require(db, model, key):
    row = db.get(model, key)
    if row is None:
        raise HTTPException(404, "台账记录不存在")
    return row


def batch(db, model, ids):
    if len(ids) != len(set(ids)):
        raise DataConflictError("所选记录中有重复项")
    return [require(db, model, key) for key in ids]


def record(row):
    if row is None:
        return None
    return {col.key: getattr(row, col.key) for col in row.__table__.columns}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def product(a, b):
    try:
        return ledger_product(a, b)
    except MoneyError as exc:
        raise DataConflictError(str(exc)) from exc


def total(values):
    known = [value for value in values if value is not None]
    return sum(known, Decimal(0)) if known else None
