"""月租的接续、当月决议与排序。"""
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.core.errors import DataConflictError
from app.core.identity import current_operator
from .common import encoded, product, record, require, total
from .models import EquipmentItem, EquipmentScrap, EquipmentTransfer, RentalLine, RentalMonth
from .projects import ProjectRef, project_index


def meta(line):
    return json.loads(line.pending_meta_json or "{}")


def recalculate(line):
    line.unit_price = line.custom_unit_price
    if line.unit_price is None:
        line.unit_price = product(line.original_value, Decimal("0.05"))
    line.amount = product(line.unit_price, line.quantity) if line.billing_status == "normal" else None


def category_label(item):
    return "周转材料" if item.item_category == "turnover" else "大型工机具"


def carry_line(db, old, month, item=None):
    carry = meta(old)
    if item and item.in_rental == "no" and month >= date.today().strftime("%Y-%m"):
        return None
    if old.billing_status == "stopped" or carry.get("stop_next"):
        return None
    values = record(old)
    for key in ("id", "created_at", "updated_at", "pending_meta_json"):
        values.pop(key)
    if item is not None:
        values["category_label"] = category_label(item)
    if "next_transfer_id" in carry:
        transfer = require(db, EquipmentTransfer, carry["next_transfer_id"])
        values.update(ProjectRef.from_row(transfer, "to_project").fields("project", label="project_name"))
    elif "next_project" in carry:
        values.update(ProjectRef(carry["next_project"]).fields("project", label="project_name"))
    values.update(month=month, pending_action_type="none")
    if old.billing_status == "skip_month":
        values["billing_status"] = "normal"
    new = RentalLine(**values)
    recalculate(new)
    return new


def month_row(db, month):
    row = db.scalar(select(RentalMonth).where(RentalMonth.month == month))
    if row is None:
        row = RentalMonth(month=month)
        db.add(row)
        db.flush()
    elif row.status == "confirmed" or db.scalar(select(RentalLine.id).where(RentalLine.month == month).limit(1)):
        return row
    prior = db.scalar(select(func.max(RentalMonth.month)).where(RentalMonth.month < month))
    if prior:
        for old, item in lines_with_equipment(db, prior):
            new = carry_line(db, old, month, item)
            if new is not None:
                db.add(new)
        db.flush()
    return row


def draft(db, month):
    if month_row(db, month).status == "confirmed":
        raise DataConflictError(f"{month} 月租已经确认")


def lines_with_equipment(db, month):
    return db.execute(select(RentalLine, EquipmentItem).outerjoin(
        EquipmentItem, EquipmentItem.id == RentalLine.equipment_id
    ).where(RentalLine.month == month).order_by(RentalLine.project_sort_order, RentalLine.project_name,
                                                RentalLine.row_sort_order, RentalLine.id))


def position(db, month, project):
    same_project = RentalLine.project_id == project.id
    if project.id is None:
        label = func.coalesce(func.nullif(func.trim(RentalLine.project_custom), ""), RentalLine.project_name)
        same_project = same_project & (label == project.key())
    sibling = db.scalar(select(RentalLine).where(RentalLine.month == month, same_project)
                        .order_by(RentalLine.row_sort_order.desc()).limit(1))
    if sibling:
        return sibling.project_sort_order, sibling.row_sort_order + 1
    highest = db.scalar(select(func.max(RentalLine.project_sort_order)).where(RentalLine.month == month))
    return (0 if highest is None else highest + 1), 0


def move(db, line, project):
    if ProjectRef.from_row(line, "project").key() != project.key():
        line.project_sort_order, line.row_sort_order = position(db, line.month, project)
    line.project_name, line.project_id, line.project_custom = project.legacy, project.id, project.custom


def action(db, item, month, kind, details, custom_price=None, *, project=None):
    draft(db, month)
    closed = db.scalar(select(RentalMonth.month).where(
        RentalMonth.month > month, RentalMonth.status == "confirmed").order_by(RentalMonth.month).limit(1))
    if closed:
        raise DataConflictError(f"该变动影响后续已确认租赁月份 {closed}，请核对日期")
    line = db.scalar(select(RentalLine).where(RentalLine.month == month, RentalLine.equipment_id == item.id))
    if line is None:
        project = project or ProjectRef.from_row(item, "current_project")
        group, order = position(db, month, project)
        line = RentalLine(month=month, equipment_id=item.id, **project.fields("project", label="project_name"),
                          project_sort_order=group,
                          category_label=category_label(item), row_sort_order=order, name=item.name, spec=item.spec, unit=item.unit,
                          quantity=item.quantity, original_value=item.purchase_price, custom_unit_price=custom_price,
                          pending_action_type="none", billing_status="skip_month" if kind == "new_purchase_start" else "normal")
        db.add(line)
    state = meta(line)
    if line.pending_action_type == "none":
        line.pending_action_type = kind
        state.update(details)
    else:
        state.setdefault("queue", []).append({"kind": kind, "details": details})
    line.pending_meta_json = encoded(state)
    recalculate(line)
    db.flush()
    if kind == "new_purchase_start":
        following = db.scalars(select(RentalMonth.month).where(RentalMonth.month > month).order_by(RentalMonth.month))
        for later in following:
            existing = db.scalar(select(RentalLine.id).where(RentalLine.month == later, RentalLine.equipment_id == item.id))
            if existing:
                break
            new = carry_line(db, line, later)
            if new is None:
                break
            new.project_sort_order, new.row_sort_order = position(db, later, ProjectRef.from_row(new, "project"))
            db.add(new)
            db.flush()
    return line


def line_record(line, projects):
    return record(line) | ProjectRef.from_row(line, "project").response("project", projects, rental=True)


def view(db, month, project=None):
    row = month_row(db, month)
    archive = project_index(db)
    groups = {}
    pending = 0
    amounts = []
    for line, item in lines_with_equipment(db, month):
        pending += line.pending_action_type != "none"
        ref = ProjectRef.from_row(line, "project")
        if project is None or ref.rental_name(archive) == project:
            values = line_record(line, archive)
            if item:
                values["category_label"] = category_label(item)
            group = groups.setdefault(ref.key(), {"project_id": ref.id, "project_name": values["project_name"],
                                                 "lines": []})
            group["lines"].append(values)
            amounts.append(line.amount)
    projects = list(groups.values())
    for group in projects:
        group["lines"].sort(key=lambda line: (line["row_sort_order"], line["id"]))
        group["subtotal"] = total(line["amount"] for line in group["lines"])
    return {"month": month, "status": row.status, "pending_count": pending, "projects": projects,
            "grand_total": total(amounts), "printable_project_count": sum((g["subtotal"] or 0) > 0 for g in projects)}


def stop_lines(db, equipment_id, month, *, include_current=False):
    if equipment_id is None:
        return
    cutoff = RentalLine.month >= month if include_current else RentalLine.month > month
    rows = db.execute(select(RentalLine, RentalMonth.status).join(
        RentalMonth, RentalMonth.month == RentalLine.month
    ).where(RentalLine.equipment_id == equipment_id, cutoff).order_by(RentalLine.month))
    for line, status in rows:
        if status == "confirmed":
            if not include_current and line.billing_status == "normal":
                raise DataConflictError(f"{line.month} 已确认且仍对该设备计租，请先核对后续月份")
        else:
            line.billing_status, line.amount = "stopped", None


def patch(db, key, changes):
    line = require(db, RentalLine, key)
    draft(db, line.month)
    if changes.get("billing_status") == "stopped":
        stop_lines(db, line.equipment_id, line.month)
    for name, value in changes.items():
        setattr(line, name, value)
    recalculate(line)
    db.flush()
    return line_record(line, project_index(db))


def resolve(db, key, choice):
    line = require(db, RentalLine, key)
    draft(db, line.month)
    data = meta(line)
    kind = line.pending_action_type
    following = {k: data[k] for k in ("next_project", "next_transfer_id", "stop_next") if k in data}
    if kind == "transfer_attribution" and choice in ("from_project", "to_project"):
        transfer = require(db, EquipmentTransfer, data["transfer_id"])
        move(db, line, ProjectRef.from_row(transfer, choice))
        transfer.rental_attribution = choice
        following["next_project"] = transfer.to_project
        following["next_transfer_id"] = transfer.id
    elif kind == "new_purchase_start" and choice in ("this_month", "next_month"):
        line.billing_status = "normal" if choice == "this_month" else "skip_month"
    elif kind == "scrap_stop" and choice in ("stop_this_month", "charge_this_month"):
        line.billing_status = "stopped" if choice == "stop_this_month" else "normal"
        require(db, EquipmentScrap, data["scrap_id"]).rental_stop_status = (
            "stopped" if choice == "stop_this_month" else choice)
        following["stop_next"] = True
    else:
        raise DataConflictError("选择与当前待确认事项不符，请刷新租赁明细")
    queue = data.get("queue", [])
    line.pending_action_type = "none"
    if queue:
        upcoming = queue.pop(0)
        line.pending_action_type = upcoming["kind"]
        following.update(upcoming["details"], queue=queue)
    line.pending_meta_json = encoded(following) if following else None
    # A user may already have opened later drafts before settling this event.
    later = db.scalars(select(RentalLine).where(RentalLine.equipment_id == line.equipment_id,
                        RentalLine.month > line.month).order_by(RentalLine.month)).all()
    for other in later:
        if kind == "scrap_stop":
            draft(db, other.month)
            db.delete(other)
        elif kind == "transfer_attribution":
            if other.pending_action_type != "none" or "next_project" in meta(other):
                break
            draft(db, other.month)
            move(db, other, ProjectRef.from_row(transfer, "to_project"))
    recalculate(line)
    db.flush()
    return line_record(line, project_index(db))


def reorder(db, request):
    draft(db, request.month)
    archive = project_index(db)
    lines, keys = {}, set()
    for line, _ in lines_with_equipment(db, request.month):
        ref = ProjectRef.from_row(line, "project")
        if "project_id" in request.model_fields_set and ref.id != request.project_id:
            continue
        if ref.rental_name(archive) == request.project_name:
            lines[line.id] = line
            keys.add(ref.key())
    ids = request.ordered_line_ids
    if len(keys) != 1 or set(ids) != lines.keys() or len(ids) != len(lines):
        raise DataConflictError("排序须包含该项目本月全部明细且无重复")
    for order, key in enumerate(ids):
        lines[key].row_sort_order = order
    db.flush()
    return {"ordered_line_ids": ids}


def confirm(db, month):
    row = month_row(db, month)
    if row.status != "confirmed":
        pending = db.scalar(select(func.count()).select_from(RentalLine).where(
            RentalLine.month == month, RentalLine.pending_action_type != "none"))
        if pending:
            raise DataConflictError(f"本月还有 {pending} 行租赁事项待确认")
        unresolved = db.scalar(select(RentalLine.month).where(
            RentalLine.month < month, RentalLine.pending_action_type != "none",
            RentalLine.equipment_id.in_(select(RentalLine.equipment_id).where(RentalLine.month == month)),
        ).order_by(RentalLine.month).limit(1))
        if unresolved:
            raise DataConflictError(f"本月接续的设备在 {unresolved} 仍有待确认事项")
        row.status, row.confirmed_at, row.confirmed_by = "confirmed", datetime.now(), current_operator()
        db.flush()
    return record(row)
