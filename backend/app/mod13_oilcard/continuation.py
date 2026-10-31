"""首次接续专用服务：原始事实先留待核，只有明确确认才进入现行业务。

调用方负责原件只读与当次写入授权。本模块不下载、不按名称匹配项目，
不以当前卡片关系改写历史，也不从历史开票金额编造票号或日期。
"""
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.core.errors import DataConflictError, MustReportError
from app.core.identity import current_operator
from app.core.money import sum_money
from . import invoice_adjustments, invoices, ledger, reporting, transfers
from .invoice_pdf import recognize_pdf
from .models import (OilContinuationSource, OilEntry, OilOpeningBalance, OilInvoice,
    OilInvoiceOriginal, OilFeeCustom, OilBigCustom)
from .service import _check_version, _get, _lock

KINDS = {'archive', 'recharge', 'invoice', 'transfer', 'pdf', 'fee_legacy', 'big_legacy'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value):
    return sha256(_json(value).encode('utf-8')).hexdigest()


def stage_source(session, manifest):
    """同源重跑比较完整清单；源文件hash是证据版本，绝不用于生成新行身份。"""
    _lock(session)
    source_id = manifest.get('source_id', '')
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 128:
        raise MustReportError('请指定稳定的油卡来源身份。')
    rows = manifest.get('rows', [])
    if not rows or any(not row.get('key') or row.get('kind') not in KINDS or not isinstance(row.get('raw'), dict) for row in rows):
        raise MustReportError('接续清单需要明确来源行、类别和原始事实。')
    if len({row['key'] for row in rows}) != len(rows):
        raise MustReportError('接续来源行身份重复，请先核对清单。')
    for item in rows:
        if item['kind'] in ('recharge', 'invoice', 'transfer'):
            if not isinstance(item['raw'].get('amount'), str):
                raise MustReportError('源金额须以准确十进制文本保留。')
            ledger._amount(item['raw']['amount'])
    # Exclude only the assigned source ID: renaming an identical manifest cannot
    # enroll the same facts a second time under another identity.
    fingerprint = _digest({k: v for k, v in manifest.items() if k != 'source_id'})
    existing = session.get(OilContinuationSource, source_id, populate_existing=True)
    if existing:
        if existing.fingerprint != fingerprint:
            raise DataConflictError('同一油卡来源的内容或证据版本已变化；保留原清单，请逐项核对，不覆盖接续。')
        _verify_confirmations(session, json.loads(existing.confirmations_json))
        return source_report(session, source_id)
    duplicate = session.scalar(select(OilContinuationSource.source_id).where(OilContinuationSource.fingerprint == fingerprint))
    if duplicate:
        raise DataConflictError('这份油卡来源已使用另一稳定身份登记，请沿原来源续办。')
    session.add(OilContinuationSource(source_id=source_id, fingerprint=fingerprint,
        manifest_json=_json(manifest), confirmations_json='{}', created_by=current_operator(), updated_by=current_operator()))
    session.flush()
    return source_report(session, source_id)


def _snapshot(session, kind, key):
    if kind in ('fee_legacy', 'big_legacy'):
        if kind == 'fee_legacy':
            from app.mod09_fee import service as fees
            state, original = fees.oil_linkage_status(session, project_id=key), fees.review_oil_linkage(session, project_id=key)
            model = OilFeeCustom
        else:
            from app.mod07_setl import service as big
            state, original = big.big_oil_status(session, project_id=key), big.review_big_oil(session, project_id=key)
            model = OilBigCustom
        return {'state': state, 'original': original, 'customs': [_columns(row) for row in session.scalars(
            select(model).where(model.project_id == key).order_by(model.id))]}
    models = {'entry': OilEntry, 'opening': OilOpeningBalance, 'invoice': OilInvoice, 'pdf': OilInvoiceOriginal}
    row = session.get(models[kind], key, populate_existing=True)
    if row is None:
        return None
    result = _columns(row)
    if kind == 'invoice':
        result['allocations'] = [invoices.allocation_data(a) for a in invoices._allocations(session, key)]
    if kind == 'pdf':
        result['content_sha256'] = sha256(row.content).hexdigest()
    return result


def _columns(row):
    return {column.key: (str(value) if value is not None else None)
        for column in row.__table__.columns if column.key not in ('created_at', 'updated_at', 'content')
        for value in [getattr(row, column.key)]}


def _verify_confirmations(session, confirmations):
    for key, result in confirmations.items():
        for target in result['targets']:
            expected = target['snapshot']
            if target['kind'] == 'invoice':
                # Existing confirmation receipts predate the additive local-delete flag.
                expected = {'deleted': 'False', **expected}
            if _snapshot(session, target['kind'], target['id']) != expected:
                raise DataConflictError(f'来源行 {key} 的已接续目标已更正或不存在；保留人工结果，请核对，不能重跑覆盖。')


def source_report(session, source_id):
    row = _get(session, OilContinuationSource, source_id)
    manifest, confirmations = json.loads(row.manifest_json), json.loads(row.confirmations_json)
    rows = [{**item, 'status': 'confirmed' if item['key'] in confirmations else 'pending',
        'confirmation': confirmations.get(item['key'])} for item in manifest['rows']]
    # These are source amounts awaiting review, explicitly separate from ledger
    # and invoice queries. Missing invoice facts must never silently enter totals.
    pending_amounts = {kind: str(sum_money(item['raw']['amount'] for item in rows
        if item['kind'] == kind and item['status'] == 'pending')) for kind in ('recharge', 'invoice', 'transfer')}
    return {'source_id': source_id, 'fingerprint': row.fingerprint, 'rows': rows,
        'confirmed_count': len(confirmations), 'pending_count': len(rows) - len(confirmations),
        'pending_source_amounts': pending_amounts, 'pending_is_booked': False}


def _request(source_id, key, suffix=''):
    return str(uuid5(NAMESPACE_URL, 'oilcard-continuation:' + _json([source_id, key, suffix])))


def _assignment(session, decision, prefix=''):
    values = {key: decision[prefix + key] for key in ('project_id', 'account_id')}
    actual = ledger._attribution(session, values)
    if prefix + 'card_id' not in decision or decision[prefix + 'card_id'] != actual['card_id']:
        raise MustReportError('接续须明确确认账户及卡片快照（未知卡填空）；与当前档案不同请先核对历史账户，不自动猜配。')
    return values


def _apply(session, source_id, item, decision, contents):
    raw, kind, key = item['raw'], item['kind'], item['key']
    request = _request(source_id, key)
    note = decision.get('note', '').strip()
    if not note:
        raise MustReportError('每项接续必须保留明确的人工核对结论。')
    if kind == 'recharge':
        assignment = _assignment(session, decision)
        if raw.get('explicit_date'):
            if decision.get('entry_kind') not in ('recharge', 'adjustment'):
                raise MustReportError('请明确源记录接续为充值或调整，不能从原备注推定。')
            row = ledger.save_entry(session, {**assignment, 'request_id': request,
                'kind': decision['entry_kind'], 'amount': raw['amount'],
                'date_text': raw['explicit_date'], 'remark': raw.get('remark', '')})
            return [('entry', row.id)]
        row = ledger.stage_opening(session, **assignment, source_key=request, source_note=note,
            amount=raw['amount'], original_date_text=raw.get('original_date_text', ''),
            cutoff_ym=decision.get('cutoff_ym'), confirmed=True, remark=raw.get('remark', ''))
        return [('opening', row.id)]
    if kind == 'transfer':
        if not decision.get('treatment', '').strip():
            raise MustReportError('原转账的业务性质须明确核对，不能从备注猜配。')
        amount = ledger._amount(raw['amount'])
        if amount <= 0:
            raise MustReportError('接续转账须核对为正数，双边各自保留归属。')
        if decision['out_account_id'] == decision['in_account_id']:
            raise MustReportError('接续转账须明确两个不同用卡账户。')
        for side in ('out_', 'in_'):
            _assignment(session, decision, side)
        if raw.get('explicit_date'):
            rows = transfers.create(session, {**decision, 'request_id': request, 'amount': raw['amount'],
                'date_text': raw['explicit_date'], 'out_remark': raw.get('remark', ''), 'in_remark': raw.get('remark', '')})
            return [('entry', row.id) for row in rows]
        targets = []
        for side, signed in [('out_', -amount), ('in_', amount)]:
            row = ledger.stage_opening(session, **_assignment(session, decision, side),
                source_key=_request(source_id, key, side), source_note=note,
                amount=str(signed), original_date_text=raw.get('original_date_text', ''),
                cutoff_ym=decision.get('cutoff_ym'), confirmed=True, remark=raw.get('remark', ''))
            targets.append(('opening', row.id))
        return targets
    if kind == 'invoice':
        facts = invoice_adjustments._facts({'invoice_no': decision.get('invoice_no', ''),
            'invoice_date': decision.get('invoice_date'), 'card_no': decision.get('card_no'), 'amount': raw['amount']}, 'normal')
        if raw.get('explicit_date') and facts['invoice_date'].isoformat() != raw['explicit_date']:
            raise MustReportError('已明确的源开票日期不一致，请先核对原始事实。')
        owner = invoices.number_owner(session, facts['invoice_no'])
        if decision.get('existing_invoice_id'):
            row = _get(session, OilInvoice, decision['existing_invoice_id'])
            _check_version(row, decision['version'])
            invoices.require_editable(row)
            if owner != row.id or row.status != 'registered' or any(getattr(row, k) != v for k, v in facts.items()):
                raise DataConflictError('已有发票的票号、日期、金额或卡号不一致，请先核对，不再记金额。')
        else:
            if owner is not None:
                raise DataConflictError('票号已存在，请明确关联已有发票及其版本，不能再次登记。')
            if not decision.get('allocations'):
                raise MustReportError('历史开票须完整确认分配，缺票号或日期的原行继续留待核。')
            for allocation in decision['allocations']:
                _assignment(session, allocation)
            row = OilInvoice(updated_by=current_operator())
            session.add(row); session.flush()
            invoice_adjustments.correct(session, row.id, {**decision, 'amount': raw['amount'], 'version': row.version})
        return [('invoice', row.id)]
    if kind == 'pdf':
        content = contents.get(key)
        if content is None or sha256(content).hexdigest() != raw['sha256']:
            raise DataConflictError('补档原件未提供或hash与已核来源不一致。')
        recognized = recognize_pdf(content)
        row = _get(session, OilInvoice, decision['invoice_id'])
        _check_version(row, decision['version'])
        invoices.require_editable(row)
        facts = (recognized['invoice_no'], recognized['invoice_date'], recognized['amount'])
        if row.status != 'registered' or facts != (row.invoice_no,
                row.invoice_date.isoformat() if row.invoice_date else None, str(row.amount)) or not all(facts):
            raise DataConflictError('PDF票号、日期、金额与已记发票未能核对，保留待核，不新增金额。')
        if invoices.number_owner(session, row.invoice_no) != row.id:
            raise DataConflictError('PDF票号已有冲突，不能补档。')
        existing = session.scalar(select(OilInvoiceOriginal).where(OilInvoiceOriginal.sha256 == raw['sha256']))
        if existing is not None:
            if existing.invoice_id != row.id:
                raise DataConflictError('此PDF已属于另一发票，请核对，不能改挂。')
        else:
            existing = OilInvoiceOriginal(sha256=raw['sha256'], invoice_id=row.id, content=content,
                byte_size=len(content), outcome='duplicate', reason='首次接续人工核对补档；原已记金额保持。',
                recognized_json=_json(recognized), received_by=current_operator())
            session.add(existing); session.flush()
        return [('pdf', existing.id), ('invoice', row.id)]
    if kind == 'fee_legacy':
        from app.mod09_fee import service as fees
        fees.enable_oil_linkage(session, project_id=raw['project_id'], fee_item_id=decision['fee_item_id'],
            reviewed_items=raw['reviewed_items'], converted_customs=decision['converted_customs'], source_note=note)
        return [('fee_legacy', raw['project_id'])]
    if kind == 'big_legacy':
        from app.mod07_setl import service as big
        big.enable_big_oil(session, project_id=raw['project_id'], reviewed_rows=raw['reviewed_rows'],
            converted_customs=decision['converted_customs'], source_note=note)
        return [('big_legacy', raw['project_id'])]
    raise MustReportError('档案候选需先通过现有档案流程明确建立；不能由源名称自动建档。')


def confirm_source(session, source_id, decisions, *, pdf_contents=None):
    """一批明确确认原子保存；同源同决议重跑不写，已人工更正的目标拒绝覆盖。"""
    _lock(session)
    row = _get(session, OilContinuationSource, source_id)
    manifest, saved = json.loads(row.manifest_json), json.loads(row.confirmations_json)
    _verify_confirmations(session, saved)
    items = {item['key']: item for item in manifest['rows']}
    if len({d['key'] for d in decisions}) != len(decisions):
        raise MustReportError('本次确认包含重复来源行。')
    with session.begin_nested():
        for decision in decisions:
            key = decision['key']
            if key not in items:
                raise MustReportError('确认行不属于此来源清单。')
            if key in saved:
                if saved[key]['decision'] != decision:
                    raise DataConflictError('来源行已有不同确认结论，请核对，不能覆盖人工结果。')
                continue
            targets = _apply(session, source_id, items[key], decision, pdf_contents or {})
            session.flush()
            saved[key] = {'decision': decision, 'confirmed_by': current_operator(), 'targets': [
                {'kind': kind, 'id': target_id, 'snapshot': _snapshot(session, kind, target_id)} for kind, target_id in targets]}
        row.confirmations_json, row.updated_by = _json(saved), current_operator()
        session.flush()
    return source_report(session, source_id)
