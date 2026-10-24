"""TAIL-417: invoice and payment subtables through the real isolated backend."""
import os
import re
import subprocess
import sys

import httpx
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output


@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        if os.environ.get('MTRL_SUB_TEST_BUILD'):
            env['FRONTEND_PREVIEW_DIR'] = os.environ['MTRL_SUB_TEST_BUILD']
        code = """
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod11_jc.models import JcContract, JcInvoice, JcPayment
from app.mod03_notice.models import PaymentNotice
from sqlalchemy import select
with session_scope() as s:
    p = s.scalar(select(Project).where(Project.disp == '隔离项目'))
    a = JcContract(project_id=p.id, contract_no='TAIL417-A', contract_date='2026-10-01',
                   material_name='隔离线缆合同A', supplier='合成供应商A', contract_amt=1000)
    s.add(a); s.flush()
    s.add_all([JcInvoice(contract_id=a.id, kind='supplier', invoice_date='2026-09-0%d' % d, amount=100)
               for d in (1, 2, 3)])
    b = JcContract(project_id=p.id, contract_no='TAIL417-B', material_name='隔离管件合同B',
                   supplier='合成供应商A', contract_amt=500)
    c = JcContract(project_id=p.id, contract_no='TAIL417-C', material_name='隔离阀门合同C',
                   supplier='合成供应商A', contract_amt=300)
    n1 = PaymentNotice(ph_id='TAIL417-N1', bill_no='TAIL417-N1', project_name=p.name_full,
                       ownership_id=p.id, category='jc', jc_supplier='合成供应商A',
                       doc_date='2026-10-03', approve_status='已批', amount_approved=150,
                       stat_settle=150, stat_paid=150)
    n2 = PaymentNotice(ph_id='TAIL417-N2', bill_no='TAIL417-N2', project_name=p.name_full,
                       ownership_id=p.id, category='jc', jc_supplier='合成供应商A',
                       doc_date='2026-10-01', approve_status='已批', amount_approved=200,
                       stat_settle=200, stat_paid=120)
    n3 = PaymentNotice(ph_id='TAIL417-N3', bill_no='TAIL417-N3', project_name=p.name_full,
                       ownership_id=p.id, category='jc', jc_supplier='合成供应商A',
                       doc_date='2026-10-02', approve_status='已批', amount_approved=300,
                       stat_settle=300, stat_paid=300)
    s.add_all([b, c, n1, n2, n3]); s.flush()
    s.add(JcPayment(contract_id=b.id, source='notice', notice_id=n2.id, pay_date='', amount=0))
    s.add(JcPayment(contract_id=c.id, source='notice', notice_id=n3.id, pay_date='', amount=55.5))
"""
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, check=True)
    return seed


def contract_id(page, server, no):
    return next(row['id'] for row in page.request.get(server + '/api/m11/list').json()['rows']
                if row['contract_no'] == no)


def detail(page, server, cid):
    return page.request.get(server + f'/api/m11/detail?id={cid}').json()['data']


def notice_id(page, server, bill_no):
    items = page.request.get(server + '/api/m03/notice-list?period=').json()['items']
    return next(row['notice_id'] for row in items if row['bill_no'] == bill_no)


def manual_payments(page, server, cid):
    return [row['amount'] for row in detail(page, server, cid)['payments'] if row['source'] == 'manual']


def test_payment_subrow_add_validate_delete_with_readback(server, browser_page):
    """付款子行真实增删走 HTTP：前端金额校验零请求、后端同款语义拒绝、删除须显式确认并读回。"""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    cid = contract_id(page, server, 'TAIL417-A')
    page.get_by_role('button', name='TAIL417-A 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    amount = modal.get_by_label('手工付款金额（元）', exact=True)
    expect(amount).to_have_value('')
    # Invalid amounts are refused client-side without issuing any write request.
    posts = []
    page.on('request', lambda request: posts.append(request.url)
            if request.url.endswith('/api/m11/payment/add') else None)
    for bad in ('0', '-5', 'abc', '1.999'):
        amount.fill(bad)
        modal.get_by_role('button', name='新增手工付款', exact=True).click()
        expect(modal.get_by_role('alert')).to_contain_text('金额须大于0，最多两位小数。')
    assert posts == []
    assert manual_payments(page, server, cid) == []
    # The same semantics hold on the real backend for a direct write.
    body = page.request.post(server + '/api/m11/payment/add',
                             data={'id': cid, 'date': '2026-10-24', 'amount': '0', 'source': 'manual'}).json()
    assert body['ok'] is False and '金额' in body['message']
    body = page.request.post(server + '/api/m11/payment/add',
                             data={'id': cid, 'date': '', 'amount': '5', 'source': 'manual'}).json()
    assert body['ok'] is False and '日期必填' in body['message']
    assert detail(page, server, cid)['pay_sum'] == '0.00'
    # A valid manual payment round-trips through HTTP and is read back everywhere.
    amount.fill('123.45')
    modal.get_by_role('button', name='新增手工付款', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='手工付款已新增')).to_be_visible()
    expect(modal.locator('tfoot')).to_contain_text('123.45')
    assert manual_payments(page, server, cid) == ['123.45']
    assert detail(page, server, cid)['pay_sum'] == '123.45'
    # Deleting requires the explicit confirmation; cancel keeps the row untouched.
    modal.get_by_role('button', name='删除手工付款', exact=True).click()
    confirm = modal.get_by_role('group', name='确认删除子行')
    expect(confirm).to_contain_text('123.45')
    confirm.get_by_role('button', name='取消删除', exact=True).click()
    expect(confirm).not_to_be_visible()
    assert manual_payments(page, server, cid) == ['123.45']
    modal.get_by_role('button', name='删除手工付款', exact=True).click()
    modal.get_by_role('group', name='确认删除子行').get_by_role('button', name='确认删除', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已删除。')).to_be_visible()
    assert manual_payments(page, server, cid) == []
    assert detail(page, server, cid)['pay_sum'] == '0.00'
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()


def test_invoice_add_positions_focus_and_readback(server, browser_page):
    """发票子行真实新增后定位新对象：分页跳到新行所在页、焦点落到该行、合计与读回一致；删除同样须确认。"""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    cid = contract_id(page, server, 'TAIL417-A')
    page.get_by_role('button', name='TAIL417-A 供应商发票子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    expect(modal.get_by_text('共 3 条', exact=True)).to_be_visible()
    expect(modal.locator('tr[data-subtable="supplier"]')).to_have_count(2)
    expect(modal.locator('tfoot')).to_contain_text('300.00')
    modal.get_by_label('供应商发票金额（元）', exact=True).fill('77.77')
    modal.get_by_role('button', name='新增供应商发票', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='供应商发票已新增')).to_be_visible()
    data = detail(page, server, cid)
    assert [row['amount'] for row in data['supplier_invoices']] == ['100.00', '100.00', '100.00', '77.77']
    assert data['inv_sum'] == '377.77'
    new_id = next(row['id'] for row in data['supplier_invoices'] if row['amount'] == '77.77')
    # The saved row is located: the pager turns to its page and the row takes focus.
    expect(modal.get_by_text('共 4 条', exact=True)).to_be_visible()
    row = modal.locator(f'tr[data-subtable="supplier"][data-row="{new_id}"]')
    expect(row).to_be_visible()
    expect(row).to_contain_text('77.77')
    page.wait_for_function(
        "id => document.activeElement && document.activeElement.getAttribute('data-row') === id",
        arg=str(new_id))
    page.screenshot(path=str(output('tail417-invoice-focus.png', kind='screenshots')), full_page=True)
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()
    # Deleting the new invoice also requires its explicit confirmation and reads back.
    page.get_by_role('button', name='TAIL417-A 供应商发票子表', exact=True).click()
    modal.locator('tr[data-subtable="supplier"]').filter(has_text='77.77').get_by_role('button', name='删除发票').click()
    confirm = modal.get_by_role('group', name='确认删除子行')
    expect(confirm).to_contain_text('77.77')
    confirm.get_by_role('button', name='确认删除', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已删除。')).to_be_visible()
    data = detail(page, server, cid)
    assert [row['amount'] for row in data['supplier_invoices']] == ['100.00', '100.00', '100.00']
    assert data['inv_sum'] == '300.00'
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()


def test_subtable_draft_survives_navigation_and_close_confirm(server, browser_page):
    """弹窗草稿跨页往返保留；关闭有变化须确认，放弃后草稿清空。"""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    page.get_by_role('button', name='TAIL417-A 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    amount = modal.get_by_label('手工付款金额（元）', exact=True)
    amount.fill('88.88')
    # In-app navigation away and back keeps the per-contract draft and reopens the dialog.
    page.go_back()
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    page.get_by_role('link', name='MOD-11 集采台账').click()
    expect(modal).to_be_visible()
    expect(amount).to_have_value('88.88')
    # Closing with a draft asks first; continuing keeps it.
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal.get_by_role('heading', name='放弃未保存的修改？')).to_be_visible()
    modal.get_by_role('button', name='继续编辑', exact=True).click()
    expect(amount).to_have_value('88.88')
    # Discarding closes the dialog and resets that draft.
    modal.get_by_role('button', name='关闭', exact=True).click()
    modal.get_by_role('button', name='放弃并关闭', exact=True).click()
    expect(modal).not_to_be_visible()
    page.get_by_role('button', name='TAIL417-A 付款子表', exact=True).click()
    expect(modal.get_by_label('手工付款金额（元）', exact=True)).to_have_value('')
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()


def test_payment_domain_reference_keeps_source_and_notice_lookback(server, browser_page):
    """从付款域引用走真实 link：来源为 notice、全库去重拒绝重复、通知书跨页回看同一对象。"""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    b = contract_id(page, server, 'TAIL417-B')
    c = contract_id(page, server, 'TAIL417-C')
    nid = notice_id(page, server, 'TAIL417-N1')
    nid2 = notice_id(page, server, 'TAIL417-N2')
    rec = page.request.get(server + f'/api/m11/link-recommendations?notice_id={nid}').json()
    assert rec['ok'] is True and rec['current_contract_id'] is None and len(rec['rows']) >= 3
    page.get_by_role('button', name='TAIL417-B 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    modal.get_by_role('button', name='从付款域引用', exact=True).click()
    ref = page.locator('.contract-payment-reference')
    ref.get_by_label('引用集采通知书', exact=True).click()
    option = page.locator('.ant-select-item-option-content').filter(has_text='TAIL417-N1')
    expect(option).to_be_visible()
    # Let the open motion and the candidate refetch settle before the mouse click.
    page.wait_for_timeout(350)
    if not page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').count():
        ref.get_by_label('引用集采通知书', exact=True).click()
        expect(option).to_be_visible()
    option.click()
    ref.get_by_role('button', name='引用', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已从付款域引用')).to_be_visible()
    # The referenced notice disappears from the candidate list: one reference only.
    modal.get_by_role('button', name='从付款域引用', exact=True).click()
    expect(ref).to_contain_text('没有可引用的通知书。')
    ref.get_by_role('button', name='取消', exact=True).click()
    expect(ref).not_to_be_visible()
    # The link lands as a source='notice' payment row and the contract reads it back;
    # the pre-existing N2 link on the same contract stays untouched.
    data = detail(page, server, b)
    linked = sorted(row['notice_id'] for row in data['payments'] if row['source'] == 'notice')
    assert linked == sorted([nid, nid2])
    page.screenshot(path=str(output('tail417-payment-reference.png', kind='screenshots')), full_page=True)
    # Notice look-back from the contract jumps to the same notice object.
    modal.locator(f'.subtable-links a[href="/preview/notices?notice={nid}"]').click()
    expect(page).to_have_url(re.compile(rf'/notices\?notice={nid}$'))
    expect(page.locator('.notice-focused')).to_contain_text('TAIL417-N1')
    items = {row['bill_no']: row for row in page.request.get(server + '/api/m03/notice-list?period=').json()['items']}
    assert items['TAIL417-N1']['has_link'] is True
    # Backend dedup refuses a second reference of the same notice, contract-side delete is blocked.
    body = page.request.post(server + '/api/m11/payment/add',
                             data={'id': c, 'date': '2026-10-24', 'amount': '10', 'source': 'notice',
                                   'notice_id': nid}).json()
    assert body['ok'] is False and '全库去重' in body['message']
    body = page.request.post(server + '/api/m11/link', data={'notice_id': nid, 'contract_id': b}).json()
    assert body['ok'] is True and body.get('changed') is False and '未重复关联' in body['message']
    n1_row = next(row for row in detail(page, server, b)['payments']
                  if row['source'] == 'notice' and row['notice_id'] == nid)
    body = page.request.post(server + '/api/m11/payment/del', data={'row_id': n1_row['id']}).json()
    assert body['ok'] is False and '改关联或解绑' in body['message']
    # Deleting a row that is already gone (stale id) is refused and changes nothing.
    body = page.request.post(server + '/api/m11/invoice/del', data={'row_id': 0}).json()
    assert body['ok'] is False and '找不到发票行' in body['message']
    body = page.request.post(server + '/api/m11/payment/del', data={'row_id': 0}).json()
    assert body['ok'] is False and '找不到付款行' in body['message']
    assert sorted(row['notice_id'] for row in detail(page, server, b)['payments']
                  if row['source'] == 'notice') == sorted([nid, nid2])


def test_reverse_link_same_object_no_implicit_move(server, browser_page):
    """通知书反链深链与关联弹窗指向同一合同；取消不改任何已有关系；引用行只能回通知书改关联。"""
    page, _ = browser_page
    login(page, server)
    a = contract_id(page, server, 'TAIL417-A')
    b = contract_id(page, server, 'TAIL417-B')
    c = contract_id(page, server, 'TAIL417-C')
    nid2 = notice_id(page, server, 'TAIL417-N2')
    nid3 = notice_id(page, server, 'TAIL417-N3')
    rec = page.request.get(server + f'/api/m11/link-recommendations?notice_id={nid2}').json()
    assert rec['current_contract_id'] == b
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    page.get_by_role('row').filter(has_text='TAIL417-N2').get_by_role('button', name='查看 / 更改关联', exact=True).click()
    dialog = page.locator('.contract-dialog')
    expect(dialog.get_by_role('heading', name='修改合同关联')).to_be_visible()
    expect(dialog.get_by_text('隔离管件合同B').first).to_be_visible()
    # The reverse deep link lands on the same contract object the dialog calls current.
    dialog.get_by_role('link', name='查看合同详情', exact=True).click()
    expect(page).to_have_url(re.compile(rf'contract={b}(?:&|$)'))
    expect(page.get_by_role('button', name='TAIL417-B 付款子表', exact=True)).to_be_visible()
    # Back on the notice the dialog keeps its state; selecting a candidate and cancelling moves nothing.
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    expect(dialog).to_be_visible()
    dialog.get_by_role('radio', name='选择隔离阀门合同C · TAIL417-C').check()
    dialog.get_by_role('button', name='取消', exact=True).click()
    dialog.get_by_role('button', name='放弃并关闭', exact=True).click()
    expect(dialog).not_to_be_visible()
    assert page.request.get(server + f'/api/m11/link-recommendations?notice_id={nid2}').json()['current_contract_id'] == b
    # The other notice's payment stays on contract C and contract A stays empty.
    assert [row['notice_id'] for row in detail(page, server, c)['payments'] if row['source'] == 'notice'] == [nid3]
    assert detail(page, server, a)['payments'] == []
    # Contract C shows the referenced payment as a stat row: the amount is the notice's
    # statistical paid value, with notice look-back and no contract-side delete.
    page.get_by_role('link', name='MOD-11 集采台账').click()
    page.get_by_role('button', name='TAIL417-C 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    stat_row = modal.locator('tr[data-subtable="payment"]').filter(has_text='统计累计')
    expect(stat_row).to_contain_text('300.00')
    expect(stat_row.get_by_role('link', name='查看通知书', exact=True)).to_be_visible()
    expect(stat_row).to_contain_text('回通知书改关联')
    assert stat_row.get_by_role('button', name='删除手工付款').count() == 0
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()


def test_writes_require_login_401_and_data_unchanged(server, browser_page):
    """未登录：子表操作禁用；invoice/payment/link/unlink 直发全部 401 且数据零变化。"""
    page, _ = browser_page
    a = contract_id(page, server, 'TAIL417-A')
    b = contract_id(page, server, 'TAIL417-B')
    nid2 = notice_id(page, server, 'TAIL417-N2')
    before_a, before_b = detail(page, server, a), detail(page, server, b)
    invoice_row = before_a['supplier_invoices'][0]['id']
    payment_row = before_b['payments'][0]['id']
    with httpx.Client(base_url=server) as client:
        for path, payload in [
            ('/api/m11/invoice/add', {'id': a, 'kind': 'supplier', 'date': '2026-10-24', 'amount': '9.99'}),
            ('/api/m11/invoice/del', {'row_id': invoice_row}),
            ('/api/m11/payment/add', {'id': a, 'date': '2026-10-24', 'amount': '9.99', 'source': 'manual'}),
            ('/api/m11/payment/del', {'row_id': payment_row}),
            ('/api/m11/link', {'notice_id': nid2, 'contract_id': a}),
            ('/api/m11/unlink', {'notice_id': nid2}),
        ]:
            response = client.post(path, json=payload)
            assert response.status_code == 401, (path, response.status_code)
            assert '未登录' in response.json()['message']
    assert detail(page, server, a) == before_a
    assert detail(page, server, b) == before_b
    # The page itself stays read-only: subtable inputs and actions are disabled without an account.
    page.goto(server + '/preview/contracts')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    page.get_by_role('button', name='TAIL417-A 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    expect(modal.get_by_label('手工付款金额（元）', exact=True)).to_be_disabled()
    expect(modal.get_by_role('button', name='新增手工付款', exact=True)).to_be_disabled()
    expect(modal.get_by_role('button', name='从付款域引用', exact=True)).to_be_disabled()


def test_duplicate_submit_blocked_and_damaged_receipt_recovery(server, browser_page):
    """在途禁重复提交；200 截断回执进待核实、禁再写、重读核对后解锁且无重复落库。"""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    cid = contract_id(page, server, 'TAIL417-A')
    page.get_by_role('button', name='TAIL417-A 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    add = modal.get_by_role('button', name='新增手工付款', exact=True)
    # While the write is in flight the button is disabled: no duplicate submission.
    pending = []
    page.route('**/api/m11/payment/add', lambda route: pending.append(route))
    modal.get_by_label('手工付款金额（元）', exact=True).fill('55.00')
    add.click()
    expect(modal.get_by_role('status').filter(has_text='正在处理合同子表')).to_be_visible()
    expect(add).to_be_disabled()
    assert len(pending) == 1
    # Let the real response through exactly once: a single row lands in the database.
    pending[0].fulfill(response=pending[0].fetch())
    expect(modal.get_by_role('status').filter(has_text='手工付款已新增')).to_be_visible()
    assert manual_payments(page, server, cid) == ['55.00']
    page.unroute('**/api/m11/payment/add')
    # A 200 write with a damaged body has landed server-side: no second submission, reread then unlock.
    writes = []

    def damaged(route):
        writes.append(route.request.post_data)
        response = route.fetch()
        assert response.ok and response.json()['ok'] is True
        route.fulfill(response=response, body='{')

    page.route('**/api/m11/payment/add', damaged)
    modal.get_by_label('手工付款金额（元）', exact=True).fill('66.00')
    add.click()
    expect(modal.get_by_role('alert')).to_contain_text('未取得保存确认，请重读核对，勿重复操作。')
    expect(add).to_be_disabled()
    assert len(writes) == 1
    assert manual_payments(page, server, cid) == ['55.00', '66.00']
    page.screenshot(path=str(output('tail417-uncertain.png', kind='screenshots')), full_page=True)
    # Recovery is manual: reread, confirm the reconciled result, then writes unlock.
    modal.get_by_role('button', name='重读明细', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已重读，请对照已保存行与本次输入核对结果')).to_be_visible()
    modal.get_by_role('button', name='已核对结果，继续处理', exact=True).click()
    expect(add).to_be_enabled()
    assert manual_payments(page, server, cid) == ['55.00', '66.00']
    # The kept input is dropped explicitly, then the dialog closes clean.
    modal.get_by_role('button', name='取消', exact=True).click()
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()
