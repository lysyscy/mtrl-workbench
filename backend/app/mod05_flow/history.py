"""历史台账直接填表；2025-12起保留正常统计。"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import re

from app.core.errors import MustReportError
from app.core.money import MoneyError, ZERO, amount_text, to_money
from app.mod01_projects import service as projects
from . import repository as repo
from .domain import OpeningView
from .models import OpeningBalance

CUTOFF = "2025-11"


def kind(row):
    return getattr(row, "entry_kind", None) or "manual"


def digest(values):
    return sha256(json.dumps(values, default=str, ensure_ascii=False).encode()).hexdigest()


def record_token(row):
    return digest([getattr(row, key) for key in
                   ("id", "project_id", "category", "entry_kind", "cutoff_ym",
                    "settle_amount", "paid_amount", "remark")])


def cell_token(project_id, category, month, settle, paid, remark, record_id=None):
    return digest([project_id, category, month, str(to_money(settle)), str(to_money(paid)), remark, record_id])


def adjustments(records, rows=()):
    """手填行直接计入；月份覆盖只计与通知书的差额，保证看板与台账一致。"""
    result = []
    for row in records:
        settle, paid = to_money(row.settle_amount), to_money(row.paid_amount)
        if kind(row) == "month":
            for notice in rows:
                if (not notice.excluded and notice.ownership_id == row.project_id
                        and notice.category == row.category and notice.doc_date[:7] == row.cutoff_ym):
                    if row.category == "material":
                        settle -= notice.settle_stat
                    paid -= notice.pay_stat
        result.append(OpeningView(row.category, row.project_id, row.cutoff_ym, settle, paid, int(row.id)))
    return result


def money(value):
    try:
        result = to_money(amount_text(value))
    except (MoneyError, ArithmeticError, ValueError):
        raise MustReportError("请填写有效金额") from None
    if abs(result) >= Decimal("10000000000000000"):
        raise MustReportError("金额过大，请核对")
    return result


def save(session, data, token=""):
    from .service import build_ledger
    project_id, category, month = int(data["project_id"]), data["category"], str(data["cutoff_ym"])
    project = projects.get_project(session, project_id, for_update=True)
    if project is None or project.project_type == "shell":
        raise MustReportError("请选择已有的非壳项目")
    if category not in ("material", "mechanical"):
        raise MustReportError("请选择辅材或机械")
    if not re.fullmatch(r"[1-9]\d{3}-(0[1-9]|1[0-2])", month) or month > CUTOFF:
        raise MustReportError("只能修改2025-11及以前的历史月份")
    entry_kind = data.get("entry_kind", "manual")
    if entry_kind not in ("manual", "month") or (category == "mechanical" and entry_kind != "month"):
        raise MustReportError("机械请直接修改已有月份的付款金额")
    row = repo.get_opening(session, data["id"]) if data.get("id") else None
    if data.get("id") and (row is None or row.project_id != project_id or row.category != category
                           or kind(row) != entry_kind):
        raise MustReportError("历史记录已变化，请刷新后重试")
    if entry_kind == "month":
        ledger = build_ledger(session, project_id=project_id)
        side = next(s for s in ledger["sides"] if s["category"] == category)
        current = next((r for r in side["rows"] if r["row_kind"] == "month" and r["month"] == month), None)
        if current is None or current["token"] != token or current["record_id"] != data.get("id"):
            raise MustReportError("这一行已变化，请刷新后重试")
    elif row is not None and record_token(row) != token:
        raise MustReportError("这一行已变化，请刷新后重试")
    settle, paid = money(data["settle_amount"]), money(data["paid_amount"])
    if category == "mechanical":
        if settle != to_money(current["other_expense"]):
            raise MustReportError("机械结算取台账，不能在这里修改")
        settle = ZERO
    if row is None:
        row = OpeningBalance(project_id=project_id, category=category, entry_kind=entry_kind)
    row.cutoff_ym, row.settle_amount, row.paid_amount = month, settle, paid
    row.remark = str(data.get("remark", "")).strip()
    session.add(row)
    session.flush()
    return {"ok": True, "id": row.id, "message": "台账已保存"}


def delete(session, record_id, token):
    row = session.get(OpeningBalance, record_id, with_for_update=True)
    if row is None or kind(row) != "manual" or record_token(row) != token:
        raise MustReportError("这一行已变化，请刷新后重试")
    session.delete(row)
    return {"ok": True, "message": "历史行已删除"}
