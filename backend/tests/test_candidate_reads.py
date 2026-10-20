"""候选读取跨真实查询验证；仅专用测试库，所有写入由rollback_db回滚。"""
from sqlalchemy import event

from app.core.db import session_scope
from app.mod11_jc import service as S, repository as R
from tests.test_acc_jc_pay_link import _project, _contract, _notice
from tests.test_jc_auto_link import source


def measured_read(connection, call):
    statements = []

    def trace(conn, cursor, statement, params, context, many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append((statement, params))

    event.listen(connection, 'before_cursor_execute', trace)
    try:
        with session_scope() as s:
            result = call(s)
        return result, statements
    finally:
        event.remove(connection, 'before_cursor_execute', trace)


def test_推荐只读候选发票一次且序号不随候选范围变化(rollback_db):
    with session_scope() as s:
        project = _project(s, '__候选读取__')
        earlier = _contract(s, project_id=project.id, supplier='其他供应商')
        earlier.contract_date = '2026-01-01'
        target = _contract(s, project_id=project.id, supplier='甲')
        target.contract_date = '2026-10-02'
        R.insert_invoice(s, contract_id=target.id, kind='supplier', invoice_date='2026-10-01', amount='100.01')
        notice = _notice(s, ph='__候选只读__', approved='100.01')
        notice.ownership_id = project.id; notice.jc_supplier = '甲'
        s.flush(); nid, cid = notice.id, target.id
    result, queries = measured_read(rollback_db, lambda s: S.link_recommendations(s, nid))
    assert [row['id'] for row in result['rows']] == [cid]
    assert result['rows'][0]['project_seq'] == 2
    invoices = [(sql, params) for sql, params in queries if 'FROM jc_invoice' in sql]
    assert len(invoices) == 1
    assert set(invoices[0][1].values()) == {cid}
    with session_scope() as s:
        assert R.payment_of_notice(s, nid) is None


def test_批量预览查询次数不随通知书数量增长(rollback_db):
    with session_scope() as s:
        project = _project(s, '__候选批量__')
        contract = _contract(s, project_id=project.id, supplier='甲'); contract.contract_no = 'CGHT1'
        notices = [_notice(s, ph='__候选批量__'+str(i), approved='100.01') for i in range(24)]
        for notice in notices:
            notice.ownership_id = project.id; notice.jc_supplier = '甲'
            notice.project_name = '项目全名'; notice.approve_status = '已批'
        s.flush(); ids = [n.id for n in notices]
    one, one_queries = measured_read(rollback_db, lambda s: S.auto_link_plan(s, ids[:1], [source()]))
    many, many_queries = measured_read(rollback_db, lambda s: S.auto_link_plan(s, ids, [source()]))
    assert one['ready'] == 1 and many['ready'] == 24
    assert len(many_queries) == len(one_queries)
    assert [row['notice_id'] for row in many['rows']] == ids


def test_保留跨项目当前关联及缺失重复空输入的原行为(rollback_db):
    with session_scope() as s:
        project = _project(s, '__候选当前__'); other = _project(s, '__候选外部__')
        current = _contract(s, project_id=other.id, supplier='乙')
        target = _contract(s, project_id=project.id, supplier='甲')
        notice = _notice(s, ph='__候选当前__', approved='100.01')
        notice.ownership_id = project.id; notice.jc_supplier = '甲'; notice.approve_status = '已批'
        s.flush()
        S.act_link_notice(s, notice_id=notice.id, contract_id=current.id)
        data = S.link_recommendations(s, notice.id)
        assert {row['id'] for row in data['rows']} == {current.id, target.id}
        assert data['current_contract_id'] == current.id
        assert next(row for row in data['rows'] if row['id'] == current.id)['recommendation']['reasons'] == []
        plan = S.auto_link_plan(s, [notice.id, -1, notice.id], [])
        assert [row['notice_id'] for row in plan['rows']] == [notice.id, -1]
        assert [row['reason'] for row in plan['rows']] == ['已有合同关联，保持不变', '非有效集采通知书']
        assert R.payment_of_notice(s, notice.id).contract_id == current.id
    empty, queries = measured_read(rollback_db, lambda s: S.auto_link_plan(s, [], []))
    assert empty == {'ok': True, 'rows': [], 'ready': 0} and queries == []
