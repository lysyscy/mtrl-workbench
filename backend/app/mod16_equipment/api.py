"""设备台账（mod16）HTTP 接口：守卫 /api/m16 路由、事务边界与三套 Excel 导出出口。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Query, Response
from fastapi.encoders import jsonable_encoder

from app import export_registry as EXP
from app.core.config import get_settings, i8_base_of
from app.core.db import session_scope
from app.core.session import current_name
from app.mod02_i8.browser_relay import MODE_BROWSER, MODE_HTTP, open_i8_client
from app.mod02_i8.client import I8Client
from app.mod02_i8.session_policy import unified_i8_session
from app.mod15_user.service import active_account
from . import rental, schemas as S, service
from .common import ledger_lock, record
from .sync import I8CustomFormEquipmentAdapter, sync_lock, sync_queue
from .models import EquipmentScrap, EquipmentTransfer

router = APIRouter(prefix="/api/m16", tags=["设备台账"])


@contextmanager
def i8_adapter(session_mode: str, device_id: str) -> Iterator[I8CustomFormEquipmentAdapter | None]:
    settings = get_settings()
    owner = current_name()
    if not settings.m16_i8_sync_enabled or not owner:
        yield None
        return
    with session_scope() as db:
        account = active_account(db, owner)
        user = (account.i8_user or "").strip() if account is not None else ""
    if not user:
        yield None
        return

    def adapter(transport):
        return I8CustomFormEquipmentAdapter(
            transport, project_ids=settings.m16_i8_sync_project_ids,
            unit_ids=settings.m16_i8_sync_unit_ids,
            transfer_operator=settings.m16_i8_sync_operators.get(user),
        )

    if session_mode == MODE_HTTP:
        transport = I8Client.from_cached_session(i8_base_of(settings), user)
        if transport is None:
            yield None
        else:
            try:
                yield adapter(transport)
            finally:
                transport.close()
        return

    with unified_i8_session({"session_mode": session_mode, "device_id": device_id}, owner=owner,
                            operation="m16.equipment.sync", scope={}):
        transport = open_i8_client(owner=owner, equipment_sync=True)
        try:
            yield adapter(transport)
        finally:
            transport.close()


def call(fn, *args, write=False, **kwargs):
    with session_scope() as db:
        if write:
            ledger_lock(db)
        result = fn(db, *args, **kwargs)
        return jsonable_encoder(result, custom_encoder={Decimal: str})


def save_local(fn, request, field):
    result = call(fn, request, write=True)
    result["i8_sync"] = [{"id": r["id"], "status": r["i8_sync_status"], "message": r["i8_sync_message"]}
                         for r in result[field]]
    result["i8_sync_enabled"] = get_settings().m16_i8_sync_enabled
    return result


PreviewQuery = Query()


@router.get("/equipment/preview")
def preview_get(request: S.Preview = PreviewQuery):
    return {"codes": call(service.codes, request)}


@router.get("/project-options")
def project_options():
    return call(service.project_options)


@router.get("/locations", response_model=S.LocationList)
def locations(include_inactive: bool = False):
    return call(service.locations, include_inactive)


@router.post("/locations", response_model=S.LocationResult)
def create_location(request: S.LocationCreate):
    return call(service.save_location, request.model_dump(), write=True)


@router.patch("/locations/{id}", response_model=S.LocationResult)
def update_location(id: int, request: S.LocationPatch):
    return call(service.save_location, request.model_dump(exclude_unset=True), id, write=True)


@router.post("/equipment/preview")
def preview_post(request: S.Preview):
    return {"codes": call(service.codes, request)}


@router.post("/equipment")
def create(request: S.EquipmentCreate):
    return save_local(service.create, request, "equipment")


@router.get("/equipment")
def equipment(item_category: S.ItemCategory | None = None, project: str | None = None, status: str | None = None,
              include_scrapped: bool = False, asset_scope: S.Scope | None = None,
              in_rental: S.RentalFlag | None = None, sync_issue_only: bool = False, keyword: str | None = None):
    return call(service.equipment, item_category, project, status, include_scrapped, asset_scope,
                in_rental, sync_issue_only, keyword)


@router.get("/equipment/{id}")
def detail(id: int, month: S.Month | None = None):
    return call(service.detail, id, month or date.today().strftime("%Y-%m"))


@router.patch("/equipment/{id}")
def update(id: int, request: S.EquipmentPatch):
    with sync_lock(id):
        return call(service.update, id, request.model_dump(exclude_unset=True), write=True)


@router.post("/transfers")
def transfer(request: S.Transfer):
    return save_local(service.transfer, request, "transfers")


@router.get("/transfers")
def transfers(item_category: S.ItemCategory | None = None, project: str | None = None,
              keyword: str | None = None, sync_status: str | None = None):
    return {"items": call(service.history, EquipmentTransfer, item_category, project, keyword, sync_status)}


@router.delete("/transfers/{transfer_id}", response_model=S.TransferDeleteResult)
def delete_transfer(transfer_id: int):
    equipment_id = call(service.transfer_equipment_id, transfer_id)
    with sync_lock(equipment_id):
        return call(service.delete_transfer, transfer_id, write=True)


@router.post("/scraps")
def scrap(request: S.Scrap):
    return call(service.scrap, request, write=True)


@router.get("/scraps")
def scraps(item_category: S.ItemCategory | None = None, project: str | None = None, keyword: str | None = None):
    return {"items": call(service.history, EquipmentScrap, item_category, project, keyword)}


@router.get("/i8-sync/issues")
def sync_issues():
    return call(service.issues)


@router.post("/i8-sync/retry")
def retry(request: S.Retry, session_mode: str = MODE_BROWSER, device_id: str = ""):
    keys = call(service.retry_ids, request)
    result = {"equipment": [], "transfers": []}
    with i8_adapter(session_mode, device_id) as adapter:
        for key in keys:
            queue = sync_queue(key, adapter)
            for field in result:
                result[field].extend(queue[field])
    return result


@router.get("/rental")
def monthly(month: S.Month, project: str | None = None):
    return call(month_snapshot, month, project, write=True)


def month_snapshot(db, month, project=None):
    if current_name():
        return rental.view(db, month, project)
    # Guests may view the projected carry-forward without creating a saved month.
    with db.begin_nested() as preview:
        result = rental.view(db, month, project)
        preview.rollback()
    return result


@router.patch("/rental/lines/{id}")
def edit_line(id: int, request: S.RentPatch):
    return call(rental.patch, id, request.model_dump(exclude_unset=True), write=True)


@router.post("/rental/lines/{id}/resolve")
def resolve(id: int, request: S.Resolve):
    return call(rental.resolve, id, request.choice, write=True)


@router.put("/rental/reorder")
def reorder(request: S.Reorder):
    return call(rental.reorder, request, write=True)


@router.put("/rental/reorder-projects", response_model=S.ReorderProjects)
def reorder_projects(request: S.ReorderProjects):
    return call(rental.reorder_projects, request, write=True)


@router.get("/inventory")
def inventory(category: S.Category | None = None):
    return call(service.inventory, category)


def inventory_write(db, request, key=None):
    return record(service.save_inventory(db, request.model_dump(exclude_unset=key is not None), key))


@router.post("/inventory")
def add_inventory(request: S.InventoryCreate):
    return call(inventory_write, request, write=True)


@router.patch("/inventory/{id}")
def edit_inventory(id: int, request: S.InventoryPatch):
    return call(inventory_write, request, id, write=True)


def download(body, filename):
    return Response(content=body, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename + ".xlsx")})


@router.get("/export/distribution")
def export_distribution():
    with session_scope() as db:
        ledger_lock(db)
        snapshot = {"items": service.equipment(db, include_scrapped=True)["items"],
                    "transfers": service.history(db, EquipmentTransfer), "scraps": service.history(db, EquipmentScrap)}
    return download(EXP.get("equipment_distribution_xlsx")(snapshot), "设备分布总表")


@router.get("/export/rental")
def export_rental(month: S.Month):
    with session_scope() as db:
        ledger_lock(db)
        snapshot = month_snapshot(db, month)
    return download(EXP.get("equipment_rental_xlsx")(snapshot), month + "分公司租赁费")


@router.get("/export/inventory")
def export_inventory():
    with session_scope() as db:
        snapshot = service.inventory(db)["items"]
    return download(EXP.get("equipment_inventory_xlsx")(snapshot), "流动资产盘点表")
