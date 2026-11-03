"""Controlled HTTP and durable API continuation, without real delivery credentials."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import httpx
import pytest
from app.core.db import session_scope
from app.mod13_oilcard import delivery, invoice_batches
from app.mod13_oilcard.models import OilDeliveryLink
from tests.oilcard_invoice_samples import NUMBER, invoice_pdf
from tests.test_oilcard_archives import scene  # noqa: F401
from tests.test_oilcard_invoices import receive, setup_account, invoices
from tests.test_oilcard_invoice_adjustments import allocation, correct

TOKEN = 'SyntheticLink001'
LINK = 'http://invoice.sinopec.com/' + TOKEN
PDF_URL = 'https://ymhce-vpc3-xls-bmp-invoice.oss-cn-beijing.aliyuncs.com/synthetic.pdf'


def test_real_http_adapter_shape_and_pdf_bytes():
    content = invoice_pdf()
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == delivery.DETAIL_PATH:
            assert request.url.params['invoiceNo'] == TOKEN
            assert request.headers['appid'] == 'invoice'
            return httpx.Response(200, json={'code': '00000000', 'data': {'invoiceNo': NUMBER, 'pdfUrl': PDF_URL}})
        assert request.url.host in delivery.PDF_HOSTS
        return httpx.Response(200, content=content, headers={'Content-Type': 'application/pdf'})
    assert delivery.link_token(LINK) == TOKEN
    assert delivery.download_pdf(TOKEN, transport=httpx.MockTransport(handler)) == (content, NUMBER)
    assert len(requests) == 2


@pytest.mark.parametrize('scenario', ['redirect', 'bad_code', 'untrusted_pdf_host', 'html', 'timeout'])
def test_http_failures_are_bounded_and_do_not_disclose_tokens(scenario):
    requests = []
    def handler(request):
        requests.append(request)
        if scenario == 'redirect': return httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'})
        if scenario == 'timeout': raise httpx.ReadTimeout('secret url ' + TOKEN, request=request)
        if request.url.path == delivery.DETAIL_PATH:
            return httpx.Response(200, json={'code': 'bad' if scenario == 'bad_code' else '00000000', 'data': {
                'invoiceNo': NUMBER, 'pdfUrl': 'https://example.invalid/private' if scenario == 'untrusted_pdf_host' else PDF_URL}})
        return httpx.Response(200, text='<html>not a PDF</html>')
    with pytest.raises(delivery.DeliveryError) as failure:
        delivery.download_pdf(TOKEN, transport=httpx.MockTransport(handler))
    assert TOKEN not in str(failure.value)
    assert all(r.url.host in delivery.PDF_HOSTS for r in requests)
    if scenario in ('redirect', 'bad_code', 'untrusted_pdf_host', 'timeout'): assert len(requests) == 1


def batch(client, links, request_id=None):
    response = client.post('/api/m13/invoice-batches', json={'request_id': request_id or str(uuid4()), 'links': links})
    assert response.status_code == 200, response.text
    return response.json()['batch']


def run(client, b, item):
    response = client.post(f"/api/m13/invoice-batches/{b['id']}/items/{item['id']}/run")
    assert response.status_code == 200, response.text
    return response.json()['batch']


def test_per_item_results_same_receipt_no_long_transaction_and_cross_batch_reuse(scene, monkeypatch):
    client, (project, _) = scene
    setup_account(client, project)
    links = [LINK, 'https://invoice.sinopec.com/SyntheticLink002', 'https://invoice.sinopec.com/SyntheticLink003', LINK, 'https://invalid.example/nope']
    req = str(uuid4())
    b = batch(client, '\n'.join(links), req)
    assert batch(client, '\n'.join(links), req)['id'] == b['id']
    assert client.post('/api/m13/invoice-batches', json={'request_id': req, 'links': LINK}).status_code == 409
    assert TOKEN not in str(b) and 'http://' not in str(b)
    active, calls = [], []
    real_scope = invoice_batches.session_scope
    @contextmanager
    def observed_scope():
        active.append(True)
        try:
            with real_scope() as session: yield session
        finally: active.pop()
    monkeypatch.setattr(invoice_batches, 'session_scope', observed_scope)
    def download(token):
        assert not active, '下载不得持有批次写事务'
        calls.append(token)
        if token.endswith('002'): return invoice_pdf(number='20261031000000000002', card='45678'), '20261031000000000002'
        if token.endswith('003'): raise delivery.DeliveryError('受控下载失败，可续办')
        return invoice_pdf(), NUMBER
    monkeypatch.setattr(delivery, 'download_pdf', download)
    for item in b['items']:
        b = run(client, b, item)
    assert [i['status'] for i in b['items']] == ['success', 'pending', 'failed', 'duplicate', 'failed']
    assert len(calls) == 3
    assert invoices(client)['total_amount'] == '3000.00'
    reused = batch(client, LINK)
    assert reused['items'][0]['status'] == 'duplicate'
    run(client, reused, reused['items'][0])
    assert len(calls) == 3
    monkeypatch.setattr(delivery, 'download_pdf', lambda token: (invoice_pdf(number='20261031000000000003'), '20261031000000000003'))
    b = run(client, b, b['items'][2])
    assert b['items'][2]['status'] == 'success' and invoices(client)['total_amount'] == '6000.00'


def test_expired_claim_fences_old_worker_and_resumes(scene):
    client, (project, _) = scene
    setup_account(client, project)
    b = batch(client, LINK)
    item = b['items'][0]
    with session_scope() as session:
        old = invoice_batches._claim(session, b['id'], item['id'])
    current = client.get(f"/api/m13/invoice-batches/{b['id']}").json()
    assert current['items'][0]['status'] == 'working' and not current['items'][0]['can_run']
    with session_scope() as session:
        session.get(OilDeliveryLink, old[0]).claimed_at = datetime.now() - timedelta(minutes=4)
    assert client.get(f"/api/m13/invoice-batches/{b['id']}").json()['items'][0]['status'] == 'uncertain'
    with session_scope() as session:
        new = invoice_batches._claim(session, b['id'], item['id'])
    from app.mod13_oilcard.invoice_pdf import recognize_pdf
    content = invoice_pdf()
    with session_scope() as session:
        assert not invoice_batches._complete(session, old[0], old[2], content, recognize_pdf(content))
    assert invoices(client)['invoices'] == []
    with session_scope() as session:
        assert invoice_batches._complete(session, new[0], new[2], content, recognize_pdf(content))
    assert invoices(client)['total_amount'] == '3000.00'


def test_lost_completion_reply_is_reliably_read_and_never_downloaded_twice(scene, monkeypatch):
    client, (project, _) = scene
    setup_account(client, project)
    b = batch(client, LINK)
    calls = []
    monkeypatch.setattr(delivery, 'download_pdf', lambda token: (calls.append(token) or invoice_pdf(), NUMBER))
    original_read = invoice_batches.read
    monkeypatch.setattr(invoice_batches, 'read', lambda *args: (_ for _ in ()).throw(RuntimeError('受控回执读取中断')))
    with pytest.raises(RuntimeError): run(client, b, b['items'][0])
    monkeypatch.setattr(invoice_batches, 'read', original_read)
    recovered = client.get(f"/api/m13/invoice-batches/{b['id']}").json()
    assert recovered['items'][0]['status'] == 'success'
    assert client.get(f"/api/m13/invoice-batches/request/{b['request_id']}").json()['batch']['id'] == b['id']
    run(client, recovered, recovered['items'][0])
    assert len(calls) == 1 and invoices(client)['total_amount'] == '3000.00'


def test_current_confirmation_resolution_and_void_replace_initial_receipt_reason(scene, monkeypatch):
    client, (project, _) = scene
    account = setup_account(client, project)
    content = invoice_pdf(card='45678')
    monkeypatch.setattr(delivery, 'download_pdf', lambda token: (content, NUMBER))
    b = batch(client, LINK)
    b = run(client, b, b['items'][0])
    assert b['items'][0]['status'] == 'pending'
    row = invoices(client)['invoices'][0]
    corrected = correct(client, row, [allocation(account, '3000')], card_no=None)
    assert corrected.status_code == 200
    current = client.get(f"/api/m13/invoice-batches/{b['id']}").json()['items'][0]
    assert current['status'] == 'success' and '不可靠' not in current['message']
    digest = sha256(content).hexdigest()
    assert client.get('/api/m13/invoices/receipts/' + digest).json()['receipt_status'] == 'duplicate'
    row = corrected.json()['item']
    voided = client.post(f"/api/m13/invoices/{row['id']}/void", json={'version': row['version'], 'date': '2026-10-31', 'note': '合成作废'})
    assert voided.status_code == 200
    current = client.get(f"/api/m13/invoice-batches/{b['id']}").json()['items'][0]
    assert current['status'] == 'success' and '作废' in current['message']
    assert '作废' in client.get('/api/m13/invoices/receipts/' + digest).json()['receipt_message']


def test_resolved_conflict_is_currently_complete_on_repeated_link_and_hash(scene, monkeypatch):
    client, (project, _) = scene
    setup_account(client, project)
    receive(client, invoice_pdf())
    content = invoice_pdf(buyer='合成冲突购买方')
    conflict = receive(client, content)
    monkeypatch.setattr(delivery, 'download_pdf', lambda token: (content, NUMBER))
    b = batch(client, LINK)
    b = run(client, b, b['items'][0])
    assert b['items'][0]['status'] == 'pending'
    row, source = conflict['item'], conflict['original']
    resolved = client.put(f"/api/m13/invoices/{row['id']}/originals/{source['id']}/resolve", json={'version': row['version'], 'note': '已核对保留原票'})
    assert resolved.status_code == 200
    current = client.get(f"/api/m13/invoice-batches/{b['id']}").json()['items'][0]
    assert current['status'] == 'duplicate' and '已核对' in current['message']
    receipt = client.get('/api/m13/invoices/receipts/' + sha256(content).hexdigest()).json()
    assert receipt['original']['resolution'] == '已核对保留原票'
    assert receipt['receipt_status'] == 'duplicate' and '已核对' in receipt['receipt_message']
