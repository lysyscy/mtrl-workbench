"""设备、盘点以及调拨报废联动。一个业务动作使用同一事务。"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select

from app.core.errors import DataConflictError
from app.core.identity import current_operator
from . import rental
from .common import batch, product, record, require, total
from .models import EquipmentItem, EquipmentScrap, EquipmentTransfer, InventoryItem, RentalLine
from .sync import ISSUES, UNAVAILABLE


def codes(db, request):
    prefix = f"{request.name}-{request.purchase_date:%Y%m%d}"
    existing = db.scalars(select(EquipmentItem.code).where(or_(EquipmentItem.code == prefix,
                    EquipmentItem.code.startswith(prefix + "-", autoescape=True)))).all()
    suffixes = [int(c[len(prefix) + 1:]) for c in existing if c[len(prefix) + 1:].isascii()
                and c[len(prefix) + 1:].isdigit()]
    last = max(suffixes + [int(prefix in existing)])
    count = int(request.quantity) if request.item_category == "equipment" else 1
    if request.quantity == 1 and not existing:
        return [prefix]
    return [f"{prefix}-{n:02d}" for n in range(last + 1, last + count + 1)]


def inventory_amounts(row):
    row.book_amount = product(row.book_qty, row.unit_price)
    row.count_amount = product(row.count_qty, row.unit_price)
    row.diff_amount = product(row.diff_qty, row.unit_price)
    row.updated_by = current_operator()


def save_inventory(db, values, key=None):
    row = InventoryItem() if key is None else require(db, InventoryItem, key)
    for name, value in values.items():
        setattr(row, name, value)
    inventory_amounts(row)
    db.add(row)
    db.flush()
    return row


def inventory(db, category=None):
    query = select(InventoryItem).where(InventoryItem.is_active.is_(True))
    if category:
        query = query.where(InventoryItem.category == category)
    rows = db.scalars(query.order_by(InventoryItem.sort_order, InventoryItem.id)).all()
    return {"items": [record(r) for r in rows], "book_amount": total(r.book_amount for r in rows),
            "count_amount": total(r.count_amount for r in rows)}


def asset_row(db, item, qty):
    return save_inventory(db, {"category": "tool" if item.item_category == "equipment" else "turnover",
                              "name": item.name, "spec": item.spec, "unit": item.unit,
                              "unit_price": item.purchase_price, "book_qty": qty, "count_qty": qty})


def start_rental(db, item, month, custom=None):
    start = date.fromisoformat(month + "-01")
    following = (start.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
    return rental.action(db, item, month, "new_purchase_start", {
        "purchase_date": item.purchase_date, "this_month": month, "next_month": following}, custom)


def create(db, req):
    allocated = codes(db, req)
    if req.expected_codes is not None and req.expected_codes != allocated:
        raise DataConflictError("编号已被占用或录入内容已变化，请刷新编号预览", detail="expected_codes")
    inv = asset_row(db, req, req.quantity) if req.asset_scope == "current_asset" else None
    data = req.model_dump(exclude={"quantity", "custom_unit_price", "target_month", "current_project", "expected_codes"})
    items, lines = [], []
    for code in allocated:
        item = EquipmentItem(**data, code=code, i8_sync_message=UNAVAILABLE, current_project=req.current_project or req.purchase_project,
                             quantity=Decimal(1) if req.item_category == "equipment" else req.quantity,
                             inventory_item_id=inv.id if inv else None)
        db.add(item)
        db.flush()
        if req.in_rental == "yes":
            line = start_rental(db, item, req.target_month or req.purchase_date.strftime("%Y-%m"), req.custom_unit_price)
            lines.append(line.id)
        items.append(record(item))
    return {"codes": allocated, "equipment": items, "inventory_item": record(inv),
            "rental_line_ids": lines}


def deduct(row, qty):
    row.book_qty -= qty
    row.count_qty = max(Decimal("0"), row.count_qty - qty)
    row.diff_qty = row.count_qty - row.book_qty
    row.is_active = row.book_qty > 0 or row.count_qty > 0 or row.diff_qty != 0
    inventory_amounts(row)


def update(db, key, changes):
    item = require(db, EquipmentItem, key)
    if item.status == "scrapped":
        raise DataConflictError("已报废设备不能直接修改")
    old_flag, old_scope = item.in_rental, item.asset_scope
    for name, value in changes.items():
        setattr(item, name, value)
    item.updated_by = current_operator()
    if "purchase_date" in changes:
        item.purchase_date_text = None
    if old_scope != item.asset_scope:
        item.source_lists_inventory = None
    linked = db.get(InventoryItem, item.inventory_item_id) if item.inventory_item_id else None
    fields = {"name": "name", "spec": "spec", "unit": "unit", "purchase_price": "unit_price"}
    edited = {dst: changes[src] for src, dst in fields.items() if src in changes}
    if linked and item.asset_scope != "current_asset":
        deduct(linked, item.quantity)
        item.inventory_item_id = None
    elif linked and edited:
        others = db.scalar(select(func.count()).select_from(EquipmentItem).where(
            EquipmentItem.inventory_item_id == linked.id, EquipmentItem.id != key, EquipmentItem.status != "scrapped"))
        if others:
            deduct(linked, item.quantity)
            item.inventory_item_id = asset_row(db, item, item.quantity).id
        else:
            save_inventory(db, edited, linked.id)
    # An imported on-book item may be excluded from inventory or have only a group match.
    elif not linked and item.asset_scope == "current_asset" and item.source_lists_inventory is None:
        item.inventory_item_id = asset_row(db, item, item.quantity).id
    if old_flag != "yes" and item.in_rental == "yes":
        start_rental(db, item, date.today().strftime("%Y-%m"))
    if old_flag == "yes" and item.in_rental == "no":
        rental.stop_lines(db, item.id, date.today().strftime("%Y-%m"), include_current=True)
    if changes:
        item.i8_sync_status, item.i8_sync_message = "pending", "设备资料已修改，待同步"
    db.flush()
    return record(item)


def equipment_records(db, items):
    """Show the earliest unresolved sync step without losing the equipment's own retry state."""
    values = {item.id: record(item) for item in items}
    if values:
        pending = db.scalars(select(EquipmentTransfer).where(
            EquipmentTransfer.equipment_id.in_(values), EquipmentTransfer.i8_sync_status.in_(ISSUES)
        ).order_by(EquipmentTransfer.transfer_date, EquipmentTransfer.id))
        for transfer in pending:
            item = values[transfer.equipment_id]
            if item["i8_sync_status"] not in ISSUES:
                item["i8_sync_status"] = transfer.i8_sync_status
                item["i8_sync_message"] = transfer.i8_sync_message
    return list(values.values())


def equipment(db, item_category=None, project=None, status=None, include_scrapped=False,
              asset_scope=None, in_rental=None, sync_issue_only=False, keyword=None):
    query = select(EquipmentItem)
    for col, value in ((EquipmentItem.item_category, item_category), (EquipmentItem.current_project, project),
                       (EquipmentItem.status, status), (EquipmentItem.asset_scope, asset_scope),
                       (EquipmentItem.in_rental, in_rental)):
        if value is not None:
            query = query.where(col == value)
    if not include_scrapped and status != "scrapped":
        query = query.where(EquipmentItem.status != "scrapped")
    if sync_issue_only:
        query = query.where(or_(EquipmentItem.i8_sync_status.in_(ISSUES), EquipmentItem.id.in_(
            select(EquipmentTransfer.equipment_id).where(EquipmentTransfer.i8_sync_status.in_(ISSUES)))))
    if keyword:
        query = query.where(or_(*(c.icontains(keyword, autoescape=True) for c in (
            EquipmentItem.code, EquipmentItem.name, EquipmentItem.spec, EquipmentItem.current_project))))
    rows = db.scalars(query.order_by(EquipmentItem.id)).all()
    pending = db.scalar(select(func.count()).select_from(RentalLine).where(
        RentalLine.equipment_id.in_(query.with_only_columns(EquipmentItem.id)),
        RentalLine.pending_action_type != "none"))
    values = equipment_records(db, rows)
    return {"items": values, "summary": {
        "active_count": sum(r.status != "scrapped" for r in rows),
        "pending_sync_count": sum(r["i8_sync_status"] in ("pending", "failed") for r in values),
        "conflict_count": sum(r["i8_sync_status"] == "conflict" for r in values), "pending_rental_count": pending}}


def history(db, model, item_category=None, project=None, keyword=None, sync_status=None, equipment_id=None):
    query = select(model, EquipmentItem).join(EquipmentItem, model.equipment_id == EquipmentItem.id)
    if equipment_id:
        query = query.where(model.equipment_id == equipment_id)
    if item_category:
        query = query.where(model.item_category == item_category)
    if project:
        query = query.where(or_(model.from_project == project, model.to_project == project)
                            if model is EquipmentTransfer else model.original_project == project)
    if sync_status:
        query = query.where(model.i8_sync_status == sync_status)
    if keyword:
        query = query.where(or_(*(c.icontains(keyword, autoescape=True) for c in (
            EquipmentItem.code, EquipmentItem.name, EquipmentItem.spec))))
    return [record(row) | {"code": item.code, "name": item.name, "spec": item.spec, "unit": item.unit}
            for row, item in db.execute(query.order_by(model.id))]


def detail(db, key, month):
    item = require(db, EquipmentItem, key)
    scraps = history(db, EquipmentScrap, equipment_id=key)
    display = equipment_records(db, [item])[0]
    return {"equipment": display, "transfers": history(db, EquipmentTransfer, equipment_id=key),
            "scrap": scraps[0] if scraps else None,
            "inventory_item": record(db.get(InventoryItem, item.inventory_item_id)) if item.inventory_item_id else None,
            "rental_lines": [record(r) for r in db.scalars(select(RentalLine).where(
                RentalLine.equipment_id == key, RentalLine.month == month))],
            "i8_sync": {"status": display["i8_sync_status"], "message": display["i8_sync_message"],
                        "snapshot_json": item.i8_snapshot_json}}


def active_batch(db, ids):
    items = batch(db, EquipmentItem, ids)
    if any(item.status == "scrapped" for item in items):
        raise DataConflictError("所选设备含已报废项，请重新选择")
    return items


def transfer(db, req):
    items = active_batch(db, req.equipment_ids)
    month = req.transfer_date.strftime("%Y-%m")
    lines, records = [], []
    for item in items:
        if req.expected_from_projects is not None and req.expected_from_projects.get(item.id) != item.current_project:
            raise DataConflictError("设备所在项目已变化，请刷新后重新选择")
        newer = db.scalar(select(EquipmentTransfer.id).where(EquipmentTransfer.equipment_id == item.id,
                          EquipmentTransfer.transfer_date > req.transfer_date).limit(1))
        if newer:
            raise DataConflictError("调拨日期早于该设备已有调拨，请核对日期")
        if item.current_project == req.to_project:
            raise DataConflictError("调入项目与设备当前项目相同")
        old = item.current_project
        item.current_project, item.updated_by = req.to_project, current_operator()
        row = EquipmentTransfer(i8_sync_message=UNAVAILABLE, equipment_id=item.id, item_category=item.item_category, from_project=old,
                                to_project=req.to_project, transfer_date=req.transfer_date, quantity=item.quantity,
                                remark=req.remark, rental_month=month if item.in_rental == "yes" else None,
                                rental_attribution="pending" if item.in_rental == "yes" else "not_applicable")
        db.add(row)
        db.flush()
        if item.in_rental == "yes":
            lines.append(rental.action(db, item, month, "transfer_attribution", {
                "transfer_id": row.id, "from_project": old, "to_project": req.to_project,
                "transfer_date": req.transfer_date,
                "suggested_side": "from_project" if req.transfer_date.day >= 25 else "to_project"}).id)
        records.append(row)
    return {"equipment_ids": req.equipment_ids, "transfers": [record(r) for r in records],
            "rental_line_ids": lines}


def scrap(db, req):
    ids = req.equipment_ids or [req.equipment_id]
    lines, records = [], []
    for item in active_batch(db, ids):
        item.status, item.scrap_date, item.scrap_reason = "scrapped", req.scrap_date, req.reason
        item.updated_by = current_operator()
        row = EquipmentScrap(equipment_id=item.id, item_category=item.item_category, scrap_date=req.scrap_date,
                             original_project=item.current_project, quantity=item.quantity, purchase_price=item.purchase_price,
                             reason=req.reason, rental_stop_status="pending" if item.in_rental == "yes" else "not_applicable")
        db.add(row)
        db.flush()
        if item.inventory_item_id:
            deduct(require(db, InventoryItem, item.inventory_item_id), item.quantity)
        if item.in_rental == "yes":
            lines.append(rental.action(db, item, req.scrap_date.strftime("%Y-%m"), "scrap_stop",
                                      {"scrap_id": row.id, "scrap_date": req.scrap_date}).id)
        records.append(record(row))
    return {"equipment_ids": ids, "scraps": records, "rental_line_ids": lines}


def issues(db):
    return {"equipment": [record(r) for r in db.scalars(select(EquipmentItem).where(
        EquipmentItem.i8_sync_status.in_(ISSUES)).order_by(EquipmentItem.id))],
        "transfers": [record(r) for r in db.scalars(select(EquipmentTransfer).where(
            EquipmentTransfer.i8_sync_status.in_(ISSUES)).order_by(EquipmentTransfer.id))]}


def retry_ids(db, req):
    if not req.equipment_ids and not req.transfer_ids:
        raise DataConflictError("请选择要重试的设备或调拨记录")
    items = batch(db, EquipmentItem, req.equipment_ids)
    transfers = batch(db, EquipmentTransfer, req.transfer_ids)
    for item in items:
        pending = db.scalar(select(EquipmentTransfer.id).where(
            EquipmentTransfer.equipment_id == item.id, EquipmentTransfer.i8_sync_status.in_(ISSUES)).limit(1))
        if item.i8_sync_status not in ISSUES and not pending:
            raise DataConflictError("该设备没有待重试的记录")
    if any(row.i8_sync_status not in ISSUES for row in transfers):
        raise DataConflictError("只能重试待同步、失败或冲突的记录")
    return list(dict.fromkeys([item.id for item in items] + [row.equipment_id for row in transfers]))
