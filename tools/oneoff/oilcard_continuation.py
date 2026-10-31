"""TAIL-463: build a private read-only manifest, or drill on the registered disposable preview.

Run with backend/.venv/Scripts/python.exe -B -X utf8. No production write mode is
provided. Manifest compilation only reads the prepared JSON reports; original
workbooks and PDFs are never renamed, modified, or received automatically.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
SOURCE_ID = 'fourth-company-oilcard-ledger'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build_manifest(directory):
    inventory, source, pdfs, legacy, candidates = [read(directory / name) for name in (
        'source-inventory.json', 'source-rows-private.json', 'pdf-facts-private.json',
        'legacy-totals.json', 'project-candidates-private.json')]
    if inventory['sha256'] != source['source_sha256']:
        raise ValueError('Prepared workbook evidence versions disagree')
    rows = []
    for field, sheet, first, last, kind in [('cards', '油卡', 2, 49, 'archive'),
            ('recharges', '油卡充值', 2, 50, 'recharge'),
            ('invoice_amounts', '油卡开票', 2, 102, 'invoice'),
            ('transfers', '转账', 2, 8, 'transfer')]:
        for raw in source[field]:
            if not first <= raw['source_row'] <= last or raw.get('source_sheet', sheet) != sheet:
                raise ValueError('Row outside the four approved active ranges')
            rows.append({'key': f"{sheet}!{raw['source_row']}", 'kind': kind, 'raw': raw})
    inventory_pdfs = {item['sha256']: item for item in inventory['pdfs']}
    if len(inventory_pdfs) != len(pdfs['pdfs']):
        raise ValueError('Prepared PDF evidence count disagrees')
    for raw in pdfs['pdfs']:
        if raw['sha256'] not in inventory_pdfs or raw['bytes'] != inventory_pdfs[raw['sha256']]['bytes']:
            raise ValueError('Prepared PDF evidence versions disagree')
        rows.append({'key': 'PDF:' + raw['sha256'], 'kind': 'pdf', 'raw': raw})
    for project in legacy['projects']:
        key = project['id']
        definitions = sorted((d for d in legacy['fee_definitions'] if d['project_id'] == key), key=lambda d: d['id'])
        reviewed = [{'item_id': d['id'], 'name': d['name'], 'deleted': d['deleted'], 'months': [
            {k: r[k] for k in ('id', 'ym', 'amount')} for r in sorted(legacy['fee_complete_totals'], key=lambda r: r['id'])
            if r['fee_item_id'] == d['id']]} for d in definitions]
        rows.append({'key': f'特殊费用:{key}', 'kind': 'fee_legacy', 'raw': {'project_id': key, 'reviewed_items': reviewed}})
        rows.append({'key': f'会议大表:{key}', 'kind': 'big_legacy', 'raw': {'project_id': key,
            'reviewed_rows': [r for r in legacy['big_complete_totals'] if r['project_id'] == key]}})
    return {'source_id': SOURCE_ID, 'source_sha256': inventory['sha256'],
        'active_ranges': {k: v['range'] for k, v in inventory['sheets'].items()},
        'source_counts': {'archive_raw_rows': len(source['cards']),
            'archive_nonempty_rows': sum(any(raw.get(k) for k in ('category', 'initial_project_text',
                'current_project_text', 'card_text', 'remark')) for raw in source['cards']),
            'distinct_full_card_candidates': len({raw['card_text'] for raw in source['cards']
                if re.fullmatch(r'(?:\d{16}|\d{19})', raw['card_text'])}),
            'archive_auto_create': False},
        'excluded': ['油卡 存档2025.9.10', '充值H67:K69', '转账I22'],
        'project_candidates': candidates, 'legacy_revision': legacy['revision'], 'rows': rows}


def synthetic_manifest(session, source_id):
    """A declared synthetic confirmation payload, independent of real candidates."""
    from decimal import Decimal
    from sqlalchemy import select
    from app.mod01_projects.models import Project
    from app.mod09_fee.models import FeeItem, FeeManualItem
    from app.mod07_setl.models import AnalysisBigManual
    from app.mod09_fee import service as fees
    from app.mod07_setl import service as big
    from app.mod13_oilcard import service
    from app.mod13_oilcard.models import OilContinuationSource
    from tests.oilcard_invoice_samples import CARD, invoice_pdf
    request = lambda label: str(uuid5(NAMESPACE_URL, source_id + ':' + label))
    projects, accounts = [], []
    card = service.save_card(session, {'request_id': request('card'), 'kind': 'secondary', 'card_no': CARD,
        'parent_card_id': None, 'remark': '463合成卡；非原件接续'})
    for suffix in ('a', 'b'):
        warehouse = '__oilcard_463_' + suffix + '__'
        project = session.scalar(select(Project).where(Project.warehouse_name == warehouse))
        if project is None:
            project = Project(project_type='normal', name_full='463接续演练' + suffix.upper(),
                warehouse_name=warehouse, disp='463演练' + suffix.upper(), status='active')
            session.add(project); session.flush()
        projects.append(project)
        accounts.append(service.save_account(session, {'request_id': request('account:' + suffix),
            'name': '463接续演练' + suffix.upper(), 'project_id': project.id, 'card_id': card.id,
            'status': 'active', 'remark': '明确合成确认；真实候选全部待核'}))
    first, second = projects
    if session.get(OilContinuationSource, source_id) is None:
        old = FeeItem(project_id=first.id, name='463合成旧用油完整总额')
        session.add(old); session.flush()
        session.add(FeeManualItem(project_id=first.id, fee_item_id=old.id, item_name=old.name,
            ym='2026-10', amount=Decimal('12000')))
        session.add(AnalysisBigManual(project_id=first.id, warehouse_name=first.warehouse_name,
            ym='2026-10', oil=Decimal('13000'), note='463原大表通用备注'))
        session.flush()
    rows, decisions = [], []
    assignment = {'project_id': first.id, 'account_id': accounts[0].id, 'card_id': card.id}
    for key, day, amount, kind in [('opening', None, '500', 'recharge'),
            ('prior', '2025-12-31', '70', 'recharge'), ('october', '2026-10-01', '10000', 'recharge'),
            ('adjustment', '2026-10-31', '200', 'adjustment'), ('november', '2026-11-01', '4900', 'recharge')]:
        rows.append({'key': key, 'kind': 'recharge', 'raw': {'explicit_date': day, 'amount': amount,
            'original_date_text': day or '原始数据', 'remark': '463合成来源'}})
        decisions.append({'key': key, **assignment, 'entry_kind': kind, 'cutoff_ym': '2025-11', 'note': '合成样例明确确认'})
    rows.append({'key': 'transfer', 'kind': 'transfer', 'raw': {'explicit_date': '2026-10-15', 'amount': '30', 'remark': '463合成内部调拨'}})
    decisions.append({'key': 'transfer', 'out_project_id': first.id, 'out_account_id': accounts[0].id,
        'out_card_id': card.id, 'in_project_id': second.id, 'in_account_id': accounts[1].id,
        'in_card_id': card.id, 'treatment': '经核为内部调拨', 'note': '合成内部调拨30，双边公司合计0'})
    number = '20261031000000000463'
    content = invoice_pdf(number=number, amount='10000.00', subtotal='8849.56', tax='1150.44')
    rows.extend([{'key': 'invoice', 'kind': 'invoice', 'raw': {'amount': '10000', 'explicit_date': '2026-10-31', 'original_date_text': '2026-10-31'}},
        {'key': 'unknown-invoice', 'kind': 'invoice', 'raw': {'amount': '123', 'explicit_date': None, 'original_date_text': '原始数据'}},
        {'key': 'pdf', 'kind': 'pdf', 'raw': {'sha256': sha256(content).hexdigest()}}])
    decisions.append({'key': 'invoice', 'invoice_no': number, 'invoice_date': '2026-10-31', 'card_no': CARD,
        'allocations': [{'project_id': project.id, 'account_id': account.id, 'card_id': card.id, 'amount': amount}
            for project, account, amount in zip(projects, accounts, ('6000', '4000'))], 'note': '合成已记开票一票两分配'})
    # Original snapshots remain unchanged after activation; their complete old
    # amounts are the independently declared 12000 / 13000, never the new custom.
    for project in projects:
        reviewed = fees.review_oil_linkage(session, project_id=project.id)
        fee_item = next((r['item_id'] for r in reviewed if r['name'] == '463合成旧用油完整总额'), None)
        rows.append({'key': f'fee:{project.id}', 'kind': 'fee_legacy', 'raw': {'project_id': project.id, 'reviewed_items': reviewed}})
        decisions.append({'key': f'fee:{project.id}', 'fee_item_id': fee_item, 'converted_customs':
            [{'ym': '2026-10', 'amount': '1830', 'remark': '旧12000 - 当月10170'}] if project.id == first.id else [],
            'note': '合成完整旧费用核对；12000 = 10170 + 1830'})
        rows.append({'key': f'big:{project.id}', 'kind': 'big_legacy', 'raw': {'project_id': project.id,
            'reviewed_rows': big.review_big_oil(session, project_id=project.id)}})
        decisions.append({'key': f'big:{project.id}', 'converted_customs':
            [{'ym': '2026-10', 'amount': '430', 'remark': '旧13000 - 累计10740 - 特殊额1830'}] if project.id == first.id else [],
            'note': '合成完整旧大表核对；13000 = 10740 + 1830 + 430'})
    return ({'source_id': source_id, 'synthetic': True, 'rows': rows}, decisions, content,
        {'project_ids': [p.id for p in projects], 'project_names': [p.disp for p in projects],
         'account_ids': [a.id for a in accounts], 'invoice_no': number})


def drill(source_env, manifest_path):
    from tools.dev.frontend_preview_runtime import registered_preview, assert_same_preview
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from app.mod13_oilcard import continuation, ledger, invoices, reporting
    path, owner, _ = registered_preview()
    assert_same_preview(owner, registered_preview()[1], disposable=True)
    if owner['revision'] != 'oil463261031':
        raise RuntimeError('Drill requires the exact TAIL-463 migrated preview')
    source = Settings(_env_file=source_env)
    guard = TestDatabaseGuard.from_sources((source.database_url,), source.test_database_url)
    engine = create_engine(guard.test_url, connect_args={'options': '-c search_path=' + owner['schema']}, hide_parameters=True)
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            actual = session.execute(text('SELECT current_database(),current_schema()')).one()
            revision = session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
            if tuple(actual) != ('mtrl_workbench_test', owner['schema']) or revision != owner['revision']:
                raise RuntimeError('Database/schema/revision does not match registered preview')
            assert_same_preview(owner, registered_preview()[1], disposable=True)
            before = (ledger.reconciliation(session), invoices.invoices(session)['total_amount'])
            real = continuation.stage_source(session, read(manifest_path)) if manifest_path else None
            if before != (ledger.reconciliation(session), invoices.invoices(session)['total_amount']):
                raise RuntimeError('Pending real manifest unexpectedly affected money')
            source_id = 'synthetic-463:' + owner['schema']
            manifest, decisions, content, identifiers = synthetic_manifest(session, source_id)
            continuation.stage_source(session, manifest)
            first = continuation.confirm_source(session, source_id, decisions)
            invoice_id = first['rows'][6]['confirmation']['targets'][0]['id']
            invoice = next(row for row in invoices.invoices(session)['invoices'] if row['id'] == invoice_id)
            pdf = {'key': 'pdf', 'invoice_id': invoice_id, 'version': invoice['version'], 'note': '合成原件明确补到已记票，不新增金额'}
            before_pdf = invoices.invoices(session)['total_amount']
            result = continuation.confirm_source(session, source_id, [pdf], pdf_contents={'pdf': content})
            if invoices.invoices(session)['total_amount'] != before_pdf:
                raise RuntimeError('PDF attachment increased invoice money')
            continuation.confirm_source(session, source_id, [*decisions, pdf], pdf_contents={'pdf': content})
            continuation.stage_source(session, manifest)
            summary = ledger.reconciliation(session)
            own_rows = [r for r in summary['rows'] if r['account_id'] in identifiers['account_ids']]
            assert sum(ledger._amount(r['total_amount']) for r in own_rows) == ledger._amount('15670')
            assert sum(ledger._amount(r['invoiced_amount']) for r in own_rows) == ledger._amount('10000')
            linkage = {ym: [reporting.linkage_month(session, project_id=p, ym=ym) for p in identifiers['project_ids']]
                for ym in ('2026-10', '2026-11')}
            assert linkage['2026-10'][0]['fee_amount'] == '12000.00'
            assert linkage['2026-10'][0]['big']['amount'] == '13000.00'
            assert linkage['2026-11'][0]['big']['amount'] == '17900.00'
            assert_same_preview(owner, registered_preview()[1], disposable=True)
        report = {'synthetic': True, 'schema': owner['schema'], 'revision': owner['revision'], **identifiers,
            'source_id': source_id, 'confirmed_count': result['confirmed_count'], 'pending_count': result['pending_count'],
            'real_manifest': {'source_id': real['source_id'], 'confirmed_count': real['confirmed_count'],
                'pending_count': real['pending_count'], 'pending_source_amounts': real['pending_source_amounts']} if real else None,
            'account_rows': own_rows, 'linkage': linkage, 'pdf_money_unchanged': True, 'same_source_repeat_verified': True,
            'expected': {'company_recharge': '15670.00', 'company_invoiced': '10000.00', 'company_difference': '5670.00',
                'ledger_detail_total': '15170.00', 'opening_separate': '500.00', 'A_october_fee': '12000.00',
                'A_october_big': '13000.00', 'A_november_fee': '4900.00', 'A_november_big': '17900.00',
                'B_october_fee_and_big': '30.00', 'unbooked_invoice': '123.00'}}
        write(path.parent / 'continuation-drill.json', report)
        print(json.dumps({'ok': True, 'report': str(path.parent / 'continuation-drill.json'), **identifiers}, ensure_ascii=False))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    manifest = sub.add_parser('manifest')
    manifest.add_argument('--input-dir', type=Path, required=True)
    manifest.add_argument('--output', type=Path, required=True)
    preview = sub.add_parser('drill')
    preview.add_argument('--source-env', type=Path, required=True)
    preview.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.action == 'manifest':
        result = build_manifest(args.input_dir)
        write(args.output, result)
        print(json.dumps({'source_id': result['source_id'], 'rows': len(result['rows']), 'all_pending': True,
            'manifest': str(args.output.resolve())}, ensure_ascii=False))
    else:
        drill(args.source_env, args.manifest)


if __name__ == '__main__':
    main()
