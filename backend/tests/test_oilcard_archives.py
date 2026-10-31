"""通过真实 API/事务核油卡档案、当前关联及安全操作历史。"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import session as SESS
from app.core.db import session_scope
from app.main import create_app
from app.mod01_projects.models import Project
from app.mod13_oilcard.models import OilAccount, OilCard


@pytest.fixture
def scene(rollback_db, monkeypatch):
    from app import history_api
    monkeypatch.setattr(SESS, 'secret', lambda: b'oilcard-isolated-test-only')
    monkeypatch.setattr(history_api, 'active_account', lambda s, identity: object())
    with session_scope() as session:
        first = Project(project_type='normal', name_full='油卡测试甲', warehouse_name='__oilcard_a__', disp='甲')
        second = Project(project_type='normal', name_full='油卡测试乙', warehouse_name='__oilcard_b__', disp='乙', status='archived')
        session.add_all([first, second]); session.flush()
        projects = [first.id, second.id]
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_actor__'))
        yield client, projects


def create(client, path, **fields):
    result = client.post(f'/api/m13/{path}', json={'request_id': str(uuid4()), **fields})
    assert result.status_code == 200, result.text
    assert result.headers.get('X-Operation-History') == 'recorded'
    return result.json()['item']


def edit(client, path, row, **fields):
    data = {key: value for key, value in row.items() if key not in ('id', 'request_id')}
    result = client.put(f"/api/m13/{path}/{row['id']}", json={**data, **fields})
    assert result.status_code == 200, result.text
    assert result.headers.get('X-Operation-History') == 'recorded'
    return result.json()['item']


def read(client):
    response = client.get('/api/m13/archives')
    assert response.status_code == 200
    return response.json()


def test_roundtrip_multiple_accounts_unknown_cards_and_independent_archive(scene):
    client, (project_a, project_b) = scene
    primary = create(client, 'cards', card_no='0000123456789012', kind='primary', remark='主卡圈存资料')
    secondary = create(client, 'cards', card_no='0001234567890123456', parent_card_id=primary['id'], remark='副卡资料')
    unknown = create(client, 'cards', card_no=None)
    another_unknown = create(client, 'cards', card_no=None)
    assert unknown['id'] != another_unknown['id']
    a = create(client, 'accounts', name='车辆一', project_id=project_a, card_id=secondary['id'], remark='账户独立备注')
    b = create(client, 'accounts', name='车辆二', project_id=project_a, card_id=secondary['id'])
    c = create(client, 'accounts', name='乙用途', project_id=project_b, card_id=secondary['id'])
    no_card = create(client, 'accounts', name='卡号待核', project_id=project_a)
    assert len({a['id'], b['id'], c['id'], no_card['id']}) == 4
    a = edit(client, 'accounts', a, status='archived')
    with session_scope() as session:
        assert session.get(Project, project_a).status == 'active'
        assert session.get(Project, project_b).status == 'archived'
        assert session.get(OilAccount, c['id']).status == 'active'
    a = edit(client, 'accounts', a, status='active', project_id=project_b, card_id=unknown['id'])
    data = read(client)
    assert next(row for row in data['cards'] if row['id'] == primary['id'])['card_no'] == '0000123456789012'
    assert next(row for row in data['cards'] if row['id'] == secondary['id'])['card_no'] == '0001234567890123456'
    assert next(row for row in data['accounts'] if row['id'] == a['id']) == a
    assert a['remark'] == '账户独立备注'
    assert next(row for row in data['cards'] if row['id'] == primary['id'])['remark'] == '主卡圈存资料'
    trail = client.get(f"/api/m13/accounts/{a['id']}/assignments").json()
    assert [(row['project_id'], row['card_id']) for row in trail] == [(project_a, secondary['id']), (project_b, unknown['id'])]
    assert all(row['changed_by'] for row in trail)
    impact = client.get(f'/api/m01/projects/{project_a}/delete-impact').json()
    assert not impact['can_delete']
    assert any(group['label'] == '油卡关联历史' and group['count'] for group in impact['groups'])


def test_auth_idempotency_text_number_and_versions(scene):
    client, (project_a, _) = scene
    request_id = str(uuid4())
    fields = {'request_id': request_id, 'card_no': '0001234567890123456'}
    client.cookies.clear()
    before = read(client)
    assert client.post('/api/m13/cards', json=fields).status_code == 401
    assert read(client) == before
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_actor__'))
    first = client.post('/api/m13/cards', json=fields).json()['item']
    duplicate = client.post('/api/m13/cards', json=fields).json()['item']
    assert first == duplicate
    assert len(read(client)['cards']) == 1
    assert client.post('/api/m13/cards', json={'request_id': str(uuid4()), 'card_no': 1234567890123456}).status_code == 422
    account_request = {'request_id': str(uuid4()), 'name': '往返测试', 'project_id': project_a, 'card_id': first['id']}
    account = client.post('/api/m13/accounts', json=account_request).json()['item']
    assert client.post('/api/m13/accounts', json=account_request).json()['item'] == account
    assert len(client.get(f"/api/m13/accounts/{account['id']}/assignments").json()) == 1
    updated = edit(client, 'accounts', account, remark='其他窗口已保存')
    stale = {key: value for key, value in account.items() if key not in ('id', 'request_id')}
    response = client.put(f"/api/m13/accounts/{account['id']}", json={**stale, 'name': '过期覆盖'})
    assert response.status_code == 409
    assert next(a for a in read(client)['accounts'] if a['id'] == account['id']) == updated


def test_invalid_management_relationship_does_not_change_archives(scene):
    client, (project_a, _) = scene
    primary = create(client, 'cards', kind='primary')
    secondary = create(client, 'cards', parent_card_id=primary['id'])
    create(client, 'accounts', name='关联副卡', project_id=project_a, card_id=secondary['id'])
    before = read(client)
    assert client.post('/api/m13/accounts', json={'request_id': str(uuid4()), 'name': '不能挂主卡', 'project_id': project_a, 'card_id': primary['id']}).status_code == 400
    for row, fields in [(primary, {'kind': 'secondary'}), (secondary, {'kind': 'primary', 'parent_card_id': None}), (secondary, {'parent_card_id': secondary['id']})]:
        payload = {key: value for key, value in row.items() if key not in ('id', 'request_id')}
        assert client.put(f"/api/m13/cards/{row['id']}", json={**payload, **fields}).status_code == 400
    assert read(client) == before


def test_account_creation_and_association_change_safe_undo_redo(scene):
    client, (project_a, project_b) = scene
    card = create(client, 'cards', card_no='0123456789012345')
    account = create(client, 'accounts', name='可撤销账户', project_id=project_a, card_id=card['id'])
    operation = client.get('/api/history/status').json()['undo']
    assert operation['count'] == 2
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert not read(client)['accounts']
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    account = next(a for a in read(client)['accounts'] if a['id'] == account['id'])
    changed = edit(client, 'accounts', account, project_id=project_b, remark='新备注')
    operation = client.get('/api/history/status').json()['undo']
    assert operation['count'] == 2
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert next(a for a in read(client)['accounts'] if a['id'] == account['id']) == account
    assert len(client.get(f"/api/m13/accounts/{account['id']}/assignments").json()) == 1
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert next(a for a in read(client)['accounts'] if a['id'] == account['id']) == changed
    with session_scope() as session:
        assert session.scalar(select(OilCard).where(OilCard.id == card['id'])).card_no == '0123456789012345'
