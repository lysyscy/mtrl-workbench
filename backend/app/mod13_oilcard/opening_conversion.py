"""Approved conversion of confirmed openings to dated entries within one source batch."""
from datetime import date
import json

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import sum_money
from . import continuation, ledger, transfers
from .models import OilContinuationSource, OilEntry, OilOpeningBalance
from .service import _get, _lock


def _assignment(row):
    return {'account_id': row.account_id, 'project_id': row.project_id, 'card_id': row.card_id}


def _remark(row, context):
    original_date = row.original_date_text or '未填'
    return '；'.join(part for part in (f'{context}，原表日期：{original_date}', row.remark) if part)


def _targets(session, source_id, key, targets, paired):
    suffixes = ('out_', 'in_') if paired else ('',)
    if len(targets) != len(suffixes) or any(target['kind'] != 'opening' for target in targets):
        raise DataConflictError(f'来源行 {key} 的期初范围已变化，请重读核对。')
    rows = []
    for target, suffix in zip(targets, suffixes, strict=True):
        row = _get(session, OilOpeningBalance, target['id'])
        if (not row.confirmed or row.source_key != continuation._request(source_id, key, suffix)
                or continuation._columns(row) != target['snapshot']):
            raise DataConflictError(f'来源行 {key} 的期初已更正，请先核对，不能覆盖。')
        rows.append(row)
    return rows


def _create_entries(session, source_id, item, decision, rows, booking_date):
    key, kind = item['key'], item['kind']
    request_id = continuation._request(source_id, key)
    date_text = booking_date.isoformat()
    amount = ledger._amount(item['raw']['amount'])
    closed = decision.get('closed_side')
    if kind == 'transfer' and not closed:
        outgoing, incoming = rows
        if outgoing.amount != -amount or incoming.amount != amount or amount <= 0 or outgoing.account_id == incoming.account_id:
            raise DataConflictError(f'来源行 {key} 的两侧转账金额或账户未能核对。')
        return transfers._create_pair(session, request_id, amount, date_text,
            {'out': _assignment(outgoing), 'in': _assignment(incoming)},
            {'out': _remark(outgoing, '历史转出'), 'in': _remark(incoming, '历史转入')})
    row, = rows
    if kind == 'recharge':
        if amount <= 0 or row.amount != amount:
            raise DataConflictError(f'来源行 {key} 的历史充值金额未能核对。')
        entry_kind, context = 'recharge', '历史充值'
    else:
        counterparty = decision.get('closed_counterparty', '').strip()
        if closed not in ('out', 'in') or not counterparty or amount <= 0 or row.amount != (amount if closed == 'out' else -amount):
            raise DataConflictError(f'来源行 {key} 的单边转账金额或对方未能核对。')
        direction, opposite = ('转入', '转出') if closed == 'out' else ('转出', '转入')
        entry_kind, context = 'adjustment', f'历史{direction}，原{opposite}方为已结项目「{counterparty}」'
    entry = OilEntry(**_assignment(row), request_id=request_id, kind=entry_kind, amount=row.amount,
        date_text=date_text, entry_date=booking_date, remark=_remark(row, context), updated_by=current_operator())
    session.add(entry)
    session.flush()
    return (entry,)


def convert_confirmed_openings(session, *, source_id, fingerprint, booking_date: date, expected_count, expected_amount):
    """Call only in an explicitly authorized transaction. A retry never books twice."""
    _lock(session)
    source = _get(session, OilContinuationSource, source_id)
    if source.fingerprint != fingerprint:
        raise DataConflictError('油卡来源指纹与已核版本不符。')
    items = {item['key']: item for item in json.loads(source.manifest_json)['rows']}
    confirmed = json.loads(source.confirmations_json)
    candidates = [(key, result) for key, result in confirmed.items()
        if 'opening_conversion' in result or any(target['kind'] == 'opening' for target in result['targets'])]
    archived = [target for _, result in candidates for target in
        result.get('opening_conversion', {}).get('previous_targets', result['targets'])]
    total = sum_money(target['snapshot']['amount'] for target in archived)
    if not archived or len(archived) != expected_count or total != ledger._amount(expected_amount):
        raise DataConflictError('已确认期初笔数或净额与拟转换清单不符。')
    receipt = {'count': len(archived), 'amount': str(total), 'booking_date': booking_date.isoformat()}
    conversions = [result['opening_conversion'] for _, result in candidates if 'opening_conversion' in result]
    if conversions:
        if len(conversions) != len(candidates) or any(item['booking_date'] != receipt['booking_date'] for item in conversions):
            raise DataConflictError('来源已使用不同口径转换，请核对现有记录。')
        return {**receipt, 'already_converted': True}

    with session.begin_nested():
        for key, result in candidates:
            item, decision = items[key], result['decision']
            if item['kind'] not in ('recharge', 'transfer'):
                raise DataConflictError(f'来源行 {key} 不属于充值或转账。')
            paired = item['kind'] == 'transfer' and not decision.get('closed_side')
            previous = result['targets']
            openings = _targets(session, source_id, key, previous, paired)
            entries = _create_entries(session, source_id, item, decision, openings, booking_date)
            result['opening_conversion'] = {'booking_date': receipt['booking_date'], 'converted_by': current_operator(),
                'previous_targets': [{**target, 'created_at': row.created_at.isoformat()}
                    for target, row in zip(previous, openings, strict=True)]}
            result['targets'] = [{'kind': 'entry', 'id': row.id, 'snapshot': continuation._columns(row)} for row in entries]
            for row in openings:
                session.delete(row)
        source.confirmations_json, source.updated_by = continuation._json(confirmed), current_operator()
        session.flush()
    return {**receipt, 'already_converted': False}
