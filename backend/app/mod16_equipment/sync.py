"""The adapter must condition a transfer write on the observed source project."""
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


def synchronize(item, transfer=None, adapter: Adapter | None = None):
    target = transfer if transfer is not None else item
    status, message = "pending", UNAVAILABLE
    if adapter is not None:
        try:
            snapshot = adapter.snapshot(item.code)
            item.i8_snapshot_json = encoded(snapshot) if snapshot is not None else None
            if transfer is None and snapshot is not None and snapshot.get("current_project") != item.current_project:
                status, message = "conflict", "相同编号的 i8 设备所在项目不同，请核对"
            elif transfer is not None and snapshot is None:
                message = "未查到 i8 设备，调拨待同步"
            elif transfer is not None and snapshot.get("current_project") != transfer.from_project:
                status, message = "conflict", "i8 当前项目与本地调出项目不一致，请核对"
                transfer.i8_conflict_json = encoded({"snapshot": snapshot, "from_project": transfer.from_project})
            else:
                if transfer is not None:
                    adapter.transfer(item.code, transfer.from_project, transfer.to_project)
                    transfer.i8_conflict_json = None
                else:
                    payload = record(item)
                    payload["purchase_date"] = item.purchase_date.isoformat() if item.purchase_date else None
                    adapter.save_equipment(payload)
                after = adapter.snapshot(item.code)
                expected = item.current_project if transfer is None else transfer.to_project
                if after is not None and after.get("current_project") == expected:
                    item.i8_snapshot_json = encoded(after)
                    status, message = "synced", "已同步并核对 i8 所在项目"
                else:
                    status, message = "failed", "i8 写入后的项目未核对成功，请核对后重试"
        except Exception:
            status, message = "failed", "i8 同步失败，已保存本地，可重新核对同步"
    target.i8_sync_status, target.i8_sync_message = status, message
    return {"id": target.id, "status": status, "message": message}

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
