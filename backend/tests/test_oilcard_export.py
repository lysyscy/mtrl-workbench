"""核真实下载工作簿，取数范围及原文不依赖页面筛选。"""
from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook

from app.core.money import to_money
from tests.test_oilcard_archives import scene, create  # noqa: F401
from tests.test_oilcard_ledger import entry


def test_full_workbook_keeps_all_saved_rows_original_dates_and_text_card_numbers(scene):
    client, (project, other) = scene
    card = create(client, 'cards', card_no='0001234567890123456789')
    first = create(client, 'accounts', project_id=project, name='甲用卡', card_id=card['id'])
    second = create(client, 'accounts', project_id=other, name='乙用卡')
    recharge = entry(client, first, '10000', date_text='原始数据', remark='=保留原文')
    entry(client, first, '200', kind='adjustment', date_text='2026-10-31')
    entry(client, second, '-20', kind='adjustment', date_text='')
    refund = client.post('/api/m13/ledger/refunds', json={'request_id': str(uuid4()),
        'original_id': recharge['id'], 'amount': '125.50', 'date_text': '退款待核', 'remark': '实际退款'}).json()['item']
    result = client.get('/api/m13/ledger/export?kind=adjustment&project_id=0')
    assert result.status_code == 200 and result.headers['X-Export-Filename'].endswith('.xlsx')
    assert 'attachment' in result.headers['Content-Disposition']
    sheet = load_workbook(BytesIO(result.content), data_only=False).active
    rows = list(sheet.values)
    assert len(rows) == 6
    assert rows[0] == ('记录编号', '日期', '类型', '项目', '用卡账户', '实体卡号', '金额', '备注', '关联原充值')
    assert [row[1] for row in rows[1:-1]] == ['原始数据', '2026-10-31', None, '退款待核']
    assert [to_money(row[6]) for row in rows[1:-1]] == [to_money('10000'), to_money('200'), to_money('-20'), to_money('-125.50')]
    assert rows[1][5] == '0001234567890123456789' and sheet['F2'].data_type == 's'
    assert rows[1][7] == '=保留原文' and sheet['H2'].data_type == 's'
    assert rows[4][0] == refund['id'] and rows[4][8] == recharge['id']
    assert rows[-1][0] == '合计' and to_money(rows[-1][6]) == to_money('10054.50')


def test_undo_removed_entry_is_not_exported_and_decimals_match_authority(scene):
    client, (project, _) = scene
    account = create(client, 'accounts', project_id=project, name='金额核对')
    entry(client, account, '0.10')
    entry(client, account, '0.20')
    removed = entry(client, account, '50')
    operation = client.get('/api/history/status').json()['undo']
    assert client.post('/api/history/undo', json={'operation_id': operation['id']}).json()['ok']
    sheet = load_workbook(BytesIO(client.get('/api/m13/ledger/export').content), data_only=True).active
    rows = list(sheet.values)
    assert len(rows) == 4 and removed['id'] not in [row[0] for row in rows[1:-1]]
    assert to_money(rows[-1][6]) == to_money('0.30')
