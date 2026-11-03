"""Whole invoice corrections and linked follow-ups through real API/history."""
from io import BytesIO
from urllib.parse import unquote

from openpyxl import load_workbook

from app.core import session as SESS
from tests.oilcard_invoice_samples import CARD, NUMBER, invoice_pdf
from tests.test_oilcard_archives import scene, create  # noqa: F401
from tests.test_oilcard_invoices import invoices, receive, setup_account


def allocation(account, amount):
    return {'project_id': account['project_id'], 'account_id': account['id'], 'amount': amount}


def correct(client, row, allocations, **values):
    fields = {key: row[key] for key in ('invoice_no', 'invoice_date', 'amount', 'card_no', 'version')}
    return client.put(f"/api/m13/invoices/{row['id']}/correct", json={**fields, 'allocations': allocations, 'note': '合成票面补正依据', **values})


def allocate(client, row, allocations):
    return client.put(f"/api/m13/invoices/{row['id']}/allocations", json={'version': row['version'], 'allocations': allocations})


def replay(client, direction, operation):
    response = client.post('/api/history/' + direction, json={'operation_id': operation['id']})
    assert response.status_code == 200, response.text
    assert response.json()['ok']


def test_pending_correction_whole_split_archived_account_undo_and_original(scene):
    client, (project, other) = scene
    first = setup_account(client, project)
    archived = create(client, 'accounts', project_id=other, name='归档迟到票', status='archived')
    content = invoice_pdf(card='45678', amount='10000.00', subtotal='8849.56', tax='1150.44')
    pending = receive(client, content)['item']
    parts = [allocation(first, '6000'), allocation(archived, '4000')]
    saved = correct(client, pending, parts, card_no=CARD, invoice_no='20261031000000000009', review_original_id=pending['originals'][0]['id'])
    assert saved.status_code == 200, saved.text
    assert saved.headers['X-Operation-History'] == 'recorded'
    row = saved.json()['item']
    assert row['status'] == 'registered' and row['reason'] == ''
    assert [a['amount'] for a in row['allocations']] == ['6000.00', '4000.00']
    assert row['originals'][0]['resolution'] == '合成票面补正依据'
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    restored = invoices(client)['invoices'][0]
    assert restored['status'] == 'pending' and restored['invoice_no'] == NUMBER
    assert restored['allocations'] == [] and restored['originals'][0]['resolution'] is None
    assert client.get(f"/api/m13/invoices/originals/{pending['originals'][0]['id']}").content == content
    replay(client, 'redo', operation)
    row = invoices(client)['invoices'][0]
    assert invoices(client)['total_amount'] == '10000.00'
    filename = unquote(client.get(f"/api/m13/invoices/originals/{row['originals'][0]['id']}").headers['X-Export-Filename'])
    assert '多项目 10000.00 20261031000000000009.pdf' in filename
    # Both the historical recognized number and the corrected number resolve to
    # this invoice; no second accounting record can be created.
    old = receive(client, invoice_pdf(card='45678', amount='10000.00', subtotal='8849.56', tax='1150.44', variant='different metadata'))
    assert old['item']['id'] == row['id'] and old['original']['outcome'] == 'duplicate'
    current = receive(client, invoice_pdf(number='20261031000000000009', amount='10000.00', subtotal='8849.56', tax='1150.44'))
    assert current['item']['id'] == row['id']
    assert len(invoices(client)['invoices']) == 1 and invoices(client)['total_amount'] == '10000.00'


def test_invalid_whole_split_and_colliding_alias_leave_no_partial_changes(scene):
    client, (project, other) = scene
    first = setup_account(client, project)
    second = create(client, 'accounts', project_id=other, name='分配乙')
    row = receive(client, invoice_pdf())['item']
    for parts in ([allocation(first, '2000'), allocation(second, '999')], [allocation(first, '2000'), allocation(first, '1000')], [allocation(first, '3001'), allocation(second, '-1')]):
        assert allocate(client, row, parts).status_code == 400
        assert invoices(client)['invoices'][0] == row
    another = receive(client, invoice_pdf(number='20261031000000000002'))['item']
    assert correct(client, row, [allocation(first, '3000')], invoice_no=another['invoice_no']).status_code == 409
    assert invoices(client)['invoices'][0] == row
    saved = allocate(client, row, [allocation(second, '3000')])
    assert saved.status_code == 200
    assert allocate(client, row, [allocation(first, '3000')]).status_code == 409
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    assert invoices(client)['invoices'][0]['allocations'] == row['allocations']
    replay(client, 'redo', operation)
    assert invoices(client)['invoices'][0]['allocations'][0]['account_id'] == second['id']


def test_observed_corrected_number_survives_other_actor_receipt_and_alias_undo(scene):
    client, (project, _) = scene
    account = setup_account(client, project)
    row = receive(client, invoice_pdf())['item']
    saved = correct(client, row, [allocation(account, '3000')], invoice_no='20261031000000000009')
    assert saved.status_code == 200
    operation = client.get('/api/history/status').json()['undo']
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_other_actor__'))
    observed = receive(client, invoice_pdf(number='20261031000000000009'))
    assert observed['item']['id'] == row['id']
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_actor__'))
    replay(client, 'undo', operation)
    assert invoices(client)['invoices'][0]['invoice_no'] == NUMBER
    repeated = receive(client, invoice_pdf(number='20261031000000000009', variant='new metadata after undo'))
    assert repeated['item']['id'] == row['id']
    assert len(invoices(client)['invoices']) == 1 and invoices(client)['total_amount'] == '3000.00'
    another = receive(client, invoice_pdf(number='20261031000000000002'))['item']
    assert correct(client, another, [allocation(account, '3000')], invoice_no='20261031000000000009').status_code == 409


def test_conflict_resolution_is_reversible_without_mutating_original(scene):
    client, (project, _) = scene
    setup_account(client, project)
    receive(client, invoice_pdf())
    content = invoice_pdf(buyer='冲突合成购买方')
    conflict = receive(client, content)
    row, source = conflict['item'], conflict['original']
    result = client.put(f"/api/m13/invoices/{row['id']}/originals/{source['id']}/resolve", json={'version': row['version'], 'note': '已核对，保留原已确认票据'})
    assert result.status_code == 200, result.text
    reviewed = result.json()['item']['originals'][-1]
    assert reviewed['resolution'] == '已核对，保留原已确认票据'
    assert reviewed['recognized'] == row['originals'][-1]['recognized']
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    assert invoices(client)['invoices'][0]['originals'][-1]['resolution'] is None
    replay(client, 'redo', operation)
    assert invoices(client)['invoices'][0]['originals'][-1]['resolution']
    assert client.get(f"/api/m13/invoices/originals/{source['id']}").content == content
    sheet = load_workbook(BytesIO(client.get('/api/m13/invoices/export').content)).active
    assert sheet['I2'].value is None


def credit(client, red, original, account, amount=None):
    fields = {key: red[key] for key in ('invoice_no', 'invoice_date', 'amount', 'card_no', 'version')}
    if amount is not None: fields['amount'] = amount
    return client.post(f"/api/m13/invoices/{red['id']}/credit", json={**fields,
        'related_invoice_id': original['id'], 'note': '实际收到合成红票', 'allocations': [allocation(account, fields['amount'])]})


def test_credit_followup_undo_redo_limits_parent_correction_and_void(scene):
    client, (project, _) = scene
    account = setup_account(client, project)
    original = receive(client, invoice_pdf())['item']
    red = receive(client, invoice_pdf(number='20261031000000000002', amount='-1000.00', subtotal='-884.96', tax='-115.04'))['item']
    registered = credit(client, red, original, account)
    assert registered.status_code == 200, registered.text
    red = registered.json()['item']
    assert red['kind'] == 'credit' and red['related_invoice_id'] == original['id']
    assert invoices(client)['total_amount'] == '2000.00'
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    assert invoices(client)['total_amount'] == '3000.00'
    replay(client, 'redo', operation)
    original = invoices(client)['invoices'][0]
    assert correct(client, original, [allocation(account, '900')], amount='900').status_code == 400
    assert client.post(f"/api/m13/invoices/{original['id']}/void", json={'version': original['version'], 'date': '2026-10-31', 'note': '重复冲减不允许'}).status_code == 400
    assert invoices(client)['total_amount'] == '2000.00'
    assert credit(client, red, original, account, '-3001').status_code == 400


def test_other_actor_credit_blocks_undoing_an_older_parent_amount(scene):
    client, (project, _) = scene
    account = setup_account(client, project)
    original = receive(client, invoice_pdf())['item']
    # Receive red evidence first, so later parent history is after this barrier.
    red = receive(client, invoice_pdf(number='20261031000000000002', amount='-4000.00', subtotal='-3539.82', tax='-460.18'))['item']
    result = correct(client, original, [allocation(account, '5000')], amount='5000')
    assert result.status_code == 200
    original = result.json()['item']
    operation = client.get('/api/history/status').json()['undo']
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_other_actor__'))
    assert credit(client, red, original, account).status_code == 200
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_actor__'))
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).status_code == 409
    assert invoices(client)['total_amount'] == '1000.00'


def test_misread_positive_can_be_explicitly_corrected_to_credit_and_reparented(scene):
    client, (project, _) = scene
    account = setup_account(client, project)
    first = receive(client, invoice_pdf())['item']
    other = receive(client, invoice_pdf(number='20261031000000000003'))['item']
    misread = receive(client, invoice_pdf(number='20261031000000000002', amount='1000.00', subtotal='884.96', tax='115.04'))['item']
    assert misread['status'] == 'registered' and misread['kind'] == 'normal'
    fixed = credit(client, misread, first, account, '-1000')
    assert fixed.status_code == 200, fixed.text
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    assert invoices(client)['invoices'][-1]['kind'] == 'normal'
    replay(client, 'redo', operation)
    red = invoices(client)['invoices'][-1]
    edited = credit(client, red, other, account, '-2000')
    assert edited.status_code == 200, edited.text
    assert edited.json()['item']['related_invoice_id'] == other['id']
    assert invoices(client)['total_amount'] == '4000.00'
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    red = invoices(client)['invoices'][-1]
    assert red['related_invoice_id'] == first['id'] and red['amount'] == '-1000.00'
    replay(client, 'redo', operation)
    assert invoices(client)['invoices'][-1]['related_invoice_id'] == other['id']


def test_actual_void_keeps_evidence_and_is_distinct_from_correction(scene):
    client, (project, _) = scene
    setup_account(client, project)
    content = invoice_pdf()
    row = receive(client, content)['item']
    result = client.post(f"/api/m13/invoices/{row['id']}/void", json={'version': row['version'], 'date': '2026-10-31', 'note': '合成作废回执'})
    assert result.status_code == 200, result.text
    assert result.json()['item']['status'] == 'voided'
    assert invoices(client)['total_amount'] == '0.00'
    assert client.get(f"/api/m13/invoices/originals/{row['originals'][0]['id']}").content == content
    operation = client.get('/api/history/status').json()['undo']
    replay(client, 'undo', operation)
    assert invoices(client)['total_amount'] == '3000.00'
    replay(client, 'redo', operation)
    assert invoices(client)['total_amount'] == '0.00'
