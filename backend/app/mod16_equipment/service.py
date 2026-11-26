"""设备、盘点以及调拨报废联动。一个业务动作使用同一事务。"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select, update as update_rows

from app.core.errors import DataConflictError
from app.core.identity import current_operator
from . import rental
from .common import batch, product, record, require, total
from .models import EquipmentItem, EquipmentScrap, EquipmentTransfer, InventoryItem, Location, RentalLine
from .projects import ProjectRef, project_index, requested_project
from .sync import ISSUES, UNAVAILABLE, i8_scope, transfer_awaiting_readback


def project_options(db):
    rows = sorted(project_index(db).values(), key=lambda row: (row.is_archived, row.ord, row.id))
    fields = ("id", "disp", "status", "phid", "warehouse_name", "name_full", "project_type", "ord")
    return {"items": [{field: getattr(row, field) for field in fields} for row in rows]}


PROJECT_FIELDS = {
    EquipmentItem: ("purchase_project", "current_project"),
    EquipmentTransfer: ("from_project", "to_project"),
    EquipmentScrap: ("original_project",),
}


def location_record(location, projects):
    project = projects.get(location.default_project_id)
    return {field: getattr(location, field) for field in ("id", "name", "default_project_id", "is_active", "sort_order")} | {
        "default_project_disp": project.disp if project else None,
    }


def locations(db, include_inactive=False):
    query = select(Location).order_by(Location.sort_order, Location.id)
    if not include_inactive:
        query = query.where(Location.is_active.is_(True))
    projects = project_index(db)
    return {"items": [location_record(row, projects) for row in db.scalars(query)]}


def rename_location_references(db, old, new):
    for model, prefixes in (PROJECT_FIELDS | {RentalLine: ("project",)}).items():
        for prefix in prefixes:
            label = "project_name" if model is RentalLine else prefix
            custom = getattr(model, f"{prefix}_custom")
            legacy = getattr(model, label)
            project = getattr(model, f"{prefix}_id")
            matches = (custom == old) | (custom.is_(None) & project.is_(None) & (legacy == old))
            values = {custom: new, legacy: new}
            if model is EquipmentItem:
                values[EquipmentItem.updated_by] = current_operator()
            db.execute(update_rows(model).where(matches).values(values))
    rental.rename_location_metadata(db, old, new)


def save_location(db, values, key=None):
    row = Location() if key is None else require(db, Location, key)
    projects = project_index(db)
    default = values.get("default_project_id")
    if default is not None and default not in projects:
        raise DataConflictError("所选项目档案不存在或不能关联，请刷新项目列表")
    if "name" in values and values["name"] != row.name:
        if db.scalar(select(Location.id).where(Location.name == values["name"])) is not None:
            raise DataConflictError("位置名称已存在")
        if key is not None:
            rename_location_references(db, row.name, values["name"])
    for field, value in values.items():
        setattr(row, field, value)
    db.add(row)
    db.flush()
    return location_record(row, projects)


def distribution_record(row, projects):
    values = record(row)
    for prefix in PROJECT_FIELDS[type(row)]:
        values.update(ProjectRef.from_row(row, prefix).response(prefix, projects))
    return values


def equipment_record(item, projects, inventory):
    return distribution_record(item, projects) | {
        "inventory_name": inventory.name if inventory else None,
        "inventory_book_qty": inventory.book_qty if inventory else None,
        "inventory_count_qty": inventory.count_qty if inventory else None,
    }


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
    ids, codes = defaultdict(list), defaultdict(list)
    if rows:
        for inv_id, key, code in db.execute(select(EquipmentItem.inventory_item_id, EquipmentItem.id, EquipmentItem.code)
                .where(EquipmentItem.inventory_item_id.in_([row.id for row in rows])).order_by(EquipmentItem.id)):
            ids[inv_id].append(key)
            codes[inv_id].append(code)
    return {"items": [record(r) | {"linked_equipment_ids": ids[r.id], "linked_equipment_codes": codes[r.id]} for r in rows],
            "book_amount": total(r.book_amount for r in rows),
            "count_amount": total(r.count_amount for r in rows)}


def asset_row(db, item, qty, *, counted, diff_qty=None):
    return save_inventory(db, {"category": "tool" if item.item_category == "equipment" else "turnover",
                              "name": item.name, "spec": item.spec, "unit": item.unit,
                              "unit_price": item.purchase_price, "book_qty": qty,
                              "count_qty": counted, "diff_qty": diff_qty})


def start_rental(db, item, month, custom=None):
    start = date.fromisoformat(month + "-01")
    following = (start.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
    return rental.action(db, item, month, "new_purchase_start", {
        "purchase_date": item.purchase_date, "this_month": month, "next_month": following}, custom)


def create(db, req):
    projects = project_index(db)
    purchase = requested_project(projects, req.purchase_project, req.purchase_project_id, req.purchase_project_custom)
    allocated = codes(db, req)
    if req.expected_codes is not None and req.expected_codes != allocated:
        raise DataConflictError("编号已被占用或录入内容已变化，请刷新编号预览", detail="expected_codes")
    inv = asset_row(db, req, req.quantity, counted=req.quantity) if req.asset_scope == "current_asset" else None
    data = req.model_dump(exclude={"quantity", "custom_unit_price", "target_month", "expected_codes"})
    data.update(purchase.fields("purchase_project"))
    data.update(purchase.fields("current_project"))
    items, lines = [], []
    sync = i8_scope(req)
    for code in allocated:
        item = EquipmentItem(**data, code=code, i8_sync_status="pending" if sync else "not_applicable",
                             i8_sync_message=UNAVAILABLE if sync else None,
                             quantity=Decimal(1) if req.item_category == "equipment" else req.quantity,
                             inventory_item_id=inv.id if inv else None)
        db.add(item)
        db.flush()
        if req.in_rental == "yes":
            line = start_rental(db, item, req.target_month or req.purchase_date.strftime("%Y-%m"), req.custom_unit_price)
            lines.append(line.id)
        items.append(equipment_record(item, projects, inv))
    return {"codes": allocated, "equipment": items, "inventory_item": record(inv),
            "rental_line_ids": lines}


def deduct(row, qty):
    row.book_qty -= qty
    if row.count_qty is None:
        moved_count = row.diff_qty = None
    else:
        moved_count = min(qty, max(Decimal(0), row.count_qty))
        row.count_qty -= moved_count
        row.diff_qty = row.count_qty - row.book_qty
    row.is_active = row.book_qty > 0 or bool(row.count_qty) or bool(row.diff_qty)
    inventory_amounts(row)
    return moved_count


def update(db, key, changes):
    item = require(db, EquipmentItem, key)
    if item.status == "scrapped":
        raise DataConflictError("已报废设备不能直接修改")
    old_flag, old_scope = item.in_rental, item.asset_scope
    projects = project_index(db)
    month = date.today().strftime("%Y-%m")
    dual_fields = {"purchase_project_id", "purchase_project_custom"} & changes.keys()
    previous = ProjectRef.from_row(item, "purchase_project")
    if dual_fields:
        project = requested_project(projects, changes.get("purchase_project"),
                                    changes.get("purchase_project_id", previous.id),
                                    changes.get("purchase_project_custom", previous.custom))
        changes = changes | project.fields("purchase_project")
    elif "purchase_project" in changes:
        label = changes["purchase_project"]
        project = previous if label == previous.display(projects) else requested_project(projects, label)
        changes = changes | project.fields("purchase_project")
    for name, value in changes.items():
        setattr(item, name, value)
    purchase = ProjectRef.from_row(item, "purchase_project")
    if purchase != previous and db.scalar(select(EquipmentTransfer.id).where(
            EquipmentTransfer.equipment_id == key).limit(1)) is None:
        origin = ProjectRef.from_row(item, "current_project")
        for field, value in purchase.fields("current_project").items():
            setattr(item, field, value)
        rental.correct_location(db, key, month, origin, purchase)
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
            counted = deduct(linked, item.quantity)
            difference = counted - item.quantity if counted is not None else None
            item.inventory_item_id = asset_row(db, item, item.quantity, counted=counted, diff_qty=difference).id
        else:
            save_inventory(db, edited, linked.id)
    # An imported on-book item may be excluded from inventory or have only a group match.
    elif not linked and item.asset_scope == "current_asset" and item.source_lists_inventory is None:
        item.inventory_item_id = asset_row(db, item, item.quantity, counted=item.quantity).id
    if old_flag != item.in_rental:
        if item.in_rental != "yes":
            rental.stop_lines(db, item.id, month, include_current=True)
        elif not rental.has_active_line(db, item.id, month):
            start_rental(db, item, month)
    if not i8_scope(item):
        item.i8_sync_status, item.i8_sync_message = "not_applicable", None
        if old_scope == "current_asset" and item.item_category == "equipment":
            db.execute(update_rows(EquipmentTransfer).where(
                EquipmentTransfer.equipment_id == key, EquipmentTransfer.i8_sync_status.in_(ISSUES)
            ).values(i8_sync_status="not_applicable", i8_sync_message=None))
    elif changes:
        item.i8_sync_status, item.i8_sync_message = "pending", "设备资料已修改，待同步"
    db.flush()
    return equipment_record(item, projects, db.get(InventoryItem, item.inventory_item_id) if item.inventory_item_id else None)


def equipment_records(db, items, projects, *, include_transfer_status=True):
    """Show the earliest unresolved sync step without losing the equipment's own retry state."""
    inventory_ids = {item.inventory_item_id for item in items if item.inventory_item_id is not None}
    inventories = {row.id: row for row in db.scalars(select(InventoryItem).where(InventoryItem.id.in_(inventory_ids)))} if inventory_ids else {}
    values = {item.id: equipment_record(item, projects, inventories.get(item.inventory_item_id)) for item in items}
    if values and include_transfer_status:
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
    for col, value in ((EquipmentItem.item_category, item_category),
                       (EquipmentItem.status, status), (EquipmentItem.asset_scope, asset_scope),
                       (EquipmentItem.in_rental, in_rental)):
        if value is not None:
            query = query.where(col == value)
    if not include_scrapped and status != "scrapped":
        query = query.where(EquipmentItem.status != "scrapped")
    if sync_issue_only:
        query = query.where(i8_scope(EquipmentItem), or_(EquipmentItem.i8_sync_status.in_(ISSUES), EquipmentItem.id.in_(
            select(EquipmentTransfer.equipment_id).where(EquipmentTransfer.i8_sync_status.in_(ISSUES)))))
    projects = project_index(db)
    rows = db.scalars(query.order_by(EquipmentItem.id)).all()
    if project is not None or keyword:
        rows = [item for item in rows if matches_equipment(item, projects, project, keyword)]
    pending = db.scalar(select(func.count()).select_from(RentalLine).where(
        RentalLine.equipment_id.in_([item.id for item in rows]),
        RentalLine.pending_action_type != "none"))
    values = equipment_records(db, rows, projects)
    return {"items": values, "summary": {
        "active_count": sum(r.status != "scrapped" for r in rows),
        "pending_sync_count": sum(r["i8_sync_status"] in ("pending", "failed") for r in values),
        "conflict_count": sum(r["i8_sync_status"] == "conflict" for r in values), "pending_rental_count": pending}}


def matches_equipment(item, projects, project, keyword):
    label = ProjectRef.from_row(item, "current_project").display(projects)
    return (project is None or label == project) and (not keyword or any(
        keyword.casefold() in value.casefold() for value in (item.code, item.name, item.spec, label) if value))


LATEST_TRANSFER_ORDER = (EquipmentTransfer.transfer_date.desc().nulls_last(), EquipmentTransfer.id.desc())


def history(db, model, item_category=None, project=None, keyword=None, sync_status=None, equipment_id=None, *, projects=None):
    query = select(model, EquipmentItem).join(EquipmentItem, model.equipment_id == EquipmentItem.id)
    if model is EquipmentTransfer:
        latest = (select(EquipmentTransfer.id)
                  .where(EquipmentTransfer.equipment_id == EquipmentItem.id)
                  .order_by(*LATEST_TRANSFER_ORDER).limit(1).correlate(EquipmentItem).scalar_subquery())
        query = query.add_columns(model.id == latest)
    if equipment_id:
        query = query.where(model.equipment_id == equipment_id)
    if item_category:
        query = query.where(model.item_category == item_category)
    if sync_status:
        query = query.where(model.i8_sync_status == sync_status)
    if keyword:
        query = query.where(or_(*(c.icontains(keyword, autoescape=True) for c in (
            EquipmentItem.code, EquipmentItem.name, EquipmentItem.spec))))
    projects = project_index(db) if projects is None else projects
    rows = []
    for row, item, *flags in db.execute(query.order_by(model.id)):
        values = distribution_record(row, projects)
        if not project or any(values[field] == project for field in PROJECT_FIELDS[model]):
            if flags:
                values["is_latest_for_equipment"] = flags[0]
            rows.append(values | {"code": item.code, "name": item.name, "spec": item.spec, "unit": item.unit})
    return rows


def detail(db, key, month):
    item = require(db, EquipmentItem, key)
    projects = project_index(db)
    scraps = history(db, EquipmentScrap, equipment_id=key, projects=projects)
    display = equipment_records(db, [item], projects)[0]
    return {"equipment": display, "transfers": history(db, EquipmentTransfer, equipment_id=key, projects=projects),
            "scrap": scraps[0] if scraps else None,
            "inventory_item": record(db.get(InventoryItem, item.inventory_item_id)) if item.inventory_item_id else None,
            "rental_lines": [rental.line_record(r, projects, item) for r in db.scalars(select(RentalLine).where(
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
    projects = project_index(db)
    destination = requested_project(projects, req.to_project, req.to_project_id, req.to_project_custom)
    month = req.transfer_date.strftime("%Y-%m")
    lines, records = [], []
    for item in items:
        origin = ProjectRef.from_row(item, "current_project")
        origin_label = origin.display(projects)
        if req.expected_from_projects is not None and req.expected_from_projects.get(item.id) != origin_label:
            raise DataConflictError("设备所在项目已变化，请刷新后重新选择")
        newer = db.scalar(select(EquipmentTransfer.id).where(EquipmentTransfer.equipment_id == item.id,
                          EquipmentTransfer.transfer_date > req.transfer_date).limit(1))
        if newer:
            raise DataConflictError("调拨日期早于该设备已有调拨，请核对日期")
        if origin.key() == destination.key() and origin_label == destination.display(projects):
            raise DataConflictError("调入项目与设备当前项目相同")
        for field, value in destination.fields("current_project").items():
            setattr(item, field, value)
        item.updated_by = current_operator()
        same_system_project = origin.id is not None and origin.id == destination.id
        sync = i8_scope(item) and not same_system_project
        row = EquipmentTransfer(i8_sync_status="pending" if sync else "not_applicable",
                                i8_sync_message=UNAVAILABLE if sync else None,
                                equipment_id=item.id, item_category=item.item_category,
                                **origin.fields("from_project"), **destination.fields("to_project"),
                                transfer_date=req.transfer_date, quantity=item.quantity,
                                remark=req.remark, rental_month=month if item.in_rental == "yes" else None,
                                rental_attribution="pending" if item.in_rental == "yes" else "not_applicable")
        db.add(row)
        db.flush()
        if item.in_rental == "yes":
            lines.append(rental.action(db, item, month, "transfer_attribution", {
                "transfer_id": row.id, "from_project": origin_label, "to_project": destination.display(projects),
                "transfer_date": req.transfer_date,
                "suggested_side": "from_project" if req.transfer_date.day >= 25 else "to_project"},
                project=origin).id)
        records.append(row)
    return {"equipment_ids": req.equipment_ids, "transfers": [distribution_record(r, projects) for r in records],
            "rental_line_ids": lines}


def transfer_equipment_id(db, key):
    return require(db, EquipmentTransfer, key).equipment_id


def delete_transfer(db, key):
    transfer = require(db, EquipmentTransfer, key)
    item = require(db, EquipmentItem, transfer.equipment_id)
    latest_id = db.scalar(select(EquipmentTransfer.id).where(EquipmentTransfer.equipment_id == item.id)
                          .order_by(*LATEST_TRANSFER_ORDER).limit(1))
    if latest_id != key:
        raise DataConflictError("仅可删除该设备的最新一条调拨记录")
    if item.status == "scrapped":
        raise DataConflictError("设备已报废，不能删除历史调拨记录")
    if transfer.i8_sync_status == "synced":
        raise DataConflictError("该调拨已同步 i8，暂不支持直接删除，请先核对 i8 单据")
    if transfer_awaiting_readback(transfer):
        raise DataConflictError("该调拨的 i8 保存结果待核对，暂不支持直接删除")
    reverted = ProjectRef.from_row(transfer, "from_project")
    rental.remove_transfer(db, transfer, reverted)
    for field, value in reverted.fields("current_project").items():
        setattr(item, field, value)
    item.updated_by = current_operator()
    db.delete(transfer)
    db.flush()
    return {"deleted_transfer_id": key, "equipment_id": item.id,
            "reverted_project": reverted.display(project_index(db)),
            "reverted_project_id": reverted.id, "reverted_project_custom": reverted.custom}


def scrap(db, req):
    ids = req.equipment_ids or [req.equipment_id]
    projects = project_index(db)
    lines, records = [], []
    for item in active_batch(db, ids):
        item.status, item.scrap_date, item.scrap_reason = "scrapped", req.scrap_date, req.reason
        item.updated_by = current_operator()
        row = EquipmentScrap(equipment_id=item.id, item_category=item.item_category, scrap_date=req.scrap_date,
                             **ProjectRef.from_row(item, "current_project").fields("original_project"),
                             quantity=item.quantity, purchase_price=item.purchase_price,
                             reason=req.reason, rental_stop_status="pending" if item.in_rental == "yes" else "not_applicable")
        db.add(row)
        db.flush()
        if item.inventory_item_id:
            deduct(require(db, InventoryItem, item.inventory_item_id), item.quantity)
        if item.in_rental == "yes":
            lines.append(rental.action(db, item, req.scrap_date.strftime("%Y-%m"), "scrap_stop",
                                      {"scrap_id": row.id, "scrap_date": req.scrap_date}).id)
        records.append(distribution_record(row, projects))
    return {"equipment_ids": ids, "scraps": records, "rental_line_ids": lines}


def issues(db):
    projects = project_index(db)
    items = db.scalars(select(EquipmentItem).where(
        i8_scope(EquipmentItem), EquipmentItem.i8_sync_status.in_(ISSUES)
    ).order_by(EquipmentItem.id)).all()
    return {"equipment": equipment_records(db, items, projects, include_transfer_status=False),
        "transfers": [distribution_record(r, projects) for r in db.scalars(select(EquipmentTransfer)
            .join(EquipmentItem, EquipmentItem.id == EquipmentTransfer.equipment_id)
            .where(i8_scope(EquipmentItem), EquipmentTransfer.i8_sync_status.in_(ISSUES))
            .order_by(EquipmentTransfer.id))]}


def retry_ids(db, req):
    if not req.equipment_ids and not req.transfer_ids:
        raise DataConflictError("请选择要重试的设备或调拨记录")
    items = batch(db, EquipmentItem, req.equipment_ids)
    transfers = batch(db, EquipmentTransfer, req.transfer_ids)
    for item in items:
        if not i8_scope(item):
            raise DataConflictError("该设备不适用 i8 同步")
        pending = db.scalar(select(EquipmentTransfer.id).where(
            EquipmentTransfer.equipment_id == item.id, EquipmentTransfer.i8_sync_status.in_(ISSUES)).limit(1))
        if item.i8_sync_status not in ISSUES and not pending:
            raise DataConflictError("该设备没有待重试的记录")
    if any(row.i8_sync_status not in ISSUES or not i8_scope(require(db, EquipmentItem, row.equipment_id))
           for row in transfers):
        raise DataConflictError("只能重试待同步、失败或冲突的记录")
    return list(dict.fromkeys([item.id for item in items] + [row.equipment_id for row in transfers]))
