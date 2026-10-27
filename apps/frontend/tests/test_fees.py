"""Fee-item identities use actual copied records and a disposable real copy."""
from datetime import datetime
from decimal import Decimal
from playwright.sync_api import expect
from preview_select import pick_option
from test_preview import server,browser_page,login
from live_data import get,open_page


def sample(api,projects):
    fallback=None
    for year in [str(datetime.now().year),str(datetime.now().year-1)]:
        for project in projects:
            if not project['warehouse_name'] or project['project_type']=='shell':continue
            data=get(api,'/api/m09/fee/year',year=year,pj=project['warehouse_name'])
            if not data['records']:continue
            if fallback is None:fallback=(project,data)
            records=data['records']
            # Prefer a real same-month/name sibling so the edit proves ID isolation.
            duplicate=next((row for row in records if sum(
                other['ym']==row['ym'] and other['item']==row['item'] for other in records)>1),None)
            if duplicate is not None:
                return project,{**data,'records':[duplicate]+[row for row in records if row['id']!=duplicate['id']]}
    if fallback is not None:return fallback
    raise AssertionError('真实副本没有年度手填费用，逐条编辑保护未覆盖')


def open_sample(page,server,project,data):
    open_page(page,server,'fees','特殊费用')
    pick_option(page,'费用项目',project['disp'])
    field=page.get_by_label('费用年份',exact=True);field.fill(data['year']);field.press('Enter');field.press('Escape')
    expect(page.locator('.ant-picker-dropdown:visible')).to_have_count(0)
    expect(page.get_by_label('特殊费用年度表',exact=True)).to_be_visible()


def test_actual_annual_record_ids_and_readonly_totals(server,browser_page,api,projects):
    page,_=browser_page;project,data=sample(api,projects);open_sample(page,server,project,data)
    row=data['records'][0]
    month=int(row['ym'][-2:])
    grid=page.locator('.fees-grid');grid.locator('.ag-body-horizontal-scroll-viewport').evaluate('(e,m)=>e.scrollLeft=Math.max(0,(m-2)*170)',month)
    field=page.get_by_label(f'{row["ym"]} {row["item"]}金额',exact=True)
    expect(field).to_have_value(row['amount'])
    assert not page.locator('.fees-grid [col-id="prior"] input,.fees-grid [col-id="total"] input').count()
    assert not page.locator('.fee-auto-amount input').count()
    expect(page.get_by_label(f'{row["item"]}费用项名称',exact=True)).to_be_visible()
    automatic=grid.locator('.ag-row').filter(has_text=data['auto_name'])
    assert not automatic.locator('input').count()



def test_actual_fee_save_updates_only_original_id(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,data=sample(api,projects);open_sample(page,server,project,data)
    row=data['records'][0];month=int(row['ym'][-2:]);page.locator('.fees-grid .ag-body-horizontal-scroll-viewport').evaluate('(e,m)=>e.scrollLeft=Math.max(0,(m-2)*170)',month)
    field=page.get_by_label(f'{row["ym"]} {row["item"]}金额',exact=True)
    changed=Decimal(row['amount'])+Decimal('1.25');field.fill(str(changed));field.press('Tab')
    expect(page.locator('.fees-page').get_by_role('status').filter(has_text='已保存')).to_be_visible()
    after=get(api,'/api/m09/fee/year',year=data['year'],pj=project['warehouse_name'])
    before={r['id']:r for r in data['records']};current={r['id']:r for r in after['records']}
    assert set(before)==set(current)
    assert Decimal(current[row['id']]['amount'])==changed and current[row['id']]['ym']==row['ym']
    assert all(current[key]==value for key,value in before.items() if key!=row['id'])


def test_new_annual_item_creates_only_entered_month(server,browser_page,api,projects,disposable):
    from uuid import uuid4
    page,_=browser_page; project,data=sample(api,projects); open_sample(page,server,project,data)
    year=data['year']; project_name=project['warehouse_name']; name='验证费用'+uuid4().hex[:10]
    before=get(api,'/api/m09/fee/year',year=year,pj=project_name)
    page.get_by_role('button',name='增加手填项').click()
    expect(page.locator('.fees-page').get_by_role('status').filter(has_text='已增加')).to_be_visible(timeout=15000)
    added=get(api,'/api/m09/fee/year',year=year,pj=project_name)
    ids={r.get('item_id') for r in before['rows']};new_item=next(r for r in added['rows'] if r.get('item_id') and r['item_id'] not in ids)
    field=page.get_by_label(f'{new_item["item"]}费用项名称',exact=True);field.fill(name);field.press('Enter')
    expect(page.locator('.fees-page').get_by_role('status').filter(has_text='已保存')).to_be_visible(timeout=15000)
    assert get(api,'/api/m09/fee/year',year=year,pj=project_name)['records']==before['records']
    amount=page.get_by_label(f'{year}-03 {name}金额',exact=True);expect(amount).to_be_visible();amount.fill('12.34');amount.press('Enter')
    expect(page.locator('.fees-page').get_by_role('status').filter(has_text='已保存')).to_be_visible(timeout=15000)
    after=get(api,'/api/m09/fee/year',year=year,pj=project_name)
    new=[r for r in after['records'] if r['id'] not in {x['id'] for x in before['records']}]
    assert len(new)==1 and new[0]['item']==name and new[0]['ym']==year+'-03' and Decimal(new[0]['amount'])==Decimal('12.34')
    page.reload();pick_option(page,'费用项目',project['disp']);year_field=page.get_by_label('费用年份',exact=True);year_field.fill(year);year_field.press('Enter');year_field.press('Escape')
    expect(page.get_by_label(f'{year}-03 {name}金额',exact=True)).to_have_value('12.34',timeout=15000)
    assert page.get_by_text('新增核算月',exact=True).count()==0


def test_new_annual_item_lost_receipt_reread_does_not_duplicate(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,data=sample(api,projects);open_sample(page,server,project,data)
    year=data['year'];project_name=project['warehouse_name'];writes=[]
    before=get(api,'/api/m09/fee/year',year=year,pj=project_name)
    def lose_receipt(route):
        response=route.fetch();assert response.ok;writes.append(route.request.post_data_json);route.abort('failed')
    page.route('**/api/m09/fee/item/create',lose_receipt)
    page.get_by_role('button',name='增加手填项').click()
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible(timeout=15000)
    expect(page.get_by_role('button',name='增加手填项')).to_be_disabled()
    page.get_by_role('button',name='重读核对',exact=True).click()
    expect(page.get_by_role('button',name='已核对，保留输入继续')).to_be_enabled(timeout=15000)
    after=get(api,'/api/m09/fee/year',year=year,pj=project_name);ids={r.get('item_id') for r in before['rows']}
    new=[r for r in after['rows'] if r.get('item_id') and r['item_id'] not in ids]
    assert len(writes)==1 and len(new)==1 and new[0]['months']==[None]*12
    assert after['records']==before['records']
    page.get_by_role('button',name='已核对，保留输入继续').click()
    assert len(writes)==1
