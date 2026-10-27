"""Linked inventory correction crosses the actual Decimal calculation interface."""
from decimal import Decimal

import pytest
import app.models_registry  # noqa: F401 -- this file also runs independently against the isolated DB

from app.mod08_inv.adjustment_values import calculate_values


def values(**changes):
    return {**dict(qty='3.00', price_excl='10.00', price_incl='10.60',
                   amount='30.00', tax_total='31.80', material_property='主材'), **changes}


def test_quantity_and_each_price_recalculate_the_corresponding_total():
    original = values()
    result = calculate_values({**original, 'qty': '5'}, {'amount': 'price', 'tax_total': 'price'}, baseline=original)
    assert result['amount'] == '50.00' and result['tax_total'] == '53.00'
    result = calculate_values({**original, 'price_excl': '12.50'}, {'amount': 'price'}, baseline=original)
    assert result['amount'] == '37.50' and result['tax_total'] == '31.80'
    result = calculate_values({**original, 'price_incl': '12.99'}, {'tax_total': 'price'}, baseline=original)
    assert result['tax_total'] == '38.97' and result['amount'] == '30.00'


def test_manual_totals_keep_their_value_after_reverse_price_rounding():
    original = values()
    result = calculate_values({**original, 'amount': '100.00', 'tax_total': '110.00'},
                              {'amount': 'amount', 'tax_total': 'amount'}, baseline=original)
    assert result['price_excl'] == '33.33' and result['amount'] == '100.00'
    assert result['price_incl'] == '36.67' and result['tax_total'] == '110.00'


def test_zero_quantity_cannot_reverse_a_nonzero_total_and_half_up_is_shared():
    with pytest.raises(ValueError, match='数量为0'):
        calculate_values(values(qty='0', amount='1'), {'amount': 'amount', 'tax_total': 'price'})
    result = calculate_values(values(qty='0.01', price_excl='0.50'), {'amount': 'price', 'tax_total': 'price'})
    assert result['amount'] == '0.01'
    result = calculate_values(values(qty='0'), {'amount': 'price', 'tax_total': 'price'})
    assert result['amount'] == result['tax_total'] == '0.00'


def test_unchanged_pair_cannot_smuggle_numeric_changes_and_property_does_not_recalculate():
    original = values()
    with pytest.raises(ValueError, match='联算'):
        calculate_values({**original, 'qty': '4'}, {}, baseline=original)
    result = calculate_values({**original, 'material_property': '工具'}, {}, baseline=original)
    assert result == {**original, 'material_property': '工具'}


@pytest.mark.parametrize('bad', ['-1', 'NaN', 'Infinity', '', True, '10000000000000000'])
def test_invalid_numeric_input_is_rejected_before_storage(bad):
    with pytest.raises(ValueError):
        calculate_values(values(qty=bad), {'amount': 'price', 'tax_total': 'price'})

from contextlib import contextmanager
from app.core.db import session_scope
from app.core.errors import DataConflictError
from app.mod08_inv import repository as R, router
from app.mod08_inv.models import InvDetail
from app.mod08_inv.adjustment_values import edit_token, original_values
from app.mod06_proc.domain import material_by_month, diff_rows


def source_row(s):
    detail = InvDetail(ym='2026-09', warehouse_name='__linked_inventory__', doc_no='__linked__',
                       seq='1', direction='入库', material_name='测试材料', material_property='主材',
                       qty=Decimal('3'), price_excl=Decimal('10'), price_incl=Decimal('10.60'),
                       amount=Decimal('30'), tax_total=Decimal('31.80'))
    s.add(detail); s.flush()
    return detail


def bind_router(monkeypatch, s):
    @contextmanager
    def scope():
        yield s
    monkeypatch.setattr(router, 'session_scope', scope)
    monkeypatch.setattr(router, 'current_operator', lambda: '联算测试人')


def test_linked_save_keeps_sources_refresh_guard_and_full_clear(monkeypatch, rollback_db):
    with session_scope() as s:
        detail = source_row(s); bind_router(monkeypatch, s)
        before = original_values(R.to_row(detail))
        request = router.AdjustRequest(row_id=detail.id, values={**before, 'qty': '5', 'material_property': '工具'},
                                       basis={'amount': 'price', 'tax_total': 'price'},
                                       expected=edit_token(R.to_row(detail), None), remark='复核数量与性质')
        assert router.api_adjust(request)['ok']
        adj = R.adjustments(s)[detail.id]
        assert adj.overrides == dict(qty='5.00', price_excl='10.00', price_incl='10.60',
                                     amount='50.00', tax_total='53.00', material_property='工具')
        assert adj.before_values == before and adj.operator == '联算测试人'
        assert original_values(R.to_row(detail)) == before
        rows = R.load_process_rows(s); wh = detail.warehouse_name
        assert material_by_month(rows, warehouse=wh, adjusted=False)['2026-09']['in_主辅材'] == Decimal('30')
        assert material_by_month(rows, warehouse=wh, adjusted=True)['2026-09']['in_工具'] == Decimal('50')
        assert '物料性质' in diff_rows(rows, warehouse=wh)[0]['changes']
        stale = edit_token(R.to_row(detail), adj)
        R.upsert_details(s, ym=detail.ym, warehouse=wh, rows=[dict(
            ym=detail.ym, warehouse_name=wh, doc_no=detail.doc_no, seq='1', qty=Decimal('7'),
            price_excl=Decimal('20'), price_incl=Decimal('21.20'), amount=Decimal('140'), tax_total=Decimal('148.40'))])
        assert detail.amount == Decimal('140')
        assert R.adjustments(s)[detail.id].overrides['amount'] == '50.00'
        with pytest.raises(DataConflictError):
            router.api_adjust(router.AdjustRequest(**{**request.model_dump(), 'expected': stale}))
        current = router.api_inventory()['rows']
        row = next(row for row in current if row['id'] == detail.id)
        assert row['adjusted'] and row['adjusted_values']['qty'] == '5.00'
        assert router.api_adjust_clear(router.ClearAdjustRequest(row_id=detail.id, expected=row['edit_token']))['ok']
        assert detail.id not in R.adjustments(s)
        assert R.to_row(detail)['amount'] == Decimal('140')


def test_property_only_correction_keeps_amount_but_is_visible_as_adjusted(monkeypatch, rollback_db):
    with session_scope() as s:
        detail = source_row(s); bind_router(monkeypatch, s)
        original = original_values(R.to_row(detail))
        router.api_adjust(router.AdjustRequest(row_id=detail.id, values={**original, 'material_property': '工具'},
                          expected=edit_token(R.to_row(detail), None), remark='纠正物料归类'))
        adj = R.adjustments(s)[detail.id]
        assert adj.overrides == {'material_property': '工具'}
        row = next(row for row in router.api_inventory()['rows'] if row['id'] == detail.id)
        assert row['adjusted'] and row['c5'] == '工具' and 'adj_amount' not in row
        process = R.load_process_rows(s)
        assert material_by_month(process, warehouse=detail.warehouse_name, adjusted=True)['2026-09']['in_工具'] == Decimal('30')
        assert diff_rows(process, warehouse=detail.warehouse_name)[0]['delta'] == Decimal('0')


def test_legacy_amount_adjustment_remains_compatible_with_property_edit(monkeypatch, rollback_db):
    with session_scope() as s:
        detail = source_row(s); bind_router(monkeypatch, s)
        legacy = R.save_adjustment(s, row_id=detail.id, new_amount='45', remark='旧调整', operator='旧操作人')
        assert legacy.overrides is None
        base = {**original_values(R.to_row(detail)), 'amount': '45.00'}
        router.api_adjust(router.AdjustRequest(row_id=detail.id, values={**base, 'material_property':'工具'},
                          expected=edit_token(R.to_row(detail), legacy), remark='在旧调整上纠正分类'))
        assert legacy.overrides == {'amount':'45.00','material_property':'工具'}
        R.save_adjustment(s, row_id=detail.id, new_amount='48', remark='旧界面仍可修正金额', operator='旧操作人')
        assert legacy.overrides['amount'] == '48.00' and legacy.overrides['material_property'] == '工具'


def test_legacy_save_waits_for_linked_edit_and_keeps_its_new_fields():
    """Two real transactions: an old editor must merge into the latest JSON."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.core.db import get_engine

    engine = get_engine()
    ready, proceed = Event(), Event()
    worker_state = {}
    with Session(engine) as setup, setup.begin():
        detail = source_row(setup)
        row_id = detail.id
        original = original_values(R.to_row(detail))
        R.save_linked_adjustment(setup, row_id=row_id, values={**original, 'material_property': '工具'},
                                basis={'amount': 'price', 'tax_total': 'price'},
                                expected=edit_token(R.to_row(detail), None), remark='原调整', operator='原账号')

    def legacy_save():
        with Session(engine, expire_on_commit=False) as legacy:
            cached_source = legacy.get(InvDetail, row_id)
            cached_adjustment = R.adjustments(legacy)[row_id]
            worker_state['pid'] = legacy.execute(text('SELECT pg_backend_pid()')).scalar_one()
            ready.set()
            assert proceed.wait(5), '未收到并发保存信号'
            legacy.execute(text("SET LOCAL lock_timeout = '5s'"))
            R.save_adjustment(legacy, row_id=row_id, new_amount='60', remark='旧界面金额', operator='旧账号')
            legacy.commit()
            assert cached_source is not None and cached_adjustment is not None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(legacy_save)
            assert ready.wait(5), '旧编辑器未就绪'
            with Session(engine) as latest, latest.begin():
                source = latest.get(InvDetail, row_id)
                adj = R.adjustments(latest)[row_id]
                R.save_linked_adjustment(latest, row_id=row_id,
                    values={**original, 'qty':'5', 'material_property':'劳保'},
                    basis={'amount':'price', 'tax_total':'price'},
                    expected=edit_token(R.to_row(source), adj), remark='新数量和性质', operator='新账号')
                proceed.set()
                deadline = monotonic() + 3
                while not latest.execute(text('SELECT cardinality(pg_blocking_pids(:pid))'),
                                         {'pid': worker_state['pid']}).scalar_one():
                    assert monotonic() < deadline, '未观察到实际数据库锁等待'
                    Event().wait(.01)
            future.result(timeout=5)
        with Session(engine) as check:
            patch = R.adjustments(check)[row_id].overrides
            assert patch == dict(qty='5.00', price_excl='12.00', price_incl='10.60',
                                 amount='60.00', tax_total='53.00', material_property='劳保')
            assert original_values(R.to_row(check.get(InvDetail, row_id))) == original
    finally:
        proceed.set()
        with Session(engine) as cleanup, cleanup.begin():
            source = cleanup.get(InvDetail, row_id)
            if source is not None:
                cleanup.delete(source)
