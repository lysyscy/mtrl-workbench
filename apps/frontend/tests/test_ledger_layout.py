"""Actual ledger content height, totals and normal-month remark identity."""
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import ledger_sample,grid_row,get,money
from test_ledger import open_sample


def test_actual_ledger_layout_tracks_rows_and_totals(server,browser_page,api,projects):
    page,_=browser_page;project,side,row,key=ledger_sample(api,projects);open_sample(page,server,project)
    data=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    for item in data['sides']:
        region=page.get_by_role('region',name=item['label']+'欠款台账',exact=True);expect(region).to_be_visible()
        grid=region.locator('.ledger-grid');box=grid.bounding_box();assert box and 40<box['height']<=500
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
