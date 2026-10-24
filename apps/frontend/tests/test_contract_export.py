"""TAIL-418: settlement/debt totals, maintenance, and both contract export files.

Isolated real-backend checks for the contracts page export entry:
- settle/pay_sum/debt agree between the grid, the detail API and the seed facts;
- allowed maintenance (history settle, manual payment, inline fields) saves and re-reads,
  rejections change nothing;
- export/print-export need login (401 direct, buttons disabled, data unchanged);
- damaged receipts lock instead of silently retrying; exports produce real files
  saved only into this run's artifacts.
"""
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import openpyxl
import pytest
from playwright.sync_api import expect
from preview_select import pick_option, pick_popup_option
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output

BEIJING = timezone(timedelta(hours=8))
ORD_HEADERS = ['序号', '合同日期', '材料名', '合同编号', '供应商', '合同金额', '发票金额',
               '贸易公司名', '贸易公司合同金额', '贸易公司发票金额', '结算金额', '付款金额',
               '欠款金额', '账期', '合同付款方式', '备注', '三态', '合同存档情况', '存档号', '寄回日期']


@pytest.fixture(scope='module')
def preview_seed(make_preview_seed):
    def seed(env):
        code = """
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod11_jc.models import JcContract, JcInvoice, JcPayment
from app.mod03_notice.models import PaymentNotice
from sqlalchemy import select
with session_scope() as s:
    p=s.scalar(select(Project).where(Project.disp=='隔离项目'))
    q=s.scalar(select(Project).where(Project.disp=='长项目名验收'))
    a=JcContract(project_id=p.id,contract_no='TAIL418-ORD',contract_date='2026-10-01',material_name='隔离结算合同',supplier='合成供应商',contract_amt=12345.67,payment_term='60±7天',payment_method='承兑')
    s.add(a);s.flush()
    s.add(JcInvoice(contract_id=a.id,kind='supplier',invoice_date='2026-10-10',amount=1000.50))
    s.add(JcPayment(contract_id=a.id,source='manual',pay_date='2026-10-15',amount=400.25))
    t=JcContract(project_id=p.id,contract_no='TAIL418-TRADE',contract_date='2026-10-02',material_name='隔离贸易合同',supplier='合成供应商',contract_amt=9000,trade_co='合成贸易公司',trade_contract_amt=8000)
    s.add(t);s.flush()
    s.add(JcInvoice(contract_id=t.id,kind='trade',invoice_date='2026-10-11',amount=8000))
    s.add(JcInvoice(contract_id=t.id,kind='supplier',invoice_date='2026-10-12',amount=999))
    x=JcContract(project_id=p.id,contract_no='TAIL418-OUT',contract_date='2026-10-03',material_name='隔离排除合同',supplier='另一供应商',contract_amt=500,tag='不纳入')
    s.add(x)
    h=JcContract(project_id=p.id,material_name='TAIL418历史汇总',supplier='合成供应商',remark='历史未结金额；核对截至日：2025-11-30')
    s.add(h);s.flush()
    s.add(JcInvoice(contract_id=h.id,kind='supplier',invoice_date='2025-11-30',amount=888.88))
    b=JcContract(project_id=q.id,contract_no='TAIL418-P2',contract_date='2026-10-05',material_name='二期结算合同',supplier='合成供应商',contract_amt=77.77)
    s.add(b);s.flush()
    s.add(JcInvoice(contract_id=b.id,kind='supplier',invoice_date='2026-10-05',amount=77.77))
    n=PaymentNotice(ph_id='TAIL418-NOTICE',bill_no='TAIL418-NOTICE',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-10-01',approve_status='已批',amount_approved=100,stat_settle=100,stat_paid=0)
    s.add(n);s.flush()
    s.add(JcPayment(contract_id=a.id,source='notice',notice_id=n.id,pay_date='',amount=0))
"""
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, check=True)
    return make_preview_seed(seed)


def rows_of(page, server):
    return page.request.get(server + '/api/m11/list').json()['rows']


def detail(page, server, cid):
    return page.request.get(server + f'/api/m11/detail?id={cid}').json()['data']


def cents_of(value):
    return Decimal(str(value or '0'))


def fmt(value):
    return f'{float(value):,.2f}'


def grid_row(page, row_label):
    """Center-container row holding the inline cell with the given aria-label."""
    return page.get_by_label(row_label, exact=True).locator('xpath=ancestor::*[@role="row"][1]')


def open_contracts(page, server):
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    expect(page.get_by_role('row').filter(has_text='TAIL418-ORD')).to_be_visible()
    # The export entries stay aria-disabled while the contracts/projects queries settle.
    expect(page.get_by_role('button', name='导出 Excel', exact=True)).to_be_enabled()
    expect(page.get_by_role('button', name='导出打印版…', exact=True)).to_be_enabled()


def test_export_buttons_and_endpoints_require_login(server, browser_page):
    page, _ = browser_page
    page.goto(server + '/preview/contracts')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='导出 Excel', exact=True)).to_be_disabled()
    expect(page.get_by_role('button', name='导出打印版…', exact=True)).to_have_attribute('aria-disabled', 'true')
    before = len(page.request.get(server + '/api/m11/list').json()['rows'])
    assert before == 5, before
    with httpx.Client(base_url=server) as client:
        for path, payload in [
            ('/api/m11/export', {'ids': [1, 2, 3]}),
            ('/api/m11/print-export', {'projects': ['隔离验收仓库']}),
        ]:
            response = client.post(path, json=payload)
            assert response.status_code == 401, (path, response.status_code)
            assert '未登录' in response.json()['message']
    assert len(page.request.get(server + '/api/m11/list').json()['rows']) == before


def test_detail_totals_match_grid_and_settlement_semantics(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    rows = rows_of(page, server)
    ids = {r['contract_no'] or r['material']: r['id'] for r in rows}
    assert len(rows) == 5
    # Independent seed facts: settle/pay/debt derive from the invoice and payment subtables.
    d = detail(page, server, ids['TAIL418-ORD'])
    assert (d['settle'], d['pay_sum'], d['debt']) == ('1000.50', '400.25', '600.25')
    assert d['inv_sum'] == '1000.50' and [p['source'] for p in d['payments']] == ['manual', 'notice']
    d = detail(page, server, ids['TAIL418-TRADE'])
    # With a trade company, settle follows trade invoices; the supplier invoice must not leak in.
    assert (d['settle'], d['pay_sum'], d['debt']) == ('8000.00', '0.00', '8000.00')
    assert (d['inv_sum'], d['trade_inv_sum']) == ('999.00', '8000.00')
    d = detail(page, server, ids['TAIL418历史汇总'])
    # History summary: settle is the manual unsettled amount booked at the cutoff date.
    assert d['supplier_invoices'][0]['date'] == '2025-11-30'
    assert (d['settle'], d['pay_sum'], d['debt']) == ('888.88', '0.00', '888.88')
    d = detail(page, server, ids['TAIL418-P2'])
    assert (d['settle'], d['pay_sum'], d['debt']) == ('77.77', '0.00', '77.77')
    d = detail(page, server, ids['TAIL418-OUT'])
    assert (d['settle'], d['pay_sum'], d['debt']) == ('0.00', '0.00', '0.00')
    # The excluded row is hidden by the default tag filter; widen it before reading its cells.
    pick_option(page, '纳入状态', '全部')
    for label in ['TAIL418-ORD', 'TAIL418-TRADE', 'TAIL418历史汇总', 'TAIL418-P2', 'TAIL418-OUT']:
        cid = ids[label]
        d = detail(page, server, cid)
        assert Decimal(d['debt']) == Decimal(d['settle']) - Decimal(d['pay_sum'])
        row = grid_row(page, f'{label} 备注')
        for col in ['settle', 'pay_sum', 'debt']:
            # pay_sum/inv_sum cells also hold the 子表 button; match the money text node itself.
            expect(row.locator(f'[col-id="{col}"]').get_by_text(fmt(d[col]), exact=True)).to_be_visible()
    page.screenshot(path=str(output('tail418-totals-grid.png', kind='screenshots')), full_page=True)


def test_history_settle_and_manual_payment_save_reread(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    rows = rows_of(page, server)
    hid = next(r['id'] for r in rows if r['material'] == 'TAIL418历史汇总')
    ord_id = next(r['id'] for r in rows if r['contract_no'] == 'TAIL418-ORD')
    hist_row = grid_row(page, 'TAIL418历史汇总 备注')
    # The history settle subtable books the manual unsettled amount at the cutoff date.
    page.get_by_role('button', name='TAIL418历史汇总 供应商发票子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    expect(modal.get_by_role('heading', name='历史未结金额', exact=True)).to_be_visible()
    expect(modal.get_by_text('历史未结金额，核对截至日 2025-11-30；已扣除此前付款')).to_be_visible()
    modal.get_by_label('历史未结金额（元）', exact=True).fill('111.11')
    modal.get_by_role('button', name='新增历史未结金额', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='历史未结金额已新增')).to_be_visible()
    assert modal.locator('tbody tr[data-subtable="supplier"] td[data-label="金额（元）"]').all_text_contents() == ['888.88', '111.11']
    expect(modal.locator('tfoot').filter(has_text='历史未结合计').locator('.money')).to_have_text('999.99')
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()
    data = detail(page, server, hid)
    assert [(r['date'], r['amount']) for r in data['supplier_invoices']] == [('2025-11-30', '888.88'), ('2025-11-30', '111.11')]
    assert (data['settle'], data['debt']) == ('999.99', '999.99')
    expect(hist_row.locator('[col-id="settle"]')).to_have_text('999.99')
    # Manual payments go through the payment subtable and refresh pay_sum/debt everywhere.
    page.get_by_role('button', name='TAIL418历史汇总 付款子表', exact=True).click()
    expect(modal.locator('.subtable-summary .money')).to_have_text('999.99 元')
    modal.get_by_label('手工付款金额（元）', exact=True).fill('50')
    modal.get_by_role('button', name='新增手工付款', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='手工付款已新增')).to_be_visible()
    modal.get_by_role('button', name='关闭', exact=True).click()
    data = detail(page, server, hid)
    assert (data['settle'], data['pay_sum'], data['debt']) == ('999.99', '50.00', '949.99')
    expect(hist_row.locator('[col-id="pay_sum"]').get_by_text('50.00', exact=True)).to_be_visible()
    expect(hist_row.locator('[col-id="debt"]')).to_have_text('949.99')
    # A server-side rejection of an inline field leaves the stored value untouched.
    term = page.get_by_label('TAIL418-ORD 账期', exact=True)
    term.fill('abc')
    term.press('Tab')
    expect(page.get_by_role('alert').first).to_contain_text('账期请填写非负整数 x±y天')
    expect(page.get_by_role('alert').first).to_contain_text('勿重复操作')
    expect(term).to_be_disabled()
    assert detail(page, server, ord_id)['payment_term'] == '60±7天'
    page.get_by_role('button', name='重读核对', exact=True).click()
    expect(term).to_be_enabled()
    expect(term).to_have_value('abc')
    term.fill('75天')
    term.press('Tab')
    expect(page.locator('.contract-feedback')).to_contain_text('已保存')
    expect(term).to_have_value('75±0天')
    assert detail(page, server, ord_id)['payment_term'] == '75±0天'


def test_damaged_payment_receipt_lands_once_and_locks_until_reconciled(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    ord_id = next(r['id'] for r in rows_of(page, server) if r['contract_no'] == 'TAIL418-ORD')
    page.get_by_role('button', name='TAIL418-ORD 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    expect(modal.get_by_label('手工付款金额（元）', exact=True)).to_be_visible()
    writes = []

    def damaged(route):
        writes.append(route.request.post_data)
        response = route.fetch()
        assert response.ok and response.json()['ok'] is True
        route.fulfill(response=response, body='{')
    page.route('**/api/m11/payment/add', damaged)
    modal.get_by_label('手工付款金额（元）', exact=True).fill('33.33')
    modal.get_by_role('button', name='新增手工付款', exact=True).click()
    expect(modal.get_by_role('alert')).to_contain_text('未取得保存确认')
    expect(modal.get_by_role('alert')).to_contain_text('勿重复操作')
    assert len(writes) == 1
    data = detail(page, server, ord_id)
    assert sorted(r['amount'] for r in data['payments'] if r['source'] == 'manual') == ['33.33', '400.25']
    assert data['pay_sum'] == '433.58' and data['debt'] == '566.92'
    # The uncertain state only unlocks after an explicit reread and acknowledgement.
    modal.get_by_role('button', name='重读明细', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已重读，请对照已保存行与本次输入核对结果。')).to_be_visible()
    modal.get_by_role('button', name='已核对结果，继续处理', exact=True).click()
    expect(modal.get_by_role('alert')).to_have_count(0)
    assert len(writes) == 1
    modal.get_by_role('button', name='关闭', exact=True).click()
    # The kept draft input must be explicitly discarded on close.
    modal.get_by_role('button', name='放弃并关闭').click()
    expect(modal).not_to_be_visible()
    row = grid_row(page, 'TAIL418-ORD 备注')
    expect(row.locator('[col-id="pay_sum"]').get_by_text('433.58', exact=True)).to_be_visible()
    expect(row.locator('[col-id="debt"]')).to_have_text('566.92')
    page.screenshot(path=str(output('tail418-damaged-receipt.png', kind='screenshots')), full_page=True)


def test_ordinary_export_matches_filter_sort_ids_and_file(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    rows = rows_of(page, server)
    by_no = {r['contract_no'] or r['material']: r for r in rows}
    out_id = by_no['TAIL418-OUT']['id']
    # Supplier filter plus an ascending sort on 合同金额 define the exported range.
    page.get_by_label('供应商', exact=True).fill('合成供应商')
    page.get_by_role('columnheader', name=re.compile('^合同金额$')).click()
    expected = [r['id'] for r in sorted((r for r in rows if r['tag'] == '纳入台账' and '合成供应商' in r['supplier']),
                                        key=lambda r: cents_of(r['contract_amt']))]
    assert expected == [by_no['TAIL418历史汇总']['id'], by_no['TAIL418-P2']['id'],
                        by_no['TAIL418-TRADE']['id'], by_no['TAIL418-ORD']['id']]
    assert out_id not in expected
    with page.expect_request(lambda r: r.url.endswith('/api/m11/export')) as req_info, page.expect_download() as dl_info:
        page.get_by_role('button', name='导出 Excel', exact=True).click()
    ids = req_info.value.post_data_json['ids']
    assert ids == expected
    download = dl_info.value
    assert download.suggested_filename == f'集采台账_{datetime.now(BEIJING):%Y%m%d}.xlsx'
    target = output('tail418-ordinary-export.xlsx', kind='exports')
    download.save_as(target)
    page.screenshot(path=str(output('tail418-ordinary-grid.png', kind='screenshots')), full_page=True)
    facts = {cid: detail(page, server, cid) for cid in ids}
    row_of = {r['id']: r for r in rows}
    workbook = openpyxl.load_workbook(target, data_only=True)
    assert workbook.sheetnames == ['集采台账']
    ws = workbook['集采台账']
    assert [cell.value for cell in ws[1]] == ORD_HEADERS
    body = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(body) == len(ids) + 1
    for values, cid in zip(body, ids):
        r, d = row_of[cid], facts[cid]
        assert values[0] == (r['project_seq'] if r['project_seq'] is not None else '—')
        assert values[2] == r['material']
        assert values[3] == (r['contract_no'] or '—')
        assert values[16] == r['tag']
        for col, key in [(5, 'contract_amt'), (6, 'inv_sum'), (10, 'settle'), (11, 'pay_sum'), (12, 'debt')]:
            assert values[col] == pytest.approx(float(d[key]), abs=0.005), (r['contract_no'], key, values[col])
    totals = body[-1]
    assert totals[0] == '合计'
    for col, key in [(5, 'contract_amt'), (6, 'inv_sum'), (8, 'trade_contract_amt'),
                     (9, 'trade_inv_sum'), (10, 'settle'), (11, 'pay_sum'), (12, 'debt')]:
        # trade_contract_amt is null (not zero) without a trade company; the sheet sums reals only.
        assert totals[col] == pytest.approx(sum(float(facts[cid][key] or 0) for cid in ids), abs=0.01)
    workbook.close()
    # An empty filtered range exports as an explicitly empty file, never the whole ledger.
    page.get_by_role('button', name='重置', exact=True).click()
    page.get_by_label('搜索', exact=True).fill('无此合同关键词XYZ')
    expect(page.get_by_text('没有符合条件的合同，可调整筛选。', exact=True)).to_be_visible()
    with page.expect_request(lambda r: r.url.endswith('/api/m11/export')) as req_info, page.expect_download() as dl_info:
        page.get_by_role('button', name='导出 Excel', exact=True).click()
    assert req_info.value.post_data_json['ids'] == []
    empty_target = output('tail418-ordinary-export-empty.xlsx', kind='exports')
    dl_info.value.save_as(empty_target)
    workbook = openpyxl.load_workbook(empty_target, data_only=True)
    ws = workbook['集采台账']
    assert ws.max_row == 1 and [cell.value for cell in ws[1]] == ORD_HEADERS
    workbook.close()
    # A damaged 200 receipt (incomplete content) surfaces in place and downloads nothing.
    calls = []

    def broken(route):
        calls.append(route.request.url)
        route.fulfill(json={'ok': True, 'filename': '集采台账.xlsx', 'content_b64': 'AAAA'})
    downloads = []
    page.on('download', lambda d: downloads.append(d))
    page.route('**/api/m11/export', broken)
    page.get_by_role('button', name='导出 Excel', exact=True).click()
    # The export component reports its own receipt failure next to the buttons.
    expect(page.get_by_role('status').filter(has_text='导出文件不完整')).to_be_visible()
    expect(page.get_by_role('button', name='导出 Excel', exact=True)).to_be_enabled()
    assert calls and not downloads
    page.unroute('**/api/m11/export')


def test_print_export_project_order_file_and_memory(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    rows = rows_of(page, server)
    projects = page.request.get(server + '/api/m01/projects?status=all&keyword=').json()
    warehouse = {p['disp']: p['warehouse_name'] for p in projects}
    page.get_by_role('button', name='导出打印版…', exact=True).click()
    dialog = page.locator('.ledger-export-dialog')
    expect(dialog.get_by_role('heading', name='导出打印版', exact=True)).to_be_visible()
    pick_popup_option(page, '隔离项目')
    pick_popup_option(page, '长项目名验收')
    dialog.get_by_role('button', name='确认清单', exact=True).click()
    assert dialog.locator('tbody tr td:nth-child(2)').all_text_contents() == ['隔离项目', '长项目名验收']
    # The printed project order is the confirmed order, not the natural project order.
    dialog.get_by_role('button', name='上移长项目名验收', exact=True).click()
    assert dialog.locator('tbody tr td:nth-child(2)').all_text_contents() == ['长项目名验收', '隔离项目']
    expect(dialog.get_by_text('已选 2 个项目，按以下顺序导出。', exact=True)).to_be_visible()
    page.screenshot(path=str(output('tail418-print-dialog.png', kind='screenshots')), full_page=True)
    with page.expect_download() as dl_info:
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
    download = dl_info.value
    assert download.suggested_filename == f'集采打印台账_{datetime.now(BEIJING):%Y%m%d}.xlsx'
    target = output('tail418-print-export.xlsx', kind='exports')
    download.save_as(target)
    expect(dialog).not_to_be_visible()
    workbook = openpyxl.load_workbook(target, data_only=True)
    # Sheet names and titles follow the backend's project display (warehouse) name; the order
    # is the confirmed order, not the natural project order.
    assert workbook.sheetnames == ['长名称验收仓库', '隔离验收仓库']
    assert '无贸易公司' not in workbook.sheetnames and '有贸易公司' not in workbook.sheetnames
    assert workbook['长名称验收仓库']['A1'].value == '长名称验收仓库集中采购付款清单'
    assert workbook['隔离验收仓库']['A1'].value == '隔离验收仓库集中采购付款清单'
    # 隔离项目 holds a trade contract, so the sheet keeps the trade layout with its extra columns.
    ws = workbook['隔离验收仓库']
    assert (ws['B2'].value, ws['D2'].value, ws['J2'].value, ws['K2'].value, ws['L2'].value) == \
        ('合同日期', '贸易公司', '结算', '付款', '欠款')
    included = sorted((r for r in rows if r['project_key'] == warehouse['隔离项目'] and r['tag'] == '纳入台账'),
                      key=lambda r: r['project_seq'])
    assert [r['material'] for r in included] == ['隔离结算合同', '隔离贸易合同', 'TAIL418历史汇总']
    for i, r in enumerate(included):
        d = detail(page, server, r['id'])
        n = 4 + i
        assert ws.cell(row=n, column=1).value == r['project_seq']
        assert ws.cell(row=n, column=3).value == r['material']
        assert ws.cell(row=n, column=14).value == (r['contract_no'] or None)
        for col, key in [(10, 'settle'), (11, 'pay_sum'), (12, 'debt')]:
            assert ws.cell(row=n, column=col).value == pytest.approx(float(d[key])), (r['material'], key)
    tail = 4 + len(included)
    assert ws.cell(row=tail, column=1).value == '合计'
    for col, key in [(6, 'contract_amt'), (7, 'inv_sum'), (10, 'settle'), (11, 'pay_sum'), (12, 'debt')]:
        assert ws.cell(row=tail, column=col).value == pytest.approx(
            sum(float(detail(page, server, r['id'])[key]) for r in included), abs=0.01)
    # The 不纳入 contract is a print-range fact: it must not appear anywhere in the workbook.
    everything = [str(value) for ws in workbook.worksheets for row in ws.iter_rows(values_only=True)
                  for value in row if value is not None]
    assert not any('隔离排除合同' in text or 'TAIL418-OUT' in text for text in everything)
    # 长项目名验收 has no trade contract: plain layout with its own totals.
    ws2 = workbook['长名称验收仓库']
    assert (ws2['B2'].value, ws2['G2'].value, ws2['H2'].value, ws2['I2'].value) == ('合同日期', '结算', '付款', '欠款')
    included2 = sorted((r for r in rows if r['project_key'] == warehouse['长项目名验收'] and r['tag'] == '纳入台账'),
                       key=lambda r: r['project_seq'])
    assert [r['material'] for r in included2] == ['二期结算合同']
    for i, r in enumerate(included2):
        d = detail(page, server, r['id'])
        assert ws2.cell(row=4 + i, column=3).value == r['material']
        assert ws2.cell(row=4 + i, column=7).value == pytest.approx(float(d['settle']))
        assert ws2.cell(row=4 + i, column=8).value == pytest.approx(float(d['pay_sum']))
        assert ws2.cell(row=4 + i, column=9).value == pytest.approx(float(d['debt']))
    assert ws2.cell(row=4 + len(included2), column=1).value == '合计'
    workbook.close()
    # The chosen projects and order are remembered on this machine for the next export.
    page.get_by_role('button', name='导出打印版…', exact=True).click()
    dialog = page.locator('.ledger-export-dialog')
    expect(dialog.get_by_text('已选 2 个项目', exact=True)).to_be_visible()
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).not_to_be_visible()


def test_print_export_rejects_project_without_included_contracts(server, browser_page):
    page, _ = browser_page
    open_contracts(page, server)
    page.get_by_role('button', name='导出打印版…', exact=True).click()
    dialog = page.locator('.ledger-export-dialog')
    expect(dialog.get_by_role('heading', name='导出打印版', exact=True)).to_be_visible()
    pick_popup_option(page, '归档样例')
    dialog.get_by_role('button', name='确认清单', exact=True).click()
    downloads = []
    page.on('download', lambda d: downloads.append(d))
    dialog.get_by_role('button', name='保存到本地', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('没有纳入台账的合同')
    assert not downloads
    dialog.get_by_role('button', name='关闭', exact=True).click()
