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
from app.mod09_fee.models import FeeItem, FeeManualItem


def make_fee(s, *, project_id, item_name, **values):
    item = FeeItem(project_id=project_id, name=item_name)
    s.add(item); s.flush()
    return FeeManualItem(project_id=project_id, fee_item_id=item.id, item_name=item_name, **values)


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
        fee = make_fee(s, project_id=project.id, ym='2026-10', item_name='原费用', amount=1)
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
        row = make_fee(s, project_id=data['project'], ym='2026-10', item_name='新费用', amount=Decimal('10.01'))
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
            fee = make_fee(s, project_id=p.id, ym='2026-10', item_name=actor, amount=1)
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
                                  'fee', 'big', 'balance', 'contract_tag', 'contract_field', 'contract_term', 'contract_method'])
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
                                 settle_amount=100, paid_amount=0, remark='', entry_kind='manual')
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
            'opening': ('POST', '/api/m05/history/save', {'id': opening.id, 'entry_kind': 'manual',
                        'category': 'material', 'project_id': data['project'], 'paid_amount': '0',
                        'cutoff_ym': '2025-11', 'settle_amount': '200.12', 'remark': ''},
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
            'contract_term': ('POST', '/api/m11/fields', {'id': contract.id, 'fields': {'payment_term': '60天'}},
                              JcContract, contract.id, 'payment_term', '', '60±0天'),
            'contract_method': ('POST', '/api/m11/fields', {'id': contract.id, 'fields': {'payment_method': '承兑'}},
                                JcContract, contract.id, 'payment_method', '', '承兑'),
        }
        method, path, body, model, row_id, field, before, after = cases[case]
    def value():
        with session_scope() as s:
            return getattr(s.get(model, row_id), field)
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        if case == 'opening':
            from app.mod05_flow.history import record_token
            with session_scope() as s:
                body = {**body, 'token': record_token(s.get(OpeningBalance, row_id))}
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


@pytest.mark.parametrize('action', ['selection', 'move', 'cell', 'export'])
def test_monthly_big_actions_restore_snapshot_and_keep_legacy_baseline(data, monkeypatch, tmp_path, action):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app import history_api
    from app.core import session as SESS
    from app.mod07_setl import big_service as BS
    from app.mod07_setl.models import AnalysisBigManual, AnalysisBigMonthProject, AnalysisBigProject
    from app.report_export import service as exports

    month = '2091-05'
    monkeypatch.setattr(SESS, 'secret', lambda: b'test-monthly-big-only')
    monkeypatch.setattr(history_api, 'active_account', lambda s, identity: object())
    monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
    with session_scope() as s:
        s.add(Project(project_type='normal', name_full='__monthly_other__', warehouse_name='__monthly_other__', disp='另一项目'))
        s.add_all([AnalysisBigProject(warehouse_name='__undo__', seq=0),
                   AnalysisBigProject(warehouse_name='__monthly_other__', seq=1)])
    def state():
        with session_scope() as s:
            return BS.selection_data(s, month), [(r.id, r.warehouse_name, r.seq) for r in s.scalars(select(AnalysisBigProject))]
    original, baseline = state()
    assert original['selection'] == {'fixed': False, 'source': 'legacy'}
    actions = {
        'selection': ('/api/m07/big/selection', {'month': month, 'selected': ['__monthly_other__', '__undo__']}),
        'move': ('/api/m07/big/move', {'month': month, 'warehouse': '__undo__', 'direction': 'down'}),
        'cell': ('/api/m07/big/cell', {'month': month, 'warehouse': '__undo__', 'key': 'oil', 'raw': '0'}),
        'export': (f'/api/m07/big/export?period={month}', None),
    }
    path, body = actions[action]
    with TestClient(create_app()) as client:
        assert client.post(path, json=body).status_code == 401
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        response = client.post(path, json=body)
        assert response.status_code == 200, response.text
        assert response.headers['X-Operation-History'] == 'recorded'
        fixed, current_baseline = state()
        assert fixed['selection'] == {'fixed': True, 'source': month}
        assert current_baseline == baseline
        expected = ['__monthly_other__', '__undo__'] if action in ('move', 'selection') else original['selected']
        assert fixed['selected'] == expected
        if action == 'export':
            assert response.content.startswith(b'PK')
        entry = client.get('/api/history/status').json()['undo']
        assert client.post('/api/history/undo', json={'operation_id': entry['id']}).status_code == 200
        assert state() == (original, baseline)
        with session_scope() as s:
            assert not s.scalars(select(AnalysisBigMonthProject).where(AnalysisBigMonthProject.ym == month)).all()
            if action == 'cell':
                assert not s.scalars(select(AnalysisBigManual).where(AnalysisBigManual.ym == month)).all()
        assert client.post('/api/history/redo', json={'operation_id': entry['id']}).status_code == 200
        assert state() == (fixed, baseline)
        if action == 'cell':
            with session_scope() as s:
                assert s.scalar(select(AnalysisBigManual).where(AnalysisBigManual.ym == month)).oil == Decimal('0')
        if action == 'selection':
            response = client.post('/api/m07/big/selection', json={'month': month, 'selected': ['__undo__']})
            assert response.headers['X-Operation-History'] == 'recorded'
            assert state()[0]['selected'] == ['__undo__']
            entry = client.get('/api/history/status').json()['undo']
            assert client.post('/api/history/undo', json={'operation_id': entry['id']}).status_code == 200
            assert state() == (fixed, baseline)
            assert client.post('/api/history/redo', json={'operation_id': entry['id']}).status_code == 200
            assert state()[0]['selected'] == ['__undo__']


def test_big_get_export_is_read_only_failed_post_rolls_back_and_month_list_blocks_project_delete(data, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core import session as SESS
    from app.mod01_projects import deletion
    from app.mod07_setl import big_service as BS
    from app.report_export import service as exports

    month = '2091-06'
    monkeypatch.setattr(SESS, 'secret', lambda: b'test-monthly-big-only')
    monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
    with TestClient(create_app()) as client:
        response = client.get(f'/api/m07/big/export?period={month}')
        assert response.status_code == 200 and response.content.startswith(b'PK')
        with session_scope() as s:
            assert not BS.selection_data(s, month)['selection']['fixed']
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        with monkeypatch.context() as failing:
            def broken(*args, **kwargs):
                raise MustReportError('模板损坏')
            failing.setattr(exports, 'export_big_data', broken)
            response = client.post(f'/api/m07/big/export?period={month}')
            assert response.json() == {'ok': False, 'message': '模板损坏'}
        with session_scope() as s:
            assert not BS.selection_data(s, month)['selection']['fixed']
            project = Project(project_type='normal', name_full='__monthly_only__', warehouse_name='__monthly_only__', disp='只被名单引用')
            s.add(project)
            s.flush()
            BS.save_selection(s, [project.warehouse_name], month=month)
            impact = deletion.impact(s, project.id)
            assert not impact['can_delete']
            assert next(g for g in impact['groups'] if g['table'] == 'analysis_big_month_project')['count'] == 1


@pytest.mark.parametrize('changed', [False, True])
def test_big_post_export_renders_outside_sessions_and_rechecks_intervening_selection(data, monkeypatch, tmp_path, changed):
    from contextlib import contextmanager
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core import session as SESS
    from app.mod07_setl import api, big_service as BS
    from app.mod07_setl.models import AnalysisBigProject
    from app.report_export import service as exports

    month = '2091-07'
    monkeypatch.setattr(SESS, 'secret', lambda: b'test-monthly-big-only')
    monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
    with session_scope() as s:
        s.add(Project(project_type='normal', name_full='__render_other__', warehouse_name='__render_other__', disp='渲染并发项目'))
        s.add_all([AnalysisBigProject(warehouse_name='__undo__', seq=0),
                   AnalysisBigProject(warehouse_name='__render_other__', seq=1)])
    sessions = []
    original_scope = api.session_scope
    @contextmanager
    def observed_scope():
        with original_scope() as s:
            sessions.append(s)
            yield s
    monkeypatch.setattr(api, 'session_scope', observed_scope)
    render = exports.export_big_data
    def observed_render(report, *, isolated=False):
        assert len(sessions) == 1 and not sessions[0].in_transaction()
        assert isolated is True
        path = render(report, isolated=isolated)
        if changed:
            result, recorded = perform('/api/m07/big/selection',
                lambda s: BS.save_selection(s, ['__render_other__'], month=month), actor='__other_export_writer__')
            assert result['ok'] and recorded == 'recorded'
        return path
    monkeypatch.setattr(exports, 'export_big_data', observed_render)
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__undo_a__'))
        response = client.post(f'/api/m07/big/export?period={month}')
        assert response.status_code == 200
        assert len(sessions) == 2 and all(not s.in_transaction() for s in sessions)
        with session_scope() as s:
            current = BS.selection_data(s, month)
        assert current['selection'] == {'fixed': True, 'source': month}
        if changed:
            assert response.json()['ok'] is False and '重新导出' in response.json()['message']
            assert current['selected'] == ['__render_other__']
            assert response.headers.get('X-Operation-History') != 'recorded'
        else:
            assert response.content.startswith(b'PK')
            assert current['selected'] == ['__undo__', '__render_other__']
            assert response.headers['X-Operation-History'] == 'recorded'


@pytest.fixture
def committed_data(monkeypatch):
    """真实独立提交；仅清理唯一actor及本用例创建的行。"""
    from uuid import uuid4
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import sessionmaker
    from app.core import db
    from app.core.config import get_settings
    from tests.conftest import _DB_GUARD
    engine = create_engine(get_settings().test_database_url)
    _DB_GUARD.assert_runtime(engine.url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db, '_session_factory', factory)
    actor = '__history_remediation_' + uuid4().hex
    configure()
    project_id = notice_id = None
    notice_ids = []
    fees = []
    try:
        with factory.begin() as s:
            project = Project(project_type='normal', name_full=actor, warehouse_name=actor, disp='原名')
            s.add(project); s.flush(); project_id = project.id
            rows = [make_fee(s, project_id=project_id, ym='2026-10', item_name=actor+str(i), amount=v)
                    for i,v in enumerate((1,10,100))]
            notice = PaymentNotice(ph_id=actor, bill_no=actor, category='material',
                ownership_id=project_id, amount_approved=100, planned_pay_method='',
                stat_paid=0, stat_settle=100, excluded=False, fields={})
            other = PaymentNotice(ph_id=actor+'second', bill_no=actor+'second', category='material',
                ownership_id=project_id, amount_approved=100, planned_pay_method='',
                stat_paid=0, stat_settle=100, excluded=False, fields={})
            s.add_all([*rows,notice,other]);s.flush()
            fees = [r.id for r in rows];notice_id=notice.id
            notice_ids=[notice.id,other.id]
        yield dict(actor=actor, factory=factory, engine=engine, project=project_id, fees=fees,
                   notice=notice_id, notices=notice_ids)
    finally:
        with engine.begin() as c:
            c.execute(delete(history.OperationHistory).where(history.OperationHistory.actor.in_(
                [history.actor_key(actor),history.actor_key(actor+'other')])))
            if fees: c.execute(delete(FeeManualItem).where(FeeManualItem.id.in_(fees)))
            if notice_ids: c.execute(delete(PaymentNotice).where(PaymentNotice.id.in_(notice_ids)))
            if project_id is not None: c.execute(delete(Project).where(Project.id==project_id))
        engine.dispose()


def test_interleaved_commits_and_parent_guards_roundtrip(committed_data):
    d=committed_data;actor=d['actor'];a,b,c=d['fees']
    def change(row,value):
        return perform('/api/m09/fee/amount',lambda s:setattr(s.get(FeeManualItem,row),'amount',value),actor)
    def amounts():
        with d['factory']() as s:
            return [s.get(FeeManualItem,i).amount for i in (a,b,c)]
    change(a,2);first=status(actor)['undo']['id']
    change(b,11);middle=status(actor)['undo']['id']
    change(a,3);last=status(actor)['undo']['id']
    for ident,want in [(last,[2,11,100]),(middle,[2,10,100]),(first,[1,10,100])]:
        replay('undo',actor,ident);assert amounts()==want
    for ident,want in [(first,[2,10,100]),(middle,[2,11,100]),(last,[3,11,100])]:
        replay('redo',actor,ident);assert amounts()==want
    rename=lambda name:perform(f"/api/m01/projects/{d['project']}",
        lambda s:setattr(s.get(Project,d['project']),'disp',name),actor,method='PUT')
    rename('中间名');change(a,4);change(b,12);change(c,101);rename('最终名')
    for _ in range(8): replay('undo',actor)
    assert amounts()==[1,10,100] and status(actor)['undo'] is None
    with d['factory']() as s: assert s.get(Project,d['project']).disp=='原名'
    for _ in range(8): replay('redo',actor)
    assert amounts()==[4,12,101] and status(actor)['redo'] is None
    with d['factory']() as s: assert s.get(Project,d['project']).disp=='最终名'


@pytest.mark.parametrize('parent', [False,True])
def test_external_aba_before_later_tracked_write_is_not_trusted(committed_data,parent):
    d=committed_data;actor=d['actor'];a,b,_=d['fees']
    def tracked(value):
        if parent:
            perform(f"/api/m01/projects/{d['project']}",
                lambda s:setattr(s.get(Project,d['project']),'disp',str(value)),actor,method='PUT')
        else:
            perform('/api/m09/fee/amount',lambda s:setattr(s.get(FeeManualItem,a),'amount',value),actor)
    tracked(2)
    if parent:
        # 两个子项均依赖同一父版本，不能跨过外部ABA续接。
        for row in (a,b):
            perform('/api/m09/fee/amount',lambda s,row=row:setattr(s.get(FeeManualItem,row),'amount',20),actor)
    for value in (99,2):
        with d['factory'].begin() as s:
            if parent:s.get(Project,d['project']).disp=str(value)
            else:s.get(FeeManualItem,a).amount=value
    tracked(3)
    replay('undo',actor)
    before=status(actor)
    with pytest.raises(MustReportError,match='后续操作'):
        replay('undo',actor)
    assert status(actor)==before
    with d['factory']() as s:
        assert s.get(FeeManualItem,a).amount==(20 if parent else 2)


@pytest.mark.parametrize('case', ['barrier','success','hash','fingerprint','old'])
def test_plan_methods_and_barrier_commit_atomically(committed_data,monkeypatch,case):
    from fastapi.testclient import TestClient
    from sqlalchemy import event
    from app import history_api
    from app.main import create_app
    from app.core import session as SESS
    from app.mod03_notice import plan_audit_api as api
    from tests.test_plan_audit_api import preview
    from hashlib import sha256
    import json
    d=committed_data;actor=d['actor'];a=d['fees'][0]
    perform('/api/m09/fee/amount',lambda s:setattr(s.get(FeeManualItem,a),'amount',2),actor)
    replay('undo',actor)
    before=status(actor)
    p=preview();p['changes'][0].update(id=d['notice'],bill_no=actor,ownership_id=d['project'],paid='0')
    p['changes'].append({**p['changes'][0],'id':d['notices'][1],'bill_no':actor+'second','source_row':5})
    if case=='old':p['changes'][1]['old']='现汇'
    p['snapshot']['database_fingerprint']=('c'*64 if case=='fingerprint' else api.DATA.database_fingerprint(d['engine']))
    fail_barrier=case=='barrier'
    failed=case!='success'
    raw=json.dumps(p);body={'preview_json':raw,'approved_sha256':sha256(raw.encode()).hexdigest()}
    if case=='hash':body['approved_sha256']='0'*64
    monkeypatch.setattr(SESS,'secret',lambda:b'isolated-history-atomic')
    monkeypatch.setattr(api,'active_account',lambda *args:object())
    monkeypatch.setattr(history_api,'active_account',lambda *args:object())
    def reject(conn,cursor,statement,parameters,context,many):
        if 'INSERT INTO operation_history' in statement:
            raise RuntimeError('barrier storage failure')
    if fail_barrier:event.listen(d['engine'],'before_cursor_execute',reject)
    try:
        with TestClient(create_app(),raise_server_exceptions=False) as client:
            client.cookies.set(SESS.COOKIE_NAME,SESS.make(actor))
            result=client.post('/api/m03/plan-audit/methods',json=body)
            assert result.status_code==(500 if fail_barrier else 409 if failed else 200),result.text
            if not failed:assert result.headers['X-Operation-History']=='unsupported'
    finally:
        if fail_barrier:event.remove(d['engine'],'before_cursor_execute',reject)
    with d['factory']() as s:
        assert [s.get(PaymentNotice,i).planned_pay_method for i in d['notices']]==(['',''] if failed else ['承兑','承兑'])
        rows=list(s.scalars(select(history.OperationHistory).where(
            history.OperationHistory.actor==history.actor_key(actor))))
        assert len(rows)==(1 if failed else 2)
        assert [r.state for r in rows]==(['undone'] if failed else ['discarded','barrier'])
    if failed:assert status(actor)==before
    else:assert status(actor)=={'undo':None,'redo':None,'notice':'上一步暂不支持撤销／重做'}


def test_legacy_history_without_target_version_keeps_conservative_boundary(committed_data):
    d=committed_data;actor=d['actor'];row=d['fees'][0]
    for value in (2,3):
        perform('/api/m09/fee/amount',lambda s,value=value:setattr(s.get(FeeManualItem,row),'amount',value),actor)
    latest=status(actor)['undo']['id']
    with d['factory'].begin() as s:
        item=s.get(history.OperationHistory,latest)
        item.changes=[{k:v for k,v in c.items() if k!='target_version'} for c in item.changes]
    replay('undo',actor)
    with d['factory']() as s:assert s.get(FeeManualItem,row).amount==2
    with pytest.raises(MustReportError,match='后续操作'):replay('undo',actor)
    replay('redo',actor)
    with d['factory']() as s:assert s.get(FeeManualItem,row).amount==3
