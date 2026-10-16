"""Authenticated LAN export and method-write boundary; isolated data only."""
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from tests.acc_plugin import acc
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import session as SESS
from app.mod03_notice import plan_audit_api as API
from app.mod03_notice.plan_audit_methods import validate_changes
from app.mod15_user.models import UserAccount


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    UserAccount.__table__.create(engine)
    with Session(engine) as s:
        s.add_all([UserAccount(account='active', name='测试', status='在用'),
                   UserAccount(account='disabled', status='已停用'),
                   UserAccount(account='deleted', status='在用', deleted_at=datetime.now())])
        s.commit()

    @contextmanager
    def scope():
        with Session(engine) as s:
            yield s

    monkeypatch.setattr(API, 'session_scope', scope)
    monkeypatch.setattr(SESS, 'secret', lambda: b'isolated-test-secret')
    app = FastAPI()
    app.include_router(API.router)
    with TestClient(app) as c:
        yield c
    engine.dispose()


@acc()
def test_snapshot_rejects_anonymous_forged_disabled_deleted_before_export(client, monkeypatch):
    calls = []
    monkeypatch.setattr(API.DATA, 'capture', lambda: calls.append(True))
    for account, status in [('', 401), ('forged', 401), ('disabled', 403), ('deleted', 403)]:
        client.cookies.clear()
        if account:
            client.cookies.set(SESS.COOKIE_NAME, 'forged' if account == 'forged' else SESS.make(account))
        assert client.get('/api/m03/plan-audit/snapshot').status_code == status
    assert calls == []


@acc()
def test_snapshot_keeps_complete_scope_and_no_cache(client, monkeypatch):
    payload = dict(schema=1, complete=True, projects=[{'id': 1}], notices=[{'id': 2}],
                   captured_at='2026-10-15T00:00:00+08:00', scope='全部月份与生效流水')
    monkeypatch.setattr(API.DATA, 'capture', lambda: payload)
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('active'))
    response = client.get('/api/m03/plan-audit/snapshot')
    assert response.status_code == 200 and response.json() == payload
    assert response.headers['Cache-Control'] == 'no-store'


def preview():
    return dict(schema=1, source_sha256='a'*64, snapshot={'database_fingerprint': 'b'*64}, changes=[
        dict(id=1, bill_no='D1', ownership_id=1, source_row=4, old='', new='承兑',
             approved='100', paid='20', flow_amount='100', planned_amount='80')])


@acc()
@pytest.mark.parametrize('mutation', ['shape', 'source', 'fingerprint', 'duplicates', 'amount', 'method', 'row'])
def test_write_metadata_rejected_before_any_transaction(client, monkeypatch, mutation):
    p = preview()
    if mutation == 'shape': p = []
    elif mutation == 'source': p.pop('source_sha256')
    elif mutation == 'fingerprint': p['snapshot'] = {}
    elif mutation == 'duplicates': p['changes'] *= 2
    elif mutation == 'amount': p['changes'][0]['planned_amount'] = '81'
    elif mutation == 'method': p['changes'][0]['new'] = '现金'
    elif mutation == 'row': p['changes'][0]['source_row'] = 0
    monkeypatch.setattr(API, 'get_engine', lambda: pytest.fail('invalid preview reached database'))
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('active'))
    raw = json.dumps(p)
    response = client.post('/api/m03/plan-audit/methods', json={
        'preview_json': raw, 'approved_sha256': sha256(raw.encode()).hexdigest()})
    assert response.status_code == 409


@acc()
def test_method_endpoint_binds_approved_bytes_and_current_system(client, monkeypatch):
    p = preview()
    validate_changes(p)
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('active'))
    raw = json.dumps(p)
    response = client.post('/api/m03/plan-audit/methods', json={'preview_json': raw, 'approved_sha256': 'c'*64})
    assert response.status_code == 409
    monkeypatch.setattr(API, 'get_engine', lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))
    monkeypatch.setattr(API.DATA, 'database_fingerprint', lambda _: 'c'*64)
    response = client.post('/api/m03/plan-audit/methods', json={
        'preview_json': raw, 'approved_sha256': sha256(raw.encode()).hexdigest()})
    assert response.status_code == 409 and '快照不符' in response.json()['detail']


@acc()
def test_successful_method_endpoint_uses_atomic_update_and_returns_bound_receipt(client, monkeypatch):
    calls = []

    class Conn:
        def exec_driver_sql(self, sql):
            calls.append(sql)

    class Engine:
        dialect = SimpleNamespace(name='postgresql')

        @contextmanager
        def begin(self):
            yield Conn()

    monkeypatch.setattr(API, 'get_engine', Engine)
    monkeypatch.setattr(API.DATA, 'database_fingerprint', lambda _: 'b'*64)
    monkeypatch.setattr(API, 'apply_changes', lambda conn, p: calls.append(p['changes']))
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('active'))
    raw = json.dumps(preview(), ensure_ascii=False)
    digest = sha256(raw.encode()).hexdigest()
    response = client.post('/api/m03/plan-audit/methods', json={'preview_json': raw, 'approved_sha256': digest})
    assert response.status_code == 200
    assert response.json() == dict(status='committed', count=1, preview_sha256=digest, source_sha256='a'*64)
    assert response.headers['Cache-Control'] == 'no-store'
    assert len(calls) == 3 and calls[-1] == preview()['changes']
