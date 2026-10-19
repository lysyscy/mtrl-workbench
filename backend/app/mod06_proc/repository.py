"""`MOD-06` 过程资料的读写。

⚠️ **本模块没有"材料"的行内写路径** —— 材料列要么是**库存单据的引用**（正式段，§5.2.3 单向流），
   要么是**导入的定稿快照**（历史段，§5.2.5 ①）；两者都**不由页面直接改**。
   ⇒ 历史段唯一的修改通道 = **再导一次**（同批回滚重导 / 另起新批次）。
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod06_proc.domain import CATEGORIES, MECH_COLUMNS, MECH_KEYS, MATERIAL_KEYS
from app.mod06_proc.models import (
    BATCH_ACTIVE,
    BATCH_ROLLED_BACK,
    BATCH_REPLACED,
    ProcCutoff,
    ProcHistoryBatch,
    ProcHistorySnapshot,
    ProcMechManual,
    ProcMechImportChange,
)


def load_inv_rows(s: Session) -> list[dict]:
    """库存单据明细（**已叠加调整单**的规范行）—— 走 `MOD-08` 的**包间出口**（`TAIL-218` 批 3）。

    ⚠️ 原先是**跨包直查对方的表**（`import app.mod08_inv.repository`）⇒ 已改走 `mod08_inv.service`。
    """
    from app.mod08_inv import service as P8S

    return P8S.load_rows(s)


def mech_sources(row):
    stored = (row.source_batches or {}).get('__detail_sources', {}) if row else {}
    return {column: deepcopy(stored.get(column, {'mode': 'manual'})) for column in MECH_KEYS}


def mech_effective(row, warehouse, ym):
    from app.core.money import to_money
    values = {column: format(to_money(getattr(row, column)), '.2f')
              if row and getattr(row, column) not in (None, '') else None for column in MECH_KEYS}
    sources = mech_sources(row)
    signature = hashlib.sha256(json.dumps([values, sources, str(row.updated_at) if row else None],
                                         ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    return {'warehouse': warehouse, 'ym': ym, 'values': values, 'sources': sources,
            'signature': signature, 'source': deepcopy(row.source_batches or {}) if row else {}}


def mech_row(s, warehouse, ym):
    rows = s.execute(select(ProcMechManual).where(
        ProcMechManual.warehouse_name == warehouse, ProcMechManual.ym == ym)
        .with_for_update().execution_options(populate_existing=True)).scalars()
    return next((row for row in rows if row.warehouse_name == warehouse and row.ym == ym), None)


def writable_mech_values(row, values):
    """A detail-confirmed cell keeps its amount and provenance on an identical import."""
    from app.core.errors import MustReportError
    from app.core.money import to_money
    sources, writable = mech_sources(row), {}
    for column, value in values.items():
        if sources[column]['mode'] == 'detail':
            if to_money(getattr(row, column)) != to_money(value):
                label = MECH_COLUMNS[int(column.removeprefix('mech_'))]
                raise MustReportError(f'{label}金额已由明细确认，请先明确切换为手填')
        else:
            writable[column] = value
    return writable


def load_mech(s: Session) -> list[dict]:
    """Effective six-column amounts and independently editable cell sources."""
    out = []
    for row in s.execute(select(ProcMechManual)).scalars():
        state = mech_effective(row, row.warehouse_name or '', row.ym or '')
        out.append({'ym': state['ym'], 'warehouse': state['warehouse'], 'project_id': row.project_id,
                    **{column: getattr(row, column) for column in MECH_KEYS},
                    'sources': state['sources'], 'effective_signature': state['signature']})
    return out


def save_mech(s: Session, *, ym: str, warehouse: str, values: dict, project_id: int | None = None,
              detail_sources: dict | None = None):
    """Write submitted cells; detail confirmation is the only source that can adopt details."""
    from app.core.money import require_non_negative
    from app.mod06_proc.domain import normalize_ym

    ym = normalize_ym(ym)
    if not ym:
        raise ValueError("核算月认不出，请写 YYYY-MM")
    parsed = {key: require_non_negative(value, field=key) for key, value in values.items()
              if key in MECH_KEYS}
    found = mech_row(s, warehouse, ym)
    confirmed = detail_sources or {}
    guarded = writable_mech_values(found, {k: v for k, v in parsed.items() if k not in confirmed})
    parsed = {k: v for k, v in parsed.items() if k in guarded or k in confirmed}
    if not parsed:
        return found
    if found is None:
        found = ProcMechManual(ym=ym, warehouse_name=warehouse, project_id=project_id)
        s.add(found)
    origins = deepcopy(found.source_batches or {})
    sources = origins.get('__detail_sources', {})
    if set(parsed) - set(confirmed):
        origins['__manual'] = 'manual'
    for column, value in parsed.items():
        setattr(found, column, value)
        origins.pop(column, None)
        if column in confirmed:
            previous = sources.get(column, {})
            history = previous.get('history', [])
            if previous:
                history = [*history, {k: v for k, v in previous.items() if k != 'history'}]
            sources[column] = {'mode': 'detail', 'basis': deepcopy(confirmed[column]), 'history': history}
    if sources:
        origins['__detail_sources'] = sources
    found.source_batches = origins
    found.updated_at = datetime.now()
    s.flush()
    return found


def source_manual(s, *, warehouse, ym, columns, operator):
    row = mech_row(s, warehouse, ym)
    if row is None:
        return
    origins = deepcopy(row.source_batches or {})
    sources = origins.get('__detail_sources', {})
    changed = False
    for column in columns:
        previous = sources.get(column, {})
        if previous.get('mode') != 'detail':
            continue
        sources[column] = {**previous, 'mode': 'manual', 'history': [*previous.get('history', []),
                           {'action': 'source-manual', 'operator': operator,
                            'at': datetime.now().isoformat(), 'previous_amount': str(getattr(row, column)),
                            'previous_basis': deepcopy(previous.get('basis'))}]}
        changed = True
    if changed:
        origins['__detail_sources'] = sources
        origins['__manual'] = 'manual'
        row.source_batches = origins
        row.updated_at = datetime.now()
        s.flush()


# ============================================================ 历史段（§5.2.5）


def _snapshot_keys() -> dict[str, tuple[str, int]]:
    """domain 的列 key（`in_主辅材`… / `mech_0`…）→ 快照表的列名（`in_0`… / `mech_0`…）。

    **只有这一处映射**。
    ⭐ 2026-09-26（`TAIL-107`）：**机械 6 列也进快照**（用户裁定"历史机械费都填在过程资料 excel 里"）。
    """
    out: dict[str, tuple[str, int]] = {}
    for i, cat in enumerate(CATEGORIES):
        out[f"in_{cat}"] = ("in", i)
        out[f"out_{cat}"] = ("out", i)
    for i in range(len(MECH_COLUMNS)):
        out[f"mech_{i}"] = ("mech", i)          # ⭐ 历史段的机械费落点（与手录表同名列名）
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
            if prefix != "mech" and r.material_present is False:
                continue
            row[key] = getattr(r, f"{prefix}_{idx}", 0)
        out.append(row)
    return out


def load_batches(s: Session) -> list[ProcHistoryBatch]:
    return list(s.execute(select(ProcHistoryBatch)).scalars())


def batch_exists(s: Session, *, batch_no: str) -> bool:
    """该批号是否已被占用（`proc_history_batch.batch_no` 是**唯一**的）。

    ⭐ 2026-09-26（`TAIL-108`）：给"**同一秒里两次落库**"兜底用 —— 默认批号 = `PROC-<yyyymmddHHMMSS>`
      （**秒**）⇒ 连点两次「④ 确认落库」（或两支判据在同一秒里各提交一次）会撞唯一约束，
      用户看到的是 `导入失败：IntegrityError … 重复键违反唯一约束`（**天书**）。
    """
    return any((b.batch_no or "") == str(batch_no) for b in s.execute(select(ProcHistoryBatch)).scalars())


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


def load_mechanical_cutoffs(s: Session) -> dict[str, str]:
    return {r.warehouse_name: str(r.mechanical_cutoff_ym or "")
            for r in s.execute(select(ProcCutoff)).scalars()}


def set_cutoff(s: Session, *, warehouse: str, cutoff_ym: str, mechanical_cutoff_ym: str | None = None) -> ProcCutoff:
    rows = list(s.execute(select(ProcCutoff)).scalars())
    found = next((x for x in rows if x.warehouse_name == warehouse), None)
    if found is None:
        found = ProcCutoff(warehouse_name=warehouse)
        s.add(found)
    found.cutoff_ym = str(cutoff_ym or "")
    if mechanical_cutoff_ym is not None:
        found.mechanical_cutoff_ym = mechanical_cutoff_ym
    found.updated_at = datetime.now()
    s.flush()
    return found


def import_snapshot(
    s: Session, *, warehouse: str, rows: list[dict], batch_no: str, operator: str,
    cutoff_ym: str | None = None, project_id: int | None = None,
    material_cutoff_ym: str | None = None, mechanical_cutoff_ym: str | None = None,
) -> ProcHistoryBatch | None:
    """两个截止只筛选本次输入；材料替换项目历史，机械逐月列覆盖统一有效值。"""
    from app.core.money import to_money
    from app.mod06_proc.importer import selected_cutoffs
    from app.mod06_proc.domain import normalize_ym
    from decimal import Decimal

    if not rows:
        raise ValueError("导入为空，原数据未改动")
    limits = selected_cutoffs(rows, cutoff_ym=cutoff_ym, material_cutoff_ym=material_cutoff_ym,
                             mechanical_cutoff_ym=mechanical_cutoff_ym)
    cutoff, mech_cutoff = limits["material_cutoff_ym"], limits["mechanical_cutoff_ym"]
    mapping = _snapshot_keys()
    planned = {}
    for row in rows:
        ym = normalize_ym(row.get("ym"))
        if not ym:
            raise ValueError("核算月认不出，原数据未改动")
        for key, (prefix, idx) in mapping.items():
            limit = mech_cutoff if prefix == "mech" else cutoff
            if (limit and ym > limit) or row.get(key) in (None, ""):
                continue
            value = to_money(row[key])
            monthly = planned.setdefault(ym, {})
            monthly[key] = monthly.get(key, Decimal("0.00")) + value
    if not planned:
        raise ValueError("截止月及以前没有可写入的数据，原数据未改动")
    effective_by_month = {row.ym: row for row in s.execute(
        select(ProcMechManual).where(ProcMechManual.warehouse_name == warehouse)
        .with_for_update().execution_options(populate_existing=True)).scalars()} if any(
            key in MECH_KEYS for keys in planned.values() for key in keys) else {}
    for ym, keys in list(planned.items()):
        mechanical = {key: value for key, value in keys.items() if key in MECH_KEYS}
        writable = writable_mech_values(effective_by_month.get(ym), mechanical)
        planned[ym] = {key: value for key, value in keys.items() if key not in mechanical or key in writable}
        if not planned[ym]:
            del planned[ym]
    if not planned:
        return None
    with s.begin_nested():
        for old in load_batches(s):
            if old.warehouse_name == warehouse and old.status == BATCH_ACTIVE:
                old.status = BATCH_REPLACED
        batch = ProcHistoryBatch(batch_no=batch_no, warehouse_name=warehouse, cutoff_ym=cutoff,
                                 mechanical_cutoff_ym=mech_cutoff, row_count=len(planned),
                                 operator=operator, status=BATCH_ACTIVE)
        s.add(batch)
        # Flush the unique batch key before changing any effective values.
        s.flush()
        for ym, keys in planned.items():
            values = {f"{mapping[key][0]}_{mapping[key][1]}": value for key, value in keys.items()}
            s.add(ProcHistorySnapshot(batch_no=batch_no, ym=ym, warehouse_name=warehouse,
                                      project_id=project_id,
                                      material_present=any(k in MATERIAL_KEYS for k in keys), **values))
            mechanical = {key: value for key, value in keys.items() if key.startswith("mech_")}
            if not mechanical:
                continue
            effective = effective_by_month.get(ym)
            if effective is None:
                effective = ProcMechManual(ym=ym, warehouse_name=warehouse, project_id=project_id,
                                           **{f"mech_{i}": 0 for i in range(len(MECH_COLUMNS))})
                s.add(effective)
                effective_by_month[ym] = effective
            origins = dict(effective.source_batches or {})
            if not effective.id:
                origins["__created_by"] = batch_no
            for key, value in mechanical.items():
                s.add(ProcMechImportChange(batch_no=batch_no, warehouse_name=warehouse, ym=ym,
                                          column_key=key, before_amount=getattr(effective, key) or 0,
                                          before_batch=origins.get(key, "")))
                setattr(effective, key, value)
                origins[key] = batch_no
            effective.source_batches = origins
            effective.updated_at = datetime.now()
        set_cutoff(s, warehouse=warehouse, cutoff_ym=cutoff, mechanical_cutoff_ym=mech_cutoff)
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
    if batch.status == BATCH_ROLLED_BACK:
        return 0
    changes = [change for change in s.execute(select(ProcMechImportChange).where(
        ProcMechImportChange.warehouse_name == batch.warehouse_name)).scalars()
        if change.warehouse_name == batch.warehouse_name]
    change_lookup = {(c.batch_no, c.ym, c.column_key): c for c in changes}
    batch_lookup = {b.batch_no: b for b in load_batches(s)}
    effective_lookup = {r.ym: r for r in s.execute(select(ProcMechManual).where(
        ProcMechManual.warehouse_name == batch.warehouse_name)
        .with_for_update().execution_options(populate_existing=True)).scalars()
        if r.warehouse_name == batch.warehouse_name}
    restorations = []
    for change in changes:
        if change.batch_no != batch_no:
            continue
        effective = effective_lookup.get(change.ym)
        if effective is None:
            continue
        origins = dict(effective.source_batches or {})
        if origins.get(change.column_key) != batch_no:
            continue
        # A predecessor that was separately rolled back must not be resurrected.
        previous = change
        visited = set()
        while previous.before_batch and previous.before_batch not in visited:
            visited.add(previous.before_batch)
            prior_batch = batch_lookup.get(previous.before_batch)
            if prior_batch is None or prior_batch.status != BATCH_ROLLED_BACK:
                break
            prior_change = change_lookup.get((previous.before_batch, change.ym, change.column_key))
            if prior_change is None:
                break
            previous = prior_change
        if writable_mech_values(effective, {change.column_key: previous.before_amount}):
            restorations.append((effective, change.column_key, previous))
    for effective, column, previous in restorations:
        origins = dict(effective.source_batches or {})
        setattr(effective, column, previous.before_amount)
        if previous.before_batch:
            origins[column] = previous.before_batch
        else:
            origins.pop(column, None)
        effective.source_batches = origins
        effective.updated_at = datetime.now()
    batch.status = BATCH_ROLLED_BACK
    for effective in effective_lookup.values():
        origins = dict(effective.source_batches or {})
        creator = origins.get("__created_by")
        creator_batch = batch_lookup.get(creator)
        no_remaining_import = not any(origins.get(f"mech_{i}") for i in range(len(MECH_COLUMNS)))
        if (creator and creator_batch is not None and creator_batch.status == BATCH_ROLLED_BACK
                and not origins.get("__manual") and no_remaining_import
                and not any(source['mode'] == 'detail' for source in mech_sources(effective).values())
                and all((getattr(effective, f"mech_{i}") or 0) == 0 for i in range(len(MECH_COLUMNS)))):
            s.delete(effective)
    s.flush()
    return count


__all__ = ["load_inv_rows", "load_mech", "save_mech",
           "load_history", "load_batches", "load_cutoff", "load_cutoffs", "set_cutoff",
           "import_snapshot", "rollback_batch", "MATERIAL_KEYS"]
