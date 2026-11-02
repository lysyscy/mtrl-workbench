"""`TAIL-471`：按对象核对的范围下推 —— **只缩小读取范围，不动业务口径**。

它守什么（票面验收）：
  ① 单对象弹窗（`/api/m05/flows?notice_id=`）的行**字段与行序**必须与原全量列表筛出该对象
     **逐字相等**（含已撤销流水；空id保持原范围，非法显式id拒绝）；
  ② 付款预览只核对选中集合时，流水 / 留痕 / 关联**同投影、同行序**地收窄 ——
     供应商（`jc_supplier`）与 `has_link` 不得因为只限 links 而退空；
  ③ 空集合 = 空且**不查库**（`flows_of_notices([])` / `stat_trace_index_of([])`）。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.db import session_scope
from app.mod03_notice import repository as notices
from app.mod03_notice.list_view import _flows_by_notice, _links_by_notice, _traces_by_notice, build_rows
from app.mod05_flow import service as flows
from app.mod05_flow import router as m05_router
from app.mod05_flow.models import FLOW_REVOKED, PaymentFlow


def _order(rows: list[dict]) -> list[tuple]:
    return [(r["id"], r["pay_date"], r["amount"], r["status"]) for r in rows]


@pytest.fixture
def scoped(rollback_db):
    """两张通知书 + 三条流水（同日一笔已在撤销 / 跨日两笔）＋ 一条失联流水。"""
    from tests.test_acc_jc_pay_link import _notice

    with session_scope() as s:
        a = _notice(s, ph='__471_对象甲__', category='material', paid='0', approved='900')
        b = _notice(s, ph='__471_对象乙__', category='material', paid='0', approved='900')
        a.ownership_id = b.ownership_id = None
        s.flush()
        f1 = flows.create_flow(s, notice_id=a.id, project_id=None, amount='300', pay_date='2026-09-02')
        f2 = flows.create_flow(s, notice_id=a.id, project_id=None, amount='100', pay_date='2026-09-02')
        f3 = flows.create_flow(s, notice_id=a.id, project_id=None, amount='250', pay_date='2026-06-30')
        f2.status = FLOW_REVOKED; f2.revoke_reason = '471 撤销原因'; s.flush()
        flows.create_flow(s, notice_id=b.id, project_id=None, amount='700', pay_date='2026-09-09')
        orphan = PaymentFlow(flow_no='F471ORPHAN', notice_id=None, project_id=None,
                             amount=Decimal('55.00'), pay_date='2026-09-09',
                             pay_method='现汇', status='effective', request_id='', created_by='471')
        s.add(orphan); s.flush()
        yield s, int(a.id), int(b.id), [int(f1.id), int(f2.id), int(f3.id)]


def test_single_notice_popup_equals_full_list_filtered(scoped):
    """① 弹窗口径 = 原全量列表筛出该对象（逐字段、逐行序，撤销照常出行）。"""
    s, a, b, _ = scoped
    full = flows.build_flows(s, year_month='')['rows']
    old = [r for r in full if r['notice_id'] == a]
    new = flows.build_notice_flows(s, a)['rows']

    assert old == new, '单对象下推改变了行的字段或顺序（含已撤销流水）'
    # 原序 = 「付款日期倒序、同日 id 倒序」⇒ 同日的已撤销那条排在前、六月那条在后
    assert [r['pay_date'] for r in new] == ['2026-09-02', '2026-09-02', '2026-06-30']
    assert [r['status'] for r in new] == ['revoked', 'effective', 'effective']
    # ⛔ 失联流水不属于任何通知书的弹窗，也不得被扯进来
    assert all(r['notice_id'] == a for r in new)
    assert flows.build_notice_flows(s, b)['rows'] == [r for r in full if r['notice_id'] == b]


def test_router_scope_only_narrows_and_keeps_full_semantics(scoped):
    """空id保持原范围；显式非法对象不能静默扩大为全量读取。"""
    from app.core.errors import MustReportError
    s, a, _, _ = scoped
    seen: list[dict] = []

    def load(**kw):
        seen.append(kw)
        return {'rows': ['ALL'], 'kw': kw}

    assert m05_router.api_flows(year_month='', status='', pay_method='', project_id='',
                                keyword='', notice_id='', load=load) == {'rows': ['ALL'], 'kw': {'year_month': '', 'status': None, 'pay_method': None, 'project_id': None, 'keyword': ''}}
    for raw in ('0', 'abc', ' -3 ', '1.5'):
        seen.clear()
        with pytest.raises(MustReportError, match='正整数'):
            m05_router.api_flows(year_month='', status='', pay_method='', project_id='',
                                 keyword='', notice_id=raw, load=load)
        assert not seen, f'notice_id={raw!r} 扩大到了全量读取'
    seen.clear()
    rows = m05_router.api_flows(year_month='', status='', pay_method='', project_id='',
                                keyword='', notice_id=str(a), load=load)['rows']
    assert not seen, '给了有效 notice_id 仍走了全量取数'
    assert rows == [r for r in flows.build_flows(s, year_month='')['rows'] if r['notice_id'] == a]


def test_scoped_proxies_keep_projection_order_and_supplier(scoped, monkeypatch):
    """② 收窄后的流水 / 留痕 / 关联：同投影同行序，且 `jc_supplier` / `has_link` 不退空。"""
    s, a, b, _ = scoped
    from tests.test_acc_jc_pay_link import _contract, _project
    p = _project(s, '__471_仓__')
    c = _contract(s, project_id=p.id, supplier='471 供应商')
    a_row = notices.get_notices_by_ids(s, [a])[0]
    a_row.category = 'jc'; a_row.ownership_id = p.id; s.flush()
    from app.mod11_jc import service as contracts
    assert contracts.act_link_notice(s, notice_id=a, contract_id=c.id)['ok']

    one = _flows_by_notice(s, [a])(a)
    every = _flows_by_notice(s)(a)
    assert one == every, '按对象取流水改变了投影或行序'
    assert _links_by_notice(s, [a])(a) == _links_by_notice(s)(a) == [c.id]
    assert _traces_by_notice(s, [a])(a) == _traces_by_notice(s)(a)

    narrow = build_rows(s, notice_ids=[a, b])
    wide = build_rows(s)
    got = {r.notice_id: (r.jc_supplier, r.has_link, r.flows, r.amount_paid) for r in narrow}
    want = {r.notice_id: (r.jc_supplier, r.has_link, r.flows, r.amount_paid) for r in wide if r.notice_id in (a, b)}
    assert got == want, '按对象装配让供应商 / 关联 / 已付金额发生了变化'
    assert got[a][0] == '471 供应商' and got[a][1] is True


def test_empty_scope_is_empty_and_never_queries(scoped, monkeypatch):
    """③ 空集合 = 空，且不查库（空选不等于全量）。"""
    s, a, b, _ = scoped

    def no_query(*args, **kwargs):
        raise AssertionError('空集合不得查库')

    assert notices.stat_trace_index_of(s, []) == {}
    assert flows.flows_of_notices(s, []) == []
    assert _links_by_notice(s, [])(a) == []
    monkeypatch.setattr(s, 'execute', no_query)
    assert notices.stat_trace_index_of(s, []) == {}
    assert flows.flows_of_notices(s, []) == []
    assert _links_by_notice(s, [])(a) == []
    monkeypatch.undo()
    assert build_rows(s, notice_ids=[]) == [], '空选被当成全量了'
