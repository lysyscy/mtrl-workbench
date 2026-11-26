"""月租的接续、当月决议与排序。"""
import json
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.core.errors import DataConflictError
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


def category_label(item_category):
    return "周转材料" if item_category == "turnover" else "大型工机具"


def imported_category_label(label):
    # Unlinked lines have no equipment category, so retain explicit turnover from the source.
    return category_label("turnover" if label == "周转材料" else "equipment")


def line_category(line, item):
    return category_label(item.item_category) if item else imported_category_label(line.category_label)


def carry_line(db, old, month, item=None):
    carry = meta(old)
    if not can_charge(month, item):
        return None
    if old.billing_status == "stopped" or carry.get("stop_next"):
        return None
    values = record(old)
    for key in ("id", "created_at", "updated_at", "pending_meta_json"):
        values.pop(key)
    values["category_label"] = line_category(old, item)
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
    elif db.scalar(select(RentalLine.id).where(RentalLine.month == month).limit(1)):
        return row
    prior = db.scalar(select(func.max(RentalMonth.month)).where(RentalMonth.month < month))
    if prior:
        previous = list(lines_with_equipment(db, prior))
        positions = {}
        for line, _ in previous:
            key = ProjectRef.from_row(line, "project").key()
            rank, next_row = positions.get(key, (line.project_sort_order, 0))
            positions[key] = rank, max(next_row, line.row_sort_order + 1)
        next_rank = max((rank for rank, _ in positions.values()), default=-1) + 1
        for old, item in previous:
            new = carry_line(db, old, month, item)
            if new is None:
                continue
            key = ProjectRef.from_row(new, "project").key()
            if key != ProjectRef.from_row(old, "project").key():
                if key not in positions:
                    positions[key] = next_rank, 0
                    next_rank += 1
                new.project_sort_order, new.row_sort_order = positions[key]
                positions[key] = new.project_sort_order, new.row_sort_order + 1
            db.add(new)
        db.flush()
    return row


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


def correct_location(db, equipment_id, month, origin, project):
    for line in equipment_lines(db, equipment_id, month, include_current=True):
        if line.billing_status != "stopped" and same_position(line, origin):
            move(db, line, project)


TRANSFER_DETAILS = ("transfer_id", "from_project", "to_project", "transfer_date", "suggested_side")


def rename_location_metadata(db, old, new):
    for line in db.scalars(select(RentalLine).where(RentalLine.pending_meta_json.is_not(None))):
        data = meta(line)
        changed = False
        for details in (data, *(entry["details"] for entry in data.get("queue", []))):
            for field, prefix, id_field in (("from_project", "from_project", "transfer_id"),
                                            ("to_project", "to_project", "transfer_id"),
                                            ("next_project", "to_project", "next_transfer_id")):
                if details.get(field) != old:
                    continue
                key = details.get(id_field)
                transfer = db.get(EquipmentTransfer, key) if key is not None else None
                if transfer is None or ProjectRef.from_row(transfer, prefix).custom == new:
                    details[field] = new
                    changed = True
        if changed:
            line.pending_meta_json = encoded(data)


def drop_transfer_action(line, data, key):
    queue = [entry for entry in data.pop("queue", []) if not (
        entry["kind"] == "transfer_attribution" and entry["details"].get("transfer_id") == key)]
    if line.pending_action_type == "transfer_attribution" and data.get("transfer_id") == key:
        for field in TRANSFER_DETAILS:
            data.pop(field, None)
        line.pending_action_type = "none"
        if queue:
            upcoming = queue.pop(0)
            line.pending_action_type = upcoming["kind"]
            data.update(upcoming["details"])
    if queue:
        data["queue"] = queue


def same_position(line, project):
    current = ProjectRef.from_row(line, "project")
    return current.key() == project.key() and current.custom == project.custom


def restore_transfer_attribution(db, line, data, transfer, reverted):
    data.pop("next_transfer_id")
    data.pop("next_project", None)
    previous = db.scalar(select(EquipmentTransfer).where(
        EquipmentTransfer.equipment_id == transfer.equipment_id,
        EquipmentTransfer.rental_month == transfer.rental_month,
        EquipmentTransfer.id != transfer.id,
        EquipmentTransfer.rental_attribution.in_(("from_project", "to_project")),
    ).order_by(EquipmentTransfer.transfer_date.desc().nulls_last(), EquipmentTransfer.id.desc()).limit(1))
    project = continuation = reverted
    if previous:
        data.update(next_transfer_id=previous.id, next_project=previous.to_project)
        project = ProjectRef.from_row(previous, previous.rental_attribution)
        continuation = ProjectRef.from_row(previous, "to_project")
    charged = ProjectRef.from_row(transfer, transfer.rental_attribution)
    if same_position(line, charged):
        move(db, line, project)

    destination = ProjectRef.from_row(transfer, "to_project")
    later = db.scalars(select(RentalLine).where(
        RentalLine.equipment_id == line.equipment_id, RentalLine.month > line.month).order_by(RentalLine.month))
    for other in later:
        if other.pending_action_type != "none" or "next_project" in meta(other) or not same_position(other, destination):
            break
        if same_position(other, continuation):
            continue
        move(db, other, continuation)


def remove_transfer(db, transfer, reverted):
    if transfer.rental_month is None:
        return
    line = db.scalar(select(RentalLine).where(
        RentalLine.month == transfer.rental_month, RentalLine.equipment_id == transfer.equipment_id))
    if line is None:
        return
    data = meta(line)
    drop_transfer_action(line, data, transfer.id)
    if data.get("next_transfer_id") == transfer.id:
        restore_transfer_attribution(db, line, data, transfer, reverted)
    line.pending_meta_json = encoded(data) if data else None


def action(db, item, month, kind, details, custom_price=None, *, project=None):
    month_row(db, month)
    line = db.scalar(select(RentalLine).where(RentalLine.month == month, RentalLine.equipment_id == item.id))
    if line is None:
        project = project or ProjectRef.from_row(item, "current_project")
        group, order = position(db, month, project)
        line = RentalLine(month=month, equipment_id=item.id, **project.fields("project", label="project_name"),
                          project_sort_order=group,
                          category_label=category_label(item.item_category), row_sort_order=order,
                          name=item.name, spec=item.spec, unit=item.unit,
                          quantity=item.quantity, original_value=item.purchase_price, custom_unit_price=custom_price,
                          pending_action_type="none", billing_status="skip_month" if kind == "new_purchase_start" else "normal")
        db.add(line)
    state = meta(line)
    if kind == "new_purchase_start" and line.billing_status == "stopped":
        line.billing_status = "skip_month"
        state.pop("stop_next", None)
        state.pop("suspended_billing", None)
    if line.pending_action_type == "none":
        line.pending_action_type = kind
        state.update(details)
    elif kind != "new_purchase_start" or (line.pending_action_type != kind and not any(
            entry["kind"] == kind for entry in state.get("queue", []))):
        state.setdefault("queue", []).append({"kind": kind, "details": details})
    line.pending_meta_json = encoded(state)
    recalculate(line)
    db.flush()
    if kind == "new_purchase_start":
        previous = line
        following = db.scalars(select(RentalMonth.month).where(RentalMonth.month > month).order_by(RentalMonth.month))
        for later in following:
            existing = db.scalar(select(RentalLine).where(RentalLine.month == later, RentalLine.equipment_id == item.id))
            if existing is not None:
                data = meta(existing)
                old_status = data.pop("suspended_billing", None)
                if old_status is None:
                    break
                existing.billing_status = old_status
                existing.pending_meta_json = encoded(data) if data else None
                recalculate(existing)
                previous = existing
                continue
            new = carry_line(db, previous, later, item)
            if new is None:
                break
            new.project_sort_order, new.row_sort_order = position(db, later, ProjectRef.from_row(new, "project"))
            db.add(new)
            db.flush()
            previous = new
    return line


def line_record(line, projects, item):
    return (record(line) | ProjectRef.from_row(line, "project").response("project", projects, rental=True)
            | {"category_label": line_category(line, item)})


def view(db, month, project=None):
    month_row(db, month)
    archive = project_index(db)
    groups = {}
    pending = 0
    amounts = []
    for line, item in lines_with_equipment(db, month):
        pending += line.pending_action_type != "none"
        ref = ProjectRef.from_row(line, "project")
        if project is None or ref.rental_name(archive) == project:
            values = line_record(line, archive, item)
            group = groups.setdefault(ref.key(), {"project_id": ref.id, "project_name": values["project_name"],
                                                 "lines": []})
            group["lines"].append(values)
            amounts.append(line.amount)
    projects = list(groups.values())
    for group in projects:
        group["lines"].sort(key=lambda line: (line["row_sort_order"], line["id"]))
        group["subtotal"] = total(line["amount"] for line in group["lines"])
    return {"month": month, "status": "draft", "pending_count": pending, "projects": projects,
            "grand_total": total(amounts), "printable_project_count": sum((g["subtotal"] or 0) != 0 for g in projects)}


def equipment_lines(db, equipment_id, month, *, include_current=False):
    cutoff = RentalLine.month >= month if include_current else RentalLine.month > month
    return db.scalars(select(RentalLine).where(RentalLine.equipment_id == equipment_id, cutoff)
                      .order_by(RentalLine.month, RentalLine.id))


def later_lines(db, line):
    if line.equipment_id is not None:
        return equipment_lines(db, line.equipment_id, line.month)
    # A carry-forward retains the source row and its workbook identity.
    if line.source_row is None:
        return ()
    candidates = db.scalars(select(RentalLine).where(
        RentalLine.equipment_id.is_(None), RentalLine.month > line.month, RentalLine.source_row == line.source_row,
        RentalLine.name == line.name, RentalLine.spec == line.spec, RentalLine.unit == line.unit,
    ).order_by(RentalLine.month, RentalLine.id))
    project = ProjectRef.from_row(line, "project").key()
    return (other for other in candidates if ProjectRef.from_row(other, "project").key() == project)


def stop(rows, *, suspend=False):
    for line in rows:
        data = meta(line)
        if suspend and line.billing_status != "stopped":
            data["suspended_billing"] = line.billing_status
        elif not suspend:
            data.pop("suspended_billing", None)
        line.pending_meta_json = encoded(data) if data else None
        line.billing_status, line.amount = "stopped", None


def stop_lines(db, equipment_id, month, *, include_current=False):
    stop(equipment_lines(db, equipment_id, month, include_current=include_current), suspend=True)


def has_active_line(db, equipment_id, month):
    return any(line.billing_status != "stopped"
               for line in equipment_lines(db, equipment_id, month, include_current=True))


def propagate_edits(db, line, before, changes):
    for other in later_lines(db, line):
        overrides = meta(other).get("overrides", [])
        # Older months have no override metadata. The first differing value starts its own continuation.
        before = {field: value for field, value in before.items()
                  if field not in overrides and getattr(other, field) == value}
        if not before:
            break
        for field in before:
            setattr(other, field, changes[field])
        recalculate(other)


def can_charge(month, item):
    return item is None or item.in_rental == "yes" or month < date.today().strftime("%Y-%m")


def patch(db, key, changes):
    line = require(db, RentalLine, key)
    item = db.get(EquipmentItem, line.equipment_id) if line.equipment_id else None
    if changes.get("billing_status") == "normal" and not can_charge(line.month, item):
        raise DataConflictError("该设备当前未列租赁表，不能恢复计租")
    fields = {"quantity", "custom_unit_price"} & changes.keys()
    if fields:
        data = meta(line)
        data["overrides"] = sorted(fields | set(data.get("overrides", [])))
        line.pending_meta_json = encoded(data)
        before = {field: getattr(line, field) for field in fields if getattr(line, field) != changes[field]}
        if before:
            propagate_edits(db, line, before, changes)
    if changes.get("billing_status") == "stopped":
        stop((line,))
        stop(later_lines(db, line))
    for name, value in changes.items():
        setattr(line, name, value)
    recalculate(line)
    db.flush()
    return line_record(line, project_index(db), item)


def resolve(db, key, choice):
    line = require(db, RentalLine, key)
    data = meta(line)
    kind = line.pending_action_type
    following = {k: data[k] for k in ("next_project", "next_transfer_id", "stop_next", "overrides",
                                     "suspended_billing") if k in data}
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
        following.pop("suspended_billing", None)
    else:
        raise DataConflictError("选择与当前待确认事项不符，请刷新租赁明细")
    queue = data.get("queue", [])
    line.pending_action_type = "none"
    if queue:
        upcoming = queue.pop(0)
        line.pending_action_type = upcoming["kind"]
        following.update(upcoming["details"], queue=queue)
    line.pending_meta_json = encoded(following) if following else None
    # Later months may already have been opened before this event was settled.
    if kind == "scrap_stop":
        stop(later_lines(db, line))
    elif kind == "transfer_attribution":
        for other in later_lines(db, line):
            if other.pending_action_type != "none" or "next_project" in meta(other):
                break
            move(db, other, ProjectRef.from_row(transfer, "to_project"))
    item = db.get(EquipmentItem, line.equipment_id) if line.equipment_id else None
    if line.billing_status == "normal" and not can_charge(line.month, item):
        line.billing_status = "stopped"
    recalculate(line)
    db.flush()
    return line_record(line, project_index(db), item)


def reorder(db, request):
    month_row(db, request.month)
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


def reorder_projects(db, request):
    month_row(db, request.month)
    ranks = {project.project_id if project.project_id is not None else project.project_name: order
             for order, project in enumerate(request.projects)}
    lines = db.scalars(select(RentalLine).where(RentalLine.month == request.month)).all()
    keys = {ProjectRef.from_row(line, "project").key() for line in lines}
    if len(ranks) != len(request.projects) or ranks.keys() != keys:
        raise DataConflictError("排序须包含本月全部项目且无重复")
    for line in lines:
        line.project_sort_order = ranks[ProjectRef.from_row(line, "project").key()]
    db.flush()
    return request.model_dump()
