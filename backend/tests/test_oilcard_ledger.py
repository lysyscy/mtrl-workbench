"""从真实业务API检查统一金额、历史归属、关联退款和安全撤销。"""
from uuid import uuid4

import pytest

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod13_oilcard.ledger import stage_opening
from tests.test_oilcard_archives import scene, create, edit, read  # noqa: F401


def entry(client, account, amount, **values):
    response = client.post('/api/m13/ledger/entries', json={'request_id': str(uuid4()),
        'account_id': account['id'], 'project_id': account['project_id'], 'amount': amount, **values})
    assert response.status_code == 200, response.text
    assert response.headers.get('X-Operation-History') == 'recorded'
    return response.json()['item']


def update(client, row, **values):
    fields = {key: row[key] for key in ('kind', 'account_id', 'project_id', 'date_text', 'amount', 'remark', 'version')}
    response = client.put(f"/api/m13/ledger/entries/{row['id']}", json={**fields, **values})
    assert response.status_code == 200, response.text
    return response.json()['item']


def ledger(client):
    response = client.get('/api/m13/ledger')
    assert response.status_code == 200
    return response.json()


def summary(client):
    response = client.get('/api/m13/reconciliation')
    assert response.status_code == 200
    return response.json()


def test_unified_money_dates_and_adjustments(scene):
    client, (project, _) = scene
    primary = create(client, 'cards', kind='primary', remark='主卡备注')
    card = create(client, 'cards', parent_card_id=primary['id'])
    account = create(client, 'accounts', project_id=project, name='统一金额', card_id=card['id'], remark='账户备注')
    first = entry(client, account, '¥ 10,000.00', date_text='2026-10-31', remark='充值备注')
    added = entry(client, account, '200', kind='adjustment', date_text='原始数据', remark='调整增加')
    zero = entry(client, account, '0', kind='adjustment', date_text='')
    assert first['amount'] == '10000.00' and first['entry_date'] == '2026-10-31'
    assert added['date_text'] == '原始数据' and added['entry_date'] is None
    assert zero['amount'] == '0.00' and zero['entry_date'] is None
    assert ledger(client)['total_amount'] == '10200.00'
    reconciliation = summary(client)
    assert reconciliation['total_amount'] == '10200.00'
    assert reconciliation['rows'][0]['primary_card_id'] == primary['id']
    assert reconciliation['rows'][0]['recharge_amount'] == '10200.00'
    entry(client, account, '-20.25', kind='adjustment')
    assert summary(client)['total_amount'] == '10179.75'
    data = read(client)
    assert data['cards'][0]['remark'] == '主卡备注'
    assert data['accounts'][0]['remark'] == '账户备注'
    assert ledger(client)['entries'][0]['remark'] == '充值备注'


def test_reject_invalid_money_pairing_stale_version_and_duplicate_request(scene):
    client, (project, other) = scene
    account = create(client, 'accounts', project_id=project, name='配套账户')
    payload = {'request_id': str(uuid4()), 'project_id': project, 'account_id': account['id'], 'amount': '100'}
    for invalid in ('0', '-1', 'NaN', '1e100', ''):
        assert client.post('/api/m13/ledger/entries', json={**payload, 'amount': invalid}).status_code == 400
    assert client.post('/api/m13/ledger/entries', json={**payload, 'amount': 100}).status_code == 422
    assert client.post('/api/m13/ledger/entries', json={**payload, 'project_id': other}).status_code == 400
    assert not ledger(client)['entries']
    first = client.post('/api/m13/ledger/entries', json=payload).json()['item']
    assert client.post('/api/m13/ledger/entries', json=payload).json()['item'] == first
    assert client.post('/api/m13/ledger/entries', json={**payload, 'amount': '101'}).status_code == 409
    assert len(ledger(client)['entries']) == 1
    changed = update(client, first, amount='120')
    stale = {key: first[key] for key in ('kind', 'account_id', 'project_id', 'date_text', 'amount', 'remark', 'version')}
    assert client.put(f"/api/m13/ledger/entries/{first['id']}", json={**stale, 'amount': '130'}).status_code == 409
    assert ledger(client)['entries'] == [changed]
    client.cookies.clear()
    assert client.post('/api/m13/ledger/entries', json={**payload, 'request_id': str(uuid4())}).status_code == 401
    assert ledger(client)['entries'] == [changed]


def test_current_archive_changes_do_not_reassign_old_accounting(scene):
    client, (project, other) = scene
    card = create(client, 'cards', card_no='0001234567890123456')
    next_card = create(client, 'cards')
    account = create(client, 'accounts', project_id=project, name='原账户', card_id=card['id'])
    same_card = create(client, 'accounts', project_id=project, name='另一账户', card_id=card['id'])
    first = entry(client, account, '100', date_text='往年记录')
    entry(client, same_card, '20')
    moved = edit(client, 'accounts', account, project_id=other, card_id=next_card['id'], status='archived')
    first = update(client, first, amount='150', remark='旧账金额更正')
    assert (first['project_id'], first['card_id']) == (project, card['id'])
    assert summary(client)['total_amount'] == '170.00'
    allocation = next(row for row in summary(client)['rows'] if row['account_id'] == account['id'] and not row['current'])
    assert allocation['project_id'] == project and allocation['total_amount'] == '150.00'
    entry(client, moved, '30')
    assert summary(client)['total_amount'] == '200.00'
    # 明确改项目/账户时只改所选记录，不改同卡另一账户和旧明细。
    reassigned = update(client, first, project_id=other, account_id=moved['id'])
    assert reassigned['card_id'] == next_card['id'] and reassigned['project_id'] == other
    assert next(row for row in ledger(client)['entries'] if row['account_id'] == same_card['id'])['amount'] == '20.00'


def test_linked_refund_and_correction_undo_redo_are_real_transactions(scene):
    client, (project, _) = scene
    account = create(client, 'accounts', project_id=project, name='退款账户')
    original = entry(client, account, '1000')
    request = {'request_id': str(uuid4()), 'original_id': original['id'], 'amount': '125.50', 'date_text': '退回待核日期', 'remark': '实际退款'}
    result = client.post('/api/m13/ledger/refunds', json=request)
    assert result.status_code == 200
    refund = result.json()['item']
    assert refund['amount'] == '-125.50' and refund['related_entry_id'] == original['id']
    assert client.post('/api/m13/ledger/refunds', json=request).json()['item'] == refund
    assert client.post('/api/m13/ledger/refunds', json={**request, 'amount': '130'}).status_code == 409
    assert ledger(client)['entries'][0] == original
    assert summary(client)['total_amount'] == '874.50'
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert summary(client)['total_amount'] == '1000.00'
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert summary(client)['total_amount'] == '874.50'
    changed = update(client, original, amount='1100')
    assert summary(client)['total_amount'] == '974.50'
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert summary(client)['total_amount'] == '874.50'
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert ledger(client)['entries'][0] == changed
    # 退款保固定类型及原记录，不能经普通下拉变成另一类账。
    fields = {key: refund[key] for key in ('kind', 'account_id', 'project_id', 'date_text', 'amount', 'remark', 'version')}
    assert client.put(f"/api/m13/ledger/entries/{refund['id']}", json={**fields, 'kind': 'adjustment'}).status_code == 400


def test_only_confirmed_openings_enter_full_history_once_without_made_up_dates(scene):
    client, (project, _) = scene
    account = create(client, 'accounts', project_id=project, name='期初账户')
    source = {'source_key': 'isolated:activity:row-1', 'source_note': '合成期初核对依据',
        'project_id': project, 'account_id': account['id'], 'amount': '1000',
        'original_date_text': '原始数据', 'cutoff_ym': '2025-12', 'confirmed': True}
    with session_scope() as session:
        first = stage_opening(session, **source)
        assert stage_opening(session, **source).id == first.id
        stage_opening(session, source_key='isolated:unconfirmed', source_note='未裁定样例',
            project_id=project, account_id=account['id'], amount='9000', original_date_text='日期不明')
    with pytest.raises(MustReportError, match='内容不同'):
        with session_scope() as session:
            stage_opening(session, **{**source, 'amount': '2000'})
    with pytest.raises(MustReportError, match='截至月份'):
        with session_scope() as session:
            stage_opening(session, **{**source, 'source_key': 'bad-cutoff', 'cutoff_ym': None})
    entry(client, account, '50', date_text='2026-01-01')
    assert ledger(client)['total_amount'] == '50.00'
    for _ in range(2):
        result = summary(client)
        assert result['total_amount'] == '1050.00'
        assert result['rows'][0]['opening_amount'] == '1000.00'
