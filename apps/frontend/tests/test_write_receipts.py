"""Cumulative financial write receipts must never permit blind resubmission."""
import subprocess,sys
import httpx,pytest
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from test_ledger import open_ledger,project_id,add_row,sync_ledger,cell,data,row_data

@pytest.fixture(scope='module')
def preview_seed(make_preview_seed):
    def seed(env):
        code="""
from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from sqlalchemy import select
with session_scope() as s:
    p=s.scalar(select(Project).where(Project.disp=='隔离项目'))
    for suffix in ('JSON','OBJECT','500','IDENTITY'):
        s.add(PaymentNotice(ph_id='TAIL422-PAY-'+suffix,bill_no='TAIL422-PAY-'+suffix,ownership_id=p.id,project_name=p.name_full,category='material',approve_status='已批',doc_date='2026-09-01',amount_approved=100,stat_settle=100,stat_paid=0))
"""
        subprocess.run([sys.executable,'-X','utf8','-c',code],env=env,check=True)
    return make_preview_seed(seed)

def pay_dialog(page,server,suffix):
    login(page,server)
    page.get_by_role('link',name='MOD-03 付款通知书',exact=True).click()
    bill='TAIL422-PAY-'+suffix
    page.get_by_label('勾选'+bill,exact=True).check()
    page.locator('.notice-pay-action').click()
    dialog=page.get_by_role('dialog',name='批量付款',exact=True)
    amount=dialog.get_by_label(bill+'本次付款金额',exact=True)
    expect(amount).to_be_enabled();amount.fill('10')
    expect(dialog.get_by_role('button',name='确认付款',exact=True)).to_be_enabled()
    return dialog,bill

@pytest.mark.parametrize('suffix',['JSON','OBJECT','500'])
def test_payment_committed_but_receipt_unknown_never_says_not_registered(server,browser_page,suffix):
    page,_=browser_page;dialog,bill=pay_dialog(page,server,suffix);writes=[]
    def damage(route):
        writes.append(route.request.post_data_json)
        response=route.fetch();assert response.ok and response.json()['ok']
        if suffix=='JSON':route.fulfill(response=response,body='{')
        else:route.fulfill(status=500 if suffix=='500' else 200,json={})
    page.route('**/api/m03/actions/batch-pay',damage)
    dialog.get_by_role('button',name='确认付款',exact=True).click()
    expect(dialog.get_by_role('alert').filter(has_text='提交结果尚未核实')).to_be_visible()
    expect(dialog.get_by_text('整批未登记',exact=False)).to_have_count(0)
    expect(dialog.get_by_role('button',name='确认付款',exact=True)).to_have_count(0)
    current=next(r for r in page.request.get(server+'/api/m03/notice-list?period=').json()['items'] if r['bill_no']==bill)
    assert current['amount_paid']=='10.00' and len(writes)==1
    dialog.get_by_role('button',name='重读列表核对',exact=True).click()
    expect(dialog.get_by_role('button',name='确认付款',exact=True)).to_have_count(0)
    assert len(writes)==1

def test_old_account_payment_401_does_not_expire_new_account(server,browser_page):
    page,context=browser_page;dialog,_=pay_dialog(page,server,'IDENTITY');pending=[]
    page.route('**/api/m03/actions/batch-pay',lambda route:pending.append(route))
    with page.expect_request('**/api/m03/actions/batch-pay'):
        dialog.get_by_role('button',name='确认付款',exact=True).click()
    with httpx.Client(base_url=server) as other:
        assert other.post('/m15/login',data={'account':'preview-user','password':''}).status_code==303
        context.add_cookies([{'name':'mw_preview_397','value':other.cookies['mw_preview_397'],'url':server}])
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('button',name='预览同事（普通用户）',exact=True)).to_be_visible()
    page.evaluate("window.__oldSessionLost=0;window.addEventListener('session-lost',()=>window.__oldSessionLost++)")
    assert len(pending)==1
    pending.pop().fulfill(status=401,json={'message':'旧账号迟到拒绝'})
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    assert page.evaluate('window.__oldSessionLost')==0
    expect(page.get_by_role('button',name='预览同事（普通用户）',exact=True)).to_be_visible()

@pytest.mark.parametrize('operation',['save','add','delete'])
def test_ledger_missing_success_receipt_stays_locked_until_readback(server,browser_page,operation):
    page,_=browser_page;open_ledger(page,server);project=project_id(page,server)
    rid=add_row(page,server,project,'缺回执-'+operation);sync_ledger(page);writes=[]
    endpoint='/api/m05/history/'+('delete' if operation=='delete' else 'save')
    def damage(route):
        writes.append(route.request.post_data_json);response=route.fetch()
        if len(writes)==1: assert response.ok, response.text()
        route.fulfill(status=200,json={})
    page.route('**'+endpoint,damage)
    if operation=='save':
        field=cell(page,rid,'payment');field.fill('55.55');field.press('Tab')
        expect(page.get_by_role('status',name='保存回执')).to_contain_text('保存结果未确认')
        expect(field).to_have_value('55.55')
        field.focus();field.press('Tab');assert len(writes)==1
        page.get_by_role('button',name='放弃未保存输入',exact=True).click()
    elif operation=='add':
        page.get_by_role('button',name='新增历史行',exact=True).click()
        expect(page.get_by_role('status',name='保存回执')).to_contain_text('新增结果未确认')
    else:
        row=page.locator(f'[row-id="material:manual:{rid}"]')
        row.get_by_role('button',name='删除',exact=True).click()
        expect(page.get_by_role('status',name='保存回执')).to_contain_text('删除结果未确认')
    expect(page.get_by_role('button',name='重新加载',exact=True)).to_be_visible()
    page.get_by_role('button',name='新增历史行',exact=True).click();assert len(writes)==1
    page.unroute('**'+endpoint)
    page.get_by_role('button',name='重新加载',exact=True).click()
    expect(page.get_by_role('button',name='重新加载',exact=True)).to_have_count(0)


def test_manual_notice_unknown_add_preserves_draft_until_explicit_readback(server,browser_page):
    from preview_select import pick_option
    page,_=browser_page;login(page,server)
    page.get_by_role('link',name='MOD-03 付款通知书',exact=True).click()
    page.get_by_role('button',name='＋ 手动新增通知书',exact=True).click()
    bill='TAIL422-MANUAL-UNKNOWN'
    page.get_by_label('草稿单据编码',exact=True).fill(bill)
    pick_option(page,'草稿付款项目','隔离项目');page.keyboard.press('Escape')
    page.get_by_label('草稿审批金额',exact=True).fill('123.45')
    writes=[]
    def damage(route):
        writes.append(route.request.post_data_json);response=route.fetch();assert response.ok,response.text();route.fulfill(response=response,body='{')
    page.route('**/api/m03/actions/manual-save',damage)
    page.get_by_role('button',name='保存草稿',exact=True).click()
    expect(page.get_by_role('alert').filter(has_text='新增结果待核实')).to_be_visible()
    expect(page.get_by_label('草稿单据编码',exact=True)).to_have_value(bill)
    expect(page.get_by_role('button',name='保存草稿',exact=True)).to_be_disabled()
    assert len([r for r in page.request.get(server+'/api/m03/notice-list?period=').json()['items'] if r['bill_no']==bill])==1
    expect(page.get_by_role('button',name='已核对，关闭草稿',exact=True)).to_be_disabled()
    page.get_by_role('button',name='重读核对新增结果',exact=True).click()
    expect(page.get_by_role('button',name='已核对，关闭草稿',exact=True)).to_be_enabled()
    expect(page.get_by_role('button',name='保存草稿',exact=True)).to_be_disabled()
    page.get_by_role('button',name='已核对，关闭草稿',exact=True).click()
    expect(page.get_by_label('草稿单据编码',exact=True)).to_have_count(0)
    assert len(writes)==1
    # The normal success contract returns a string row_id, and must still clear the draft.
    page.unroute('**/api/m03/actions/manual-save')
    page.get_by_role('button',name='＋ 手动新增通知书',exact=True).click()
    page.get_by_label('草稿单据编码',exact=True).fill(bill+'-OK')
    pick_option(page,'草稿付款项目','隔离项目');page.keyboard.press('Escape')
    page.get_by_role('button',name='保存草稿',exact=True).click()
    expect(page.get_by_label('草稿单据编码',exact=True)).to_have_count(0)
    assert len([r for r in page.request.get(server+'/api/m03/notice-list?period=').json()['items'] if r['bill_no']==bill+'-OK'])==1


def test_contract_add_500_after_commit_requires_readback_and_no_resubmit(server,browser_page):
    from preview_select import pick_option
    page,_=browser_page;login(page,server)
    page.get_by_role('link',name='MOD-11 集采台账',exact=True).click()
    page.get_by_role('button',name='＋ 手工新增合同',exact=True).click()
    editor=page.locator('.contract-inline-editor')
    pick_option(page,'合同项目','隔离项目')
    editor.get_by_label('材料名',exact=True).fill('TAIL422-合同未知新增')
    writes=[]
    def damage(route):
        writes.append(route.request.post_data_json);response=route.fetch();assert response.ok,response.text();route.fulfill(status=500,json={'message':'提交后连接异常'})
    page.route('**/api/m11/add',damage)
    editor.get_by_role('button',name='保存合同',exact=True).click()
    expect(editor.get_by_role('alert')).to_contain_text('保存结果待核实')
    expect(editor.get_by_role('button',name='保存合同',exact=True)).to_have_count(0)
    assert len([r for r in page.request.get(server+'/api/m11/list').json()['rows'] if r['material']=='TAIL422-合同未知新增'])==1
    assert len(writes)==1
