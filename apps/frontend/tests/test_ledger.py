"""398: real browser saves, account-scoped drafts, replay and downloaded workbooks."""
from __future__ import annotations

import re
from decimal import Decimal

import httpx
import openpyxl
from playwright.sync_api import expect
from preview_select import pick_option
from tools.audit.workspace_paths import output
from test_preview import server, browser_page, login  # noqa: F401


def open_ledger(page, server, account='preview-admin'):
    login(page, server, account)
    page.get_by_role('link', name='MOD-05 付款流水与欠款统计', exact=True).click()
    select_project(page, '隔离项目')
    expect(page.get_by_role('region', name='辅材欠款台账', exact=True)).to_be_visible()


def history_row(page, remark='合成历史行甲'):
    return page.get_by_role('region',name='辅材欠款台账').locator('[row-id]').filter(has=page.locator(f'input[value="{remark}"]'))


def test_continuous_edit_real_save_and_readback(server, browser_page):
    page, context = browser_page
    open_ledger(page, server)
    row=history_row(page)
    settle=row.locator('[col-id="other_expense"] input')
    paid=row.locator('[col-id="payment"] input')
    pending=[]
    def delay_first(route):
        if not pending:
            pending.append(route)
        else:
            route.continue_()
    page.route('**/api/m05/history/save',delay_first)
    settle.fill('1234.56')
    settle.press('Tab')
    expect(paid).to_be_focused()
    paid.fill('222.22')
    assert len(pending)==1, '离格必须立即发起真实POST'
    pending[0].fulfill(response=pending[0].fetch())
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存')
    expect(paid).to_have_value('222.22')
    expect(paid).to_be_focused()
    paid.press('Tab')
    page.get_by_role('heading',name='逐月欠款台账',exact=True).click()
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存')
    expect(page.get_by_role('status',name='保存回执')).not_to_contain_text('正在保存')
    page.reload()
    select_project(page, '隔离项目')
    row=history_row(page)
    expect(row.locator('[col-id="other_expense"] input')).to_have_value('1234.56')
    expect(row.locator('[col-id="payment"] input')).to_have_value('222.22')


def data(page, server, project, end=''):
    response=page.request.get(server+f'/api/m05/ledger?project_id={project}&end_ym={end}')
    assert response.ok
    result=response.json()
    assert result['project_id']==project
    return result


def project_id(page, server, disp='隔离项目'):
    return next(row['id'] for row in page.request.get(server+'/api/m01/projects?status=all').json() if row['disp']==disp)


def row_data(ledger, record_id, category='material'):
    return next(row for side in ledger['sides'] if side['category']==category for row in side['rows'] if row['record_id']==record_id)


def body_for(project, row, category='material', **changes):
    return {'id':row['record_id'],'project_id':project,'category':category,'entry_kind':row['row_kind'],
            'cutoff_ym':row['month'],'settle_amount':row['other_expense'],'paid_amount':row['payment'],
            'remark':row['remark'],'token':row['token'],**changes}


def add_row(page, server, project, remark, month='2025-11', settle='120.00', paid='12.00'):
    result=page.request.post(server+'/api/m05/history/save',data={'project_id':project,'category':'material',
       'entry_kind':'manual','cutoff_ym':month,'settle_amount':settle,'paid_amount':paid,'remark':remark}).json()
    assert result['ok'],result
    return result['id']


def cell(page, rid, field, category='material'):
    return page.get_by_role('region',name=('辅材' if category=='material' else '机械')+'欠款台账').locator(f'[row-id="{category}:manual:{rid}"] [col-id="{field}"] input')


def select_project(page, name):
    pick_option(page, '选择项目', name)


def wait_value(page, project, rid, field, value, category='material'):
    page.wait_for_function("""({project,rid,field,value,category}) => {
      const key=JSON.stringify([project,rid,field,value,category]);
      if(window.ledger398Probe?.key!==key) window.ledger398Probe={key,pending:false,matched:false};
      const probe=window.ledger398Probe;
      if(probe.matched) return true;
      if(!probe.pending) {
        probe.pending=true;
        fetch(`/api/m05/ledger?project_id=${project}&end_ym=`).then(response=>response.json()).then(data=>{
          probe.matched=data.sides.find(side=>side.category===category)?.rows.find(row=>row.record_id===rid)?.[field]===value;
        }).finally(()=>{probe.pending=false;});
      }
      return false;
    }""",arg={'project':project,'rid':rid,'field':field,'value':value,'category':category},timeout=8000)
    # Assert the actual response once more; a pending Promise is never a passed predicate.
    actual=row_data(data(page, page.url.split('/preview/')[0], project),rid,category)
    assert actual[field]==value


def test_month_reorder_keeps_record_id_and_queued_field(server,browser_page):
    page,_=browser_page
    open_ledger(page,server)
    project=project_id(page,server)
    rid=add_row(page,server,project,'月份重排测试')
    sync_ledger(page)
    month=cell(page,rid,'month');settle=cell(page,rid,'other_expense');paid=cell(page,rid,'payment')
    month.fill('2025-08');month.press('Tab')
    expect(settle).to_be_focused();settle.fill('333.33');settle.press('Tab')
    expect(paid).to_be_focused();paid.fill('44.44');paid.press('Tab')
    page.get_by_role('heading',name='逐月欠款台账',exact=True).click()
    wait_value(page,project,rid,'month','2025-08')
    wait_value(page,project,rid,'other_expense','333.33')
    wait_value(page,project,rid,'payment','44.44')
    expect(month).to_have_value('2025-08')
    current=row_data(data(page,server,project),rid)
    assert current['remark']=='月份重排测试'


def test_mouse_and_chinese_composition_survive_prior_receipt(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'中文合成测试')
    sync_ledger(page)
    pending=[];writes=[]
    def hold(route):
        writes.append(route.request.post_data_json)
        if len(writes)==1: pending.append(route)
        else: route.continue_()
    page.route('**/api/m05/history/save',hold)
    settle=cell(page,rid,'other_expense');note=cell(page,rid,'remark')
    settle.fill('222.00');note.click();note.dispatch_event('compositionstart',{'data':'中'})
    note.fill('中文连续草稿');assert len(writes)==1
    pending[0].fulfill(response=pending[0].fetch())
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存')
    expect(note).to_be_focused();expect(note).to_have_value('中文连续草稿')
    note.dispatch_event('keydown',{'key':'Enter','code':'Enter','isComposing':True})
    expect(note).to_be_focused();assert len(writes)==1
    note.dispatch_event('compositionend',{'data':'中文连续草稿'});note.press('Tab')
    wait_value(page,project,rid,'remark','中文连续草稿')
    assert len(writes)==2


def test_refusal_preserves_input_blank_is_not_zero_and_no_partial_write(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'金额拒绝测试')
    sync_ledger(page)
    paid=cell(page,rid,'payment');paid.fill('invalid');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('保存被拒')
    expect(paid).to_have_value('invalid')
    current=row_data(data(page,server,project),rid)
    rejected=page.request.post(server+'/api/m05/history/save',data=body_for(project,current,settle_amount='bad',remark='不得部分写入'))
    assert rejected.status==400 and '有效金额' in rejected.json()['message']
    unchanged=row_data(data(page,server,project),rid)
    assert unchanged['remark']=='金额拒绝测试' and unchanged['payment']=='12.00' and unchanged['other_expense']=='120.00'
    paid.fill('');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('保存被拒')
    expect(paid).to_have_value('')
    assert row_data(data(page,server,project),rid)['payment']=='12.00'
    paid.fill('0');paid.press('Tab');page.get_by_role('heading',name='逐月欠款台账',exact=True).click()
    wait_value(page,project,rid,'payment','0.00')
    expect(paid).to_have_value('0.00')


def test_saved_but_refresh_failed_does_not_resubmit(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'刷新失败测试')
    sync_ledger(page)
    paid=cell(page,rid,'payment');expect(paid).to_be_visible()
    writes=[]
    page.route('**/api/m05/history/save',lambda route:(writes.append(route.request.post_data_json),route.continue_()))
    page.route('**/api/m05/ledger?**',lambda route:route.fulfill(status=500,json={'message':'隔离读取失败'}))
    paid.fill('88.88');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存，读取失败')
    assert row_data(data(page,server,project),rid)['payment']=='88.88'
    assert len(writes)==1
    page.unroute('**/api/m05/ledger?**')
    page.get_by_role('button',name='重新加载',exact=True).click()
    expect(paid).to_have_value('88.88');assert len(writes)==1


def test_old_save_remains_original_record_and_draft_is_month_scoped(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'跨项目保存测试')
    sync_ledger(page)
    pending=[]
    page.route('**/api/m05/history/save',lambda route:pending.append(route))
    paid=cell(page,rid,'payment');paid.fill('66.66');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('正在保存');assert len(pending)==1
    select_project(page,'长项目名验收')
    expect(page.locator('input[value="另一项目测试行"]')).to_be_visible()
    assert pending[0].request.post_data_json['project_id']==project
    assert pending[0].request.post_data_json['id']==rid
    pending[0].fulfill(response=pending[0].fetch())
    wait_value(page,project,rid,'payment','66.66')
    expect(page.locator('[aria-label="保存回执"]')).not_to_contain_text('台账已保存')
    page.unroute('**/api/m05/history/save')
    select_project(page,'隔离项目');paid=cell(page,rid,'payment');expect(paid).to_have_value('66.66')
    paid.fill('bad');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('保存被拒')
    select_project(page,'长项目名验收')
    expect(cell(page,rid,'payment')).to_have_count(0)
    select_project(page,'隔离项目')
    expect(cell(page,rid,'payment')).to_have_value('bad')
    assert row_data(data(page,server,project),rid)['payment']=='66.66'


def test_identity_pause_preserves_real_edit_draft_and_blocks_saves(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'身份草稿测试')
    sync_ledger(page)
    paid=cell(page,rid,'payment');paid.fill('987.65')
    writes=[]
    page.route('**/api/m05/history/save',lambda route:(writes.append(route.request.post_data_json),route.continue_()))
    page.route('**/api/m15/users',lambda route:route.abort('failed'))
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('已暂停操作')
    expect(page.locator('.workspace')).to_be_hidden()
    page.locator('.workspace input').evaluate_all('(inputs)=>inputs.forEach(input=>input.blur())')
    assert not writes
    page.unroute('**/api/m15/users');page.get_by_role('button',name='重试',exact=True).click()
    expect(paid).to_have_value('987.65');assert not writes
    paid.focus();paid.press('Tab');wait_value(page,project,rid,'payment','987.65')
    assert len(writes)==1


def test_real_undo_redo_conflict_and_account_ownership(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server);rid=add_row(page,server,project,'撤销重做测试')
    sync_ledger(page)
    paid=cell(page,rid,'payment');paid.fill('77.77');paid.press('Tab')
    page.get_by_role('heading',name='逐月欠款台账',exact=True).click();wait_value(page,project,rid,'payment','77.77')
    expect(page.get_by_role('status',name='保存回执')).not_to_contain_text('正在保存')
    page.get_by_role('button',name='撤销',exact=True).click();wait_value(page,project,rid,'payment','12.00')
    page.get_by_role('button',name='重做',exact=True).click();wait_value(page,project,rid,'payment','77.77')
    admin_history=page.request.get(server+'/api/history/status').json()['undo']
    with httpx.Client(base_url=server) as other:
        assert other.post('/m15/login',data={'account':'preview-user','password':''}).status_code==303
        denied=other.post('/api/history/undo',json={'operation_id':admin_history['id']})
        assert denied.status_code==409 and denied.json()['ok'] is False
        current=row_data(data(page,server,project),rid)
        assert other.post('/api/m05/history/save',json=body_for(project,current,paid_amount='99.99')).json()['ok']
    page.get_by_role('button',name='撤销',exact=True).click()
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已被后续操作修改')
    current=row_data(data(page,server,project),rid)
    assert current['payment']=='99.99' and current['other_expense']=='120.00'


def test_duplicate_add_stale_token_and_real_export(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    project=project_id(page,server)
    before={row['record_id'] for side in data(page,server,project)['sides'] for row in side['rows'] if row['record_id']}
    writes=[]
    page.route('**/api/m05/history/save',lambda route:(writes.append(route.request.post_data_json),route.continue_()))
    page.get_by_role('button',name='新增历史行',exact=True).evaluate('(button)=>{button.click();button.click()}')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已新增历史行')
    assert len(writes)==1
    after={row['record_id'] for side in data(page,server,project)['sides'] for row in side['rows'] if row['record_id']}
    assert len(after-before)==1
    rid=next(iter(after-before));old=row_data(data(page,server,project),rid)
    expect(cell(page,rid,'month')).to_be_focused()
    page.get_by_role('heading',name='逐月欠款台账',exact=True).click()
    body=body_for(project,old,settle_amount='234.56',paid_amount='34.56',remark='导出核对行')
    assert page.request.post(server+'/api/m05/history/save',data=body).json()['ok']
    duplicate=page.request.post(server+'/api/m05/history/save',data=body)
    assert duplicate.status==400 and '已变化' in duplicate.json()['message']
    sync_ledger(page)
    expect(cell(page,rid,'remark')).to_have_value('导出核对行')
    expected=data(page,server,project,previous_report_month(page))
    page.get_by_role('button',name='逐月台账导出…',exact=True).click()
    page.get_by_role('button',name='确认清单',exact=True).click()
    with page.expect_download() as event:page.get_by_role('button',name='保存到本地',exact=True).click()
    download=event.value;path=output(download.suggested_filename,kind='exports');download.save_as(path)
    assert path.stat().st_size>1000 and path.suffix=='.xlsx'
    workbook=openpyxl.load_workbook(path,data_only=True)
    assert workbook.sheetnames==['辅材','机械','特殊费用月报表']
    for side in expected['sides']:
        rows=[]
        for cells in workbook[side['label']].iter_rows(min_row=3,max_col=6,values_only=True):
            if re.fullmatch(r'\d{4}-\d{2}',str(cells[1] or '')):
                rows.append((str(cells[1]),*[f'{Decimal(str(value)):.2f}' for value in cells[2:5]],str(cells[5] or '')))
        assert rows==[(row['month'],row['other_expense'],row['payment'],row['debt'],row['remark']) for row in side['rows']]
    workbook.close()
    page.screenshot(path=str(output('ledger398-1920.png',kind='screenshots')),full_page=True)
    page.set_viewport_size({'width':1024,'height':900})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output('ledger398-1024.png',kind='screenshots')),full_page=True)


def test_mechanical_payment_readonly_settlement_and_normal_month(server,browser_page):
    page,_=browser_page;open_ledger(page,server,'preview-user')
    project=project_id(page,server)
    mechanical=next(side for side in data(page,server,project)['sides'] if side['category']=='mechanical')['rows'][0]
    region=page.get_by_role('region',name='机械欠款台账')
    expect(region.locator('[col-id="other_expense"] input')).to_have_count(0)
    paid=region.locator('[col-id="payment"] input');paid.fill('101.01');paid.press('Tab')
    page.get_by_role('heading',name='逐月欠款台账',exact=True).click()
    wait_value(page,project,mechanical['record_id'],'payment','101.01','mechanical')
    current=row_data(data(page,server,project),mechanical['record_id'],'mechanical')
    rejected=page.request.post(server+'/api/m05/history/save',data=body_for(project,current,'mechanical',settle_amount='999',paid_amount='123'))
    assert rejected.status==400 and '机械结算取台账' in rejected.json()['message']
    assert row_data(data(page,server,project),mechanical['record_id'],'mechanical')['payment']=='101.01'
    expect(page.get_by_role('region',name='辅材欠款台账').locator('[row-id="material:month:2025-12"] [col-id="payment"] input')).to_have_count(0)
    page.screenshot(path=str(output('ledger398-dark-large.png',kind='screenshots')),full_page=True)


def test_anonymous_ledger_refresh_is_readonly_and_operable(server,browser_page):
    page,_=browser_page
    page.goto(server+'/preview/ledger')
    select_project(page,'隔离项目')
    region=page.get_by_role('region',name='辅材欠款台账');expect(region).to_be_visible()
    expect(region.locator('.ledger-input')).to_have_count(0)
    expect(page.get_by_role('button',name='新增历史行',exact=True)).to_be_disabled()
    with page.expect_request(lambda request:'/api/m05/ledger?' in request.url) as event:
        sync_ledger(page)
    response=event.value.response();assert response and response.ok
    assert response.json()['project_id']==project_id(page,server)
    expect(region.locator('.ledger-input')).to_have_count(0)


def sync_ledger(page):
    with page.expect_request(lambda request:'/api/m05/ledger?' in request.url):
        page.evaluate("window.dispatchEvent(new Event('focus'))")


def previous_report_month(page):
    return page.evaluate("""() => {const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit'}).formatToParts(new Date());return new Date(Date.UTC(Number(parts.find(p=>p.type==='year').value),Number(parts.find(p=>p.type==='month').value)-2,1)).toISOString().slice(0,7)}""")
