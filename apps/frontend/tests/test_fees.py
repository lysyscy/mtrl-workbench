"""Annual record identities use actual copied records; no amount/name seed."""
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
    field=page.get_by_label(f'{row["ym"]} {row["item"] or "未命名"}金额 #{row["id"]}',exact=True)
    expect(field).to_have_value(row['amount'])
    assert not page.locator('.fees-grid [col-id="prior"] input,.fees-grid [col-id="total"] input').count()
    assert not page.locator('.fee-auto-amount input').count()
    details=page.locator('.fee-record-name-details').filter(has_text=row['item']).first
    details.locator('summary').click()
    expect(details.locator('input').first).to_be_visible()
    page.wait_for_function("""()=>[...document.querySelectorAll('.fees-grid details[open]')].every(
      d=>d.getBoundingClientRect().bottom<=d.closest('.ag-row').getBoundingClientRect().bottom+1)""")


def test_actual_fee_save_updates_only_original_id(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,data=sample(api,projects);open_sample(page,server,project,data)
    row=data['records'][0];month=int(row['ym'][-2:]);page.locator('.fees-grid .ag-body-horizontal-scroll-viewport').evaluate('(e,m)=>e.scrollLeft=Math.max(0,(m-2)*170)',month)
    field=page.get_by_label(f'{row["ym"]} {row["item"] or "未命名"}金额 #{row["id"]}',exact=True)
    changed=Decimal(row['amount'])+Decimal('1.25');field.fill(str(changed));field.press('Tab')
    expect(page.locator('.fees-page').get_by_role('status').filter(has_text='已保存')).to_be_visible()
    after=get(api,'/api/m09/fee/year',year=data['year'],pj=project['warehouse_name'])
    before={r['id']:r for r in data['records']};current={r['id']:r for r in after['records']}
    assert set(before)==set(current)
    assert Decimal(current[row['id']]['amount'])==changed and current[row['id']]['ym']==row['ym']
    assert all(current[key]==value for key,value in before.items() if key!=row['id'])
