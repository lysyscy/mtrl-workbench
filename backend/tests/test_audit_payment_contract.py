"""325/327：真实HTTP与PG短事务；外层事务回滚所有测试写入。"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core import db
from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow import service as flows
from app.mod05_flow.models import PaymentFlow
from app.mod11_jc.models import JcContract
from tests._auth import TestClient


@pytest.fixture
def http_case(monkeypatch):
    token = uuid4().hex
    key = f'__自检仓_325_327_{token}__'
    engine = db.get_engine()
    assert engine.dialect.name == 'postgresql'
    with engine.connect() as connection:
        outer = connection.begin()
        assert connection.execute(text('select current_database()')).scalar_one() == 'mtrl_workbench_test'
        factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False,
                               join_transaction_mode='create_savepoint')
        monkeypatch.setattr(db, '_session_factory', factory)
        try:
            with db.session_scope() as s:
                project = Project(warehouse_name=key, name_full=key)
                s.add(project); s.flush()
                notices = [PaymentNotice(ph_id=f'__325_{token}_{i}', bill_no=f'325-{token}-{i}',
                           doc_date='2026-10-14', approve_status='已批', amount_approved=100,
                           ownership_id=project.id, stat_paid=0) for i in range(2)]
                s.add_all(notices); s.flush()
                ids = [n.id for n in notices]
                pid = project.id
            client = TestClient(create_app(), raise_server_exceptions=False)
            try:
                yield client, ids, pid, key
            finally:
                client.close()
        finally:
            assert outer.is_active, '路由提交不得提交测试外层事务'
            outer.rollback()
        with Session(connection) as s:
            assert not s.scalar(select(func.count()).select_from(Project).where(Project.warehouse_name == key))
            assert not s.scalar(select(func.count()).select_from(PaymentNotice)
                                .where(PaymentNotice.ph_id.like(f'__325_{token}_%')))


def _pay(client, ids, **fields):
    return client.post('/api/m03/actions/batch-pay', json={
        'ids': ids, 'pay_date': '2026-10-14', **fields})


def _paid(ids):
    with db.session_scope() as s:
        return [(f.notice_id, f.amount, f.request_id) for f in s.scalars(
            select(PaymentFlow).where(PaymentFlow.notice_id.in_(ids)).order_by(PaymentFlow.id))]


def test_http_duplicate_full_payment_preserves_first_selected_order(http_case):
    client, ids, _, _ = http_case
    a, b = ids
    rid = uuid4().hex
    response = _pay(client, [b, -325, a, b, a], request_id=rid)
    assert response.status_code == 200
    result = response.json()
    assert result['ok'] and result['created'] == [b, a] and result['count'] == 2
    assert _paid(ids) == [(b, Decimal('100.00'), rid), (a, Decimal('100.00'), rid)]
    shown = client.get('/api/m03/notice-list', params={'period': ''}).json()['items']
    selected = [r for r in shown if r['notice_id'] in ids]
    assert len(selected) == 2
    assert all(Decimal(r['amount_paid']) == 100 and Decimal(r['pay_amount']) == 0
               and Decimal(r['stat_paid']) == 100 and not r['is_overpaid'] for r in selected)


@pytest.mark.parametrize('state,draft', [
    ('未批', {}), ('jc', {}), ('', {'amount': '100.01'}),
    ('', {'amount': '0'}), ('', {'pay_method': '非法'}), ('', {'pay_method': '其他'}),
])
def test_http_payment_gates_reject_whole_batch(http_case, state, draft):
    client, ids, _, _ = http_case
    with db.session_scope() as s:
        row = s.get(PaymentNotice, ids[1])
        if state == 'jc':
            row.category = state
        elif state:
            row.approve_status = state
    response = _pay(client, [ids[0], ids[1], ids[1]], drafts={str(ids[1]): draft})
    assert response.status_code == 200
    assert not response.json()['ok'] and response.json()['created'] == []
    assert _paid(ids) == []


def test_http_payment_request_id_and_exception_rollback(http_case, monkeypatch):
    client, ids, _, _ = http_case
    original = flows.create_flow
    calls = []

    def fail_second(s, **fields):
        calls.append(fields['notice_id'])
        if len(calls) == 2:
            raise RuntimeError('325模拟第二条写入失败')
        return original(s, **fields)

    monkeypatch.setattr(flows, 'create_flow', fail_second)
    assert _pay(client, ids).status_code == 500
    assert calls == ids and _paid(ids) == []
    with db.session_scope() as s:
        assert all(s.get(PaymentNotice, i).stat_paid == 0 for i in ids)
    monkeypatch.setattr(flows, 'create_flow', original)
    rid = uuid4().hex
    payload = {'drafts': {str(ids[0]): {'amount': '10'}}, 'request_id': rid}
    assert _pay(client, [ids[0], ids[0]], **payload).json()['created'] == [ids[0]]
    duplicate = _pay(client, [ids[0], ids[0]], **payload).json()
    assert not duplicate['ok'] and '重复提交' in duplicate['message']
    assert _paid(ids) == [(ids[0], Decimal('10.00'), rid)]


def test_http_manual_contract_save_and_readback(http_case):
    client, _, pid, key = http_case
    response = client.post('/api/m11/add', json={
        'project_key': key, 'contract_date': '2026-10-14', 'material_name': '327钢材',
        'supplier': '327供应商', 'contract_amt': '123.45'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['ok']
    cid = result['id']
    with db.session_scope() as s:
        saved = s.get(JcContract, cid)
        assert saved.project_id == pid and saved.contract_amt == Decimal('123.45')
    listing = client.get('/api/m11/list', params={'project': key}).json()
    assert listing['count'] == 1
    assert listing['rows'][0]['id'] == cid and listing['rows'][0]['project_key'] == key
    assert Decimal(listing['rows'][0]['contract_amt']) == Decimal('123.45')
    detail = client.get('/api/m11/detail', params={'id': cid}).json()
    assert detail['ok'] and detail['data']['id'] == cid
    assert detail['data']['material'] == '327钢材'
    assert Decimal(detail['data']['contract_amt']) == Decimal('123.45')


def test_http_unknown_project_does_not_create_contract(http_case):
    client, _, pid, key = http_case
    with db.session_scope() as s:
        before = s.scalar(select(func.count()).select_from(JcContract))
    response = client.post('/api/m11/add', json={'project_key': key + '_missing', 'contract_amt': '1'})
    assert response.status_code == 200
    assert not response.json()['ok'] and '找不到项目' in response.json()['message']
    with db.session_scope() as s:
        assert s.scalar(select(func.count()).select_from(JcContract)) == before
        assert not s.scalar(select(func.count()).select_from(JcContract).where(JcContract.project_id == pid))
