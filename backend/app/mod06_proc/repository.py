"""`MOD-06` 过程资料的读写。

⚠️ **本模块没有"材料"的行内写路径** —— 材料列要么是**库存单据的引用**（正式段，§5.2.3 单向流），
   要么是**导入的定稿快照**（历史段，§5.2.5 ①）；两者都**不由页面直接改**。
   ⇒ 历史段唯一的修改通道 = **再导一次**（同批回滚重导 / 另起新批次）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod06_proc.domain import CATEGORIES, MECH_COLUMNS, MATERIAL_KEYS
from app.mod06_proc.models import (
    BATCH_ACTIVE,
    BATCH_ROLLED_BACK,
    ProcCutoff,
    ProcHistoryBatch,
    ProcHistorySnapshot,
    ProcMechManual,
)


def load_inv_rows(s: Session) -> list[dict]:
    """库存单据明细（**已叠加调整单**的规范行）—— 复用 `MOD-08` 的同一条出口。"""
    from app.mod08_inv.repository import load_rows

    return load_rows(s)


def load_mech(s: Session) -> list[dict]:
    """机械 6 列手录值（旁路表）→ `{ym, warehouse, mech_0…mech_5}`。"""
    out: list[dict] = []
    for r in s.execute(select(ProcMechManual)).scalars():
        row = {"ym": r.ym or "", "warehouse": r.warehouse_name or "", "project_id": r.project_id}
        for i in range(len(MECH_COLUMNS)):
            row[f"mech_{i}"] = getattr(r, f"mech_{i}", 0)
        out.append(row)
    return out


def save_mech(s: Session, *, ym: str, warehouse: str, values: dict, project_id: int | None = None):
    """写机械 6 列手录值（**旁路载体**：不被重抓 / 重导覆盖，§5.2.5 ③）。"""
    from app.core.money import require_non_negative

    rows = list(s.execute(select(ProcMechManual)).scalars())
    found = next((x for x in rows if x.ym == ym and x.warehouse_name == warehouse), None)
    if found is None:
        found = ProcMechManual(ym=ym, warehouse_name=warehouse, project_id=project_id)
        s.add(found)
    for i in range(len(MECH_COLUMNS)):
        key = f"mech_{i}"
        if key in values:
            setattr(found, key, require_non_negative(values[key], field=key))
    s.flush()
    return found


# ============================================================ 历史段（§5.2.5）


def _snapshot_keys() -> dict[str, tuple[str, int]]:
    """domain 的列 key（`in_主辅材`…）→ 快照表的列名（`in_0`…）。**只有这一处映射**。"""
    out: dict[str, tuple[str, int]] = {}
    for i, cat in enumerate(CATEGORIES):
        out[f"in_{cat}"] = ("in", i)
        out[f"out_{cat}"] = ("out", i)
    return out


def load_history(s: Session, *, active_only: bool = True) -> list[dict]:
    """历史段快照（**只取未回滚批次**）→ domain 的列 key 形态。"""
    active = {
        b.batch_no for b in s.execute(select(ProcHistoryBatch)).scalars()
        if not active_only or b.status == BATCH_ACTIVE
    }
    mapping = _snapshot_keys()
    out: list[dict] = []
    for r in s.execute(select(ProcHistorySnapshot)).scalars():
        if r.batch_no not in active:
            continue
        row = {"ym": r.ym or "", "warehouse": r.warehouse_name or "", "batch_no": r.batch_no}
        for key, (prefix, idx) in mapping.items():
            row[key] = getattr(r, f"{prefix}_{idx}", 0)
        out.append(row)
    return out


def load_batches(s: Session) -> list[ProcHistoryBatch]:
    return list(s.execute(select(ProcHistoryBatch)).scalars())


def load_cutoff(s: Session, *, warehouse: str) -> str:
    """该项目的**截止核算月**（未设定 ⇒ 空串 = 一律正式段）。"""
    for r in s.execute(select(ProcCutoff)).scalars():
        if r.warehouse_name == warehouse:
            return r.cutoff_ym or ""
    return ""


def load_cutoffs(s: Session) -> dict[str, str]:
    """**每个项目**的截止核算月（`{仓库名: 截止月}`）—— 给界面"换项目时截止月跟着换"用。

    ⚠️ 为什么需要它（2026-09-26 实测出来的真缺陷）：界面上的「截止核算月」原先只在**进域那一刻**
      取一次（取的是**候选第一个项目**的，见 `service.build_import_data` 的 `current = projects[0]`），
      用户换成别的项目时那个框**不会跟着换** ⇒ 而落库会把它**当新项目的截止月写进去**
      （`importer.commit` → `import_snapshot(cutoff_ym=…)`，截止月本身是**按项目存**的）
      ⇒ **A 项目的分界写给了 B，且不报错**。
    ⇒ 界面改成"按当前选中项目查这张表"（壳侧只认 `cutoffs` 这个键，⛔ 不认识域号）。

    口径与 `load_cutoff` **同一个**（同表 · 同字段 · "命中第一条"语义）—— 它只是**批量形态**。
    """
    out: dict[str, str] = {}
    for r in s.execute(select(ProcCutoff)).scalars():
        key = str(r.warehouse_name or "")
        if key:
            out.setdefault(key, str(r.cutoff_ym or ""))
    return out


def set_cutoff(s: Session, *, warehouse: str, cutoff_ym: str) -> ProcCutoff:
    rows = list(s.execute(select(ProcCutoff)).scalars())
    found = next((x for x in rows if x.warehouse_name == warehouse), None)
    if found is None:
        found = ProcCutoff(warehouse_name=warehouse)
        s.add(found)
    found.cutoff_ym = str(cutoff_ym or "")
    found.updated_at = datetime.now()
    s.flush()
    return found


def import_snapshot(
    s: Session, *, warehouse: str, rows: list[dict], batch_no: str, operator: str,
    cutoff_ym: str | None = None, project_id: int | None = None,
) -> ProcHistoryBatch:
    """把一批定稿快照写进**历史段**（§5.2.5 ①）。

    - **一次设定、可改**：`cutoff_ym` 给定则用它；**不给 ⇒ 默认 = 导入数据里最大的核算月**（001-05）。
    - ⭐ **不动正式段**：本函数只写快照表与截止值，**不触碰库存单据 / 机械手录**（001-04）。
    """
    if not rows:
        raise ValueError("历史段导入为空 —— 不写库（避免把历史段清空）")
    cutoff = str(cutoff_ym or max(str(r.get("ym") or "") for r in rows) or "")
    mapping = _snapshot_keys()

    batch = ProcHistoryBatch(batch_no=batch_no, warehouse_name=warehouse, cutoff_ym=cutoff,
                             row_count=len(rows), operator=operator, status=BATCH_ACTIVE)
    s.add(batch)
    for r in rows:
        snap = ProcHistorySnapshot(batch_no=batch_no, ym=str(r.get("ym") or ""),
                                   warehouse_name=warehouse, project_id=project_id)
        for key, (prefix, idx) in mapping.items():
            if r.get(key) not in (None, ""):
                setattr(snap, f"{prefix}_{idx}", r[key])
        s.add(snap)
    set_cutoff(s, warehouse=warehouse, cutoff_ym=cutoff)
    s.flush()
    return batch


def rollback_batch(s: Session, *, batch_no: str) -> int:
    """**整批回滚**（置 `rolled_back`、**不物理删**；§5.2.5 ②）→ 返回该批条数。"""
    batches = [b for b in s.execute(select(ProcHistoryBatch)).scalars() if b.batch_no == batch_no]
    if not batches:
        raise ValueError(f"没有这个批次：{batch_no}")
    batch = batches[0]
    count = sum(1 for r in s.execute(select(ProcHistorySnapshot)).scalars()
                if r.batch_no == batch_no)
    batch.status = BATCH_ROLLED_BACK
    s.flush()
    return count


__all__ = ["load_inv_rows", "load_mech", "save_mech",
           "load_history", "load_batches", "load_cutoff", "load_cutoffs", "set_cutoff",
           "import_snapshot", "rollback_batch", "MATERIAL_KEYS"]
