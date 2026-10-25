"""TAIL-399: real saved/confirmed synthetic reports and production assets."""
import re
from decimal import Decimal
import json
from urllib.parse import parse_qs, urlparse
import openpyxl
import pytest
from playwright.sync_api import expect
from sqlalchemy import select
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output, output_dir

DUPLICATE_NAME = '重复展示名'
REVIEW_WAREHOUSES = ['审查同名甲', '审查同名乙']

LONG_NAME = '长名称机械项目用于检查换行冻结列与合计保持可见' * 3

@pytest.fixture(scope='module')
def preview_seed(make_preview_seed, preview_session):
    def seed(env):
        from app import models_registry, core_bindings
        from app.mod01_projects.models import Project
        from app.mod06_proc import workbench as work
        core_bindings.register_all()
        with preview_session(env) as session:
            session.add_all([Project(name_full=f'合成机械网格项目{i:03}', disp=LONG_NAME if i == 1 else f'网格样例{i:03}', warehouse_name=f'合成机械仓库{i:03}', ord=i+3) for i in range(1, 91)])
            session.add_all([Project(name_full=wh, warehouse_name=wh, disp=DUPLICATE_NAME, ord=100+i) for i,wh in enumerate(REVIEW_WAREHOUSES)])
            session.commit()
            initial = [p.warehouse_name for p in session.scalars(select(Project).order_by(Project.ord,Project.id)) if p.warehouse_name and p.warehouse_name not in REVIEW_WAREHOUSES]
            work.action(session,'settings',{'revision':0,'shown_projects':initial})
            for wh, zero_count, monthly_count in [('隔离验收仓库',160,3),('合成机械仓库001',2,1)]:
                for month in ['2026-08','2026-09']:
                    for category, count in [('zero',zero_count),('monthly',monthly_count)]:
                        count = count if month == '2026-09' else 1
                        amount = ('103' if wh == '隔离验收仓库' else '51.5') if category == 'zero' else ('206' if wh == '隔离验收仓库' else '309')
                        rows = [{'id':f'{category}-{i}', 'device':f'升降设备{i+1:03}', 'spec':'长规格说明' * 5, 'unit':'台班', 'qty':'2小时', 'plan':'30', 'used':'28', 'rate':amount, 'amount':amount, 'tax':'3%专', 'date':'8.21至月底', 'plate':'合成牌照', 'memo':'中文备注\n分行核对' if i == 0 else f'明细{i+1:03}'} for i in range(count)]
                        saved=work.action(session,'details-save',{'warehouse':wh,'ym':month,'category':category,'revision':0,'rows':rows})
                        work.action(session,'amounts-confirm',{'warehouse':wh,'ym':month,'category':category,'revision':saved['revision'],'effective_signature':work.effective(session,wh,month)['signature']},'399-synthetic')
            for index,wh in enumerate(REVIEW_WAREHOUSES):
                for category in ['zero','monthly']:
                    rows=[{'id':f'{category}-{i}', 'device':f'升降审查设备{i}', 'amount':'103', 'rate':'103', 'tax':'3%专', 'qty':'1', 'plan':'1', 'used':'1', 'plate':'合成牌照', 'memo':f'审查明细{i}'} for i in range(140 if index==0 else 1)]
                    saved=work.action(session,'details-save',{'warehouse':wh,'ym':'2026-09','category':category,'revision':0,'rows':rows})
                    work.action(session,'amounts-confirm',{'warehouse':wh,'ym':'2026-09','category':category,'revision':saved['revision'],'effective_signature':work.effective(session,wh,'2026-09')['signature']},'399-review-synthetic')
            session.commit()
    return make_preview_seed(seed)


def open_reports(page, server, account='preview-admin'):
    login(page,server,account)
    page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_label('月份',exact=True)).to_have_value('2026-09')


def select_projects(page, names):
    page.get_by_role('button', name='显示项目', exact=True).click()
    dialog = page.get_by_role('dialog', name='选择显示项目及顺序', exact=True)
    dialog.get_by_role('button', name='全不选', exact=True).click()
    for name in names:
        dialog.get_by_role('checkbox', name=name, exact=True).check()
    for name in reversed(names):
        row = dialog.locator('li').filter(has=page.get_by_role('checkbox', name=name, exact=True))
        up = row.get_by_role('button', name='上移', exact=True)
        while up.is_enabled(): up.click()
    dialog.get_by_role('button', name='应用项目选择', exact=True).click()
    expect(dialog).to_have_count(0)
    if names: expect(page.get_by_role('region', name='公司汇总', exact=True)).to_be_visible(timeout=30000)


def export_preview(page):
    page.get_by_role('button', name='导出预览', exact=True).click()
    dialog = page.get_by_role('dialog', name='选择本次报送项目', exact=True)
    dialog.get_by_role('button', name='生成报送预览', exact=True).click()
    expect(page.get_by_role('button', name='下载四页Excel', exact=True)).to_be_enabled(timeout=30000)


def set_month(page, value):
    field = page.get_by_label('月份', exact=True)
    field.fill(value); field.press('Enter')
    expect(field).to_have_value(value)


def report_url(month='2026-09', warehouses=None):
    from urllib.parse import urlencode
    return '/api/m06/workbench/preview?'+urlencode({'ym':month,'projects':json.dumps(warehouses or ['合成机械仓库001','隔离验收仓库'],ensure_ascii=False)})


def test_grid_freeze_virtualization_scroll_and_keyboard(server, browser_page):
    page, _ = browser_page
    open_reports(page, server)
    grid = page.get_by_role('region', name='公司汇总', exact=True)
    expect(grid.locator('.ag-row-pinned')).to_have_count(1)
    rows = grid.locator('.ag-grid-scrolling-container .ag-row')
    expect(rows.first).to_be_visible()
    assert 0 < rows.count() < 93
    frozen = grid.locator('.ag-grid-scrolling-container [col-id=c1]').first
    before_x = frozen.bounding_box()['x']
    grid.locator('.ag-body-horizontal-scroll-viewport').evaluate('(e)=>e.scrollLeft=700')
    assert abs(frozen.bounding_box()['x'] - before_x) < 1
    grid.locator('.ag-grid-viewport').evaluate('(e)=>e.scrollTop=e.scrollHeight')
    last = rows.filter(has_text='网格样例090').locator('[col-id=c1]')
    expect(last).to_be_visible()
    last.click()
    last.press('ArrowRight')
    expect(grid.locator('.ag-cell-focus')).to_have_attribute('col-id', 'c2')
    grid.locator('.ag-cell-focus').press('Tab')
    expect(grid.locator('.ag-cell-focus')).to_have_attribute('col-id', 'c3')
    expect(grid.locator('.ag-row-pinned')).to_be_visible()


def test_four_real_sheets_file_order_money_formulas_and_snapshot(server,browser_page):
    page,_=browser_page;open_reports(page,server)
    select_projects(page,[LONG_NAME,'隔离项目'])
    preview=page.request.get(server+report_url()).json()
    assert len(preview['sheets'])==4
    export_preview(page)
    for sheet in preview['sheets']:
        expect(page.get_by_role('region',name=sheet['name'],exact=True)).to_be_visible()
    annual=page.get_by_role('region',name='年度汇总',exact=True)
    frozen=annual.locator('tbody .mechanical-frozen').first;before_x=frozen.bounding_box()['x']
    annual.evaluate('(e)=>e.scrollLeft=400')
    assert abs(frozen.bounding_box()['x']-before_x)<2
    expect(page.get_by_role('region',name='零租设备月报表',exact=True)).to_contain_text('明细160')
    page.screenshot(path=str(output('399-four-page-preview.png',kind='screenshots')),full_page=True)
    requests=[];page.on('request',lambda request:requests.append(request.url) if '/workbench/export?' in request.url else None)
    with page.expect_download() as event: page.get_by_role('button',name='下载四页Excel',exact=True).click()
    downloaded=event.value;path=output(downloaded.suggested_filename,kind='exports');downloaded.save_as(path)
    before=path.read_bytes();params=parse_qs(urlparse(requests[-1]).query)
    assert json.loads(params['projects'][0])==['合成机械仓库001','隔离验收仓库']
    assert params['snapshot_token']==[preview['snapshot_token']]
    assert list(output_dir('exports').glob('机械费报表-*.xlsx')), 'actual server file must use this run shared export root'
    wb=openpyxl.load_workbook(path,data_only=True);formulas=openpyxl.load_workbook(path,data_only=False)
    assert wb.sheetnames==[sheet['name'] for sheet in preview['sheets']]
    assert [wb.worksheets[0][f'B{i}'].value for i in (6,7)]==[LONG_NAME,'隔离项目']
    assert [Decimal(str(wb.worksheets[0][f'J{i}'].value)) for i in (6,7)]==[Decimal('103'),Decimal('16480')]
    assert wb.worksheets[0]['J8'].value==16583
    assert wb.worksheets[1]['J6'].value=='8.21至月底'
    assert wb.worksheets[2]['M6'].value=='中文备注\n分行核对'
    assert wb.worksheets[2]['O4'].value=='不含税价'
    assert str(wb.worksheets[1].freeze_panes)=='C5'
    assert all(sheet.print_area and sheet.print_title_rows for sheet in wb)
    assert 'E4:I4' in str(wb.worksheets[0].merged_cells)
    assert sum(cell.data_type=='f' for sheet in formulas for row in sheet for cell in row)>20
    wb.close();formulas.close()
    # Saved detail changes without confirming a new effective value: old token must refuse.
    state=page.request.get(server+'/api/m06/workbench?ym=2026-09').json()
    detail=next(d for d in state['details'] if d['warehouse']=='合成机械仓库001' and d['ym']=='2026-09' and d['category']=='zero')
    detail['rows'][0]['memo']='已保存修订，不改变旧文件'
    response=page.request.post(server+'/api/m06/workbench/details-save',data=detail); assert response.ok,response.text()
    page.get_by_role('button',name='下载四页Excel',exact=True).click()
    expect(page.get_by_role('status').filter(has_text='预览后已保存内容有变化')).to_be_visible()
    assert path.read_bytes()==before
    page.get_by_role('button',name='重新预览',exact=True).click()
    expect(page.get_by_role('button',name='下载四页Excel',exact=True)).to_be_enabled(timeout=30000)
    with page.expect_download() as event: page.get_by_role('button',name='下载四页Excel',exact=True).click()
    second=output(event.value.suggested_filename,kind='exports');event.value.save_as(second)
    assert second!=path and path.read_bytes()==before


def test_report_failures_empty_selection_and_stale_response(server,browser_page):
    page,_=browser_page;open_reports(page,server)
    pending=[];page.route('**/api/m06/workbench/preview?**ym=2026-08**',lambda route:pending.append(route))
    with page.expect_request('**/api/m06/workbench/preview?**ym=2026-08**'):
        set_month(page, '2026-08')
    expect(page.get_by_text('正在读取机械报表…',exact=True)).to_be_visible();assert pending
    set_month(page, '2026-09')
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    pending.pop().fulfill(status=500,json={'message':'旧月份失败'})
    expect(page.get_by_text('旧月份失败',exact=True)).to_have_count(0)
    page.unroute('**/api/m06/workbench/preview?**ym=2026-08**')
    page.route('**/api/m06/workbench/preview?**ym=2026-08**',lambda route:route.fulfill(status=200,json={'ok':True,'sheets':[]}))
    set_month(page, '2026-08')
    expect(page.get_by_role('alert')).to_contain_text('机械报表结果不完整')
    expect(page.get_by_role('button',name='下载四页Excel',exact=True)).to_have_count(0)
    page.unroute('**/api/m06/workbench/preview?**ym=2026-08**')
    page.get_by_role('button',name='重新读取',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    select_projects(page,[])
    expect(page.get_by_text('请选择项目查看报表。',exact=True)).to_be_visible()


def test_detail_jump_uses_project_identity_with_duplicate_names(server, browser_page):
    page, _ = browser_page; login(page, server)
    page.get_by_role('link', name='MOD-10 机械费', exact=True).click()
    page.get_by_role('button', name='显示项目', exact=True).click()
    dialog = page.get_by_role('dialog', name='选择显示项目及顺序', exact=True)
    dialog.get_by_role('button', name='全不选', exact=True).click()
    for index in range(2): dialog.get_by_role('checkbox', name=DUPLICATE_NAME, exact=True).nth(index).check()
    dialog.get_by_role('button', name='应用项目选择', exact=True).click()
    grid = page.get_by_role('region', name='公司汇总', exact=True)
    expect(grid).to_be_visible(timeout=30000)
    projects = page.request.get(server+'/api/m01/projects?status=all').json()
    project = next(project for project in projects if project['warehouse_name']=='审查同名乙')
    grid.locator(f'[row-id="{project["id"]}"] [col-id="c9"] button').click()
    detail = page.get_by_role('region', name='零租明细', exact=True)
    expect(detail).to_be_visible()
    # Same display name: the second project's one row must not become the first project's 140 rows.
    expect(detail.locator('.mechanical-detail-group-row')).to_have_count(1)
    expect(detail.locator('.mechanical-detail-group-row')).to_contain_text('1条')
    expect(detail.locator('tbody tr')).to_have_count(2)
    page.get_by_role('button', name='取消筛选', exact=True).click()
    expect(detail.locator('.mechanical-detail-group-row')).to_have_count(2)
    expect(detail.locator('tbody tr')).to_have_count(143)
    page.screenshot(path=str(output('399-review-jump-same-name.png', kind='screenshots')), full_page=True)


def test_saved_empty_project_list_requires_explicit_selection_on_entry_and_reload(server,browser_page):
    page,_=browser_page;login(page,server)
    state=page.request.get(server+'/api/m06/workbench').json();original=state['settings']
    saved=page.request.post(server+'/api/m06/workbench/settings',data={**original,'shown_projects':[]});assert saved.ok,saved.text()
    reads=[]
    page.on('request',lambda request: reads.append(request.url) if '/api/m06/workbench/preview?' in request.url or '/api/m06/workbench/export?' in request.url else None)
    try:
        page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
        expect(page.get_by_text('请选择项目查看报表。',exact=True)).to_be_visible(timeout=30000)
        page.get_by_role('button', name='导出预览', exact=True).click()
        dialog = page.get_by_role('dialog', name='选择本次报送项目', exact=True)
        expect(dialog).to_contain_text('已选 0 个项目')
        expect(dialog.get_by_role('button', name='生成报送预览', exact=True)).to_be_disabled()
        dialog.get_by_role('button', name='取消', exact=True).click()
        expect(page.get_by_role('button',name='下载四页Excel',exact=True)).to_have_count(0)
        assert reads==[]
        page.screenshot(path=str(output('399-review-empty-saved-scope.png',kind='screenshots')),full_page=True)
        page.reload()
        expect(page.get_by_text('请选择项目查看报表。',exact=True)).to_be_visible(timeout=30000)
        assert reads==[]
        select_projects(page,['隔离项目'])
        assert reads and all(json.loads(parse_qs(urlparse(url).query)['projects'][0])==['隔离验收仓库'] for url in reads)
    finally:
        current=page.request.get(server+'/api/m06/workbench').json()['settings']
        response=page.request.post(server+'/api/m06/workbench/settings',data={**original,'revision':current['revision']});assert response.ok,response.text()


@pytest.mark.parametrize('state', ['draft', 'unknown'])
def test_ledger_cross_page_guard_blocks_mechanical_download(server, browser_page, state):
    from preview_select import pick_option
    page, _ = browser_page
    open_reports(page, server)
    export_preview(page)
    page.get_by_role('link', name='MOD-05 付款流水与欠款统计', exact=True).click()
    pick_option(page, '选择项目', '隔离项目')
    row = page.get_by_role('region', name='辅材欠款台账', exact=True).locator('[row-id]').filter(
        has=page.locator('input[value="合成历史行甲"]'))
    field = row.locator('[col-id="other_expense"] input')
    if state == 'unknown':
        # This is the UI's unknown-response branch; committed-then-unknown is covered separately.
        page.route('**/api/m05/history/save', lambda route: route.fulfill(status=502, json={'message':'定向未知回执'}))
        field.fill('98.76')
        field.press('Tab')
        expect(page.get_by_role('status', name='保存回执')).to_contain_text('待核实')
        reason = '台账操作结果待核实'
    else:
        field.fill('未保存输入')
        field.press('Tab')
        reason = '台账有未保存输入'
    page.get_by_role('link', name='MOD-10 机械费', exact=True).click()
    page.get_by_role('button', name='导出预览', exact=True).click()
    dialog = page.get_by_role('dialog', name='选择本次报送项目', exact=True)
    dialog.get_by_role('button', name='生成报送预览', exact=True).click()
    download = page.get_by_role('button', name='下载四页Excel', exact=True)
    expect(download).to_be_disabled()
    expect(download).to_have_attribute('title', re.compile(reason))
    page.get_by_role('link', name='MOD-05 付款流水与欠款统计', exact=True).click()
    expect(field).to_have_value('98.76' if state == 'unknown' else '未保存输入')
