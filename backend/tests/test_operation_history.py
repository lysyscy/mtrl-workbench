"""通过真实事务保护整批撤销、重做分支、冲突及账号隔离。"""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import history
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.history_bindings import configure
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_api_router import IdsIn, api_exclude, api_restore
from app.mod09_fee.models import FeeManualItem


@pytest.fixture
def data(rollback_db):
    configure()
    with session_scope() as s:
        project = Project(project_type='normal', name_full='__undo__', warehouse_name='__undo__', disp='撤销测试')
        s.add(project)
        s.flush()
        notices = [PaymentNotice(ph_id=f'__undo_{i}__', bill_no=f'UNDO-{i}',
                                 category='material', doc_date='2026-10-01',
                                 ownership_id=project.id, stat_settle=100, stat_paid=0,
                                 excluded=False, fields={}) for i in range(19)]
        fee = FeeManualItem(project_id=project.id, ym='2026-10', item_name='原费用', amount=1)
        s.add_all([*notices, fee])
        s.flush()
        return {'ids': [n.id for n in notices], 'fee': fee.id, 'project': project.id}


def perform(path, fn, actor='__undo_a__', method='POST'):
    token, state = history.begin_request(actor, method, path)
    try:
        with session_scope() as s:
            result = fn(s)
        return result, state.result
    finally:
        history.end_request(token)


def status(actor='__undo_a__'):
    with session_scope() as s:
        return history.status(s, actor)


def replay(direction, actor='__undo_a__', expected=None):
    expected = expected or status(actor)[direction]['id']
    with session_scope() as s:
        return history.replay(s, actor, direction, expected)


def flags(ids):
    with session_scope() as s:
        return [bool(v) for v in s.scalars(select(PaymentNotice.excluded).where(
            PaymentNotice.id.in_(ids)).order_by(PaymentNotice.id))]


def test_batch_18_is_one_undo_and_redo_and_restore_has_own_history(data):
    ids = data['ids'][:18]
    result, recorded = perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s))
    assert result['ok'] and recorded == 'recorded'
    assert status()['undo']['count'] == 18 and status()['redo'] is None
    assert flags(data['ids']) == [True] * 18 + [False]
    operation_id = status()['undo']['id']
    assert replay('undo')['count'] == 18
    assert flags(data['ids']) == [False] * 19
    assert replay('redo')['count'] == 18
    assert flags(ids) == [True] * 18
    perform('/api/m03/actions/restore', lambda s: api_restore(IdsIn(ids=ids), s))
    assert flags(ids) == [False] * 18
    replay('undo')
    assert flags(ids) == [True] * 18
    assert status()['undo']['id'] == operation_id


def test_conflict_rejects_whole_batch_and_does_not_move_stack(data):
    ids = data['ids'][:2]
    perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s))
    before = status()
    with session_scope() as s:
        s.get(PaymentNotice, ids[1]).stat_paid = Decimal('10')
    with pytest.raises(MustReportError, match='后续操作'):
        replay('undo')
    assert flags(ids) == [True, True]
    assert status() == before


def test_parent_project_change_blocks_leaf_restore(data):
    def change(s):
        s.get(FeeManualItem, data['fee']).amount = Decimal('10.12')
    perform('/api/m09/fee/amount', change)
    with session_scope() as s:
        s.get(Project, data['project']).disp = '后续项目修改'
    with pytest.raises(MustReportError, match='所属项目'):
        replay('undo')
    with session_scope() as s:
        assert s.get(FeeManualItem, data['fee']).amount == Decimal('10.12')


def test_same_row_multiple_steps_redo_branch_and_stale_double_click(data):
    def set_amount(value):
        def apply(s):
            s.get(FeeManualItem, data['fee']).amount = Decimal(value)
        return apply
    def amount():
        with session_scope() as s:
            return s.get(FeeManualItem, data['fee']).amount
    perform('/api/m09/fee/amount', set_amount('2.34'))
    first = status()['undo']['id']
    perform('/api/m09/fee/amount', set_amount('3.45'))
    second = status()['undo']['id']
    with pytest.raises(MustReportError, match='历史已变化'):
        replay('undo', expected=first)
    replay('undo', expected=second)
    with pytest.raises(MustReportError, match='历史已变化'):
        replay('undo', expected=second)
    assert amount() == Decimal('2.34')
    replay('undo')
    assert amount() == Decimal('1')
    replay('redo')
    assert amount() == Decimal('2.34')
    replay('redo')
    assert amount() == Decimal('3.45')
    replay('undo')
    perform('/api/m09/fee/amount', set_amount('9.87'))
    assert status()['redo'] is None and amount() == Decimal('9.87')


def test_other_account_is_isolated_and_other_writer_conflicts(data):
    ids = data['ids'][:1]
    perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s))
    assert status('__undo_b__') == {'undo': None, 'redo': None}
    with pytest.raises(MustReportError, match='历史已变化'):
        replay('undo', actor='__undo_b__', expected=status()['undo']['id'])
    perform('/api/m03/actions/restore', lambda s: api_restore(IdsIn(ids=ids), s), actor='__undo_b__')
    with pytest.raises(MustReportError, match='后续操作'):
        replay('undo')
    assert flags(ids) == [False]


def test_unsupported_and_failed_or_unchanged_transactions(data):
    ids = data['ids'][:1]
    perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s))
    before = status()
    _, result = perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s))
    assert not result and status() == before
    with pytest.raises(RuntimeError):
        def abort(s):
            s.get(PaymentNotice, ids[0]).excluded = False
            s.flush()
            raise RuntimeError('rollback')
        perform('/api/m03/actions/restore', abort)
    assert flags(ids) == [True] and status() == before
    def unsupported(s):
        s.get(PaymentNotice, ids[0]).stat_paid = 11
    _, result = perform('/api/m03/actions/stat', unsupported)
    assert result == 'unsupported' and status()['undo'] is status()['redo'] is None
    assert '不支持' in status()['notice']
    perform('/api/m03/actions/restore', lambda s: api_restore(IdsIn(ids=ids), s))
    replay('undo')
    assert status() == {'undo': None, 'redo': status()['redo']}


def test_leaf_create_delete_roundtrip(data):
    made = {}
    def create(s):
        row = FeeManualItem(project_id=data['project'], ym='2026-10', item_name='新费用', amount=Decimal('10.01'))
        s.add(row)
        s.flush()
        made['id'] = row.id
    perform('/api/m09/fee/add', create)
    replay('undo')
    with session_scope() as s:
        assert s.get(FeeManualItem, made['id']) is None
    replay('redo')
    perform('/api/m09/fee/delete', lambda s: s.delete(s.get(FeeManualItem, made['id'])))
    replay('undo')
    with session_scope() as s:
        assert s.get(FeeManualItem, made['id']).amount == Decimal('10.01')


def test_disallowed_field_in_supported_route_is_entirely_unsupported(data):
    def wrong_field(s):
        row = s.get(PaymentNotice, data['ids'][0])
        row.category = 'mechanical'
        row.stat_settle = 999
    _, result = perform('/api/m03/actions/category', wrong_field)
    assert result == 'unsupported' and status()['undo'] is None


def test_unbounded_unicode_account_does_not_add_business_write_limit(data):
    actor = '中文账号.不限长度' * 60
    ids = data['ids'][:1]
    perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=ids), s), actor)
    assert status(actor)['undo']['count'] == 1
    replay('undo', actor)
    assert flags(ids) == [False]


def test_http_transaction_receipt_auth_and_account_isolation(data, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app import history_api
    from app.core import session as SESS
    monkeypatch.setattr(SESS, 'secret', lambda: b'test-history-signing-only')
    monkeypatch.setattr(history_api, 'active_account', lambda s, identity: object())
    with TestClient(create_app()) as client:
        assert client.get('/api/history/status').status_code == 401
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        result = client.post('/api/m03/actions/exclude', json={'ids': data['ids'][:2]})
        assert result.status_code == 200 and result.json()['ok']
        assert result.headers.get('X-Operation-History') == 'recorded'
        summary = client.get('/api/history/status')
        assert summary.headers['Cache-Control'] == 'no-store'
        operation = summary.json()['undo']
        assert set(operation) == {'id', 'label', 'count'} and operation['count'] == 2
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_b__'))
        assert client.get('/api/history/status').json() == {'undo': None, 'redo': None}
        assert client.post('/api/history/undo', json={'operation_id': operation['id']}).status_code == 409
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
        assert flags(data['ids'][:2]) == [False, False]
        assert client.post('/api/history/undo', json={'operation_id': operation['id']}).status_code == 409
        assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
        monkeypatch.setattr(history_api, 'active_account', lambda s, identity: None)
        assert client.get('/api/history/status').status_code == 403


def test_committed_versions_aba_and_concurrent_same_actor_are_safe(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import sessionmaker
    from app.core import db
    from app.core.config import get_settings
    from tests.conftest import _DB_GUARD
    actor = '__history_committed_' + uuid4().hex
    engine = create_engine(get_settings().test_database_url)
    _DB_GUARD.assert_runtime(engine.url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db, '_session_factory', factory)
    configure()
    project_id = notice_id = fee_id = None
    try:
        with factory.begin() as s:
            p = Project(project_type='normal', name_full=actor, warehouse_name=actor, disp=actor)
            s.add(p)
            s.flush()
            project_id = p.id
            n = PaymentNotice(ph_id=actor, bill_no=actor, category='material',
                              ownership_id=p.id, stat_paid=0, stat_settle=100, excluded=False, fields={})
            fee = FeeManualItem(project_id=p.id, ym='2026-10', item_name=actor, amount=1)
            s.add_all([n, fee])
            s.flush()
            notice_id, fee_id = n.id, fee.id
        perform('/api/m03/actions/exclude', lambda s: api_exclude(IdsIn(ids=[notice_id]), s), actor)
        for value in (2, 0):
            with session_scope() as s:
                s.get(PaymentNotice, notice_id).stat_paid = value
        # 数值改回原样仍是外部写入，必须由真实xmin检出。
        with pytest.raises(MustReportError, match='后续操作'):
            replay('undo', actor)
        assert flags([notice_id]) == [True]
        start = Barrier(2)
        def concurrent(value):
            start.wait(timeout=5)
            def change(s):
                s.get(FeeManualItem, fee_id).amount = Decimal(value)
            return perform('/api/m09/fee/amount', change, actor)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(concurrent, '2.34'), pool.submit(concurrent, '3.45')
            assert a.result(timeout=10)[1] == b.result(timeout=10)[1] == 'recorded'
        with factory() as s:
            final_amount = s.get(FeeManualItem, fee_id).amount
            assert history.status(s, actor)['undo'] is not None
        replay('undo', actor)
        replay('undo', actor)
        with factory() as s:
            assert s.get(FeeManualItem, fee_id).amount == Decimal(1)
        replay('redo', actor)
        replay('redo', actor)
        with factory() as s:
            assert s.get(FeeManualItem, fee_id).amount == final_amount
        def rename(s):
            s.get(Project, project_id).disp = '同账号后续项目名'
        perform(f'/api/m01/projects/{project_id}', rename, actor, method='PUT')
        perform('/api/m09/fee/amount', lambda s: setattr(s.get(FeeManualItem, fee_id), 'amount', Decimal('9.99')), actor)
        replay('undo', actor)
        replay('undo', actor)
        replay('redo', actor)
        replay('redo', actor)
        with factory() as s:
            assert s.get(FeeManualItem, fee_id).amount == Decimal('9.99')
    finally:
        # 只清理本测试明确创建的独有记录，既有测试数据保持。
        with engine.begin() as c:
            c.execute(delete(history.OperationHistory).where(history.OperationHistory.actor == history.actor_key(actor)))
            if fee_id is not None:
                c.execute(delete(FeeManualItem).where(FeeManualItem.id == fee_id))
            if notice_id is not None:
                c.execute(delete(PaymentNotice).where(PaymentNotice.id == notice_id))
            if project_id is not None:
                c.execute(delete(Project).where(Project.id == project_id))
        engine.dispose()


@pytest.mark.parametrize('case', ['category', 'supplier', 'project', 'opening', 'remark',
                                  'fee', 'big', 'balance', 'contract_tag', 'contract_field'])
def test_declared_safe_actions_use_real_http_handlers_and_restore_values(data, monkeypatch, case):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app import history_api
    from app.core import session as SESS
    from app.mod05_flow.models import OpeningBalance, LedgerRemark
    from app.mod07_setl.models import AnalysisBigManual, WeldGasBalance
    from app.mod11_jc.models import JcContract, TAG_IN, TAG_OUT
    monkeypatch.setattr(SESS, 'secret', lambda: b'test-history-signing-only')
    monkeypatch.setattr(history_api, 'active_account', lambda s, identity: object())
    with session_scope() as s:
        opening = OpeningBalance(project_id=data['project'], category='material', cutoff_ym='2025-11',
                                 settle_amount=100, paid_amount=0, remark='', entry_kind='settlement')
        note = LedgerRemark(project_id=data['project'], category='material', ym='2026-01', remark='原备注')
        big = AnalysisBigManual(project_id=data['project'], warehouse_name='__undo__', ym='2026-10', oil=1)
        balance = WeldGasBalance(warehouse_name='__undo__', kind='焊材', amount=1)
        contract = JcContract(project_id=data['project'], contract_no='__undo_contract__', tag=TAG_IN, remark='原备注')
        s.add_all([opening, note, big, balance, contract])
        s.get(PaymentNotice, data['ids'][0]).category = 'jc' if case == 'supplier' else 'material'
        s.flush()
        cases = {
            'category': ('POST', '/api/m03/actions/category', {'ids': data['ids'][:1], 'category': 'mechanical'},
                         PaymentNotice, data['ids'][0], 'category', 'material', 'mechanical'),
            'supplier': ('POST', '/api/m03/actions/jc-supplier', {'notice_id': data['ids'][0], 'supplier': '新供应商'},
                         PaymentNotice, data['ids'][0], 'jc_supplier', '', '新供应商'),
            'project': ('PUT', f"/api/m01/projects/{data['project']}", {'disp': '新展示名'},
                        Project, data['project'], 'disp', '撤销测试', '新展示名'),
            'opening': ('POST', '/api/m05/history/save', {'id': opening.id, 'entry_kind': 'settlement',
                        'category': 'material', 'project_id': data['project'], 'input_mode': 'paid',
                        'cutoff_ym': '2025-11', 'amount': '200.12', 'remark': ''},
                        OpeningBalance, opening.id, 'settle_amount', Decimal('100'), Decimal('200.12')),
            'remark': ('POST', '/m05/ledger/remark', {'category': 'material', 'project_id': data['project'],
                        'ym': '2026-01', 'remark': '新备注'},
                       LedgerRemark, note.id, 'remark', '原备注', '新备注'),
            'fee': ('POST', '/api/m09/fee/amount', {'ym': '2026-10', 'project': '__undo__', 'index': 0, 'value': '12.34'},
                    FeeManualItem, data['fee'], 'amount', Decimal(1), Decimal('12.34')),
            'big': ('POST', '/api/m07/big/cell', {'month': '2026-10', 'warehouse': '__undo__', 'key': 'oil', 'raw': '12.34'},
                    AnalysisBigManual, big.id, 'oil', Decimal(1), Decimal('12.34')),
            'balance': ('POST', '/api/m07/extract/balance', {'warehouse': '__undo__', 'kind': '焊材', 'raw': '12.34'},
                        WeldGasBalance, balance.id, 'amount', Decimal(1), Decimal('12.34')),
            'contract_tag': ('POST', '/api/m11/tag', {'id': contract.id, 'tag': TAG_OUT},
                             JcContract, contract.id, 'tag', TAG_IN, TAG_OUT),
            'contract_field': ('POST', '/api/m11/fields', {'id': contract.id, 'fields': {'remark': '新备注'}},
                               JcContract, contract.id, 'remark', '原备注', '新备注'),
        }
        method, path, body, model, row_id, field, before, after = cases[case]
    def value():
        with session_scope() as s:
            return getattr(s.get(model, row_id), field)
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        if case == 'opening':
            preview = client.post('/api/m05/history/preview', json=body)
            assert preview.status_code == 200, preview.text
            body = {**body, 'token': preview.json()['token']}
        args = {'data': body} if path.startswith('/m05/') else {'json': body}
        response = client.request(method, path, follow_redirects=False, **args)
        assert response.status_code in (200, 303), response.text
        assert response.headers.get('X-Operation-History') == 'recorded', response.text
        assert value() == after
        entry = client.get('/api/history/status').json()['undo']
        result = client.post('/api/history/undo', json={'operation_id': entry['id']})
        assert result.status_code == 200 and value() == before, result.text
        if case == 'opening':
            with session_scope() as s:
                assert s.get(OpeningBalance, row_id).cutoff_ym == '2025-11'
        result = client.post('/api/history/redo', json={'operation_id': entry['id']})
        assert result.status_code == 200 and value() == after, result.text
