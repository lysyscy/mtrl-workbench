"""311：owner/大表的真实隔离会话、固定查询数与不可得语义；样本回滚。"""
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.db import get_engine
from app.mod07_setl import big_service as big, big_repository as order, api
from app.mod07_setl.models import AnalysisBigManual
from app.mod11_jc import repository as jc, service as contracts
from app.mod11_jc.models import JcContract, JcInvoice, TAG_IN, TAG_OUT
from tests.test_acc_jc_pay_link import _project
from tests.acc_plugin import acc


@pytest.fixture
def sample(monkeypatch):
    with Session(get_engine(), autoflush=False) as s:
        assert s.execute(text('select current_database()')).scalar_one() == 'mtrl_workbench_test'
        token = uuid4().hex
        projects = [_project(s, f'__自检仓_311_{token}_{i}__') for i in range(3)]
        a, b, empty = [p.warehouse_name for p in projects]
        rows = [JcContract(project_id=p.id, material_name='311材料', trade_co=trade,
                           tag=tag, contract_date='2020-01-01')
                for p, trade, tag in [(projects[0], '', TAG_IN),
                                      (projects[0], '贸易公司', TAG_IN),
                                      (projects[0], '', TAG_OUT),
                                      (projects[1], '  ', TAG_IN)]]
        s.add_all(rows); s.flush()
        for c, supplier, trade in zip(rows, ('120.50', '888', '999', '7.25'),
                                     ('999', '11.50', '777', '999')):
            for kind, amount in [('supplier', supplier), ('trade', trade)]:
                s.add(JcInvoice(contract_id=c.id, kind=kind, invoice_date='2025-01-01',
                                amount=Decimal(amount)))
        s.add(AnalysisBigManual(ym='2026-09', warehouse_name=a, oil=Decimal('0'), note='311带入'))
        s.flush()
        monkeypatch.setattr(big.P1S, 'all_projects', lambda session: projects)
        monkeypatch.setattr(order, 'load_order', lambda session: [b, a, empty])
        monkeypatch.setattr(order, 'has_choice', lambda session: True)
        try:
            yield s, (a, b, empty), rows
        finally:
            s.rollback()


def build(s):
    return big.build_big_data(s, {'month': '2026-10'})


@acc()
def test_owner_matches_list_and_big_sees_uncommitted_invoice(sample, monkeypatch):
    s, (a, b, empty), rows = sample
    expected = {a: Decimal('132.00'), b: Decimal('7.25'), empty: Decimal('0.00')}
    assert contracts.settlement_totals_by_project(s, {a, b, empty}) == expected
    legacy = contracts.build_list(s, tags=[TAG_IN])['rows']
    for key in expected:
        assert sum((r['settle'] for r in legacy if r['project_key'] == key), Decimal('0.00')) == expected[key]

    def forbidden(*args, **kwargs):
        raise AssertionError('大表不得读展示/付款或新建会话')
    monkeypatch.setattr(contracts, 'build_list', forbidden)
    monkeypatch.setattr(jc, 'payments_of_many', forbidden)
    import app.core.db as db
    monkeypatch.setattr(db, 'session_scope', forbidden)
    # 不按月切；flush但不提交的新贸易发票必须在调用者同Session内可见。
    s.add(JcInvoice(contract_id=rows[1].id, kind='trade', invoice_date='2027-01-01',
                    amount=Decimal('0.01'))); s.flush()
    data = build(s)
    assert data['selected'] == [b, a, empty] and data['mat_available'] is True
    assert [r['derived']['mat_cum'] for r in data['rows']] == [
        Decimal('7.25'), Decimal('132.01'), Decimal('0.00')]
    assert data['totals']['mat_cum'] == Decimal('139.26')
    assert data['rows'][1]['manual']['oil'] == {'value': Decimal('0.00'), 'from': '2026-09'}
    assert data['rows'][1]['manual']['note']['value'] == '311带入'


@acc()
def test_owner_fixed_query_count_and_empty_set(sample):
    s, keys, _ = sample
    statements = []
    conn = s.connection()
    def track(conn, cursor, statement, params, context, executemany):
        statements.append(statement.lower())
    event.listen(conn, 'before_cursor_execute', track)
    try:
        counts = []
        for requested in ({keys[0]}, set(keys)):
            statements.clear()
            contracts.settlement_totals_by_project(s, requested)
            counts.append(len(statements))
            assert sum('from jc_contract' in q for q in statements) == 1
            assert sum('from jc_invoice' in q for q in statements) == 1
            assert not any('jc_payment' in q or 'payment_flow' in q for q in statements)
        assert counts == [3, 3]  # 项目键、合同、发票各一次。
        statements.clear()
        assert contracts.settlement_totals_by_project(s, set()) == {}
        assert statements == []
    finally:
        event.remove(conn, 'before_cursor_execute', track)


@acc()
def test_big_calls_port_once_same_session_and_none_error(sample, monkeypatch):
    s, keys, _ = sample
    original = big.MAIN_MATERIAL_PORT
    calls = []
    def spy(session, warehouse_keys):
        assert session is s and warehouse_keys == set(keys)
        calls.append(warehouse_keys)
        return original(session, warehouse_keys)
    monkeypatch.setattr(big, 'MAIN_MATERIAL_PORT', spy)
    assert build(s)['rows'][2]['derived']['mat_cum'] == Decimal('0.00')
    assert len(calls) == 1
    big.set_main_material_port(None)
    data = build(s)
    assert data['mat_available'] is False
    assert all(r['derived']['mat_cum'] is None for r in data['rows'])
    assert data['totals']['mat_cum'] is None
    big.set_main_material_port(original)
    def broken(*args, **kwargs):
        raise RuntimeError('311取数失败')
    monkeypatch.setattr(contracts, 'list_contracts', broken)
    with pytest.raises(RuntimeError, match='取数失败'):
        build(s)
    # 清空选题仍装配空表，owner不查合同/发票。
    monkeypatch.setattr(order, 'load_order', lambda session: [])
    assert build(s)['rows'] == []


@acc()
def test_api_preserves_rows_order_and_decimal_strings(sample, monkeypatch):
    s, (a, b, empty), _ = sample
    @contextmanager
    def borrowed():
        yield s
    monkeypatch.setattr(api, 'session_scope', borrowed)
    body = api.api_big(Request({'type': 'http', 'query_string': b'period=2026-10'}))
    assert body['selected'] == [b, a, empty]
    assert body['mat_available'] is True and body['month'] == '2026-10'
    assert [r['derived']['mat_cum'] for r in body['rows']] == ['7.25', '132.00', '0.00']
    assert body['manual_keys'] == ['open_ym', 'mech_est', 'contract', 'output_cum', 'oil', 'note']
