"""Actual ledger content height, totals and normal-month remark identity."""
import pytest
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import ledger_sample,grid_row,get,money
from test_ledger import open_sample


def test_actual_ledger_layout_tracks_rows_and_totals(server,browser_page,api,projects):
    page,_=browser_page;project,side,row,key=ledger_sample(api,projects);open_sample(page,server,project)
    data=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    for item in data['sides']:
        region=page.get_by_role('region',name=item['label']+'欠款台账',exact=True);expect(region).to_be_visible()
        grid=region.locator('.ledger-grid');box=grid.bounding_box();assert box and box['height']>=240
        if item['rows']:expect(region.locator('.ag-row').first).to_be_visible()
    assert not page.locator('.ledger-grid .ag-cell[col-id="debt"]').evaluate_all('els=>els.some(e=>e.scrollWidth>e.clientWidth+1)')


def test_real_normal_month_remark_save_uses_same_month(server,browser_page,api,projects,disposable):
    page,_=browser_page
    found=None
    for project in projects:
        if project['project_type']=='shell':continue
        data=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
        for side in data['sides']:
            for row in side['rows']:
                if row['row_kind']=='month' and not row['editable']:found=(project,side,row);break
            if found:break
        if found:break
    assert found,'真实副本没有普通月备注行，该保护未覆盖'
    project,side,row=found;open_sample(page,server,project)
    key=side['category']+':month:'+row['month'];field=grid_row(page,'.ledger-grid',key).locator('[col-id="remark"] input')
    # Scroll rendered rows rather than assuming the first viewport covers this month.
    if not field.count():
        page.get_by_role('region',name=side['label']+'欠款台账').locator('.ag-body-viewport').evaluate('e=>e.scrollTop=e.scrollHeight')
    expect(field).to_be_visible();field.fill(row['remark']+'核验');field.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存')
    after=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    actual=next(r for s in after['sides'] if s['category']==side['category'] for r in s['rows'] if r['row_kind']=='month' and r['month']==row['month'])
    assert actual['remark']==row['remark']+'核验'


def test_flow_search_keeps_workspace_height_and_state(server,browser_page):
    from live_data import open_page
    page,_=browser_page;open_page(page,server,'ledger','付款流水')
    grid=page.locator('.flow-grid');expect(grid).to_be_visible()
    before=grid.bounding_box();assert before and before['height']>240
    keyword=page.get_by_role('textbox',name='流水关键词',exact=True)
    keyword.fill('无匹配流水编码-布局核验')
    expect(page.get_by_text('显示 0 条',exact=True)).to_be_visible()
    assert abs(grid.bounding_box()['height']-before['height'])<1
    page.locator('a[href="/preview/debt"]').click()
    expect(page.locator('#page-title')).to_have_text('欠款台账')
    page.locator('a[href="/preview/ledger"]').click()
    expect(keyword).to_have_value('无匹配流水编码-布局核验')
    assert abs(grid.bounding_box()['height']-before['height'])<1
    keyword.fill('')
    operator=grid.locator('.ag-header-cell[col-id="created_by"]').bounding_box()
    status=grid.locator('.ag-header-cell[col-id="status_label"]').bounding_box()
    assert operator and status and operator['width']>=status['width']


@pytest.mark.parametrize("viewport",[(1920,1080),(900,900)])
def test_project_loading_keeps_ledger_space_and_hides_old_values(server,browser_page,api,projects,viewport):
    from preview_select import pick_option
    from live_data import open_page
    page,_=browser_page;page.set_viewport_size(dict(zip(('width','height'),viewport)));open_page(page,server,'debt','欠款台账')
    available=[p for p in projects if p['project_type']!='shell']
    assert len(available)>1,'真实副本缺少两个可切换项目'
    first,second=available[:2]
    pick_option(page,'选择项目',first['disp'])
    expect(page.locator('.ledger-sides')).to_be_visible()
    before=page.locator('.ledger-card').bounding_box();pending=[]
    page.route('**/api/m05/ledger?**',lambda route:pending.append(route))
    pick_option(page,'选择项目',second['disp'])
    expect(page.get_by_role('status').filter(has_text='正在读取台账')).to_be_visible()
    expect(page.locator('.ledger-sides')).to_have_count(0)
    during=page.locator('.ledger-card').bounding_box()
    assert abs(during['height']-before['height'])<1
    assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok
    route.fulfill(response=response);page.unroute('**/api/m05/ledger?**')
    expect(page.locator('.ledger-sides')).to_be_visible()
    assert abs(page.locator('.ledger-card').bounding_box()['height']-before['height'])<1


def test_split_pages_keep_unsaved_ledger_guard_without_business_write(server,browser_page,api,projects):
    page,_=browser_page;project,side,row,key=ledger_sample(api,projects,editable=True)
    open_sample(page,server,project)
    # The ledger opens at the latest month; expose this actual first manual record.
    page.locator('.ledger-grid .ag-grid-viewport,.ledger-grid .ag-body-viewport').evaluate_all('es=>es.forEach(e=>e.scrollTop=0)')
    field=grid_row(page,'.ledger-grid',key).locator('[col-id="remark"] input')
    expect(field).to_be_visible();attempts=[]
    def reject_locally(route):
        attempts.append(route.request.post_data)
        route.abort('failed')
    page.route('**/api/m05/history/save',reject_locally)
    draft=row['remark']+'未保存输入核验';field.fill(draft)
    page.locator('a[href="/preview/ledger"]').click()
    expect(page.locator('#page-title')).to_have_text('付款流水')
    expect(page.get_by_role('button',name='导出 Excel',exact=True)).to_be_disabled()
    page.locator('a[href="/preview/debt"]').click()
    expect(field).to_have_value(draft)
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('未确认')
    assert len(attempts)==1
    actual=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    assert any(r['remark']==row['remark'] for s in actual['sides'] if s['category']==side['category'] for r in s['rows'] if r['record_id']==row['record_id'] and r['row_kind']==row['row_kind'] and r['month']==row['month'])


def test_notice_flow_location_does_not_load_debt_page(server,browser_page,api):
    from test_preview import login
    page,_=browser_page;login(page,server)
    flows=get(api,'/api/m05/flows',year_month='')['rows']
    source=next((row for row in flows if row['notice_id'] and row['doc_no']),None)
    assert source,'真实副本缺少可定位通知书的付款流水'
    debt_requests=[]
    page.on('request',lambda request:debt_requests.append(request.url) if '/api/m05/ledger?' in request.url else None)
    page.goto(server+'/preview/ledger?notice='+str(source['notice_id']))
    expect(page.locator('#page-title')).to_have_text('付款流水')
    expect(page.locator('.flow-grid').get_by_role('link',name=source['doc_no'],exact=True).first).to_be_visible()
    expect(page.get_by_role('button',name='清除通知书定位',exact=True)).to_be_visible()
    assert not debt_requests
