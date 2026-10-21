"""Retired ledger pages must not receive redirects after a committed write."""
from contextlib import nullcontext

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import MustReportError
from app.mod05_flow import router as routes


@pytest.mark.parametrize('path,body,method', [
    ('/m05/opening', {'category': 'material', 'project_id': 1, 'cutoff_ym': '2025-11'}, 'upsert_opening'),
    ('/m05/opening/delete', {'opening_id': 1}, 'delete_opening'),
    ('/m05/ledger/remark', {'category': 'material', 'project_id': 1, 'ym': '2026-01'}, 'set_remark'),
])
def test_form_write_returns_receipt_without_visiting_retired_page(monkeypatch, path, body, method):
    app = FastAPI()
    app.include_router(routes.router)
    writes = []
    monkeypatch.setattr(routes, 'session_scope', lambda: nullcontext(None))
    monkeypatch.setattr(routes.repo, method, lambda *a, **kw: writes.append(kw) or 1)
    with TestClient(app) as client:
        response = client.post(path, data=body)
    assert len(writes) == 1
    assert response.status_code == 200, response.text
    assert response.json()['ok'] is True
    assert not response.history


def test_rejected_opening_has_no_success_receipt(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, 'session_scope', lambda: nullcontext(None))
    def reject(*a, **kw):
        raise MustReportError('金额不能为负数')
    monkeypatch.setattr(routes.repo, 'upsert_opening', reject)
    with TestClient(app) as client:
        response = client.post('/m05/opening', data={'category': 'material', 'project_id': 1, 'cutoff_ym': '2025-11'})
    assert response.status_code == 400
    assert response.json()['message'] == '金额不能为负数'
