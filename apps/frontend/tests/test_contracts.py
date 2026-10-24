"""TAIL-416: contract maintenance through the real isolated backend."""
import re
import subprocess
import sys

import httpx
import pytest
from playwright.sync_api import expect
from preview_select import pick_option
from test_preview import server, browser_page, login


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
    c=JcContract(project_id=p.id,contract_no='TAIL416-CONTRACT',contract_date='2026-10-01',material_name='隔离钢材合同',supplier='合成供应商',contract_amt=12345.67,payment_term='60±7天',payment_method='承兑')
    s.add(c);s.flush()
    s.add(JcInvoice(contract_id=c.id,kind='supplier',invoice_date='2026-10-10',amount=12345.67))
    b=JcContract(project_id=p.id,contract_no='TAIL416-B',material_name='隔离管件合同B',supplier='合成供应商',contract_amt=100)
    n=PaymentNotice(ph_id='TAIL416-NOTICE-B',bill_no='TAIL416-NOTICE-B',project_name=p.name_full,ownership_id=p.id,category='jc',jc_supplier='合成供应商',doc_date='2026-10-01',approve_status='已批',amount_approved=100,stat_settle=100,stat_paid=0)
    s.add_all([b,n]);s.flush()
    s.add(JcPayment(contract_id=b.id,source='notice',notice_id=n.id,pay_date='',amount=0))
"""
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=env, check=True)
    return make_preview_seed(seed)


def contract_id(page, server, contract_no='TAIL416-CONTRACT'):
    return next(row['id'] for row in page.request.get(server + '/api/m11/list').json()['rows'] if row['contract_no'] == contract_no)


def detail(page, server, cid):
    return page.request.get(server + f'/api/m11/detail?id={cid}').json()['data']


def test_inline_save_receipt_rejection_and_uncertain_recovery(server, browser_page):
    page, context = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    cid = contract_id(page, server)
    term = page.get_by_label('TAIL416-CONTRACT 账期', exact=True)
    expect(term).to_have_value('60±7天')
    # Inline edits save on blur with the backend receipt and the normalized value.
    term.fill('90天')
    term.press('Tab')
    expect(page.locator('.contract-feedback')).to_contain_text('已保存')
    expect(term).to_have_value('90±0天')
    assert detail(page, server, cid)['payment_term'] == '90±0天'
    # A server-side rejection disables further edits, keeps the input and stores nothing.
    term.fill('abc')
    term.press('Tab')
    expect(page.get_by_role('alert').first).to_contain_text('账期请填写非负整数 x±y天')
    expect(page.get_by_role('alert').first).to_contain_text('勿重复操作')
    expect(term).to_be_disabled()
    assert detail(page, server, cid)['payment_term'] == '90±0天'
    page.get_by_role('button', name='重读核对', exact=True).click()
    expect(term).to_be_enabled()
    expect(term).to_have_value('abc')
    term.fill('90天')
    term.press('Tab')
    expect(page.locator('.contract-feedback')).to_contain_text('已保存')
    assert detail(page, server, cid)['payment_term'] == '90±0天'
    # A successful write with a damaged HTTP 200 body must never offer a second submission.
    writes = []

    def damaged(route):
        writes.append(route.request.post_data)
        response = route.fetch()
        assert response.ok and response.json()['ok'] is True
        route.fulfill(response=response, body='{')
    page.route('**/api/m11/fields', damaged)
    term.fill('120天')
    term.press('Tab')
    expect(page.get_by_role('alert').first).to_contain_text('登记结果待核实')
    expect(term).to_be_disabled()
    assert len(writes) == 1
    assert detail(page, server, cid)['payment_term'] == '120±0天'
    page.unroute('**/api/m11/fields')
    page.get_by_role('button', name='重读核对', exact=True).click()
    expect(term).to_be_enabled()
    expect(term).to_have_value('120天')
    # Grid context (search) survives in-app navigation and back.
    page.get_by_label('搜索', exact=True).fill('钢材')
    page.go_back()
    page.get_by_role('link', name='MOD-11 集采台账').click()
    expect(page.get_by_label('搜索', exact=True)).to_have_value('钢材')
    expect(page.get_by_role('button', name='隔离钢材合同', exact=True)).to_be_visible()


def test_reverse_link_deep_link_preserves_other_contract_edit(server, browser_page):
    page, context = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    remark = page.get_by_label('TAIL416-CONTRACT 备注', exact=True)
    remark.fill('合同A未保存草稿')
    page.go_back()
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    page.get_by_role('button', name='查看 / 更改关联', exact=True).click()
    expect(page.get_by_text('当前关联', exact=True).first).to_be_visible()
    page.get_by_role('link', name='查看合同详情', exact=True).click()
    expect(page).to_have_url(re.compile(r'/contracts\?contract=\d+'))
    expect(page.get_by_role('button', name='隔离管件合同B', exact=True)).to_be_visible()
    # Entering contracts through the reverse link must not lose the other contract's edit.
    expect(page.get_by_label('TAIL416-CONTRACT 备注', exact=True)).to_have_value('合同A未保存草稿')


def test_history_summary_creation_payment_and_duplicate_rejection(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    page.get_by_role('button', name='＋ 手工新增合同', exact=True).click()
    editor = page.locator('.contract-inline-editor')
    editor.get_by_role('checkbox', name='历史汇总', exact=True).check()
    editor.get_by_label('核对截至日', exact=True).fill('2025-11-30')
    pick_option(page, '合同项目', '归档样例')
    editor.get_by_role('button', name='保存合同', exact=True).click()
    # Saving positions the new history contract at its settlement subtable.
    modal = page.locator('.contract-subtable-dialog')
    expect(modal.get_by_role('heading', name='历史未结金额', exact=True)).to_be_visible()
    expect(modal.get_by_label('核对截至日', exact=True)).to_have_value('2025-11-30')
    modal.get_by_label('历史未结金额（元）', exact=True).fill('1234.56')
    modal.get_by_role('button', name='新增历史未结金额', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='历史未结金额已新增')).to_be_visible()
    modal.get_by_role('button', name='关闭', exact=True).click()
    expect(modal).not_to_be_visible()
    summary = next(r for r in page.request.get(server + '/api/m11/list').json()['rows'] if r['remark'].startswith('历史未结金额；核对截至日：2025-11-30'))
    data = page.request.get(server + f'/api/m11/detail?id={summary["id"]}').json()['data']
    assert data['supplier_invoices'][0]['date'] == '2025-11-30'
    assert (str(data['settle']), str(data['pay_sum']), str(data['debt'])) == ('1234.56', '0.00', '1234.56')
    # Manual payments go through the payment subtable of the same contract.
    who = summary['contract_no'] or summary['material']
    page.get_by_role('button', name=f'{who} 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    # The draft date defaults to today; only the amount needs input.
    modal.get_by_label('手工付款金额（元）', exact=True).fill('25')
    modal.get_by_role('button', name='新增手工付款', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='手工付款已新增')).to_be_visible()
    # Removing a subtable row requires its explicit delete confirmation.
    modal.get_by_role('button', name='删除手工付款', exact=True).click()
    confirm = modal.get_by_role('group', name='确认删除子行')
    expect(confirm).to_contain_text('25.00')
    confirm.get_by_role('button', name='确认删除', exact=True).click()
    expect(modal.get_by_role('status').filter(has_text='已删除')).to_be_visible()
    modal.get_by_role('button', name='关闭', exact=True).click()
    data = page.request.get(server + f'/api/m11/detail?id={summary["id"]}').json()['data']
    assert (str(data['settle']), str(data['pay_sum']), str(data['debt'])) == ('1234.56', '0.00', '1234.56')
    # A second history summary for the same project is rejected and creates nothing.
    page.get_by_role('button', name='＋ 手工新增合同', exact=True).click()
    editor = page.locator('.contract-inline-editor')
    editor.get_by_role('checkbox', name='历史汇总', exact=True).check()
    editor.get_by_label('核对截至日', exact=True).fill('2025-11-30')
    pick_option(page, '合同项目', '归档样例')
    editor.get_by_role('button', name='保存合同', exact=True).click()
    expect(editor.get_by_role('alert')).to_contain_text('本项目已有历史汇总')
    rows = page.request.get(server + '/api/m11/list').json()['rows']
    assert len([r for r in rows if r['remark'].startswith('历史未结金额；核对截至日：2025-11-30')]) == 1


def test_late_new_contract_receipt_does_not_steal_deep_link_focus(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    cid = contract_id(page, server, 'TAIL416-B')
    pending = []
    page.route('**/api/m11/add', lambda route: pending.append(route))
    page.get_by_role('button', name='＋ 手工新增合同', exact=True).click()
    dialog = page.locator('.contract-inline-editor')
    pick_option(page, '合同项目', '隔离项目')
    dialog.get_by_role('button', name='保存合同', exact=True).click()
    expect(dialog.get_by_role('button', name='正在保存…', exact=True)).to_be_visible()
    page.go_back()
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    page.get_by_role('button', name='查看 / 更改关联', exact=True).click()
    page.get_by_role('link', name='查看合同详情', exact=True).click()
    expect(page).to_have_url(re.compile(r'contract=\d+'))
    expect(page.get_by_role('button', name='隔离管件合同B', exact=True)).to_be_visible()
    # No DB write: reuse an existing ID to expose any late callback that steals focus.
    assert len(pending) == 1
    pending[0].fulfill(json={'ok': True, 'id': cid, 'message': '合成迟到回执'})
    expect(page.locator('.contract-feedback')).to_contain_text('合同已新增。')
    expect(page).to_have_url(re.compile(r'contract=\d+'))
    expect(page.get_by_role('button', name='隔离管件合同B', exact=True)).to_be_visible()


def test_notice_link_changes_only_on_explicit_confirmation(server, browser_page):
    page, _ = browser_page
    login(page, server)
    notices = {row['bill_no']: row for row in page.request.get(server + '/api/m03/notice-list?period=').json()['items']}
    notice_id = notices['TAIL416-NOTICE-B']['notice_id']
    a = contract_id(page, server, 'TAIL416-CONTRACT')
    b = contract_id(page, server, 'TAIL416-B')

    def current():
        return page.request.get(server + f'/api/m11/link-recommendations?notice_id={notice_id}').json()['current_contract_id']
    assert current() == b
    page.get_by_role('link', name='MOD-03 付款通知书').click()
    page.get_by_role('button', name='查看 / 更改关联', exact=True).click()
    dialog = page.locator('.contract-dialog')
    expect(dialog.get_by_role('heading', name='修改合同关联')).to_be_visible()
    # Selecting another candidate and cancelling keeps the existing link untouched.
    dialog.get_by_role('radio', name='选择隔离钢材合同 · TAIL416-CONTRACT').check()
    dialog.get_by_role('button', name='取消', exact=True).click()
    dialog.get_by_role('button', name='放弃并关闭').click()
    expect(dialog).not_to_be_visible()
    assert current() == b
    # The link moves only on an explicit confirmation.
    page.get_by_role('button', name='查看 / 更改关联', exact=True).click()
    dialog.get_by_role('radio', name='选择隔离钢材合同 · TAIL416-CONTRACT').check()
    dialog.get_by_role('button', name='确认修改关联', exact=True).click()
    expect(dialog).not_to_be_visible()
    assert current() == a
    # Unlinking also requires an explicit confirmation.
    page.get_by_role('button', name='查看 / 更改关联', exact=True).click()
    dialog.get_by_role('button', name='解除当前关联', exact=True).click()
    expect(dialog.get_by_role('heading', name='解除当前合同关联？')).to_be_visible()
    dialog.get_by_role('button', name='确认解除', exact=True).click()
    expect(dialog).not_to_be_visible()
    assert not current()


def test_writes_require_login_and_fetch_boundary(server, browser_page):
    page, _ = browser_page
    page.goto(server + '/preview/contracts')
    expect(page.get_by_text('未登录 · 只读', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 手工新增合同', exact=True)).to_be_disabled()
    expect(page.get_by_role('button', name='抓取采购合同信息', exact=True)).to_be_disabled()
    expect(page.get_by_label('TAIL416-CONTRACT 账期', exact=True)).to_be_disabled()
    with httpx.Client(base_url=server) as client:
        for path, payload in [
            ('/api/m11/fields', {'id': 1, 'fields': {'payment_term': '90天'}}),
            ('/api/m11/add', {}),
            ('/api/m11/tag', {'id': 1, 'tag': '不纳入'}),
            ('/api/m11/fetch', {'confirm': True}),
        ]:
            response = client.post(path, json=payload)
            assert response.status_code == 401, (path, response.status_code)
            assert '未登录' in response.json()['message']
    login(page, server)
    page.get_by_role('link', name='MOD-11 集采台账').click()
    before = len(page.request.get(server + '/api/m11/list').json()['rows'])
    page.get_by_role('button', name='抓取采购合同信息', exact=True).click()
    dialog = page.get_by_role('dialog')
    expect(dialog).to_contain_text('i8：未绑定')
    expect(dialog.get_by_role('alert')).to_contain_text('i8 服务地址未配置或格式不正确')
    expect(dialog.get_by_role('button', name='确认抓取', exact=True)).to_be_disabled()
    dialog.get_by_role('button', name='取消', exact=True).click()
    # The server side refuses a forced fetch without a configured i8 target and changes nothing.
    body = page.request.post(server + '/api/m11/fetch', data={'confirm': True}).json()
    assert body.get('ok') is not True and body.get('message')
    assert len(page.request.get(server + '/api/m11/list').json()['rows']) == before
    # Row tag actions write through the same guarded endpoint and re-read.
    cid = contract_id(page, server)
    row = page.get_by_role('row').filter(has_text='隔离钢材合同')
    row.get_by_role('button', name='不纳入', exact=True).click()
    expect(page.locator('.contract-feedback')).to_contain_text('已把 1 行标记为「不纳入」')
    tags = {r['id']: r['tag'] for r in page.request.get(server + '/api/m11/list').json()['rows']}
    assert tags[cid] == '不纳入'
    # The default tag filter hides the excluded row; widen it before restoring.
    pick_option(page, '纳入状态', '全部')
    row.get_by_role('button', name='纳入', exact=True).click()
    expect(page.locator('.contract-feedback')).to_contain_text('已把 1 行标记为「纳入台账」')
    tags = {r['id']: r['tag'] for r in page.request.get(server + '/api/m11/list').json()['rows']}
    assert tags[cid] == '纳入台账'
