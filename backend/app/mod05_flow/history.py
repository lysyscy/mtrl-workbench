"""Historical settlement supplements and cumulative payment reconciliation."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import re

from app.core.errors import MustReportError
from app.core.money import MoneyError, ZERO, amount_text, sum_money, to_money
from app.mod01_projects import service as projects
from . import repository as repo
from .domain import OpeningView
from .models import OpeningBalance


def kind(row):
    return getattr(row, "entry_kind", None) or "legacy"


def record_token(row):
    values = [getattr(row, key) for key in ("id", "project_id", "category", "entry_kind", "cutoff_ym",
              "settle_amount", "paid_amount", "paid_basis", "settle_basis", "input_mode", "remark")]
    return sha256(json.dumps(values, default=str).encode()).hexdigest()


def latest_payments(records, end_ym=""):
    latest = {}
    for row in records:
        if kind(row) != "payment" or (end_ym and row.cutoff_ym > end_ym):
            continue
        key = (row.project_id, row.category)
        if key not in latest or (row.cutoff_ym, row.id) > (latest[key].cutoff_ym, latest[key].id):
            latest[key] = row
    return latest


def adjustments(records, end_ym=""):
    """Only the latest cumulative payment snapshot contributes its missing portion."""
    latest = latest_payments(records, end_ym)
    result = []
    for row in records:
        if end_ym and row.cutoff_ym > end_ym:
            continue
        k = kind(row)
        settle, paid = ZERO, ZERO
        if k == "legacy":
            settle, paid = to_money(row.settle_amount), to_money(row.paid_amount)
        elif k == "settlement":
            settle = to_money(row.settle_amount)
        elif latest.get((row.project_id, row.category)) is row:
            paid = to_money(row.paid_amount) - to_money(row.paid_basis)
        result.append(OpeningView(row.category, row.project_id, row.cutoff_ym,
                                  settle, paid, int(row.id)))
    return result


def paid_before(rows, project_id, category, cutoff):
    return sum_money(r.pay_stat for r in rows if not r.excluded and r.ownership_id == project_id
                     and r.category == category and (not r.doc_date or r.doc_date[:7] <= cutoff))


def mechanical_months(session, project_id):
    from .service import mechanical_settlements
    return mechanical_settlements(session).get(int(project_id), {})


def settlement_before(session, rows, records, project_id, category, cutoff):
    if category == "mechanical":
        return sum_money(v for ym, v in mechanical_months(session, project_id).items() if ym <= cutoff)
    notices = sum_money(r.settle_stat for r in rows if not r.excluded and r.ownership_id == project_id
                        and r.category == category and (not r.doc_date or r.doc_date[:7] <= cutoff))
    supplements = sum_money(r.settle_amount for r in records if r.project_id == project_id
                            and r.category == category and r.cutoff_ym <= cutoff
                            and kind(r) in ("settlement", "legacy"))
    return notices + supplements


def preview(session, data):
    from .service import notice_debt_views
    project_id, category = int(data["project_id"]), data["category"]
    project = projects.get_project(session, project_id)
    if project is None or project.project_type == "shell":
        raise MustReportError("请选择已有的非壳项目")
    if category not in ("material", "mechanical"):
        raise MustReportError("请选择辅材或机械")
    entry_kind = data["entry_kind"]
    if entry_kind not in ("settlement", "payment"):
        raise MustReportError("请选择结算补录或累计付款对账")
    if entry_kind == "settlement" and category != "material":
        raise MustReportError("机械结算来自机械费台账，不再重复补录结算")
    cutoff = str(data["cutoff_ym"])
    if not re.fullmatch(r"[1-9]\d{3}-(0[1-9]|1[0-2])", cutoff):
        raise MustReportError("请填写有效的截止年月")
    mode = data.get("input_mode", "paid")
    if mode not in ("paid", "debt"):
        raise MustReportError("请选择累计付款或截至当时欠款")
    try:
        amount = to_money(amount_text(data["amount"]))
    except (MoneyError, ArithmeticError):
        raise MustReportError("请填写有效金额") from None
    if abs(amount) >= Decimal("10000000000000000"):
        raise MustReportError("金额过大，请核对")
    if amount < ZERO and (entry_kind == "settlement" or mode == "paid"):
        raise MustReportError("结算和累计付款金额不能为负数")
    records = repo.list_openings(session, project_id=project_id)
    existing = next((r for r in records if r.id == data.get("id")), None)
    if data.get("id") and (existing is None or kind(existing) != entry_kind
                            or existing.category != category):
        raise MustReportError("历史记录已变化，请刷新后重试")
    rows = notice_debt_views(session)
    settle = settlement_before(session, rows, records, project_id, category, cutoff)
    basis = paid_before(rows, project_id, category, cutoff)
    paid = settle - amount if mode == "debt" else amount
    if entry_kind == "payment" and max(abs(settle), abs(paid)) >= Decimal("10000000000000000"):
        raise MustReportError("对账金额过大，请核对结算及付款范围")
    if entry_kind == "payment" and (paid < ZERO or paid < basis):
        raise MustReportError("累计付款小于系统已记录付款，请先核对截止范围和通知书统计金额")
    if entry_kind == "payment" and any(kind(r) == "payment" and r.id != data.get("id")
                                        and r.category == category and r.cutoff_ym == cutoff for r in records):
        raise MustReportError("这个截止月已有累计付款记录，请编辑已有记录")
    facts = [data, str(amount), str(settle), str(basis),
             [(r.id, r.entry_kind, r.cutoff_ym, str(r.settle_amount), str(r.paid_amount),
               str(r.paid_basis), str(r.settle_basis), r.input_mode, r.remark) for r in records]]
    token = sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    return {"ok": True, "token": token, "settlement": f"{settle:.2f}",
            "recorded_paid": f"{basis:.2f}", "paid_total": f"{paid:.2f}",
            "payment_adjustment": f"{paid - basis:.2f}", "amount": f"{amount:.2f}",
            "debt": f"{settle - paid:.2f}", "project_label": project.disp or project.name_full}


def save(session, data, token):
    projects.get_project(session, int(data["project_id"]), for_update=True)
    result = preview(session, data)
    if not token or token != result["token"]:
        raise MustReportError("金额或历史记录已变化，请重新核对后保存")
    row = repo.get_opening(session, data["id"]) if data.get("id") else OpeningBalance()
    row.project_id, row.category = data["project_id"], data["category"]
    row.cutoff_ym, row.entry_kind = data["cutoff_ym"], data["entry_kind"]
    row.remark = str(data.get("remark", "")).strip()
    row.input_mode = data.get("input_mode", "paid")
    row.settle_amount = to_money(result["amount"]) if row.entry_kind == "settlement" else ZERO
    row.paid_amount = to_money(result["paid_total"]) if row.entry_kind == "payment" else ZERO
    row.paid_basis = to_money(result["recorded_paid"]) if row.entry_kind == "payment" else ZERO
    row.settle_basis = to_money(result["settlement"]) if row.entry_kind == "payment" else ZERO
    session.add(row)
    session.flush()
    return {"ok": True, "id": row.id, "message": "历史数据已保存"}


def records_data(session, project_id, rows, records):
    latest = latest_payments(records)
    result = []
    for row in records:
        k = kind(row)
        if k == "legacy":
            continue
        basis = paid_before(rows, project_id, row.category, row.cutoff_ym)
        settle = settlement_before(session, rows, records, project_id, row.category, row.cutoff_ym)
        changed = k == "payment" and (basis != to_money(row.paid_basis)
                    or (row.input_mode == "debt" and settle != to_money(row.settle_basis)))
        result.append({"id": row.id, "entry_kind": k, "category": row.category,
                       "cutoff_ym": row.cutoff_ym, "settle_amount": f"{row.settle_amount:.2f}",
                       "paid_amount": f"{row.paid_amount:.2f}", "paid_basis": f"{row.paid_basis:.2f}",
                       "settle_basis": f"{row.settle_basis:.2f}", "input_mode": row.input_mode,
                       "current_paid": f"{basis:.2f}", "current_settlement": f"{settle:.2f}",
                       "input_amount": f"{to_money(row.settle_basis) - to_money(row.paid_amount):.2f}"
                            if row.input_mode == "debt" else f"{row.paid_amount:.2f}",
                       "remark": row.remark, "needs_review": changed, "token": record_token(row),
                       "active": k == "settlement" or latest.get((row.project_id, row.category)) is row})
    return result
