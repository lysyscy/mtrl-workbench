"""真实事务核双边金额、幂等、归属、失败回滚与全局安全撤销。"""
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import event

from app.core import session as SESS
from app.core.money import to_money
from app.mod13_oilcard.models import OilEntry
from tests.test_oilcard_archives import scene, create  # noqa: F401
from tests.test_oilcard_ledger import entry, ledger, summary, update


def setup(client, project, other):
    card = create(client, 'cards', card_no='0001234567890123456')
    source = create(client, 'accounts', project_id=project, name='转出账户', card_id=card['id'])
    target = create(client, 'accounts', project_id=other, name='转入账户', card_id=card['id'])
    extra = create(client, 'accounts', project_id=project, name='同项目另一账户', card_id=card['id'])
    return source, target, extra


def payload(source, target, **values):
    return {'request_id': str(uuid4()), 'out_project_id': source['project_id'], 'out_account_id': source['id'],
        'in_project_id': target['project_id'], 'in_account_id': target['id'], 'amount': '1000',
        'date_text': '原始数据', 'out_remark': '转出备注', 'in_remark': '转入备注', **values}


def transfer(client, values):
    result = client.post('/api/m13/ledger/transfers', json=values)
    assert result.status_code == 200, result.text
    assert result.headers.get('X-Operation-History') == 'recorded'
    return result.json()['items']


def pair(client, transfer_id):
    return [row for row in ledger(client)['entries'] if row['transfer_id'] == transfer_id]


def test_paired_transfer_is_idempotent_zero_company_total_and_complete_export(scene):
    client, (project, other) = scene
    source, target, extra = setup(client, project, other)
    original = entry(client, source, '10000')
    values = payload(source, target)
    out, incoming = transfer(client, values)
    assert (out['kind'], out['amount'], incoming['kind'], incoming['amount']) == ('transfer_out', '-1000.00', 'transfer_in', '1000.00')
    assert out['transfer_id'] == incoming['transfer_id'] == values['request_id']
    assert out['version'] == incoming['version']
    assert client.post('/api/m13/ledger/transfers', json=values).json()['items'] == [out, incoming]
    assert client.post('/api/m13/ledger/transfers', json={**values, 'amount': '2000'}).status_code == 409
    assert len(ledger(client)['entries']) == 3
    assert ledger(client)['total_amount'] == summary(client)['total_amount'] == '10000.00'
    assert next(row for row in ledger(client)['entries'] if row['id'] == original['id']) == original
    rows = list(load_workbook(BytesIO(client.get('/api/m13/ledger/export').content), data_only=True).active.values)
    assert [row[2] for row in rows[2:4]] == ['转出', '转入']
    assert [to_money(row[6]) for row in rows[2:4]] == [to_money('-1000'), to_money('1000')]
    assert rows[2][9] == rows[3][9] == values['request_id']
    assert to_money(rows[-1][6]) == to_money('10000')
    # 同项目的不同账户也允许成对调拨。
    transfer(client, payload(source, extra, amount='50'))
    assert ledger(client)['total_amount'] == '10000.00'


def test_either_side_date_amount_change_together_attribution_and_notes_only_change_one_side(scene):
    client, (project, other) = scene
    source, target, extra = setup(client, project, other)
    original = entry(client, source, '5000', remark='无关充值')
    out, incoming = transfer(client, payload(source, target))
    update(client, incoming, date_text='2026-10-31')
    out, incoming = pair(client, out['transfer_id'])
    assert out['date_text'] == incoming['date_text'] == '2026-10-31'
    assert out['entry_date'] == incoming['entry_date'] == '2026-10-31'
    update(client, out, amount='-250.50')
    out, incoming = pair(client, out['transfer_id'])
    assert out['amount'] == '-250.50' and incoming['amount'] == '250.50'
    assert out['version'] == incoming['version']
    before_in = incoming.copy()
    update(client, out, account_id=extra['id'], project_id=extra['project_id'], remark='仅改转出')
    out, incoming = pair(client, out['transfer_id'])
    assert out['account_id'] == extra['id'] and out['remark'] == '仅改转出'
    assert {key: incoming[key] for key in incoming if key != 'version'} == {key: before_in[key] for key in before_in if key != 'version'}
    assert incoming['remark'] == '转入备注'
    assert ledger(client)['total_amount'] == '5000.00'
    assert next(row for row in ledger(client)['entries'] if row['id'] == original['id']) == original


def test_global_history_replays_both_and_stale_or_other_actor_conflicts_never_touch_one_side(scene):
    client, (project, other) = scene
    source, target, _ = setup(client, project, other)
    out, incoming = transfer(client, payload(source, target))
    operation = client.get('/api/history/status').json()['undo']
    assert operation['count'] == 2
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert not ledger(client)['entries']
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    out, incoming = pair(client, out['transfer_id'])
    stale = incoming.copy()
    update(client, out, amount='-750')
    changed = pair(client, out['transfer_id'])
    fields = {key: stale[key] for key in ('kind', 'project_id', 'account_id', 'amount', 'date_text', 'remark', 'version')}
    assert client.put(f"/api/m13/ledger/entries/{stale['id']}", json={**fields, 'amount': '600'}).status_code == 409
    assert pair(client, out['transfer_id']) == changed
    operation = client.get('/api/history/status').json()['undo']
    assert operation['count'] == 2
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert [row['amount'] for row in pair(client, out['transfer_id'])] == ['-1000.00', '1000.00']
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    out, incoming = pair(client, out['transfer_id'])
    expected = client.get('/api/history/status').json()['undo']['id']
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__other_transfer_actor__'))
    update(client, incoming, remark='另一账号的后续更正')
    current = pair(client, out['transfer_id'])
    client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_actor__'))
    assert client.post('/api/history/undo', json={'operation_id': expected}).status_code == 409
    assert pair(client, out['transfer_id']) == current


def test_invalid_sides_fixed_types_and_database_failure_leave_no_partial_transfer(scene):
    client, (project, other) = scene
    source, target, _ = setup(client, project, other)
    values = payload(source, target)
    for invalid in ('0', '-10', 'bad'):
        assert client.post('/api/m13/ledger/transfers', json={**values, 'amount': invalid}).status_code == 400
    assert client.post('/api/m13/ledger/transfers', json={**values, 'in_account_id': source['id']}).status_code == 400
    assert client.post('/api/m13/ledger/transfers', json={**values, 'in_project_id': project}).status_code == 400
    assert not ledger(client)['entries']
    def fail_after_insert(_mapper, _connection, row):
        if row.kind == 'transfer_in':
            raise RuntimeError('controlled-insert-failure')
    event.listen(OilEntry, 'after_insert', fail_after_insert)
    try:
        with pytest.raises(RuntimeError, match='controlled-insert-failure'):
            client.post('/api/m13/ledger/transfers', json=values)
    finally:
        event.remove(OilEntry, 'after_insert', fail_after_insert)
    assert not ledger(client)['entries']
    out, incoming = transfer(client, values)
    before = ledger(client)
    fields = {key: out[key] for key in ('kind', 'project_id', 'account_id', 'amount', 'date_text', 'remark', 'version')}
    assert client.put(f"/api/m13/ledger/entries/{out['id']}", json={**fields, 'kind': 'adjustment'}).status_code == 400
    assert ledger(client) == before
    ordinary = entry(client, source, '10')
    fields = {key: ordinary[key] for key in ('kind', 'project_id', 'account_id', 'amount', 'date_text', 'remark', 'version')}
    assert client.put(f"/api/m13/ledger/entries/{ordinary['id']}", json={**fields, 'kind': 'transfer_in'}).status_code == 400
