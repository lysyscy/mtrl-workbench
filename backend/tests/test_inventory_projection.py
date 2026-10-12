"""库存瘦读与完整ORM等价、原单入库金额及固定查询数；仅测试库事务回滚。"""
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as D

from sqlalchemy import event

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.mod07_setl import extract, inventory_extract
from app.mod08_inv import repository as R, router, service
from app.mod08_inv.models import InvDetail, InvAdjustment
from tests.acc_plugin import acc


@contextmanager
def selects(s):
    statements = []
    conn = s.connection()

    def record(conn, cursor, stmt, parameters, context, many):
        if stmt.lstrip().upper().startswith('SELECT'):
            statements.append(stmt)

    event.listen(conn, 'before_cursor_execute', record)
    try:
        yield statements
    finally:
        event.remove(conn, 'before_cursor_execute', record)


def seed(s):
    assert s.get_bind().url.database == 'mtrl_workbench_test'
    rows = [InvDetail(ym=ym, warehouse_name='__314__', direction=direction,
                      material_name=name, material_property='辅材', amount=D(amount),
                      qty=D('1.23'), price_excl=D('10.13'), tax_total=D('999.99'),
                      doc_no=f'__314_{i}__', seq='1', raw={'source': [None, 0, '原单']})
            for i, (ym, direction, name, amount) in enumerate([
                ('2025-11', '入库', '焊条', '10.13'),
                ('2026-01', '出库', '焊丝', '800.01'),
                ('2026-01', '入库', '氧气', '0.00'),
                ('2026-01', '入库', '氧气瓶', '900.99'),
                ('2026-01', '入库', '焊丝', '20.17'),
            ])]
    s.add_all(rows)
    s.flush()
    s.add(InvAdjustment(row_id=rows[0].id, before_amount=D('10.13'), amount=D('0.00'),
                        remark='调整到零', operator='测试人', changed_at=datetime(2026, 10, 12, 9, 8)))
    s.flush()
    return [r.id for r in rows]


@acc()
def test_rows_api_and_orm_consumers_keep_values_and_query_count(monkeypatch):
    with session_scope() as s:
        ids = seed(s)
        adjs = R.adjustments(s)
        original = [R.to_row(d, adjs.get(d.id)) for d in R.list_details(s)]
        s.expunge_all()
        with selects(s) as queries:
            rows = service.load_rows(s)
        assert rows == original
        assert len(queries) == 2
        detail_sql = next(q for q in queries if 'FROM inv_detail' in q)
        assert 'inv_detail.raw' not in detail_sql and 'inv_detail.created_at' not in detail_sql
        assert not any(isinstance(obj, InvDetail) for obj in s.identity_map.values())
        adjusted = next(r for r in rows if r['id'] == ids[0])
        assert adjusted['amount'] == D('10.13') and adjusted['adj_amount'] == D('0.00')
        assert adjusted['adj_at'] == '2026-10-12 09:08'
        assert 'adj_amount' not in next(r for r in rows if r['id'] == ids[2])
        with selects(s) as queries:
            unadjusted = R.load_rows(s, ym='2026-01', adjs={})
        assert len(queries) == 1 and all(r['ym'] == '2026-01' for r in unadjusted)
        assert all('adj_amount' not in r for r in unadjusted)

        @contextmanager
        def same_session():
            yield s

        monkeypatch.setattr(router, 'session_scope', same_session)
        with selects(s) as queries:
            actual = router.api_inventory()
        assert len(queries) == 2
        monkeypatch.setattr(router, 'load_rows', lambda session, **kw: original)
        assert actual == router.api_inventory()  # 包含全量count/projects/分类/调整清单与行序。

        # 真正需要ORM/raw的出口仍可读；写调整与抓取刷新保持原单、调整单分离。
        detail = next(d for d in service.load_original_details(s) if d.id == ids[0])
        assert detail.raw == {'source': [None, 0, '原单']}
        R.save_adjustment(s, row_id=detail.id, new_amount='30.29', remark='复核', operator='测试人')
        R.upsert_details(s, ym='2025-11', warehouse='__314__', rows=[{
            'ym': '2025-11', 'warehouse_name': '__314__', 'doc_no': detail.doc_no,
            'seq': '1', 'amount': D('11.19')}])
        s.expire_all()
        changed = next(r for r in R.load_rows(s) if r['id'] == ids[0])
        assert changed['amount'] == D('11.19') and changed['adj_amount'] == D('30.29')
        assert s.get(InvDetail, ids[0]).raw == {'source': [None, 0, '原单']}
        R.clear_adjustment(s, row_id=ids[0])
        assert 'adj_amount' not in next(r for r in R.load_rows(s) if r['id'] == ids[0])
        s.rollback()


@acc()
def test_original_inbound_four_fields_excludes_outbound_adjustment_and_tax():
    with session_scope() as s:
        seed(s)
        original = [dict(resource_name=d.material_name, warehouse=d.warehouse_name,
                         ym=d.ym, **{'in': d.amount})
                    for d in R.list_details(s) if d.direction == '入库']
        with selects(s) as queries:
            amounts = inventory_extract.load_amounts(s)
        assert amounts == extract.extract_amounts(original)
        assert amounts['焊材']['__314__'] == {'2025-11': D('10.13'), '2026-01': D('20.17')}
        assert amounts['气体']['__314__'] == {'2026-01': D('0.00')}
        assert len(queries) == 1
        sql = queries[0]
        assert sql.split('FROM')[0].count('inv_detail.') == 4
        assert 'inv_detail.raw' not in sql and 'inv_adjustment' not in sql
        assert 'WHERE inv_detail.direction =' in sql
        annual = inventory_extract.annual_grid(amounts, '焊材', warehouses=['__314__'], year='2025')
        assert annual['rows'][0]['cells'] == [None] * 11 + [D('0.00')]
        s.rollback()
