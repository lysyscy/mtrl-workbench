"""The adapter must condition a transfer write on the observed source project."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
from threading import Lock
from typing import Protocol

from sqlalchemy import select

from app.core.db import session_scope
from .common import encoded, ledger_lock, record, require
from .models import EquipmentItem, EquipmentTransfer


ISSUES = ("pending", "failed", "conflict")
UNAVAILABLE = "i8接口暂未接通，已保存本地待同步"


class Adapter(Protocol):
    def snapshot(self, code: str) -> dict | None: ...
    def save_equipment(self, data: dict) -> None: ...
    def transfer(self, code: str, expected_project: str, to_project: str) -> None: ...


@dataclass
class SyncResult:
    status: str
    message: str
    snapshot: dict | None = None
    conflict: dict | None = None


def transfer_precondition(snapshot, code, from_project, to_project):
    if snapshot is None:
        return SyncResult("pending", "未查到 i8 设备，调拨待同步")
    if snapshot["current_project"] != from_project:
        local = {"code": code, "from_project": from_project, "to_project": to_project}
        return SyncResult("conflict", "i8 当前项目与本地调出项目不一致，请核对", snapshot,
                          {"snapshot": snapshot, "local": local, "from_project": from_project})
    return None


def checked_project(snapshot, project, matches=True):
    if snapshot and snapshot["current_project"] == project and matches:
        return SyncResult("synced", "已同步并核对 i8 所在项目", snapshot)
    return SyncResult("failed", "i8 写入后未核对成功，请核对后重试", snapshot)


def equipment_conflict(snapshot):
    return SyncResult("conflict", "相同编号的 i8 设备所在项目不同，请核对", snapshot)


class FormTransport(Protocol):
    def post_json(self, path: str, **kwargs) -> dict: ...


class SaveRejected(ValueError):
    """The form explicitly stopped before saving."""


class I8CustomFormEquipmentAdapter:
    """Inject an authorized I8Client-compatible transport and verified reference IDs."""

    LIST = "/sup/customServer/getList"
    SAVE = "/sup/customServer/save"
    ORG = "3700000000000014"
    # Fixed organizational query filters observed on the sbzx list, not session data.
    CLIENT_FILTER = ("e48f570da0f71818a59e798cfa48fa57bc388a6b8519dc9d0f237f397f1fdf63"
                     "f4b6f41b8fbed0c7a9520cd37c2e728810b59c1f0f0f253c")
    QUERY_FILTER = "5e3410ab22038162"

    def __init__(self, transport: FormTransport, *, project_ids: Mapping[str, str],
                 unit_ids: Mapping[str, str] | None = None):
        self.transport = transport
        self.project_ids = project_ids
        self.unit_ids = unit_ids or {}

    def list_equipment(self):
        rows, ids = [], set()
        total = None
        page = 0
        while True:
            body = self.transport.post_json(self.LIST, data={
                "customBusCode": "sbzx", "containerId": "p_form_sbzx_m_list",
                "clientfilter": self.CLIENT_FILTER, "queryfilter": self.QUERY_FILTER,
                "page": str(page), "start": str(len(rows)), "limit": "100",
            })
            batch, count = body["data"], int(body["total"])
            if (not isinstance(batch, list) or count < 0 or
                    (total is not None and total != count) or body.get("success") is False
                    or body.get("Success") is False or body.get("status") not in (None, "success")):
                raise ValueError("i8 设备列表不完整")
            total = count
            for row in batch:
                if not row.get("phid") or str(row["phid"]) in ids or not row.get("u_device_code"):
                    raise ValueError("i8 设备主键重复或缺少标识")
                ids.add(str(row["phid"]))
                rows.append({key: row.get(key) for key in (
                    "phid", "bill_name", "phid_pc", "phid_pc_EXName", "u_device_code",
                    "u_indata", "u_yz", "u_spec", "u_msunit", "u_bz", "phid_org", "u_use_org",
                )} | {"current_project": row.get("phid_pc_EXName")})
            if len(rows) == total:
                return rows
            if not batch or len(rows) > total:
                raise ValueError("i8 设备列表条数不符")
            page += 1

    def lookup_by_code(self, code):
        matches = [row for row in self.list_equipment() if row["u_device_code"] == code]
        if len(matches) > 1:
            raise ValueError("i8 设备编码重复")
        return matches[0] if matches else None

    def _save(self, code, data):
        response = self.transport.post_json(self.SAVE, retry_expired=False, data={
            "customBusCode": code, "data": encoded(data), "billNoStatus": "1",
            "isContinue": encoded({"warn": "0", "validateWarn": "0", "checkProjOrgWarn": "0"}),
        })
        if response.get("status") in ("validateWarn", "warn", "error"):
            raise SaveRejected("i8 未接受保存")
        if response.get("status") != "success":
            raise ValueError("i8 保存回执未确认成功")

    @staticmethod
    def _form(row):
        return {"form": {"key": "phid", "modifiedRow" if row.get("phid") else "newRow": row}}

    def create_equipment(self, data):
        code, project = data["code"], data["current_project"]
        if not code or len(code) > 50:
            raise ValueError("i8 设备编码须为 1 至 50 个字符")
        before = self.lookup_by_code(code)
        project_id = self.project_ids[project]
        if not project_id:
            raise ValueError("缺少 i8 项目标识")
        if before and (before["current_project"] != project or str(before["phid_pc"]) != project_id):
            return equipment_conflict(before)
        purchase_date = data.get("purchase_date")
        row = {"u_device_code": code, "bill_name": data["name"], "phid_pc": project_id,
               "u_spec": data.get("spec"),
               "u_yz": data.get("purchase_price"), "u_bz": data.get("remark"),
               "u_indata": f"{date.fromisoformat(str(purchase_date))} 00:00:00" if purchase_date else None}
        if data.get("unit"):
            row["u_msunit"] = self.unit_ids[data["unit"]]
            if not row["u_msunit"]:
                raise ValueError("缺少 i8 单位标识")
        if before:
            row["phid"] = before["phid"]
            if all(_field_matches(key, before.get(key), value) for key, value in row.items()):
                return checked_project(before, project)
        else:
            row.update(phid_org=self.ORG, u_use_org=self.ORG)
        self._save("sbzx", {"p_form_sbzx_m": self._form(row)})
        after = self.lookup_by_code(code)
        matches = after is not None and all(
            _field_matches(key, after.get(key), value) for key, value in row.items())
        return checked_project(after, project, matches)

    def create_transfer(self, code, from_project, to_project, *, transfer_date=None, remark=None):
        before = self.lookup_by_code(code)
        stop = transfer_precondition(before, code, from_project, to_project)
        if stop:
            return stop
        origin, destination = self.project_ids[from_project], self.project_ids[to_project]
        if not origin or not destination:
            raise ValueError("缺少 i8 调拨项目标识")
        if str(before["phid_pc"]) != origin:
            local = {"code": code, "from_project": from_project, "phid_pc": origin, "to_project": to_project}
            return SyncResult("conflict", "i8 调出项目主键不一致，请核对", before,
                              {"snapshot": before, "local": local, "from_project": from_project})
        header = {"phid_org": self.ORG, "phid_pc": origin}
        if transfer_date:
            header["bill_dt"] = f"{date.fromisoformat(str(transfer_date))} 00:00:00"
        detail = {"u_sbmc": before["phid"], "u_sbbm": code, "phid_pc": origin,
                  "u_inproj": destination, "detail_row_no": 1, "u_bz": remark}
        payload = {
            "p_form_ldzcdb_m": self._form(header),
            "p_form_ldzcdb_d": {"isChanged": True, "table": {"key": "phid", "newRow": [detail]}},
        }
        evidence = {"awaiting_readback": True, "code": code, "phid": before["phid"],
                    "to_project": to_project, "destination_id": destination}
        try:
            self._save("ldzcdb", payload)
        except SaveRejected:
            raise
        except Exception:
            return SyncResult("failed", "i8 调拨保存回执未知，重试时只核对所在项目", before, evidence)
        return self.verify_transfer(evidence)

    def verify_transfer(self, evidence):
        try:
            after = self.lookup_by_code(evidence["code"])
        except Exception:
            after = None
        if (after and after["phid"] == evidence["phid"]
                and str(after["phid_pc"]) == evidence["destination_id"]
                and after["current_project"] == evidence["to_project"]):
            return checked_project(after, evidence["to_project"])
        return SyncResult("failed", "i8 调拨尚未核对成功，重试时只核对所在项目", after, evidence)


def _field_matches(key, actual, wanted):
    if actual in (None, "") or wanted in (None, ""):
        return actual in (None, "") and wanted in (None, "")
    if key == "u_yz":
        return Decimal(str(actual)) == Decimal(str(wanted))
    return str(actual) == str(wanted)


def _sync_legacy(adapter, data, transfer):
    code, project = data["code"], data["current_project"]
    snapshot = adapter.snapshot(code)
    if transfer is None:
        if snapshot and snapshot["current_project"] != project:
            return equipment_conflict(snapshot)
        adapter.save_equipment(data)
    else:
        project = transfer.to_project
        stop = transfer_precondition(snapshot, code, transfer.from_project, project)
        if stop:
            return stop
        adapter.transfer(code, transfer.from_project, project)
    return checked_project(adapter.snapshot(code), project)


def synchronize(item, transfer=None, adapter: Adapter | I8CustomFormEquipmentAdapter | None = None):
    target = transfer if transfer is not None else item
    result = SyncResult("pending", UNAVAILABLE)
    if adapter is not None:
        try:
            data = record(item)
            data["purchase_date"] = item.purchase_date.isoformat() if item.purchase_date else None
            if isinstance(adapter, I8CustomFormEquipmentAdapter):
                if transfer is None:
                    result = adapter.create_equipment(data)
                elif (prior := json.loads(transfer.i8_conflict_json or "{}")).get("awaiting_readback"):
                    result = adapter.verify_transfer(prior)
                else:
                    result = adapter.create_transfer(item.code, transfer.from_project, transfer.to_project,
                                                     transfer_date=transfer.transfer_date, remark=transfer.remark)
            else:
                result = _sync_legacy(adapter, data, transfer)
            item.i8_snapshot_json = encoded(result.snapshot) if result.snapshot is not None else None
            if transfer is not None:
                transfer.i8_conflict_json = encoded(result.conflict) if result.conflict else None
        except Exception:
            result = SyncResult("failed", "i8 同步失败，已保存本地，可重新核对同步")
    target.i8_sync_status, target.i8_sync_message = result.status, result.message
    return receipt(target)


# Concurrent requests in the API worker must not replay the same equipment queue.
_sync_locks = tuple(Lock() for _ in range(64))


def receipt(row):
    return {"id": row.id, "status": row.i8_sync_status, "message": row.i8_sync_message}


def sync_queue(key, adapter):
    with _sync_locks[key % len(_sync_locks)]:
        return _drain(key, adapter)


def _drain(key, adapter):
    with session_scope() as db:
        item = require(db, EquipmentItem, key)
        pending = db.scalars(select(EquipmentTransfer).where(
            EquipmentTransfer.equipment_id == key, EquipmentTransfer.i8_sync_status.in_(ISSUES)
        ).order_by(EquipmentTransfer.transfer_date, EquipmentTransfer.id)).all()
        # The first outstanding transfer retains the project before the local move.
        # This also respects an explicitly supplied initial current project.
        revision = item.updated_at
        db.expunge_all()
    equipment, transfers = [], []
    if item.i8_sync_status in ISSUES:
        if pending:
            item.current_project = pending[0].from_project
        equipment.append(synchronize(item, adapter=adapter))
        with session_scope() as db:
            ledger_lock(db)
            saved = require(db, EquipmentItem, key)
            if saved.updated_at != revision:
                # A newer local edit owns the pending status.
                return {"equipment": [receipt(saved)], "transfers": [receipt(r) for r in pending]}
            saved.i8_snapshot_json = item.i8_snapshot_json
            saved.i8_sync_status, saved.i8_sync_message = item.i8_sync_status, item.i8_sync_message
        if item.i8_sync_status != "synced":
            return {"equipment": equipment, "transfers": [receipt(r) for r in pending]}
    for index, row in enumerate(pending):
        result = synchronize(item, row, adapter)
        with session_scope() as db:
            ledger_lock(db)
            saved = require(db, EquipmentTransfer, row.id)
            saved.i8_sync_status, saved.i8_sync_message = row.i8_sync_status, row.i8_sync_message
            saved.i8_conflict_json = row.i8_conflict_json
            require(db, EquipmentItem, key).i8_snapshot_json = item.i8_snapshot_json
        transfers.append(result)
        if row.i8_sync_status != "synced":
            transfers.extend(receipt(r) for r in pending[index + 1:])
            break
    return {"equipment": equipment, "transfers": transfers}
