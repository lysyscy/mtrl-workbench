"""大表用油截止累计、同笔沿用、旧入口和跨账号历史及真实Excel。"""
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest

from app.core import history
from app.core.db import session_scope
from app.core.errors import DataConflictError, MustReportError
from app.history_bindings import configure
from app.mod07_setl import service as big
from app.mod07_setl.models import AnalysisBigManual
from app.mod13_oilcard.ledger import stage_opening
from tests.test_oilcard_archives import scene, create, edit  # noqa: F401
from tests.test_oilcard_ledger import entry
from tests.test_oilcard_fee_linkage import row, save, enable
from tests.test_operation_history import perform, replay


def enable_big(client, project):
    result = client.post(f'/api/m13/linkage/{project}/big/enable')
    assert result.status_code == 200, result.text


def extra(client, current, amount, remark=''):
    source = current['big']
    result = client.put(f"/api/m13/linkage/{current['project_id']}/{current['ym']}/big", json={
        'amount': amount, 'remark': remark, 'version': source['version'],
        'source_ym': source['source_ym'], 'source_version': source['source_version']})
    assert result.status_code == 200, result.text
    assert result.headers.get('X-Operation-History') == 'recorded'
    return result.json()['item']


def big_row(client, ym='2026-10'):
    result = client.get('/api/m07/big', params={'period': ym})
    assert result.status_code == 200, result.text
    return next(item for item in result.json()['rows'] if item['warehouse'] == '__oilcard_a__')


def test_confirmed_formula_carry_zero_clear_and_actual_big_excel(scene, tmp_path, monkeypatch):
    client, (project, _) = scene
    account = create(client, 'accounts', project_id=project, name='大表公式')
    enable(client, project); enable_big(client, project)
    entry(client, account, '10000', date_text='2026-10-01')
    entry(client, account, '200', kind='adjustment', date_text='2026-10-31')
    save(client, row(client, project), '50', '十月特殊费用')
    october = extra(client, row(client, project), '1000', '十月额外说明')
    assert october['big']['amount'] == '11250.00'
    entry(client, account, '4900', date_text='2026-11-01')
    save(client, row(client, project, '2026-11'), '-20', '十一月特殊费用')
    november = row(client, project, '2026-11')
    assert november['big']['amount'] == '16130.00'
    assert november['big']['extra_amount'] == '1000.00' and november['big']['remark'] == '十月额外说明'
    assert november['big']['source_ym'] == '2026-10' and november['big']['version'] is None
    november = extra(client, november, '1000', '本月仅改独立备注')
    assert november['big']['source_ym'] == '2026-11' and november['big']['remark'] == '本月仅改独立备注'
    november = extra(client, november, '0', '清零说明')
    assert november['big']['amount'] == '15130.00'
    december = row(client, project, '2026-12')['big']
    assert december['amount'] == '15130.00' and december['extra_amount'] == '0.00' and december['remark'] == '清零说明'
    entry(client, account, '99999', date_text='2027-01-01')
    assert big_row(client, '2026-11')['manual']['oil']['value'] == '15130.00'
    assert big_row(client, '2026-11')['oil_linked'] is True
    # 清本月一笔同时恢复前笔金额和对应备注；撤销/重做真实恢复或删除同一快照。
    cleared = extra(client, row(client, project, '2026-11'), None)
    assert cleared['big']['version'] is None and cleared['big']['amount'] == '16130.00'
    assert cleared['big']['source_ym'] == '2026-10' and cleared['big']['remark'] == '十月额外说明'
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert row(client, project, '2026-11')['big']['amount'] == '15130.00'
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert row(client, project, '2026-11')['big']['amount'] == '16130.00'
    from app.report_export import service as exports
    monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
    with session_scope() as session:
        path = exports.export_big(session, '2026-11')
    workbook = openpyxl.load_workbook(path, data_only=True)
    try:
        assert workbook['Sheet1']['S5'].value == 16130
        assert workbook['Sheet1']['S6'].value == 16130
        assert workbook['Sheet1']['T5'].value is None
    finally:
        workbook.close()


def test_prior_year_confirmed_opening_cutoff_attribution_and_transfers(scene):
    client, (project, other) = scene
    account = create(client, 'accounts', project_id=project, name='跨年账户')
    peer = create(client, 'accounts', project_id=project, name='同项目另一账户')
    target = create(client, 'accounts', project_id=other, name='另一项目账户')
    enable(client, project); enable_big(client, project)
    enable(client, other); enable_big(client, other)
    entry(client, account, '70', date_text='2025-12-31')
    entry(client, account, '10200', date_text='2026-10-01')
    entry(client, account, '88888', date_text='原始数据')
    with session_scope() as session:
        for key, amount, cutoff, confirmed in [('confirmed', '100', '2025-11', True),
                ('unconfirmed', '9000', '2025-11', False), ('future', '8000', '2026-11', True)]:
            stage_opening(session, source_key=key, source_note='合成期初依据', project_id=project,
                account_id=account['id'], amount=amount, cutoff_ym=cutoff, confirmed=confirmed)
    save(client, row(client, project, '2025-12'), '5', '往年自定义')
    save(client, row(client, project), '50', '当月自定义')
    assert extra(client, row(client, project), '-20', '负数额外')['big']['amount'] == '10405.00'
    fields = {'request_id': str(uuid4()), 'out_project_id': project, 'out_account_id': account['id'],
        'in_project_id': project, 'in_account_id': peer['id'], 'amount': '10', 'date_text': '2026-10-15'}
    assert client.post('/api/m13/ledger/transfers', json=fields).status_code == 200
    assert row(client, project)['big']['amount'] == '10405.00'
    assert client.post('/api/m13/ledger/transfers', json={**fields, 'request_id': str(uuid4()),
        'in_project_id': other, 'in_account_id': target['id'], 'amount': '30'}).status_code == 200
    assert row(client, project)['big']['amount'] == '10375.00' and row(client, other)['big']['amount'] == '30.00'
    edit(client, 'accounts', account, project_id=other, status='archived')
    assert row(client, project)['big']['amount'] == '10375.00'
    assert row(client, project, '2025-10')['big']['amount'] == '0.00'


def test_source_conflict_scope_permissions_and_zero_requires_review(scene):
    client, (project, other) = scene
    assert client.post(f'/api/m13/linkage/{project}/big/enable').status_code == 400
    enable(client, project); enable_big(client, project)
    october = extra(client, row(client, project), '1000', '沿用来源')
    stale = row(client, project, '2026-11')
    extra(client, october, '1100', '另一账号更新来源')
    result = client.put(f'/api/m13/linkage/{project}/2026-11/big', json={'amount': '1000', 'remark': '旧来源',
        'version': None, 'source_ym': stale['big']['source_ym'], 'source_version': stale['big']['source_version']})
    assert result.status_code == 409
    assert row(client, project, '2026-11')['big']['version'] is None
    assert client.put(f'/api/m13/linkage/{other}/2026-10/big', json={'amount': '1000'}).status_code == 400
    enable(client, other)
    with session_scope() as session:
        session.add(AnalysisBigManual(ym='2026-10', warehouse_name='__oilcard_b__', project_id=other, oil=Decimal('0')))
    assert not row(client, other)['big']['can_enable']
    assert client.post(f'/api/m13/linkage/{other}/big/enable').status_code == 400
    client.cookies.clear()
    assert client.put(f'/api/m13/linkage/{project}/2026-10/big', json={'amount': '2'}).status_code == 401
    assert client.post(f'/api/m13/linkage/{project}/big/enable').status_code == 401


def test_explicit_old_totals_preserved_other_fields_work_and_remarks_independent(scene):
    client, (project, _) = scene
    enable(client, project)
    account = create(client, 'accounts', project_id=project, name='旧总额核对')
    entry(client, account, '10000', date_text='2026-10-01')
    with session_scope() as session:
        old = AnalysisBigManual(ym='2026-10', warehouse_name='__oilcard_a__', project_id=project,
            oil=Decimal('12000'), note='大表通用备注')
        session.add(old); session.flush(); old_id = old.id
        reviewed = big.review_big_oil(session, project_id=project)
    assert not big_row(client)['oil_linked'] and big_row(client)['manual']['oil']['value'] == '12000.00'
    assert client.post('/api/m07/big/cell', json={'month': '2026-10', 'warehouse': '__oilcard_a__', 'key': 'oil', 'raw': '999'}).json()['ok'] is False
    with pytest.raises(DataConflictError):
        with session_scope() as session:
            big.enable_big_oil(session, project_id=project, reviewed_rows=[], converted_customs=[], source_note='过期清单')
    with pytest.raises(MustReportError, match='逐月'):
        with session_scope() as session:
            big.enable_big_oil(session, project_id=project, reviewed_rows=reviewed, converted_customs=[], source_note='缺差额')
    with session_scope() as session:
        big.enable_big_oil(session, project_id=project, reviewed_rows=reviewed,
            converted_customs=[{'ym': '2026-10', 'amount': '2000', 'remark': '单独用油说明'}], source_note='已核旧12000与累计10000')
        assert session.get(AnalysisBigManual, old_id).oil == Decimal('12000')
    result = big_row(client)
    assert result['oil_linked'] and result['manual']['oil']['value'] == '12000.00'
    assert result['manual']['note']['value'] == '大表通用备注'
    assert row(client, project, '2026-11')['big']['remark'] == '单独用油说明'
    response = client.post('/api/m07/big/cell', json={'month': '2026-10', 'warehouse': '__oilcard_a__', 'key': 'note', 'raw': '正常修改通用备注'})
    assert response.json()['ok'] and response.headers.get('X-Operation-History') == 'recorded'
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert big_row(client)['manual']['note']['value'] == '大表通用备注'
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert big_row(client)['manual']['note']['value'] == '正常修改通用备注'
    assert row(client, project)['big']['remark'] == '单独用油说明'


@pytest.mark.parametrize('kind,direction', [('new', 'undo'), ('new', 'redo'), ('update', 'undo'), ('update', 'redo')])
def test_old_oil_history_cannot_bypass_retirement_from_other_account(scene, kind, direction):
    client, (project, _) = scene
    enable(client, project)
    actor = '__old_big_other_actor__'
    old_policies = [(method, pattern, label, [replace(rule, fields=rule.fields | {'oil'}, retired_fields=frozenset())
        if rule.model is AnalysisBigManual else rule for rule in rules]) for method, pattern, label, rules in history._policies]
    if kind == 'update':
        with session_scope() as session:
            session.add(AnalysisBigManual(ym='2026-10', warehouse_name='__oilcard_a__', project_id=project, oil=Decimal('80')))
    def old_write(session):
        from sqlalchemy import select
        from app.mod07_setl.big_service import materialize_selection
        materialize_selection(session, '2026-10')
        old = session.scalar(select(AnalysisBigManual).where(AnalysisBigManual.warehouse_name == '__oilcard_a__'))
        if old is None:
            old = AnalysisBigManual(ym='2026-10', warehouse_name='__oilcard_a__', project_id=project)
            session.add(old)
        old.oil = Decimal('0') if kind == 'new' else Decimal('90')
    history.bind_policies(old_policies)
    try:
        _, recorded = perform('/api/m07/big/cell', old_write, actor=actor)
        assert recorded == 'recorded'
        if direction == 'redo':
            replay('undo', actor=actor)
    finally:
        configure()
    from sqlalchemy import select
    from app.mod07_setl.models import AnalysisBigMonthProject
    with session_scope() as session:
        before_selection = [(item.id, item.ym, item.warehouse_name, item.seq) for item in session.scalars(select(AnalysisBigMonthProject))]
    with pytest.raises(MustReportError, match='已退出编辑|恢复规则'):
        replay(direction, actor=actor)
    with session_scope() as session:
        assert [(item.id, item.ym, item.warehouse_name, item.seq) for item in session.scalars(select(AnalysisBigMonthProject))] == before_selection
    # 未接续也不能经旧history重写；确认后继续保留相同旧依据。
    with session_scope() as session:
        reviewed = big.review_big_oil(session, project_id=project)
        converted = [{'ym': item['ym'], 'amount': item['oil'], 'remark': '已核额外值'} for item in reviewed if item['oil'] is not None]
        big.enable_big_oil(session, project_id=project, reviewed_rows=reviewed, converted_customs=converted, source_note='独立账号接续')
    with pytest.raises(MustReportError, match='已退出编辑|恢复规则'):
        replay(direction, actor=actor)
