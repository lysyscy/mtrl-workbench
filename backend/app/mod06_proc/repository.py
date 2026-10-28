"""MOD-06 有效机械值读写及既有历史快照、批次和截止月读取。"""

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
    ProcCutoff,
    ProcHistoryBatch,
    ProcHistorySnapshot,
    ProcMaterialManual,
    ProcMechManual,
)


def load_inv_rows(s: Session) -> list[dict]:
    """过程资料所需库存金额与差异定位字段，叠加调整并经 `MOD-08` 的包间出口读取。

    ⚠️ 原先是**跨包直查对方的表**（`import app.mod08_inv.repository`）⇒ 已改走 `mod08_inv.service`。
    """
    from app.mod08_inv import service as P8S

    return P8S.load_process_rows(s)


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


def lock_mech_month(s, warehouse, ym):
    """Serialize detail edits and amount decisions, including previously empty months."""
    if s.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        s.execute(text('SELECT pg_advisory_xact_lock(406, hashtext(:scope))'),
                  {'scope': json.dumps([warehouse, ym], ensure_ascii=False)})


def mech_row(s, warehouse, ym):
    lock_mech_month(s, warehouse, ym)
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
            if getattr(row, column) is None or to_money(getattr(row, column)) != to_money(value):
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
    """Manual writes respect sources; saved detail totals may be unknown or cleared."""
    from app.core.money import require_non_negative
    from app.mod06_proc.domain import normalize_ym

    ym = normalize_ym(ym)
    if not ym:
        raise ValueError("核算月认不出，请写 YYYY-MM")
    derived = detail_sources or {}
    parsed = {key: None if value is None and key in derived else require_non_negative(value, field=key) for key, value in values.items()
              if key in MECH_KEYS}
    found = mech_row(s, warehouse, ym)
    guarded = writable_mech_values(found, {k: v for k, v in parsed.items() if k not in derived})
    parsed = {k: v for k, v in parsed.items() if k in guarded or k in derived}
    if not parsed:
        return found
    if found is None:
        found = ProcMechManual(ym=ym, warehouse_name=warehouse, project_id=project_id)
        s.add(found)
    origins = deepcopy(found.source_batches or {})
    sources = origins.get('__detail_sources', {})
    if set(parsed) - set(derived):
        origins['__manual'] = 'manual'
    for column, value in parsed.items():
        setattr(found, column, value)
        origins.pop(column, None)
        if column in derived:
            previous = sources.get(column, {})
            history = previous.get('history', [])
            if previous:
                history = [*history, {k: v for k, v in previous.items() if k != 'history'}]
            sources[column] = {'mode': 'detail', 'basis': deepcopy(derived[column]), 'history': history}
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
    if active_only:
        for r in s.execute(select(ProcMaterialManual)).scalars():
            out.append({'ym': r.ym, 'warehouse': r.warehouse_name,
                        'material_manual': True, r.column_key: r.amount})
    return out


def save_material(s: Session, *, warehouse: str, ym: str, column: str, amount, expected):
    """Serialize material writes, preserving the imported snapshot and other cells."""
    s.connection().exec_driver_sql('SELECT pg_advisory_xact_lock(%s, %s)', (406, 1))
    inventory = load_inv_rows(s)
    if any(r.get('warehouse') == warehouse and r.get('ym') == ym for r in inventory):
        from app.core.errors import MustReportError
        raise MustReportError('该月已有库存数据，请先核对来源，未保存。')
    from app.mod06_proc.domain import build_matrix
    current = next((r[column] for r in build_matrix(inv_rows=inventory, history_rows=load_history(s),
                    warehouse=warehouse, adjusted=False) if r['ym'] == ym), None)
    if current != expected:
        from app.core.errors import MustReportError
        raise MustReportError('该金额已被其他操作修改，请重读核对后重新输入。')
    row = s.scalar(select(ProcMaterialManual).where(
        ProcMaterialManual.warehouse_name == warehouse, ProcMaterialManual.ym == ym,
        ProcMaterialManual.column_key == column).with_for_update())
    if row is None:
        from app.mod01_projects import service as projects
        match = projects.warehouse_index(s).get(warehouse)
        project_id = None
        if match is not None:
            project = projects.get_project(s, match.id, for_update=True)
            if project is None or project.warehouse_name != warehouse:
                from app.core.errors import MustReportError
                raise MustReportError('项目已变化，请重读核对后重新输入。')
            project_id = project.id
        row = ProcMaterialManual(warehouse_name=warehouse, project_id=project_id, ym=ym, column_key=column, amount=amount)
        s.add(row)
    else:
        row.amount = amount
    s.flush()
    return row


def load_batches(s: Session) -> list[ProcHistoryBatch]:
    return list(s.execute(select(ProcHistoryBatch)).scalars())


def load_cutoff(s: Session, *, warehouse: str) -> str:
    """该项目的**截止核算月**（未设定 ⇒ 空串 = 一律正式段）。"""
    for r in s.execute(select(ProcCutoff)).scalars():
        if r.warehouse_name == warehouse:
            return r.cutoff_ym or ""
    return ""


def load_cutoffs(s: Session) -> dict[str, str]:
    """按项目读取既有材料截止月，供过程资料查询与导出分段。"""
    out: dict[str, str] = {}
    for r in s.execute(select(ProcCutoff)).scalars():
        key = str(r.warehouse_name or "")
        if key:
            out.setdefault(key, str(r.cutoff_ym or ""))
    return out


__all__ = ["load_inv_rows", "load_mech", "save_mech",
           "load_history", "load_batches", "load_cutoff", "load_cutoffs", "MATERIAL_KEYS"]
