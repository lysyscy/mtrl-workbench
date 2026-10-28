"""Mechanical workbench public API. Amounts are decimal yuan strings everywhere.

Saved details/source facts live here; effective six-column amounts use repository.save_mech.
No source-file writes, i8 writes, implicit database setup, or live session acquisition.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import uuid4

from sqlalchemy import select, update

from app.core.errors import MustReportError
from app.core.money import QUANT, to_money
from app.mod01_projects import service as project_service
from app.mod06_proc.domain import normalize_ym
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc import repository as repo
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord as Record
from app.mod06_proc.workbench_models import MechanicalWorkbenchPreview as Preview

DEFAULT_KEYWORDS = ['挖机', '挖掘机', '叉车', '铲车', '压路机', '发电机', '塔吊', '履带吊', '升降', '直臂式高空作业车', '直臂车']
CATEGORY_COLUMNS = {'zero': ('mech_2', 'mech_4'), 'monthly': ('mech_3', 'mech_5')}
CENT = QUANT


def money(value, *, nullable=True, nonnegative=True, precise=False):
    if value is None or value == '':
        if nullable:
            return None
        raise MustReportError('金额不能为空')
    try:
        if isinstance(value, bool):
            raise InvalidOperation
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) >= Decimal('10000000000000000'):
            raise InvalidOperation
        if nonnegative and number < 0:
            raise InvalidOperation
        if not precise and number != number.quantize(CENT):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MustReportError('请输入有效金额，最多两位小数') from exc
    return format(number, 'f') if precise else format(to_money(number), '.2f')


def total(values):
    values = list(values)
    if any(v is None for v in values):
        return None
    return format(to_money(sum((Decimal(v) for v in values), Decimal(0))), '.2f')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def key(kind, *parts):
    return kind + ':' + json.dumps(parts, ensure_ascii=False, separators=(',', ':'))


def read(s, record_key, *, records=None):
    row = s.get(Record, record_key) if records is None else records.get(record_key)
    if not row:
        return {}, 0
    # Only state computations pass a request-local map; writable callers keep copies.
    return (deepcopy(row.payload) if records is None else row.payload), row.revision


def write(s, record_key, payload, revision):
    """CAS covers another tab/device; no stale full-document overwrite."""
    revision = int(revision)
    if revision == 0:
        if s.get(Record, record_key):
            raise MustReportError('数据已被其他操作修改，请刷新后重试')
        s.add(Record(key=record_key, payload=deepcopy(payload), revision=1))
    else:
        changed = s.execute(update(Record).where(Record.key == record_key, Record.revision == revision)
                            .values(payload=deepcopy(payload), revision=revision + 1, updated_at=datetime.now())
                            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise MustReportError('数据已被其他操作修改，请刷新后重试')
        s.expire_all()
    s.flush()
    return revision + 1


def settings(s, *, records=None):
    data, revision = read(s, 'settings', records=records)
    return {'shown_projects': list(data.get('shown_projects', [])),
            'plate_keywords': list(data.get('plate_keywords', DEFAULT_KEYWORDS)), 'revision': revision}


def warehouse(s, value):
    value = str(value or '').strip()
    if not value or value not in project_service.warehouse_index(s):
        raise MustReportError('项目尚未可靠对应仓库档案，请先明确项目映射')
    return value


def monthly_args(s, data):
    wh = warehouse(s, data.get('warehouse'))
    ym = normalize_ym(data.get('ym'))
    category = data.get('category')
    if not ym or category not in CATEGORY_COLUMNS:
        raise MustReportError('请选择有效月份和零租／包月类别')
    return wh, ym, category


def effective(s, wh, ym, *, lock=False, cached_rows=None):
    if lock:
        row = repo.mech_row(s, wh, ym)
    elif cached_rows is None:
        row = s.scalar(select(ProcMechManual).where(
            ProcMechManual.warehouse_name == wh, ProcMechManual.ym == ym))
    else:
        row = cached_rows.get((wh, ym))
    return repo.mech_effective(row, wh, ym)


def check_effective(s, wh, ym, signature):
    current = effective(s, wh, ym, lock=True)
    if not signature or signature != current['signature']:
        raise MustReportError('有效月值已变化，请刷新并重新确认')
    return current


def normalize_rows(rows):
    if not isinstance(rows, list) or len(rows) > 10000:
        raise MustReportError('明细格式不正确或超过10000行')
    output, ids = [], set()
    for original in rows:
        if not isinstance(original, dict):
            raise MustReportError('明细必须逐行提供字段')
        row = deepcopy(original)
        row['id'] = str(row.get('id') or uuid4())
        if row['id'] in ids:
            raise MustReportError('明细标识重复，拆合行请明确对应关系')
        ids.add(row['id'])
        for field in ('amount', 'rate', 'sourceNet', 'original'):
            if field in row:
                row[field] = money(row[field], precise=True)
        for field in ('qty', 'plan', 'used'):
            if row.get(field) not in (None, ''):
                try:
                    value = Decimal(str(row[field]))
                except (InvalidOperation, ValueError) as exc:
                    # Original quantity text is evidence, never an implicit zero multiplier.
                    row[field] = str(row[field])
                else:
                    if not value.is_finite() or value < 0:
                        raise MustReportError('数量须为非负有限数字或原报文字')
                    row[field] = str(value)
        output.append(row)
    return output


def row_net(row):
    tax = str(row.get('tax') or '').strip()
    gross = row.get('amount')
    if gross is None or not tax:
        return None
    ordinary = '普票' in tax
    match = re.fullmatch(r'(?:专票\s*)?(\d+(?:\.\d+)?)\s*%(?:\s*专票?)?(?:[，,\s].*)?', tax)
    if not ordinary and (not match or Decimal(match[1]) > 100):
        return None
    if (tax == row.get('originalTax') and row.get('original') is not None
            and Decimal(gross) == Decimal(row['original']) and row.get('sourceNet') is not None):
        return row['sourceNet']
    if ordinary:
        return gross
    return format(to_money(Decimal(gross) / (1 + Decimal(match[1]) / 100)), '.2f')


def detail_view(s, payload, revision, *, keywords=None):
    data = deepcopy(payload)
    if keywords is None:
        keywords = settings(s)['plate_keywords']
    issues = []
    for row in data.get('rows', []):
        missing = []
        if not str(row.get('device') or '').strip():
            missing.append('设备名称')
        net = row_net(row)
        if row.get('amount') is None:
            missing.append('合价')
        if net is None:
            missing.append('票种／税率')
        plate_required = not (data['category'] == 'monthly' and data['ym'] < '2026-06') and not any(
            word in str(row.get('device') or '') for word in keywords)
        plate = str(row.get('plate') or '').strip()
        if plate_required and (not plate or re.fullmatch(r'无|无牌|场内|炮捶|加班.*|有加班', plate)):
            missing.append('车牌')
        if missing:
            issues.append({'id': row['id'], 'fields': missing})
        row['net'] = net
        row['plateRequired'] = plate_required
    amount_rows = [row for row in data.get('rows', []) if row.get('amount') is not None]
    data.update(revision=revision, totals={'gross': total(row['amount'] for row in amount_rows) if amount_rows else None,
                                         'net': total(row_net(row) for row in amount_rows) if amount_rows else None}, issues=issues)
    return data


def amount_inputs(rows, *, net=False):
    """Only monetary inputs can replace an explicit process-page manual override."""
    def canonical(value):
        return None if value is None else format(Decimal(str(value)).normalize(), 'f')
    return sorted([[row['id'], canonical(row['amount']), *([
        str(row.get('tax') or '').strip(), canonical(row_net(row))] if net else [])]
        for row in rows if row.get('amount') is not None])


def store_details(s, wh, ym, cat, old, revision, rows, operator='', extra=None):
    payload = {**old, 'warehouse': wh, 'ym': ym, 'category': cat, 'rows': rows, **(extra or {})}
    for field in ('confirmed_signature', 'confirmation_request', 'confirmation_result', 'previous_effective'):
        payload.pop(field, None)
    new_revision = write(s, key('details', wh, ym, cat), payload, revision)
    view = detail_view(s, payload, new_revision)
    gross, net = CATEGORY_COLUMNS[cat]
    changed = [column for column in (gross, net)
               if amount_inputs(old.get('rows', []), net=column == net) != amount_inputs(rows, net=column == net)]
    if changed:
        current = effective(s, wh, ym)
        basis = {'category': cat, 'detail_revision': new_revision, 'rows': deepcopy(rows),
                 'source': deepcopy(payload.get('source')), 'operator': operator,
                 'at': datetime.now().isoformat(), 'previous_effective': current['values']}
        values = {column: view['totals']['net' if column == net else 'gross'] for column in changed}
        repo.save_mech(s, ym=ym, warehouse=wh, values=values,
                       detail_sources={column: {**basis, 'amount': value} for column, value in values.items()})
        if not amount_inputs(rows):
            repo.source_manual(s, warehouse=wh, ym=ym, columns=changed, operator=operator)
        mark_adoption(s, wh, ym, changed)
    return view


def save_details(s, data, operator=''):
    wh, ym, cat = monthly_args(s, data)
    repo.lock_mech_month(s, wh, ym)
    record_key = key('details', wh, ym, cat)
    old, revision = read(s, record_key)
    return store_details(s, wh, ym, cat, old, data.get('revision', -1),
                         normalize_rows(data.get('rows')), operator)


def detail_signatures(s):
    """Only nonempty saved details trigger the process-page decision, across categories."""
    grouped = {}
    for record in s.scalars(select(Record).where(Record.key.like('details:%')).execution_options(populate_existing=True)):
        payload = record.payload
        if payload.get('rows'):
            grouped.setdefault((payload['warehouse'], payload['ym']), []).append([record.key, record.revision])
    result = {}
    for (wh, ym), revisions in grouped.items():
        result.setdefault(wh, {})[ym] = digest(sorted(revisions))
    return result


def save_process_mech(s, *, warehouse, ym, values, confirmed=False, effective_signature='',
                      detail_signature='', operator=''):
    """One transaction checks the decision, changes source and saves only edited cells."""
    current = effective(s, warehouse, ym, lock=True)
    changed = {column: value for column, value in values.items()
               if current['values'][column] is None or Decimal(current['values'][column]) != value}
    if not changed:
        return
    details = detail_signatures(s).get(warehouse, {}).get(ym, '')
    if details or any(current['sources'][column]['mode'] == 'detail' for column in changed):
        if confirmed is not True:
            raise MustReportError('同项目同月已有机械明细，请确认后保存手填金额；原明细保留。')
        check_effective(s, warehouse, ym, effective_signature)
        if detail_signature != details:
            raise MustReportError('机械明细已变化，请重读并重新确认金额。')
        repo.source_manual(s, warehouse=warehouse, ym=ym, columns=list(changed), operator=operator)
    repo.save_mech(s, warehouse=warehouse, ym=ym, values=changed, project_id=None)


def source_manual(s, data, operator=''):
    wh = warehouse(s, data.get('warehouse'))
    ym = normalize_ym(data.get('ym'))
    columns = data.get('columns')
    if (not ym or not isinstance(columns, list) or not columns or
            any(not isinstance(column, str) or column not in {f'mech_{i}' for i in range(6)} for column in columns)):
        raise MustReportError('请选择有效月份和金额格')
    if data.get('confirmed') is not True:
        raise MustReportError('请明确确认切换为手填')
    check_effective(s, wh, ym, data.get('effective_signature'))
    repo.source_manual(s, warehouse=wh, ym=ym, columns=list(dict.fromkeys(columns)), operator=operator)
    return effective(s, wh, ym)


def rebase_empty_month(s, wh, ym, row, history):
    """Move only this cleared month's existing delta into the active reference bases."""
    if not history:
        return history
    history_key = key('history', wh)
    adopted, _ = read(s, key('adoption', wh, ym))
    records = {history_key: Record(key=history_key, payload=history, revision=0),
               key('adoption', wh, ym): Record(payload=adopted, revision=0)}
    present, absent = {wh: [row]}, {wh: []}
    rebased = deepcopy(history)
    if history.get('report_total') is not None:
        contribution = (Decimal(report_total(s, wh, records=records, manual_rows=present)) -
                        Decimal(report_total(s, wh, records=records, manual_rows=absent)))
        rebased['report_total'] = format(Decimal(str(history['report_total'])) + contribution, 'f')

    def adjust(base, period):
        with_month = cumulative(s, wh, period, records=records, manual_rows=present)
        without_month = cumulative(s, wh, period, records=records, manual_rows=absent)
        return {category: (format(Decimal(str(amount)) + Decimal(with_month[category]) -
                                  Decimal(without_month[category]), 'f')
                           if amount is not None and with_month.get(category) is not None else amount)
                for category, amount in base.items()}

    for period, base in history.get('cumulative_at', {}).items():
        rebased['cumulative_at'][period] = adjust(base, period)
    # Later months use category_totals and reference_months, rather than a dated reference_at.
    fallback = {**history, 'cumulative_at': {}, 'reference_at': {}}
    records[history_key].payload = fallback
    if history.get('category_totals'):
        rebased['category_totals'] = adjust(history['category_totals'], max(ym, history.get('base_month') or ym))
    rebased.setdefault('reference_months', {})[ym] = dict.fromkeys(repo.MECH_KEYS, '0.00')
    for period, references in rebased.get('reference_at', {}).items():
        if period >= ym:
            references[ym] = dict.fromkeys(repo.MECH_KEYS, '0.00')
    rebased.get('effective_base', {}).pop(ym, None)
    return rebased


def empty_month_remove(s, data, operator=''):
    from sqlalchemy import func
    from app.mod06_proc.models import (BATCH_ACTIVE, ProcHistoryBatch, ProcHistorySnapshot,
                                       ProcMechImportChange)

    wh = warehouse(s, data.get('warehouse'))
    ym = normalize_ym(data.get('ym'))
    if not ym:
        raise MustReportError('请选择有效月份')
    if data.get('confirmed') is not True:
        raise MustReportError('请明确确认删除空月份')
    current = check_effective(s, wh, ym, data.get('effective_signature'))
    row = repo.mech_row(s, wh, ym)
    if row is None:
        raise MustReportError('该月没有可删除的机械记录')
    if any(Decimal(value or '0') != 0 for value in current['values'].values()):
        raise MustReportError('该月机械费尚有金额，不能删除')
    if any(source.get('mode') == 'detail' for source in current['sources'].values()):
        raise MustReportError('该月仍有明细确认金额，不能删除')
    details = list(s.scalars(select(Record).where(Record.key.in_(
        [key('details', wh, ym, category) for category in CATEGORY_COLUMNS])).with_for_update()))
    if any(record.payload.get('rows') for record in details):
        raise MustReportError('该月仍有设备明细，不能删除')
    if any(item.get('warehouse') == wh and item.get('ym') == ym for item in repo.load_inv_rows(s)):
        raise MustReportError('该月仍有库存单据，不能删除')
    batches = list(s.scalars(select(ProcHistoryBatch).where(
        ProcHistoryBatch.warehouse_name == wh, ProcHistoryBatch.status == BATCH_ACTIVE).with_for_update()))
    snapshots = list(s.scalars(select(ProcHistorySnapshot).where(
        ProcHistorySnapshot.warehouse_name == wh, ProcHistorySnapshot.ym == ym,
        ProcHistorySnapshot.batch_no.in_([batch.batch_no for batch in batches])).with_for_update()))
    material_columns = [f'{direction}_{i}' for direction in ('in', 'out') for i in range(5)]
    if any(Decimal(str(getattr(snapshot, column) or 0)) != 0
           for snapshot in snapshots for column in material_columns):
        raise MustReportError('该月仍有材料金额，不能删除')
    history_key = key('history', wh)
    history_record = s.scalar(select(Record).where(Record.key == history_key).with_for_update()
                              .execution_options(populate_existing=True))
    history = deepcopy(history_record.payload) if history_record else {}
    revision = history_record.revision if history_record else 0
    rebased = rebase_empty_month(s, wh, ym, row, history)
    changes = list(s.scalars(select(ProcMechImportChange).where(
        ProcMechImportChange.warehouse_name == wh, ProcMechImportChange.ym == ym).with_for_update()))
    affected = {snapshot.batch_no for snapshot in snapshots}
    batch_counts = {batch.batch_no: s.scalar(select(func.count()).select_from(ProcHistorySnapshot).where(
        ProcHistorySnapshot.batch_no == batch.batch_no)) - sum(snapshot.batch_no == batch.batch_no for snapshot in snapshots)
        for batch in batches if batch.batch_no in affected}

    def saved_row(item):
        return json.loads(json.dumps({column.key: getattr(item, column.key)
                                      for column in item.__table__.columns}, default=str))

    audit_key = key('empty-month-removal', wh, ym, str(uuid4()))
    audit = {'warehouse': wh, 'ym': ym, 'operator': operator, 'at': datetime.now().isoformat(),
             'effective_before': current, 'mechanical_row': saved_row(row), 'history_before': history,
             'snapshots': [saved_row(snapshot) for snapshot in snapshots],
             'batches_before': [saved_row(batch) for batch in batches if batch.batch_no in affected],
             'import_changes': [saved_row(change) for change in changes]}
    with s.begin_nested():
        write(s, audit_key, audit, 0)
        if history:
            write(s, history_key, rebased, revision)
        for snapshot in snapshots:
            s.delete(snapshot)
        for batch in batches:
            if batch.batch_no in batch_counts:
                batch.row_count = batch_counts[batch.batch_no]
        s.delete(row)
        s.flush()
    return {'removed': True, 'warehouse': wh, 'ym': ym, 'audit_key': audit_key,
            'removed_snapshots': len(snapshots), 'report_total': report_total(s, wh)}


def internal_save(s, data):
    wh = warehouse(s, data.get('warehouse'))
    ym = normalize_ym(data.get('ym'))
    if not ym:
        raise MustReportError('月份格式不正确')
    check_effective(s, wh, ym, data.get('effective_signature'))
    values = data.get('values') or {}
    if not values or set(values) - {'mech_0', 'mech_1'}:
        raise MustReportError('此处仅确认两类内租金额')
    parsed = {k: Decimal(money(v, nullable=False)) for k, v in values.items()}
    repo.save_mech(s, ym=ym, warehouse=wh, values=parsed)
    mark_adoption(s, wh, ym, list(parsed))
    return effective(s, wh, ym)


def mark_adoption(s, wh, ym, columns):
    record_key = key('adoption', wh, ym)
    old, revision = read(s, record_key)
    write(s, record_key, {'columns': sorted(set(old.get('columns', [])) | set(columns))}, revision)


def merge_rows(baseline, incoming, current):
    """Stable ids only; uncertain insertion/deletion is a row-level decision."""
    b, n, c = ({r['id']: r for r in rows} for rows in (baseline, incoming, current))
    merged, conflicts = [], []
    for row_id in dict.fromkeys([*c, *n, *b]):
        before, new, present = b.get(row_id), n.get(row_id), c.get(row_id)
        if new == before:
            chosen = present
        elif present == before or new == present:
            chosen = new
        elif None in (before, new, present):
            conflict_id = row_id + ':__row__'
            conflicts.append({'id': conflict_id, 'row_id': row_id, 'field': '__row__',
                              'baseline': before, 'incoming': new, 'current': present})
            chosen = present
        else:
            chosen = dict(present)
            for field in set(before) | set(new) | set(present):
                bv, nv, cv = before.get(field), new.get(field), present.get(field)
                if nv == bv:
                    continue
                if cv == bv or cv == nv:
                    if field in new:
                        chosen[field] = nv
                    else:
                        chosen.pop(field, None)
                else:
                    conflicts.append({'id': row_id + ':' + field, 'row_id': row_id, 'field': field,
                                      'baseline': bv, 'incoming': nv, 'current': cv})
        if chosen is not None:
            merged.append(deepcopy(chosen))
    return merged, conflicts


def make_preview(s, kind, data, payload):
    request_id = str(data.get('request_id') or uuid4())
    preview_id = digest([kind, request_id])[:64]
    existing = s.get(Preview, preview_id)
    request_hash = digest(data)
    if existing:
        if existing.payload.get('request_hash') != request_hash:
            raise MustReportError('同一请求标识不能用于不同内容')
        return {'preview_id': preview_id, **deepcopy(existing.payload), 'result': existing.result}
    payload = {**payload, 'request_hash': request_hash}
    s.add(Preview(id=preview_id, kind=kind, payload=payload))
    s.flush()
    return {'preview_id': preview_id, **payload}


def get_preview(s, data, kind):
    preview = s.scalar(select(Preview).where(Preview.id == str(data.get('preview_id'))).with_for_update())
    if not preview or preview.kind != kind:
        raise MustReportError('找不到对应预览，请重新预览')
    return preview


def record_details(s, data, operator=''):
    """Trusted local skill entry: revision-checked source merge and one atomic write."""
    request_id = str(data.get('request_id') or '').strip()
    if not request_id or len(request_id) > 160:
        raise MustReportError('录入须提供本批请求标识')
    repo.lock_mech_month(s, 'recording', request_id)
    request_hash = digest({**data, 'batches': [{k: v for k, v in batch.items() if k != 'revision'}
                                            for batch in data.get('batches', [])]})
    receipt_key = key('recording', request_id)
    receipt, _ = read(s, receipt_key)
    if receipt:
        if receipt['request_hash'] != request_hash:
            raise MustReportError('同一请求标识不能用于不同内容')
        return deepcopy(receipt['result'])
    incoming = data.get('batches') or []
    if not isinstance(incoming, list) or not incoming:
        raise MustReportError('没有可录入的明细')
    scopes = [monthly_args(s, item) for item in incoming]
    if len(set(scopes)) != len(scopes):
        raise MustReportError('同批项目／月份／类别重复')
    for wh, ym in sorted({(wh, ym) for wh, ym, _ in scopes}):
        repo.lock_mech_month(s, wh, ym)
    batches = []
    resolutions = data.get('resolutions') or {}
    # Resolve every scope before mutating any detail/effective record.
    for item, (wh, ym, cat) in zip(incoming, scopes):
        record_key = key('details', wh, ym, cat)
        old, revision = read(s, record_key)
        if revision != item.get('revision'):
            raise MustReportError('明细已变化，请重新读取并核对本批')
        rows_in = normalize_rows(item.get('rows'))
        if not rows_in or not item.get('source'):
            raise MustReportError('录入须有明细及原报来源，整类清空请在明细页办理')
        merged, conflicts = merge_rows(old.get('baseline_rows', []), rows_in, old.get('rows', []))
        rows = {row['id']: row for row in merged}
        for conflict in conflicts:
            choice = resolutions.get(record_key + '|' + conflict['id'], resolutions.get(conflict['id']))
            if choice not in ('incoming', 'current'):
                raise MustReportError(f"原报与现有明细有修订冲突，请逐项选择：{wh} {ym} {cat} {conflict['id']}")
            chosen = conflict[choice]
            if conflict['field'] == '__row__':
                if chosen is None:
                    rows.pop(conflict['row_id'], None)
                else:
                    rows[conflict['row_id']] = deepcopy(chosen)
            else:
                rows[conflict['row_id']][conflict['field']] = chosen
        batches.append((item, wh, ym, cat, old, revision, list(rows.values()), rows_in))
    results = []
    for item, wh, ym, cat, old, revision, rows, rows_in in batches:
        version = {'source': deepcopy(item['source']), 'rows': rows_in, 'request_id': request_id}
        saved = store_details(s, wh, ym, cat, old, revision, rows, operator, {
            'baseline_rows': rows_in, 'source': deepcopy(item['source']),
            'versions': [*old.get('versions', []), version]})
        results.append({k: saved[k] for k in ('warehouse', 'ym', 'category', 'revision', 'totals')})
    result = {'ok': True, 'request_id': request_id, 'batches': results}
    write(s, receipt_key, {'request_hash': request_hash, 'result': result}, 0)
    return result


def normalize_sources(sources):
    result = {}
    for kind in ('usage', 'project', 'team'):
        rows, ids = [], set()
        for source in sources.get(kind, []):
            row = deepcopy(source)
            document_id = str(row.get('id') or row.get('bill') or '')
            if not document_id or document_id in ids:
                raise MustReportError('i8来源缺少唯一单据标识或单据重复')
            ids.add(document_id)
            row['id'] = document_id
            row['amount'] = money(row.get('amount'))
            row['approval'] = money(row.get('approval'))
            rows.append(row)
        result[kind] = sorted(rows, key=lambda r: r['id'])
    return result


def source_totals(sources):
    result = {}
    for kind in ('usage', 'project', 'team'):
        rows = sources.get(kind, [])
        field = 'approval' if kind == 'team' else 'amount'
        # A known unapproved empty document remains a fact, outside approved totals.
        applicable = [r for r in rows if not (r.get(field) is None and r.get('status') == 0 and r.get('workflow') == 0)]
        result[kind] = total(r.get(field) for r in applicable)
    return result


def observe_discovery(s, scope, fact, payload, *, actionable=True):
    observed_key = key('discovery-observation', scope)
    observed, observed_revision = read(s, observed_key)
    new_fact = observed.get('fact') != fact
    if new_fact:
        write(s, observed_key, {'fact': fact}, observed_revision)
    discovery_key = key('discovery', payload['warehouse'], fact)
    previous, revision = read(s, discovery_key)
    if actionable and (not previous or (new_fact and previous.get('status') == 'resolved')):
        history = list(previous.get('resolution_history', []))
        if previous.get('status') == 'resolved':
            history.append({'note': previous.get('note', ''), 'resolved_at': previous.get('resolved_at')})
        write(s, discovery_key, {**payload, 'resolution_history': history}, revision)


def i8_preview(s, data):
    projects, seen = [], set()
    for item in data.get('projects') or []:
        wh = warehouse(s, item.get('warehouse'))
        if wh in seen:
            raise MustReportError('同批i8项目重复')
        seen.add(wh)
        sources = normalize_sources(item.get('sources') or {})
        old, revision = read(s, key('i8', wh))
        complete = all(item.get('complete', {}).get(kind) is True and kind in item.get('sources', {})
                       for kind in ('usage', 'project', 'team'))
        totals = source_totals(sources)
        missing = []
        if old:
            for kind in ('usage', 'project', 'team'):
                old_ids = {r['id'] for r in old.get('sources', {}).get(kind, [])}
                new_ids = {r['id'] for r in sources[kind]}
                missing.extend(kind + ':' + i for i in sorted(old_ids - new_ids))
        reduction = bool(missing) or any(totals[k] is not None and old.get('totals', {}).get(k) is not None
                                         and Decimal(totals[k]) < Decimal(old['totals'][k]) for k in totals)
        changed = digest(sources) != digest(old.get('sources', {}))
        fact = digest([wh, sources])
        observe_discovery(s, 'warehouse:' + wh, fact, {'id': fact, 'warehouse': wh,
                          'kind': 'changed' if old else 'first', 'status': 'pending',
                          'fetched_at': item.get('fetched_at'), 'totals': totals}, actionable=changed)
        projects.append({'warehouse': wh, 'sources': sources, 'totals': totals, 'complete': complete,
                         'projectId': str(item.get('projectId') or ''),
                         'unknown_documents': [{'kind': kind, **r} for kind, rows in sources.items() for r in rows
                                               if r.get('approval' if kind == 'team' else 'amount') is None],
                         'fetched_at': item.get('fetched_at'), 'scope': item.get('scope', data.get('scope')),
                         'revision': revision, 'before': old, 'missing': missing, 'reduction': reduction,
                         'changed': changed, 'discovery_id': fact})
    unmapped_projects = []
    for original in data.get('unmapped_projects') or []:
        project_id = str(original.get('projectId') or original.get('project_id') or '')
        if not project_id:
            raise MustReportError('未匹配项目须保留i8项目原键')
        sources = normalize_sources(original.get('sources') or {})
        fact = digest(['unmapped', project_id, sources])
        item = {'id': fact, 'warehouse': '', 'projectId': project_id,
                'projectName': str(original.get('projectName') or original.get('project_name') or ''),
                'kind': 'unmapped', 'status': 'pending', 'sources': sources,
                'totals': source_totals(sources), 'complete': deepcopy(original.get('complete')),
                'fetched_at': original.get('fetched_at'),
                'candidate_warehouses': deepcopy(original.get('candidate_warehouses', []))}
        observe_discovery(s, 'project:' + project_id, fact, item)
        unmapped_projects.append(item)
    # An omitted old project is a discovery, never a zero-valued replacement.
    if data.get('full_scope'):
        for row in s.scalars(select(Record).where(Record.key.like('i8:%'))):
            wh = row.payload['warehouse']
            if wh not in seen:
                fact = digest([wh, 'missing-project'])
                observe_discovery(s, 'warehouse:' + wh, fact,
                                  {'id': fact, 'warehouse': wh, 'kind': 'missing-project', 'status': 'pending'})
    return make_preview(s, 'i8', data, {'projects': projects, 'unmapped_projects': unmapped_projects})


def i8_confirm(s, data):
    preview = get_preview(s, data, 'i8')
    selected = set(data.get('warehouses') or [])
    if not selected or selected - {p['warehouse'] for p in preview.payload['projects']}:
        raise MustReportError('请选择预览中的项目')
    adopted = set((preview.result or {}).get('warehouses', []))
    if selected <= adopted:
        return deepcopy(preview.result)
    projects = [p for p in preview.payload['projects'] if p['warehouse'] in selected - adopted]
    for item in projects:
        if not item['complete']:
            raise MustReportError('三类来源未完整取得，项目旧值保持不变')
        if read(s, key('i8', item['warehouse']))[1] != item['revision']:
            raise MustReportError('预览后i8已更新，请重新预览')
        if item['reduction'] and not (data.get('allow_reduction') and str(data.get('reduction_reason') or '').strip()):
            raise MustReportError('单据减少或金额降低，须核实查询范围并填写采用依据')
    for item in projects:
        payload = {k: deepcopy(v) for k, v in item.items() if k not in ('before', 'revision')}
        payload['reduction_reason'] = data.get('reduction_reason', '')
        write(s, key('i8', item['warehouse']), payload, item['revision'])
    resolve_adopted_discoveries(s)
    preview.result = {'ok': True, 'warehouses': sorted(selected | adopted)}
    s.flush()
    return deepcopy(preview.result)


def resolve_adopted_discoveries(s):
    """Retire an old ownership warning only after every exact source fact has one adopted owner."""
    adopted = {}
    for record in s.scalars(select(Record).where(Record.key.like('i8:%'))):
        for kind, rows in record.payload.get('sources', {}).items():
            for row in rows:
                adopted.setdefault(digest([kind, row]), set()).add(record.payload['warehouse'])
    for record in s.scalars(select(Record).where(Record.key.like('discovery:%'))):
        item = record.payload
        if item.get('kind') != 'unmapped' or item.get('status') != 'pending':
            continue
        facts = [digest([kind, row]) for kind, rows in item.get('sources', {}).items() for row in rows]
        if facts and all(len(adopted.get(fact, set())) == 1 for fact in facts):
            owners = sorted({next(iter(adopted[fact])) for fact in facts})
            write(s, record.key, {**item, 'status': 'resolved', 'mapped_warehouses': owners,
                  'note': '原单据已逐单确定归属并采用；' + '、'.join(owners),
                  'resolved_at': datetime.now().isoformat()}, record.revision)


def report_total(s, wh, *, records=None, manual_rows=None):
    history, _ = read(s, key('history', wh), records=records)
    rows = (list(s.scalars(select(ProcMechManual).where(ProcMechManual.warehouse_name == wh)))
            if manual_rows is None else manual_rows.get(wh, []))
    if not history:
        return None
    base = money(history.get('report_total'), precise=True)
    if base is None:
        return None
    refs = history.get('reference_months', {})
    delta = Decimal(0)
    for row in rows:
        adopted, _ = read(s, key('adoption', wh, row.ym), records=records)
        for column in ('mech_1', 'mech_2', 'mech_3'):
            reference = refs.get(row.ym, {}).get(column)
            current = money(getattr(row, column))
            initial = history.get('effective_base', {}).get(row.ym, {}).get(column)
            if row.ym <= str(history.get('base_month') or '') and current == initial and column not in adopted.get('columns', []):
                continue
            if reference is None:
                if row.ym <= str(history.get('base_month') or ''):
                    continue
                reference = '0.00'
            delta += Decimal(current or '0') - Decimal(str(reference))
    return format(to_money(Decimal(base) + delta), '.2f')


def cumulative(s, wh, ym, *, records=None, manual_rows=None):
    history, _ = read(s, key('history', wh), records=records)
    reference = history.get('cumulative_at', {}).get(ym, {})
    if not reference and ym >= str(history.get('base_month') or '~'):
        reference = history.get('category_totals', {})
    refs = history.get('reference_at', {}).get(ym, history.get('reference_months', {}))
    mapping = {'zero': 'mech_2', 'monthly': 'mech_3', 'internal': 'mech_1', 'company': 'mech_0'}
    rows = (list(s.scalars(select(ProcMechManual).where(ProcMechManual.warehouse_name == wh, ProcMechManual.ym <= ym)))
            if manual_rows is None else [r for r in manual_rows.get(wh, []) if r.ym <= ym])
    result = {}
    for category in ('zero', 'monthly', 'weekly', 'internal', 'company'):
        base = reference.get(category)
        if base is None:
            result[category] = None
            continue
        amount = Decimal(str(base))
        column = mapping.get(category)
        if column:
            for row in rows:
                old = refs.get(row.ym, {}).get(column)
                if old is None and column == 'mech_0':
                    old = history.get('original_months', {}).get(row.ym, {}).get(column)
                adopted, _ = read(s, key('adoption', wh, row.ym), records=records)
                initial = history.get('effective_base', {}).get(row.ym, {}).get(column)
                if money(getattr(row, column)) == initial and column not in adopted.get('columns', []):
                    continue
                if old is not None:
                    amount += Decimal(str(getattr(row, column) or 0)) - Decimal(str(old))
                elif row.ym > str(history.get('base_month') or '~'):
                    amount += Decimal(str(getattr(row, column) or 0))
        result[category] = format(to_money(amount), '.2f')
    return result


def reconciliations(s, warehouses, *, records=None, manual_rows=None):
    result, bill_differences = [], []
    for wh in warehouses:
        history, _ = read(s, key('history', wh), records=records)
        snapshot, revision = read(s, key('i8', wh), records=records)
        totals = snapshot.get('totals', {})
        usage, project, team = (totals.get(k) for k in ('usage', 'project', 'team'))
        i6 = money(history.get('i6'), precise=True)
        report_left = report_total(s, wh, records=records, manual_rows=manual_rows)
        for relation, left, right in [('report', report_left, total([i6, usage])),
                                      ('internal', usage, total([project, team]))]:
            raw = money(Decimal(left) - Decimal(right), nonnegative=False) if left is not None and right is not None else None
            ignored, ignore_revision = read(s, key('ignore', wh, relation), records=records)
            ignored_amount = ignored.get('amount', '0.00')
            pending = ('0.00' if raw == '0.00' else money(Decimal(raw) - Decimal(ignored_amount), nonnegative=False)) if raw is not None else None
            result.append({'warehouse': wh, 'relation': relation, 'left': left, 'right': right,
                           'raw': raw, 'ignored': ignored_amount, 'pending': pending,
                           'revision': ignore_revision, 'i8_revision': revision,
                           'fetched_at': snapshot.get('fetched_at'), 'scope': deepcopy(snapshot.get('scope')),
                           'unknown_documents': deepcopy(snapshot.get('unknown_documents', [])),
                           'i6': i6 if relation == 'report' else None})
        for row in snapshot.get('sources', {}).get('team', []):
            a, b = row.get('amount'), row.get('approval')
            if a is not None and b is not None and a != b:
                fact = digest([wh, row['id'], a, b])
                ignored, ignore_revision = read(s, key('document-ignore', wh, fact), records=records)
                bill_differences.append({**deepcopy(row), 'warehouse': wh, 'document_id': row['id'],
                                         'fact': fact, 'settlement': a, 'approval': b,
                                         'difference': money(Decimal(b) - Decimal(a), nonnegative=False),
                                         'ignored': bool(ignored.get('ignored')), 'revision': ignore_revision})
    return result, bill_differences


def ignore(s, data):
    wh = warehouse(s, data.get('warehouse'))
    relation = data.get('relation')
    if relation not in ('report', 'internal'):
        raise MustReportError('核对关系不正确')
    row = next(r for r in reconciliations(s, [wh])[0] if r['relation'] == relation)
    if ('raw' in data and data['raw'] != row['raw']) or ('i8_revision' in data and data['i8_revision'] != row['i8_revision']):
        raise MustReportError('核对数据已变化，请刷新后重新确认忽略')
    if row['raw'] is None:
        raise MustReportError('来源不完整，不能忽略未知差额')
    amount = '0.00' if data.get('undo') else row['raw']
    revision = write(s, key('ignore', wh, relation), {'warehouse': wh, 'relation': relation,
                                                    'amount': amount}, data.get('revision', -1))
    return {'amount': amount, 'revision': revision}


def document_ignore(s, data):
    wh = warehouse(s, data.get('warehouse'))
    rows = reconciliations(s, [wh])[1]
    row = next((r for r in rows if r['document_id'] == str(data.get('document_id'))), None)
    if not row or (data.get('fact') and data['fact'] != row['fact']):
        raise MustReportError('单据两额事实已变化，请刷新后确认')
    revision = write(s, key('document-ignore', wh, row['fact']), {'ignored': not bool(data.get('undo'))}, data.get('revision', -1))
    return {'revision': revision, 'ignored': not bool(data.get('undo'))}


def matter_save(s, data):
    wh = warehouse(s, data.get('warehouse'))
    text = str(data.get('text') or '').strip()
    if not text:
        raise MustReportError('请写一句事项／处理备注')
    matter_id = str(data.get('id') or uuid4())
    record_key = key('matter', matter_id)
    old, _ = read(s, record_key)
    payload = {**old, 'id': matter_id, 'warehouse': wh, 'text': text,
               'completed': bool(data.get('completed')), 'metadata': {**old.get('metadata', {}), **(data.get('metadata') or {})}}
    revision = write(s, record_key, payload, data.get('revision', 0))
    return {**payload, 'revision': revision}


def discovery_resolve(s, data):
    matches = list(s.scalars(select(Record).where(Record.key.like('discovery:%'))))
    row = next((r for r in matches if r.payload.get('id') == data.get('id')), None)
    note = str(data.get('note') or '').strip()
    if not row or not note:
        raise MustReportError('请保留本轮无需补报的说明')
    payload = {**row.payload, 'status': 'resolved', 'note': note, 'resolved_at': datetime.now().isoformat()}
    revision = write(s, row.key, payload, data.get('revision', -1))
    return {**payload, 'revision': revision}


def state(s, ym=''):
    projects = [{'warehouse': p.warehouse_name, 'name': p.disp or p.warehouse_name, 'phid': p.phid}
                for p in sorted(project_service.all_projects(s), key=lambda p: (p.ord, p.id)) if p.warehouse_name]
    records = {record.key: record for record in s.scalars(select(Record))}
    manual = list(s.scalars(select(ProcMechManual)))
    cached_rows = {(r.warehouse_name, r.ym): r for r in manual}
    manual_rows = {}
    for row in manual:
        manual_rows.setdefault(row.warehouse_name, []).append(row)
    config = settings(s, records=records)
    details, histories, discoveries, matters, snapshots = [], [], [], [], []
    for record in records.values():
        if record.key.startswith('details:'):
            details.append(detail_view(s, record.payload, record.revision, keywords=config['plate_keywords']))
        elif record.key.startswith('history:'):
            histories.append({**deepcopy(record.payload), 'revision': record.revision})
        elif record.key.startswith('discovery:'):
            discoveries.append({**deepcopy(record.payload), 'revision': record.revision})
        elif record.key.startswith('matter:'):
            matters.append({**deepcopy(record.payload), 'revision': record.revision})
        elif record.key.startswith('i8:'):
            snapshots.append({**deepcopy(record.payload), 'revision': record.revision})
    amounts = [effective(s, r.warehouse_name, r.ym, cached_rows=cached_rows) for r in manual]
    if normalize_ym(ym):
        present = {(r['warehouse'], r['ym']) for r in amounts}
        amounts.extend(effective(s, p['warehouse'], ym, cached_rows=cached_rows) for p in projects if (p['warehouse'], ym) not in present)
    months = sorted({r['ym'] for r in [*details, *amounts]})
    if normalize_ym(ym) and ym not in months:
        months.append(ym)
        months.sort()
    from app.mod07_setl import service as meetings
    openings = meetings.opening_months(s, [p['warehouse'] for p in projects], months)
    checks, bills = reconciliations(s, [p['warehouse'] for p in projects], records=records, manual_rows=manual_rows)
    return {'ok': True, 'settings': config, 'projects': projects, 'months': months,
            'ym': ym, 'details': details, 'effective': amounts, 'histories': histories,
            'reconciliations': checks, 'billDifferences': bills, 'discoveries': discoveries,
            'matters': matters, 'i8': snapshots,
            'summary': [{'warehouse': p['warehouse'], 'ym': month,
                         'start_year': int(openings[p['warehouse']][month][:4]) if openings[p['warehouse']][month] else None,
                         'start_month': int(openings[p['warehouse']][month][5:]) if openings[p['warehouse']][month] else None,
                         'cumulative': cumulative(s, p['warehouse'], month, records=records, manual_rows=manual_rows)}
                        for p in projects for month in months]}


def snapshot(s, ym, warehouses):
    result = state(s, ym)
    selected = set(warehouses)
    result['projects'] = [r for r in result['projects'] if r['warehouse'] in selected]
    result['annual_effective'] = [r for r in result['effective'] if r['warehouse'] in selected]
    for name in ('details', 'effective'):
        result[name] = [r for r in result[name] if r['warehouse'] in selected and r['ym'] == ym]
    for name in ('histories', 'reconciliations', 'billDifferences', 'discoveries', 'matters', 'i8', 'summary'):
        result[name] = [r for r in result[name] if r['warehouse'] in selected]
    return result


def action(s, name, payload, operator=''):
    if name == 'settings':
        old = settings(s)
        shown = payload.get('shown_projects', old['shown_projects'])
        for wh in shown:
            warehouse(s, wh)
        keywords = payload.get('plate_keywords', old['plate_keywords'])
        if isinstance(keywords, str):
            keywords = keywords.splitlines()
        keywords = list(dict.fromkeys(str(v).strip() for v in keywords if str(v).strip()))
        value = {'shown_projects': list(dict.fromkeys(shown)), 'plate_keywords': keywords}
        revision = write(s, 'settings', value, payload.get('revision', -1))
        return {'ok': True, **value, 'revision': revision}
    handlers = {'details-save': save_details, 'source-manual': source_manual,
                'empty-month-remove': empty_month_remove,
                'internal-save': internal_save, 'i8-preview': i8_preview,
                'i8-confirm': i8_confirm, 'ignore': ignore, 'document-ignore': document_ignore,
                'matter-save': matter_save, 'discovery-resolve': discovery_resolve}
    if name not in handlers:
        raise MustReportError('不支持的机械费操作')
    args = {'operator': operator} if name in ('details-save', 'source-manual', 'empty-month-remove') else {}
    return {'ok': True, **handlers[name](s, payload, **args)}
