"""真实API、费用服务和成品工作簿核对月度用油及显式旧值接续。"""
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest

from app.core.db import session_scope
from app.core.errors import DataConflictError, MustReportError
from app.mod09_fee import service as fees
from app.mod09_fee.models import FeeItem, FeeManualItem, FeeOilBinding
from app.mod09_fee.oil_linkage import OIL_NAME
from app.mod13_oilcard.ledger import stage_opening
from tests.test_oilcard_archives import scene, create  # noqa: F401
from tests.test_oilcard_ledger import entry


def row(client, project, ym='2026-10'):
    result = client.get('/api/m13/linkage', params={'ym': ym})
    assert result.status_code == 200, result.text
    return next(item for item in result.json()['rows'] if item['project_id'] == project)


def save(client, current, amount, remark=''):
    result = client.put(f"/api/m13/linkage/{current['project_id']}/{current['ym']}/fee", json={
        'amount': amount, 'remark': remark, 'version': current['version']})
    assert result.status_code == 200, result.text
    assert result.headers.get('X-Operation-History') == 'recorded'
    return result.json()['item']


def enable(client, project):
    result = client.post(f'/api/m13/linkage/{project}/enable')
    assert result.status_code == 200, result.text
    assert result.json()['enabled']


def test_monthly_result_adjustments_transfers_invoice_exclusion_and_export(scene, tmp_path, monkeypatch):
    client, (project, other) = scene
    first = create(client, 'accounts', project_id=project, name='第一账户')
    second = create(client, 'accounts', project_id=project, name='同项目账户')
    target = create(client, 'accounts', project_id=other, name='另一项目')
    entry(client, first, '10000', date_text='2026-10-01')
    entry(client, second, '200', kind='adjustment', date_text='2026-10-31')
    entry(client, first, '9000', date_text='原始数据')
    entry(client, first, '8000', date_text='2026-11-01')
    entry(client, first, '70', date_text='2025-12-31')
    with session_scope() as session:
        stage_opening(session, source_key='fee-opening', source_note='合成已核期初', account_id=first['id'],
            project_id=project, amount='500', cutoff_ym='2025-11', confirmed=True)
        # 开票仅参与核对，绝不冲减报表充值。
        from app.mod13_oilcard.models import OilInvoice, OilInvoiceAllocation
        invoice = OilInvoice(invoice_no='461-isolated', status='registered', amount=Decimal('3000'))
        session.add(invoice); session.flush()
        session.add(OilInvoiceAllocation(invoice_id=invoice.id, account_id=first['id'], project_id=project, amount=Decimal('3000')))
    assert row(client, project)['recharge_amount'] == '10200.00'
    enable(client, project)
    current = save(client, row(client, project), '50', '当月额外费用')
    assert current['fee_amount'] == '10250.00'
    next_month = row(client, project, '2026-11')
    assert next_month['custom_amount'] is None and next_month['remark'] == '' and next_month['fee_amount'] == '8000.00'
    assert save(client, next_month, '-20', '次月减少')['fee_amount'] == '7980.00'
    assert save(client, row(client, project, '2026-11'), '0', '真实零')['custom_amount'] == '0.00'
    transfer = client.post('/api/m13/ledger/transfers', json={'request_id': str(uuid4()),
        'out_project_id': project, 'out_account_id': first['id'], 'in_project_id': other,
        'in_account_id': target['id'], 'amount': '30', 'date_text': '2026-10-15'})
    assert transfer.status_code == 200, transfer.text
    assert row(client, project)['fee_amount'] == '10220.00'
    assert row(client, other)['recharge_amount'] == '30.00'
    with session_scope() as session:
        data = fees.build_year_data(session, year='2026', project='__oilcard_a__')
        oil = next(item for item in data['rows'] if item['item'] == OIL_NAME)
        assert oil['prior'] == Decimal('70') and oil['months'][9] == Decimal('10220')
        assert not oil['manual'] and not oil.get('item_id')
        assert fees.build_page_data(session, {'ym': '2026-10', 'project': '__oilcard_a__'})['total'] == Decimal('10220')
        export = fees.build_export_data(session, end_ym='2026-10', project='__oilcard_a__')
        exported = next(item for item in export['rows'] if item['item'] == OIL_NAME)
        assert exported['months'][-1] == Decimal('10220') and exported['total'] == Decimal('10290')
        from app.report_export import service as exports
        monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)
        path = exports.export_ledger(session, ['__oilcard_a__'], ym='2026-10')
    workbook = openpyxl.load_workbook(path, data_only=True)
    try:
        sheet = workbook['特殊费用月报表']
        month_col = next(cell.column for cell in sheet[2] if cell.value == '2026-10')
        oil_row = next(values for values in sheet.iter_rows() if values[0].value == OIL_NAME)
        assert oil_row[month_col - 1].value == 10220 and oil_row[-1].value == 10290
    finally:
        workbook.close()


def test_custom_and_independent_remark_permissions_conflict_undo_redo(scene):
    client, (project, _) = scene
    assert row(client, project)['can_enable']
    pending = client.put(f'/api/m13/linkage/{project}/2026-10/fee', json={'amount': '50'})
    assert pending.status_code == 400
    enable(client, project)
    original = row(client, project)
    first = save(client, original, '-50', '油费独立备注')
    stale = client.put(f'/api/m13/linkage/{project}/2026-10/fee', json={'amount': '99', 'version': original['version']})
    assert stale.status_code == 409 and row(client, project) == first
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    assert row(client, project)['custom_amount'] is None
    assert client.post('/api/history/redo', json={'operation_id': operation['id']}).json()['ok']
    assert row(client, project) == first
    second = save(client, first, '-50', '仅改备注')
    assert second['custom_amount'] == '-50.00' and second['remark'] == '仅改备注'
    assert save(client, second, None, '保留备注')['custom_amount'] is None
    assert row(client, project)['remark'] == '保留备注'
    with session_scope() as session:
        fees.create_item(session, project_key='__oilcard_a__', name='后来新增运费')
    assert row(client, project)['enabled'] and not row(client, project)['can_enable']
    client.cookies.clear()
    assert client.put(f'/api/m13/linkage/{project}/2026-10/fee', json={'amount': '1'}).status_code == 401
    assert client.post(f'/api/m13/linkage/{project}/enable').status_code == 401


def legacy_item(session, project, name='工程用油', ym='2026-10', amount='12000'):
    item = FeeItem(project_id=project, name=name)
    session.add(item); session.flush()
    monthly = FeeManualItem(fee_item_id=item.id, project_id=project, item_name=name, ym=ym, amount=Decimal(amount))
    session.add(monthly); session.flush()
    return item.id, monthly.id


def test_pending_legacy_not_guessed_and_binding_preserves_original_blocks_all_old_writes(scene):
    client, (project, _) = scene
    account = create(client, 'accounts', project_id=project, name='旧用油核对')
    entry(client, account, '10000', date_text='2026-10-10')
    with session_scope() as session:
        item_id, monthly_id = legacy_item(session, project, amount='11999')
        freight, _ = legacy_item(session, project, name='运费', amount='200')
    from tests.test_operation_history import perform, replay
    _, recorded = perform('/api/m09/fee/item/amount', lambda session: fees.item_action(session,
        project_key='__oilcard_a__', item_id=item_id, action='amount', ym='2026-10', value='12000'), actor='__legacy_other_actor__')
    assert recorded == 'recorded'
    with session_scope() as session:
        reviewed = fees.review_oil_linkage(session, project_id=project)
        assert fees.build_year_data(session, year='2026', project='__oilcard_a__')['months'][9] == Decimal('12200')
        export = fees.build_export_data(session, end_ym='2026-10', project='__oilcard_a__')
        assert sum(item['months'][-1] or 0 for item in export['rows']) == Decimal('12200')
    assert not row(client, project)['enabled'] and not row(client, project)['can_enable']
    assert client.post(f'/api/m13/linkage/{project}/enable').status_code == 400
    with pytest.raises(DataConflictError):
        with session_scope() as session:
            fees.enable_oil_linkage(session, project_id=project, fee_item_id=item_id, reviewed_items=[], converted_customs=[], source_note='过期清单')
    with pytest.raises(MustReportError, match='逐月'):
        with session_scope() as session:
            fees.enable_oil_linkage(session, project_id=project, fee_item_id=item_id, reviewed_items=reviewed, converted_customs=[], source_note='缺月')
    with session_scope() as session:
        fees.enable_oil_linkage(session, project_id=project, fee_item_id=item_id, reviewed_items=reviewed,
            converted_customs=[{'ym': '2026-10', 'amount': '2000', 'remark': '已核差额'}], source_note='合成旧12000与自动10000核对')
        assert session.get(FeeManualItem, monthly_id).amount == Decimal('12000')
        assert fees.build_year_data(session, year='2026', project='__oilcard_a__')['months'][9] == Decimal('12200')
        assert session.query(FeeOilBinding).filter_by(project_id=project).one().fee_item_id == item_id
    with pytest.raises(MustReportError, match='后续操作'):
        replay('undo', actor='__legacy_other_actor__')
    base = {'project': '__oilcard_a__', 'ym': '2026-10', 'index': 0, 'value': '999'}
    for endpoint in ('amount', 'name', 'delete'):
        assert client.post('/api/m09/fee/' + endpoint, json=base).json()['ok'] is False
    for action in ('amount', 'rename', 'delete'):
        assert client.post('/api/m09/fee/item/' + action, json={**base, 'item_id': item_id}).json()['ok'] is False
    assert not client.post('/api/m09/fee/add', json={**base, 'name': '工程用油', 'raw': '3', 'ym': '2026-11'}).json()['ok']
    assert not client.post('/api/m09/fee/batch', json={'project': '__oilcard_a__', 'items': ['工程用油'], 'months': [{'ym': '2026-10', 'values': {'工程用油': '999'}}]}).json()['ok']
    assert client.post('/api/m09/fee/item/amount', json={**base, 'item_id': freight, 'value': '300'}).json()['ok']
    with session_scope() as session:
        assert session.get(FeeManualItem, monthly_id).amount == Decimal('12000')
    assert row(client, project)['fee_amount'] == '12000.00'


@pytest.mark.parametrize('prior_action', ['new_item_undo', 'amount_redo'])
def test_binding_invalidates_other_accounts_old_parent_and_redo_credentials(scene, prior_action):
    from tests.test_operation_history import perform, replay
    client, (project, _) = scene
    actor = '__legacy_parent_actor__'
    result, recorded = perform('/api/m09/fee/add', lambda session: fees.act_add(session,
        project_key='__oilcard_a__', ym='2026-10', name='经核对的旧项目项', raw='80'), actor=actor)
    assert recorded == 'recorded'
    with session_scope() as session:
        item_id = session.get(FeeManualItem, result['row_id']).fee_item_id
    if prior_action == 'amount_redo':
        _, recorded = perform('/api/m09/fee/item/amount', lambda session: fees.item_action(session,
            project_key='__oilcard_a__', item_id=item_id, action='amount', ym='2026-10', value='90'), actor=actor)
        assert recorded == 'recorded'
        replay('undo', actor=actor)
    with session_scope() as session:
        reviewed = fees.review_oil_linkage(session, project_id=project)
        fees.enable_oil_linkage(session, project_id=project, fee_item_id=item_id, reviewed_items=reviewed,
            converted_customs=[{'ym': '2026-10', 'amount': '80', 'remark': '已核自定义额'}], source_note='另一账号明确接续')
    with pytest.raises(MustReportError, match='后续操作'):
        replay('redo' if prior_action == 'amount_redo' else 'undo', actor=actor)
    with session_scope() as session:
        assert session.get(FeeManualItem, result['row_id']).amount == Decimal('80')
        assert session.get(FeeItem, item_id) is not None
    assert row(client, project)['fee_amount'] == '80.00'
