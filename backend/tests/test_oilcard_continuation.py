"""接续真实服务：来源保真、隔离明确确认、重跑保护、补档不重记及成品导出。"""
from copy import deepcopy
from datetime import date
from io import BytesIO
import json
from uuid import uuid4

import openpyxl
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import DataConflictError, MustReportError
from app.mod13_oilcard import continuation, invoices, ledger, reporting
from app.mod13_oilcard.models import OilContinuationSource, OilEntry, OilInvoice, OilOpeningBalance
from app.mod13_oilcard.opening_conversion import convert_confirmed_openings
from tests.test_oilcard_archives import scene, create  # noqa: F401
from tools.oneoff.oilcard_continuation import synthetic_manifest, build_manifest


def stage(manifest):
    with session_scope() as session:
        return continuation.stage_source(session, manifest)


def confirm(source_id, decisions, **kwargs):
    with session_scope() as session:
        return continuation.confirm_source(session, source_id, decisions, **kwargs)


def target(result, key):
    return next(row for row in result['rows'] if row['key'] == key)['confirmation']['targets'][0]['id']


@pytest.fixture
def enrolled(scene):
    client, _ = scene
    source_id = 'synthetic-463-test'
    with session_scope() as session:
        manifest, decisions, content, ids = synthetic_manifest(session, source_id)
        before = ledger.reconciliation(session)
        staged = continuation.stage_source(session, manifest)
        assert ledger.reconciliation(session) == before
    return client, source_id, manifest, decisions, content, ids, staged


def test_all_real_candidates_stay_pending_and_never_invent_facts(enrolled):
    client, source_id, manifest, _, _, _, staged = enrolled
    assert staged['confirmed_count'] == 0 and staged['pending_count'] == 13
    assert staged['pending_source_amounts'] == {'recharge': '15670.00', 'invoice': '10123.00', 'transfer': '30.00'}
    assert staged['pending_is_booked'] is False
    assert stage(deepcopy(manifest)) == staged
    assert client.get('/api/m13/reconciliation').json()['total_amount'] == '0.00'
    assert client.get('/api/m13/invoices').json()['total_amount'] == '0.00'
    pending = next(r for r in staged['rows'] if r['key'] == 'unknown-invoice')
    assert pending['raw'] == {'amount': '123', 'explicit_date': None, 'original_date_text': '原始数据'}
    with pytest.raises(MustReportError, match='发票号码'):
        confirm(source_id, [{'key': 'unknown-invoice', 'note': '缺票号与日期仍不能入账'}])
    assert stage(manifest) == staged


def test_confirmed_manual_invoice_and_boundary_transfer_keep_original_facts(scene):
    client, (project_id, _) = scene
    account = create(client, 'accounts', name='保留账户', project_id=project_id)
    assignment = {'account_id': account['id'], 'project_id': project_id, 'card_id': None}
    source_id = 'synthetic-474-manual'
    manifest = {'source_id': source_id, 'rows': [
        {'key': 'legacy-invoice', 'kind': 'invoice', 'raw': {'amount': '23.45', 'original_date_text': '原始数据'}},
        {'key': 'legacy-transfer', 'kind': 'transfer', 'raw': {'amount': '70', 'original_date_text': ''}},
    ]}
    decisions = [
        {'key': 'legacy-invoice', 'manual': True, 'cutoff_ym': '2025-12', 'note': '已核开票金额',
         'allocations': [{**assignment, 'amount': '23.45'}]},
        {'key': 'legacy-transfer', 'closed_side': 'out', 'closed_counterparty': '已结项目',
         'note': '核对原表', 'treatment': '只接续在建侧', 'cutoff_ym': '2025-12',
         **{'in_' + key: value for key, value in assignment.items()}},
    ]
    stage(manifest)
    with pytest.raises(MustReportError, match='截至月'):
        confirm(source_id, [{**decisions[0], 'cutoff_ym': None}])
    result = confirm(source_id, decisions)
    assert confirm(source_id, decisions) == stage(manifest) == result
    data = client.get('/api/m13/invoices').json()
    invoice = data['invoices'][0]
    assert invoice['invoice_no'] is invoice['invoice_date'] is None and not invoice['originals']
    assert (invoice['manual_date_text'], invoice['manual_cutoff_ym']) == ('原始数据', '2025-12')
    assert invoice['change_note'] == ''
    assert data['total_amount'] == '23.45'
    totals = client.get('/api/m13/reconciliation').json()
    assert (totals['rows'][0]['opening_amount'], totals['invoiced_amount'], totals['difference_amount']) == ('70.00', '23.45', '46.55')
    assert client.get('/api/m13/ledger').json()['entries'] == []
    workbook = openpyxl.load_workbook(BytesIO(client.get('/api/m13/export').content))
    header, exported, *_ = workbook['发票台账'].values
    exported = dict(zip(header, exported))
    assert (exported['开票日期'], exported['发票号'], exported['历史截至月'], exported['票据关系']) == ('原始数据', None, '2025-12', '手工登记')
    workbook.close()
    edited = client.put(f"/api/m13/invoices/{invoice['id']}/remark",
        json={'version': invoice['version'], 'remark': '人工修订'})
    assert edited.status_code == 200
    with pytest.raises(DataConflictError, match='保留人工结果'):
        confirm(source_id, decisions)


def test_older_continuation_invoice_note_stays_in_audit_and_later_business_note_is_visible(enrolled):
    client, source_id, _, decisions, _, _, _ = enrolled
    decision = next(d for d in decisions if d['key'] == 'invoice')
    invoice_id = target(confirm(source_id, [decision]), 'invoice')
    with session_scope() as session:
        row = session.get(OilInvoice, invoice_id)
        row.change_note = decision['note']
        source = session.get(OilContinuationSource, source_id)
        saved = json.loads(source.confirmations_json)
        saved['invoice']['targets'][0]['snapshot']['change_note'] = decision['note']
        source.confirmations_json = json.dumps(saved)
    assert client.get('/api/m13/invoices').json()['invoices'][0]['change_note'] == ''
    with session_scope() as session:
        row = session.get(OilInvoice, invoice_id)
        assert row.change_note == decision['note']
        row.change_note = '更正票面归属'
    assert client.get('/api/m13/invoices').json()['invoices'][0]['change_note'] == '更正票面归属'


def test_dated_opening_conversion_keeps_balances_links_and_original_scope(scene):
    client, (first, second) = scene
    historical_card = create(client, 'cards', card_no='1230000000000099')
    first_account = create(client, 'accounts', name='甲账户', project_id=first, card_id=historical_card['id'])
    second_account = create(client, 'accounts', name='乙账户', project_id=second)
    a = {'account_id': first_account['id'], 'project_id': first, 'card_id': historical_card['id']}
    b = {'account_id': second_account['id'], 'project_id': second, 'card_id': None}
    source_id = 'isolated-opening-conversion'
    manifest = {'source_id': source_id, 'rows': [
        {'key': 'recharge', 'kind': 'recharge', 'raw': {'amount': '500', 'original_date_text': '原始数据', 'remark': '原备注'}},
        {'key': 'transfer', 'kind': 'transfer', 'raw': {'amount': '20'}},
        {'key': 'boundary', 'kind': 'transfer', 'raw': {'amount': '70'}},
    ]}
    in_side = {f'in_{key}': value for key, value in b.items()}
    out_side = {f'out_{key}': value for key, value in a.items()}
    decisions = [
        {'key': 'recharge', **a, 'entry_kind': 'recharge', 'cutoff_ym': '2025-12', 'note': '核定充值'},
        {'key': 'transfer', **in_side, **out_side, 'treatment': '原双边', 'cutoff_ym': '2025-12', 'note': '核定转账'},
        {'key': 'boundary', **in_side, 'closed_side': 'out', 'closed_counterparty': '已结项目甲',
            'treatment': '保留转入侧', 'cutoff_ym': '2025-12', 'note': '核定跨范围转账'},
    ]
    staged = stage(manifest)
    confirm(source_id, decisions)
    args = dict(source_id=source_id, fingerprint=staged['fingerprint'], booking_date=date(2025, 9, 1),
        expected_count=4, expected_amount='570')
    with session_scope() as session:
        # A wrong reviewed net amount fails before any write.
        with pytest.raises(DataConflictError, match='净额'):
            convert_confirmed_openings(session, **{**args, 'expected_amount': '571'})
        assert ledger.entries(session)['entries'] == []
        assert ledger.confirmed_openings(session)['total_amount'] == '570.00'
        assert reporting.fee_month(session, project_id=first, ym='2025-09')['recharge_amount'] == '0.00'
        before = ledger.reconciliation(session)
    with session_scope() as session:
        result = convert_confirmed_openings(session, **args)
        assert result == {'count': 4, 'amount': '570.00', 'booking_date': '2025-09-01', 'already_converted': False}
    with session_scope() as session:
        assert convert_confirmed_openings(session, **args)['already_converted']
        assert continuation.confirm_source(session, source_id, decisions)['confirmed_count'] == 3
        rows = ledger.entries(session)['entries']
        assert [(r['kind'], r['amount']) for r in rows] == [
            ('adjustment', '70.00'), ('recharge', '500.00'), ('transfer_out', '-20.00'), ('transfer_in', '20.00')]
        assert all(r['entry_date'] == '2025-09-01' for r in rows)
        assert rows[1]['card_id'] == historical_card['id'] and '原始数据；原备注' in rows[1]['remark']
        assert rows[2]['transfer_id'] == rows[3]['transfer_id'] is not None
        assert '已结项目甲' in rows[0]['remark']
        assert list(session.scalars(select(OilOpeningBalance))) == []
        assert ledger.confirmed_openings(session)['total_amount'] == '0.00'
        after = ledger.reconciliation(session)
        assert [(r['account_id'], r['total_amount'], r['difference_amount']) for r in after['rows']] == [
            (r['account_id'], r['total_amount'], r['difference_amount']) for r in before['rows']]
        assert reporting.fee_month(session, project_id=first, ym='2025-09')['recharge_amount'] == '480.00'
        assert reporting.fee_month(session, project_id=second, ym='2025-09')['recharge_amount'] == '90.00'
        assert reporting.big_month(session, project_id=first, ym='2025-09')['recharge_amount'] == '480.00'
        saved = json.loads(session.get(OilContinuationSource, source_id).confirmations_json)
        assert saved['boundary']['opening_conversion']['previous_targets'][0]['snapshot']['cutoff_ym'] == '2025-12'
    assert client.get('/api/m13/ledger').json()['total_amount'] == '570.00'


def test_confirmed_drill_repeated_source_pdf_allocation_reports_and_real_exports(enrolled, tmp_path, monkeypatch):
    client, source_id, manifest, decisions, content, ids, _ = enrolled
    first = confirm(source_id, decisions)
    invoice_id = target(first, 'invoice')
    invoice = client.get('/api/m13/invoices').json()['invoices'][0]
    assert invoice['id'] == invoice_id and invoice['amount'] == '10000.00'
    assert [a['amount'] for a in invoice['allocations']] == ['6000.00', '4000.00']
    pdf = {'key': 'pdf', 'invoice_id': invoice_id, 'version': invoice['version'], 'note': '明确补档到已记票，不加金额'}
    linked = confirm(source_id, [pdf], pdf_contents={'pdf': content})
    assert linked['confirmed_count'] == 12 and linked['pending_count'] == 1
    assert confirm(source_id, [*decisions, pdf], pdf_contents={'pdf': content}) == linked
    assert stage(manifest) == linked
    read_invoice = client.get('/api/m13/invoices').json()
    assert read_invoice['total_amount'] == '10000.00' and len(read_invoice['invoices']) == 1
    original = read_invoice['invoices'][0]['originals'][0]
    assert client.get(f"/api/m13/invoices/originals/{original['id']}").content == content
    # The ordinary upload entry must reuse a manually attached original and its
    # existing allocation, including replay of the same upload response.
    uploaded = client.post('/api/m13/invoices/receive', files={'file': ('repeat.pdf', content, 'application/pdf')})
    assert uploaded.status_code == 200
    assert uploaded.json()['original']['id'] == original['id']
    assert uploaded.json()['item']['id'] == invoice_id
    assert client.post('/api/m13/invoices/receive', files={'file': ('repeat.pdf', content, 'application/pdf')}).json() == uploaded.json()
    assert client.get('/api/m13/invoices').json() == read_invoice
    reconciliation = client.get('/api/m13/reconciliation').json()
    assert (reconciliation['total_amount'], reconciliation['invoiced_amount'], reconciliation['difference_amount']) == ('15670.00', '10000.00', '5670.00')
    assert [(r['total_amount'], r['invoiced_amount']) for r in reconciliation['rows']] == [('15640.00', '6000.00'), ('30.00', '4000.00')]
    assert client.get('/api/m13/ledger').json()['total_amount'] == '15170.00'
    with session_scope() as session:
        october = reporting.linkage_month(session, project_id=ids['project_ids'][0], ym='2026-10')
        november = reporting.linkage_month(session, project_id=ids['project_ids'][0], ym='2026-11')
        assert october['recharge_amount'] == '10170.00' and october['custom_amount'] == '1830.00'
        assert october['fee_amount'] == '12000.00' and october['big']['amount'] == '13000.00'
        assert october['big']['recharge_amount'] == '10740.00' and october['big']['extra_amount'] == '430.00'
        assert november['fee_amount'] == '4900.00' and november['big']['amount'] == '17900.00'
        from app.report_export import service as exports
        monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
        ledger_path = exports.export_ledger(session, ['__oilcard_463_a__'], ym='2026-10')
        big_path = exports.export_big(session, '2026-10')
    # Existing production exporters, independent expected cells/row values.
    workbook = openpyxl.load_workbook(ledger_path, data_only=True)
    try:
        sheet = workbook['特殊费用月报表']
        row = next(r for r in sheet.iter_rows() if r[0].value == '工程用油（油卡联动）')
        col = next(c.column for c in sheet[2] if c.value == '2026-10')
        assert row[col - 1].value == 12000
    finally:
        workbook.close()
    workbook = openpyxl.load_workbook(big_path, data_only=True)
    try:
        row = next(r for r in workbook.active.iter_rows() if any(c.value == '463演练A' for c in r))
        assert row[18].value == 13000
    finally:
        workbook.close()
    exported = client.get('/api/m13/invoices/export')
    assert exported.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(exported.content), data_only=True)
    try:
        assert workbook.active.max_row == 3  # one invoice with two allocations, then total
        assert workbook.active['G3'].value == 10000
    finally:
        workbook.close()


def test_changed_source_different_identity_and_confirmation_never_overwrite(enrolled):
    _, source_id, manifest, decisions, _, _, staged = enrolled
    changed = deepcopy(manifest)
    changed['rows'][0]['raw']['amount'] = '501'
    with pytest.raises(DataConflictError, match='来源的内容'):
        stage(changed)
    with pytest.raises(DataConflictError, match='另一稳定身份'):
        stage({**manifest, 'source_id': 'another-origin-name'})
    assert stage(manifest) == staged
    confirm(source_id, decisions[:1])
    with pytest.raises(DataConflictError, match='不同确认结论'):
        confirm(source_id, [{**decisions[0], 'note': '另一个结论'}])
    assert stage(manifest)['confirmed_count'] == 1


def test_manual_correction_blocks_reimport_without_overwriting_it(enrolled):
    client, source_id, manifest, decisions, _, _, _ = enrolled
    first = confirm(source_id, decisions[1:2])
    entry_id = target(first, 'prior')
    entry = client.get('/api/m13/ledger').json()['entries'][0]
    fields = {k: entry[k] for k in ('project_id', 'account_id', 'date_text', 'kind', 'amount', 'remark', 'version')}
    result = client.put(f'/api/m13/ledger/entries/{entry_id}', json={**fields, 'amount': '71', 'remark': '人工更正保留'})
    assert result.status_code == 200, result.text
    for action in (lambda: stage(manifest), lambda: confirm(source_id, decisions[1:2])):
        with pytest.raises(DataConflictError, match='已更正'):
            action()
    assert client.get('/api/m13/ledger').json()['entries'][0]['amount'] == '71.00'
    assert client.get('/api/m13/ledger').json()['entries'][0]['remark'] == '人工更正保留'


def test_pre_delete_column_invoice_confirmation_keeps_identity_and_detects_deletion(enrolled):
    _, source_id, manifest, decisions, _, _, _ = enrolled
    invoice_decision = [d for d in decisions if d['key'] == 'invoice']
    result = confirm(source_id, invoice_decision)
    invoice_id = target(result, 'invoice')
    with session_scope() as session:
        source = session.get(OilContinuationSource, source_id)
        saved = json.loads(source.confirmations_json)
        saved['invoice']['targets'][0]['snapshot'].pop('deleted')
        source.confirmations_json = json.dumps(saved)
    assert stage(manifest)['confirmed_count'] == 1
    assert confirm(source_id, invoice_decision)['confirmed_count'] == 1
    with session_scope() as session:
        assert json.loads(session.get(OilContinuationSource, source_id).confirmations_json) == saved
        session.get(OilInvoice, invoice_id).deleted = True
    with pytest.raises(DataConflictError, match='已更正'):
        stage(manifest)


def test_invalid_multi_allocation_and_undeclared_card_rollback_whole_confirmation(enrolled):
    client, source_id, manifest, decisions, _, _, staged = enrolled
    invoice = next(d for d in decisions if d['key'] == 'invoice')
    bad = deepcopy(invoice)
    bad['allocations'][1]['amount'] = '3999'
    with pytest.raises(MustReportError, match='分配合计'):
        confirm(source_id, [decisions[1], bad])
    assert client.get('/api/m13/ledger').json()['total_amount'] == '0.00'
    assert client.get('/api/m13/invoices').json()['invoices'] == []
    assert stage(manifest) == staged
    undeclared = {k: v for k, v in decisions[1].items() if k != 'card_id'}
    with pytest.raises(MustReportError, match='卡片快照'):
        confirm(source_id, [undeclared])


def test_unknown_transfer_only_enters_confirmed_opening_with_both_sides(enrolled):
    client, _, _, decisions, _, _, _ = enrolled
    transfer = next(d for d in decisions if d['key'] == 'transfer')
    source_id = 'unknown-transfer-source'
    manifest = {'source_id': source_id, 'rows': [{'key': '转账!2', 'kind': 'transfer',
        'raw': {'original_date_text': '原始数据', 'explicit_date': None, 'amount': '30', 'remark': '原平账文字'}}]}
    stage(manifest)
    decision = {**transfer, 'key': '转账!2'}
    with pytest.raises(MustReportError, match='截至月份'):
        confirm(source_id, [decision])
    with pytest.raises(MustReportError, match='业务性质'):
        confirm(source_id, [{**decision, 'cutoff_ym': '2025-11', 'treatment': ''}])
    result = confirm(source_id, [{**decision, 'cutoff_ym': '2025-11'}])
    assert len(result['rows'][0]['confirmation']['targets']) == 2
    assert client.get('/api/m13/ledger').json()['entries'] == []
    assert client.get('/api/m13/reconciliation').json()['total_amount'] == '0.00'
    with session_scope() as session:
        outgoing = transfer['out_project_id']
        assert reporting.big_amount(session, project_id=outgoing, ym='2025-10') == 0
        assert str(reporting.big_amount(session, project_id=outgoing, ym='2025-11')) == '-30.00'
        assert reporting.fee_month(session, project_id=outgoing, ym='2025-11')['recharge_amount'] == '0.00'


def test_pdf_requires_exact_hash_invoice_version_facts_and_unique_number(enrolled):
    client, source_id, _, decisions, content, _, _ = enrolled
    result = confirm(source_id, [d for d in decisions if d['key'] == 'invoice'])
    invoice_id = target(result, 'invoice')
    invoice = client.get('/api/m13/invoices').json()['invoices'][0]
    pdf = {'key': 'pdf', 'invoice_id': invoice_id, 'version': invoice['version'], 'note': '明确补档'}
    with pytest.raises(DataConflictError, match='hash'):
        confirm(source_id, [pdf], pdf_contents={'pdf': content + b'changed'})
    with pytest.raises(DataConflictError):
        confirm(source_id, [{**pdf, 'version': str(uuid4())}], pdf_contents={'pdf': content})
    with session_scope() as session:
        row = session.get(OilInvoice, invoice_id)
        row.amount = '9999.00'
    with pytest.raises(DataConflictError, match='已更正'):
        confirm(source_id, [pdf], pdf_contents={'pdf': content})
    with session_scope() as session:
        assert session.scalar(select(OilInvoice.id)) == invoice_id


def test_manifest_enforces_approved_ranges_and_keeps_full_original_markers(tmp_path):
    import json
    evidence = {'source-inventory.json': {'sha256': 'original-hash', 'sheets': {'油卡': {'range': 'A2:I49'}}, 'pdfs': []},
        'source-rows-private.json': {'source_sha256': 'original-hash', 'cards': [], 'invoice_amounts': [], 'transfers': [],
            'recharges': [{'source_row': 2, 'source_sheet': '油卡充值', 'amount': '1.00', 'original_date_text': '原始数据', 'explicit_date': None}]},
        'pdf-facts-private.json': {'pdfs': []}, 'legacy-totals.json': {'revision': 'old', 'projects': []},
        'project-candidates-private.json': {'candidates': []}}
    for name, value in evidence.items():
        (tmp_path / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    manifest = build_manifest(tmp_path)
    assert manifest['source_id'] == 'fourth-company-oilcard-ledger'
    assert manifest['rows'][0]['key'] == '油卡充值!2' and manifest['rows'][0]['raw']['original_date_text'] == '原始数据'
    evidence['source-rows-private.json']['recharges'][0]['source_row'] = 67
    (tmp_path / 'source-rows-private.json').write_text(json.dumps(evidence['source-rows-private.json']), encoding='utf-8')
    with pytest.raises(ValueError, match='approved active ranges'):
        build_manifest(tmp_path)
