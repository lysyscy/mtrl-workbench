"""Real-copy detail autosave, later drafts, first entry and last-row removal."""
from decimal import Decimal
import pytest
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page


def select_project(page, name, ym):
    month=page.get_by_label('月份',exact=True)
    month.fill(ym);month.press('Enter')
    page.get_by_role('button',name='显示项目',exact=True).click()
    dialog=page.get_by_role('dialog',name='选择显示项目及顺序',exact=True)
    dialog.get_by_role('button',name='全不选',exact=True).click()
    dialog.get_by_role('checkbox',name=name,exact=True).check()
    dialog.get_by_role('button',name='应用项目选择',exact=True).click()
    page.get_by_role('button',name='表2 零租明细',exact=True).click()
    expect(page.locator('.mechanical-detail-table .business-grid')).to_have_attribute('data-layout-state','ready')


def test_real_detail_enter_autosave_keeps_later_field_draft(server,browser_page,api,projects,disposable):
    state=get(api,'/api/m06/workbench')
    group=next((d for d in state['details'] if d['category']=='zero' and len(d['rows'])>=2 and d['rows'][0].get('amount') is not None),None)
    assert group,'真实副本没有可连续编辑的零租明细'
    project=next(p for p in projects if p['warehouse_name']==group['warehouse']);name=project['disp']
    page,_=browser_page;open_page(page,server,'mechanical','机械费');select_project(page,name,group['ym'])
    amount=page.get_by_label(name+' 第1行 合价（元）',exact=True)
    memo=page.get_by_label(name+' 第2行 备注',exact=True)
    pending=[]
    page.route('**/api/m06/workbench/details-save',lambda route:pending.append(route))
    value=Decimal(str(group['rows'][0]['amount']))+Decimal('1.25')
    with page.expect_request('**/api/m06/workbench/details-save'):
        amount.fill(str(value));amount.press('Enter')
    memo.fill('自动保存回归')
    assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(page.get_by_role('button',name='表1 公司汇总',exact=True)).to_be_enabled()
    expect(memo).to_have_value('自动保存回归')
    with page.expect_request('**/api/m06/workbench/details-save'):
        memo.press('Enter')
    assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(page.get_by_role('button',name='表1 公司汇总',exact=True)).to_be_enabled()
    saved=next(d for d in get(api,'/api/m06/workbench')['details']
               if d['warehouse']==group['warehouse'] and d['ym']==group['ym'] and d['category']=='zero')
    assert Decimal(saved['rows'][0]['amount'])==value
    assert saved['rows'][1]['memo']=='自动保存回归'


def test_real_first_amount_counts_and_removing_last_row_clears_process_amount(server,browser_page,api,projects,disposable):
    state=get(api,'/api/m06/workbench');ym=state['months'][-1]
    occupied={d['warehouse'] for d in state['details'] if d['ym']==ym and d['category']=='zero' and d['rows']}
    # Pick an existing real archive; only its empty category in our disposable copy is edited.
    allowed={p['warehouse'] for p in state['projects']}
    project=next((p for p in projects if p['warehouse_name'] in allowed and p['warehouse_name'] not in occupied),None)
    assert project,'真实副本没有首次录入可用的空零租项目'
    name=project['disp'];page,_=browser_page
    open_page(page,server,'mechanical','机械费');select_project(page,name,ym)
    grid=page.locator('.mechanical-detail-table')
    expect(grid.get_by_role('button',name='增行',exact=True)).to_have_count(1)
    expect(grid.get_by_role('button',name='移除',exact=True)).to_have_count(0)
    grid.get_by_role('button',name='增行',exact=True).click()
    amount=page.get_by_label(name+' 第1行 合价（元）',exact=True)
    with page.expect_response('**/api/m06/workbench/details-save') as response:
        amount.fill('77.00');amount.press('Enter')
    assert response.value.ok
    expect(page.get_by_role('button',name='表1 公司汇总',exact=True)).to_be_enabled()
    expect(grid).not_to_contain_text('未保存')
    state=get(api,'/api/m06/mech')['effective_values'][project['warehouse_name']][ym]
    assert state['mech_2']=='77.00' and state['mech_4'] is None
    with page.expect_response('**/api/m06/workbench/details-save') as response:
        grid.get_by_role('button',name='移除',exact=True).click()
    assert response.value.ok
    expect(page.get_by_role('button',name='表1 公司汇总',exact=True)).to_be_enabled()
    expect(grid.get_by_role('button',name='增行',exact=True)).to_have_count(1)
    expect(grid.get_by_role('button',name='移除',exact=True)).to_have_count(0)
    state=get(api,'/api/m06/mech')['effective_values'][project['warehouse_name']][ym]
    assert state['mech_2'] is None and state['mech_4'] is None


def test_lost_detail_receipt_can_reread_and_resume_without_another_write(server,browser_page,api,projects,disposable):
    state=get(api,'/api/m06/workbench')
    group=next(d for d in state['details'] if d['category']=='zero' and d['rows'] and d['rows'][0].get('amount') is not None)
    project=next(p for p in projects if p['warehouse_name']==group['warehouse']);name=project['disp']
    page,_=browser_page;open_page(page,server,'mechanical','机械费');select_project(page,name,group['ym'])
    writes=[]
    def lose_receipt(route):
        response=route.fetch();assert response.ok
        writes.append(route.request.post_data_json);route.abort('failed')
    page.route('**/api/m06/workbench/details-save',lose_receipt)
    field=page.get_by_label(name+' 第1行 合价（元）',exact=True)
    value=Decimal(str(group['rows'][0]['amount']))+Decimal('1.25')
    field.fill(str(value));field.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible()
    expect(field).not_to_be_editable()
    page.get_by_role('button',name='重读明细',exact=True).click()
    resume=page.get_by_role('button',name='已核对，继续',exact=True)
    expect(resume).to_be_enabled();resume.click()
    expect(field).to_be_editable()
    assert len(writes)==1
    saved=next(d for d in get(api,'/api/m06/workbench')['details']
               if d['warehouse']==group['warehouse'] and d['ym']==group['ym'] and d['category']=='zero')
    assert Decimal(saved['rows'][0]['amount'])==value


def test_settings_mouse_close_and_navigation_keep_only_effective_drafts(server,browser_page,api,disposable):
    page,_=browser_page;open_page(page,server,'mechanical','机械费')
    page.get_by_role('button',name='表2 零租明细',exact=True).click()
    page.get_by_role('button',name='车牌规则',exact=True).click()
    dialog=page.get_by_role('dialog',name='无需车牌设备关键词',exact=True)
    field=dialog.get_by_label('无需车牌设备关键词',exact=True);original=field.input_value()
    # Whitespace and duplicate lines do not change the settings accepted by the server.
    field.fill(original+'\n\n'+original.split('\n')[0])
    dialog.get_by_role('button',name='取消',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='车牌规则',exact=True).click();field.fill(original+'\n夜间草稿检查')
    page.go_back();expect(page.locator('#page-title')).to_have_text('项目档案')
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.go_forward();expect(field).to_have_value(original+'\n夜间草稿检查')
    dialog.get_by_role('button',name='取消',exact=True).click()
    confirmation=page.get_by_role('dialog',name='放弃未保存的修改？',exact=True)
    confirmation.get_by_role('button',name='继续编辑',exact=True).click()
    expect(field).to_have_value(original+'\n夜间草稿检查')
    dialog.get_by_role('button',name='关闭弹窗',exact=True).click()
    confirmation.get_by_role('button',name='放弃并关闭',exact=True).click()
    assert get(api,'/api/m06/workbench')['settings']['plate_keywords']==[word for word in original.split('\n') if word]

    page.get_by_role('button',name='显示项目',exact=True).click()
    picker=page.get_by_role('dialog',name='选择显示项目及顺序',exact=True)
    picker.get_by_role('button',name='全不选',exact=True).click()
    boxes=picker.get_by_role('checkbox');assert boxes.count()>2
    boxes.nth(0).check();boxes.nth(1).check()
    picker.get_by_role('button',name='应用项目选择',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='显示项目',exact=True).click()
    # Reordering an unselected project changes no effective display setting.
    picker.locator('li').nth(2).get_by_role('button',name='下移',exact=True).click()
    picker.get_by_role('button',name='取消',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='显示项目',exact=True).click()
    boxes.nth(0).uncheck();picker.get_by_role('button',name='取消',exact=True).click()
    confirmation.get_by_role('button',name='继续编辑',exact=True).click()
    expect(boxes.nth(0)).not_to_be_checked();boxes.nth(0).check()
    picker.get_by_role('button',name='取消',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='显示项目',exact=True).click()
    picker.locator('li').first.get_by_role('button',name='下移',exact=True).click()
    picker.get_by_role('button',name='关闭弹窗',exact=True).click()
    confirmation.get_by_role('button',name='放弃并关闭',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)


@pytest.mark.parametrize('kind,receipt',[('plate','lost'),('plate','stale'),('projects','mismatch')])
def test_unknown_settings_receipt_keeps_input_and_rereads_without_repeat_write(server,browser_page,api,disposable,kind,receipt):
    page,_=browser_page;open_page(page,server,'mechanical','机械费')
    if kind=='plate':
        page.get_by_role('button',name='表2 零租明细',exact=True).click()
        page.get_by_role('button',name='车牌规则',exact=True).click()
        dialog=page.get_by_role('dialog',name='无需车牌设备关键词',exact=True)
        field=dialog.get_by_label('无需车牌设备关键词',exact=True)
        draft=field.input_value()+'\n夜间回执检查'+receipt;field.fill(draft)
        save=dialog.get_by_role('button',name='保存规则',exact=True)
    else:
        page.get_by_role('button',name='显示项目',exact=True).click()
        dialog=page.get_by_role('dialog',name='选择显示项目及顺序',exact=True)
        box=dialog.get_by_role('checkbox').first;checked=not box.is_checked();box.set_checked(checked)
        save=dialog.get_by_role('button',name='应用项目选择',exact=True)
    writes=[]
    def lose_receipt(route):
        response=route.fetch();assert response.ok;writes.append(route.request.post_data_json)
        if receipt=='lost':route.abort('failed')
        else:
            result=response.json()
            if receipt=='stale':result['revision']-=1
            else:result['shown_projects']=[]
            route.fulfill(json=result)
    page.route('**/api/m06/workbench/settings',lose_receipt)
    save.click()
    expect(dialog.get_by_role('alert')).to_contain_text('保存结果待核实')
    expect(save).to_be_disabled()
    if kind=='plate':expect(field).to_have_value(draft)
    else:expect(box).to_be_checked(checked=checked)
    # Recovery remains available after leaving and returning to the retained page.
    page.go_back();expect(page.locator('#page-title')).to_have_text('项目档案')
    page.go_forward();expect(dialog.get_by_role('button',name='重新读取',exact=True)).to_be_visible()
    if receipt=='mismatch':
        page.route('**/api/m06/workbench?*',lambda route:route.abort('failed'))
        dialog.get_by_role('button',name='重新读取',exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('待核实')
        expect(dialog.get_by_role('alert')).not_to_contain_text('修改已保存')
        expect(save).to_be_disabled();assert len(writes)==1
        page.unroute('**/api/m06/workbench?*')
    dialog.get_by_role('button',name='重新读取',exact=True).click()
    expect(save).to_be_enabled();assert len(writes)==1
    actual=get(api,'/api/m06/workbench')['settings']
    key='plate_keywords' if kind=='plate' else 'shown_projects'
    assert actual[key]==writes[0][key]
    dialog.get_by_role('button',name='取消',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
