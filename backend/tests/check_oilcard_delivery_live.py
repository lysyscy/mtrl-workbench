"""Explicit authorized private-link drill; run only via backend_verify."""
from hashlib import sha256
import json
import logging
import os
from pathlib import Path

from app.mod13_oilcard import delivery
from tests.test_oilcard_archives import scene  # noqa: F401
from tests.test_oilcard_delivery import batch, run


def test_authorized_delivery_adapter_receipt_and_cross_batch_reuse(scene, monkeypatch):
    client, _ = scene
    path = Path(os.environ['MTRL_OILCARD_DELIVERY_INPUT']).resolve(strict=True)
    source = json.loads(path.read_text(encoding='utf-8'))
    logging.getLogger('httpx').setLevel(logging.WARNING)
    actual = delivery.download_pdf
    calls = []
    def counted(token):
        calls.append(True)
        return actual(token)
    monkeypatch.setattr(delivery, 'download_pdf', counted)
    b = batch(client, source['url'])
    b = run(client, b, b['items'][0])
    item = b['items'][0]
    assert item['status'] in ('success', 'pending')
    original = client.get(f"/api/m13/invoices/originals/{item['original_id']}")
    assert original.status_code == 200 and original.content.startswith(b'%PDF-')
    expected = (path.parent / 'received-real.pdf').read_bytes()
    assert original.content == expected and sha256(original.content).hexdigest() == sha256(expected).hexdigest()
    again = batch(client, source['url'])
    run(client, again, again['items'][0])
    assert len(calls) == 1
    assert len(client.get('/api/m13/invoices').json()['invoices']) == 1
