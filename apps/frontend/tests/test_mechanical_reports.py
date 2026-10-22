"""TAIL-399: real saved/confirmed synthetic reports and production assets."""
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import openpyxl
import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from test_preview import server, browser_page, login
from tools.audit.workspace_paths import output, output_dir

DUPLICATE_NAME = '重复展示名'
REMARK_NAME = '备注同文项目'
REVIEW_WAREHOUSES = ['审查同名甲', '审查同名乙', '审查同文备注']

LONG_NAME = '长名称机械项目用于检查换行冻结列与合计保持可见' * 3

@pytest.fixture(scope='module')
def preview_seed():
    def seed(env):
        from app import models_registry, core_bindings
        from app.mod01_projects.models import Project
        from app.mod06_proc import workbench as work
        core_bindings.register_all()
        engine = create_engine(env['TEST_DATABASE_URL'], connect_args={'options': env['PGOPTIONS']})
        try:
            with Session(engine) as session:
                assert session.execute(text('select current_database(),current_schema()')).one() == ('mtrl_workbench_test', env['PGOPTIONS'].split('search_path=')[1])
                session.add_all([Project(name_full=f'合成机械网格项目{i:03}', disp=LONG_NAME if i == 1 else f'网格样例{i:03}', warehouse_name=f'合成机械仓库{i:03}', ord=i+3) for i in range(1, 91)])
                session.add_all([Project(name_full=wh, warehouse_name=wh, disp=DUPLICATE_NAME if i < 2 else REMARK_NAME, ord=100+i) for i,wh in enumerate(REVIEW_WAREHOUSES)])
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
                        rows=[{'id':f'{category}-{i}', 'device':f'升降审查设备{i}', 'amount':'103', 'rate':'103', 'tax':'3%专', 'qty':'1', 'plan':'1', 'used':'1', 'plate':'合成牌照', 'memo':REMARK_NAME if i==0 else f'审查明细{i}'} for i in range(140 if index==0 else 1)]
                        saved=work.action(session,'details-save',{'warehouse':wh,'ym':'2026-09','category':category,'revision':0,'rows':rows})
                        work.action(session,'amounts-confirm',{'warehouse':wh,'ym':'2026-09','category':category,'revision':saved['revision'],'effective_signature':work.effective(session,wh,'2026-09')['signature']},'399-review-synthetic')
                session.commit()
        finally: engine.dispose()
    return seed


def open_reports(page, server, account='preview-admin'):
    login(page,server,account)
    page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_label('月份',exact=True)).to_have_value('2026-09')


def select_projects(page,names):
    page.get_by_role('button',name='报表项目',exact=True).click()
    menu=page.get_by_role('group',name='导出项目候选',exact=True)
    menu.get_by_role('button',name='清空',exact=True).click()
    for name in names:
        menu.get_by_label('搜索项目',exact=True).fill(name)
        menu.get_by_role('button',name='☐ '+name,exact=True).click()
    page.get_by_role('button',name='报表项目',exact=True).click()
    if names: expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)


def report_url(month='2026-09', warehouses=None):
    from urllib.parse import urlencode
    return '/api/m06/workbench/preview?'+urlencode({'ym':month,'projects':json.dumps(warehouses or ['合成机械仓库001','隔离验收仓库'],ensure_ascii=False)})


def test_grid_freeze_virtualization_scroll_locate_and_ime(server,browser_page):
    page,_=browser_page; open_reports(page,server)
    grid=page.get_by_role('region',name='公司汇总',exact=True)
    expect(grid.locator('.ag-row-pinned')).to_have_count(1)
    output('399-grid-dom.html',kind='logs').write_text(grid.inner_html(),encoding='utf-8')
    page.screenshot(path=str(output('399-grid-before-check.png',kind='screenshots')),full_page=True)
    expect(grid.locator('.ag-grid-scrolling-container .ag-row').first).to_be_visible()
    assert 0 < grid.locator('.ag-grid-scrolling-container .ag-row').count() < 93
    first=grid.locator('.ag-grid-scrolling-container [col-id=c1]').first.bounding_box()
    grid.locator('.ag-body-horizontal-scroll-viewport').evaluate('(e)=>e.scrollLeft=700')
    expect(grid.locator('.ag-grid-scrolling-container [col-id=c1]').first).to_have_css('position','absolute')
    assert abs(grid.locator('.ag-grid-scrolling-container [col-id=c1]').first.bounding_box()['x']-first['x'])<1
    grid.locator('.ag-grid-viewport').evaluate('(e)=>e.scrollTop=e.scrollHeight')
    expect(grid.locator('.ag-grid-scrolling-container')).to_contain_text('网格样例090')
    total_y=grid.locator('.ag-grid-pinned-bottom-rows-container').bounding_box()['y']
    field=page.get_by_label('定位项目',exact=True);field.fill('长名称机械项目')
    field.dispatch_event('keydown',{'key':'Enter','isComposing':True})
    assert grid.locator('.ag-grid-pinned-bottom-rows-container').bounding_box()['y']==total_y
    field.press('Enter')
    expect(grid.locator('.ag-cell-focus[col-id=c1]')).to_contain_text(LONG_NAME)
    assert grid.locator('.ag-cell-focus').bounding_box()['height']>34
    grid.locator('.ag-cell-focus').press('ArrowRight')
    expect(grid.locator('.ag-cell-focus')).to_have_attribute('col-id','c2')
    grid.locator('.ag-cell-focus').press('Tab')
    expect(grid.locator('.ag-cell-focus')).to_have_attribute('col-id','c3')
    assert abs(grid.locator('.ag-grid-pinned-bottom-rows-container').bounding_box()['y']-total_y)<1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output('399-grid-1080.png',kind='screenshots')),full_page=True)


def test_four_real_sheets_file_order_money_formulas_and_snapshot(server,browser_page):
    page,_=browser_page;open_reports(page,server)
    select_projects(page,[LONG_NAME,'隔离项目'])
    preview=page.request.get(server+report_url()).json()
    assert len(preview['sheets'])==4
    page.get_by_role('button',name='四页报送预览',exact=True).click()
    for sheet in preview['sheets']:
        page.get_by_role('button',name=sheet['name'],exact=True).click()
        expect(page.get_by_role('region',name=sheet['name'],exact=True)).to_be_visible()
    annual=page.get_by_role('region',name='年度汇总',exact=True)
    frozen=annual.locator('tbody .mechanical-frozen').first;before_x=frozen.bounding_box()['x']
    annual.evaluate('(e)=>e.scrollLeft=400')
    assert abs(frozen.bounding_box()['x']-before_x)<2
    page.get_by_role('button',name='零租设备月报表',exact=True).click()
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
    for sheet_data,sheet in zip(preview['sheets'],wb):
        for row_no,cells in enumerate(sheet_data['rows'],1):
            for cell in cells:
                actual=sheet.cell(row_no,cell['column']).value;expected=cell['value']
                if isinstance(actual,(int,float,Decimal)): assert Decimal(str(actual))==Decimal(expected)
                else: assert ('' if actual is None else str(actual))==expected
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


@pytest.mark.parametrize(('width','height','account','zoom'),[(1920,1080,'preview-admin',1),(1280,800,'preview-admin',1.25),(800,900,'preview-user',1)])
def test_theme_narrow_scale_and_read_only_boundary(server,browser_page,width,height,account,zoom):
    page,_=browser_page;page.set_viewport_size({'width':width,'height':height});open_reports(page,server,account)
    page.locator('body').evaluate('(e,z)=>e.style.zoom=z',zoom)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.get_by_text('明细编辑、月值确认与取数核对尚未接入。',exact=False)).to_be_visible()
    assert page.get_by_role('button',name='刷新',exact=True).count()==0
    page.get_by_role('button',name='四页报送预览',exact=True).click()
    expect(page.get_by_role('button',name='下载四页Excel',exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output(f'399-{width}-{account}-{zoom}.png',kind='screenshots')),full_page=True)
    page.get_by_role('button',name='返回公司汇总',exact=True).click()
    expect(page.get_by_role('button',name='四页报送预览',exact=True)).to_be_focused()


def test_report_failures_empty_selection_and_stale_response(server,browser_page):
    page,_=browser_page;open_reports(page,server)
    pending=[];page.route('**/api/m06/workbench/preview?**ym=2026-08**',lambda route:pending.append(route))
    page.get_by_label('月份',exact=True).select_option('2026-08')
    expect(page.get_by_text('正在读取机械报表…',exact=True)).to_be_visible();assert pending
    page.get_by_label('月份',exact=True).select_option('2026-09')
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    pending.pop().fulfill(status=500,json={'message':'旧月份失败'})
    expect(page.get_by_text('旧月份失败',exact=True)).to_have_count(0)
    page.unroute('**/api/m06/workbench/preview?**ym=2026-08**')
    page.route('**/api/m06/workbench/preview?**ym=2026-08**',lambda route:route.fulfill(status=200,json={'ok':True,'sheets':[]}))
    page.get_by_label('月份',exact=True).select_option('2026-08')
    expect(page.get_by_role('alert')).to_contain_text('机械报表结果不完整')
    expect(page.get_by_role('button',name='四页报送预览',exact=True)).to_be_disabled()
    page.unroute('**/api/m06/workbench/preview?**ym=2026-08**')
    page.get_by_role('button',name='重新读取',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    select_projects(page,[])
    expect(page.get_by_text('请选择项目查看报表。',exact=True)).to_be_visible()


def test_ledger_draft_blocks_cross_page_export_and_account_pause(server,browser_page):
    page,context=browser_page;login(page,server)
    page.get_by_role('link',name='MOD-05 付款流水与欠款统计',exact=True).click()
    field=page.locator('[row-id="material:manual:1"] [col-id=other_expense] input')
    if not field.count(): field=page.get_by_role('region',name='辅材欠款台账',exact=True).locator('[col-id=other_expense] input').first
    expect(field).to_be_visible();field.fill('非法金额');field.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('金额')
    page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    page.get_by_role('button',name='四页报送预览',exact=True).click()
    expect(page.get_by_role('button',name='下载四页Excel',exact=True)).to_be_disabled()
    expect(page.get_by_role('status').filter(has_text='台账有未保存输入')).to_be_visible()
    page.route('**/api/m15/users',lambda route:route.fulfill(status=500,json={'message':'合成账号读取失败'}))
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('账号暂时无法核实')
    expect(page.get_by_role('heading',name='机械费',exact=True)).to_be_hidden()
    page.unroute('**/api/m15/users');page.get_by_role('button',name='重试',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    context.clear_cookies();page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text('未登录 · 只读',exact=True)).to_be_visible()
    page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    page.get_by_role('button',name='四页报送预览',exact=True).click()
    expect(page.get_by_role('status').filter(has_text='登录后可下载')).to_be_visible()


def test_changed_project_scope_cannot_silently_shrink_export(server,browser_page):
    page,_=browser_page;open_reports(page,server);select_projects(page,[LONG_NAME,'隔离项目'])
    def changed(route):
        response=route.fetch()
        route.fulfill(status=200,json=[project for project in response.json() if project['warehouse_name']!='合成机械仓库001'])
    page.route('**/api/m01/projects?status=all&keyword=',changed)
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('alert')).to_contain_text('所选项目范围已变化')
    expect(page.get_by_role('button',name='四页报送预览',exact=True)).to_be_disabled()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_have_count(0)


@pytest.mark.parametrize('change',['month','account'])
def test_late_report_file_cannot_download_after_scope_or_account_changes(server,browser_page,change):
    page,context=browser_page;open_reports(page,server);select_projects(page,['隔离项目'])
    page.get_by_role('button',name='四页报送预览',exact=True).click()
    pending=[];downloads=[]
    page.on('download',lambda download:downloads.append(download.suggested_filename))
    page.route('**/api/m06/workbench/export?**',lambda route:pending.append(route))
    page.get_by_role('button',name='下载四页Excel',exact=True).click()
    expect(page.get_by_role('button',name='正在生成…',exact=True)).to_be_disabled();assert pending
    route=pending.pop();response=route.fetch();assert response.ok
    if change=='month':
        page.get_by_label('月份',exact=True).select_option('2026-08')
        expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible(timeout=30000)
    else:
        context.clear_cookies();page.evaluate("window.dispatchEvent(new Event('focus'))")
        expect(page.get_by_text('未登录 · 只读',exact=True)).to_be_visible()
    route.fulfill(response=response)
    page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    assert downloads==[]
    expect(page.get_by_text('四页文件已导出。',exact=True)).to_have_count(0)


@pytest.mark.parametrize(('warehouse','body_row'),[('审查同名乙',141),('审查同文备注',143)])
@pytest.mark.parametrize(('column','sheet_name'),[('c9','零租设备月报表'),('c10','包月外租设备月报')])
def test_detail_jump_uses_project_identity_with_duplicate_names_and_same_text_remarks(server,browser_page,warehouse,body_row,column,sheet_name):
    page,_=browser_page;open_reports(page,server)
    page.get_by_role('button',name='报表项目',exact=True).click()
    menu=page.get_by_role('group',name='导出项目候选',exact=True)
    menu.get_by_role('button',name='清空',exact=True).click()
    for _ in range(2): menu.get_by_role('button',name='☐ '+DUPLICATE_NAME,exact=True).first.click()
    menu.get_by_role('button',name='☐ '+REMARK_NAME,exact=True).click()
    page.get_by_role('button',name='报表项目',exact=True).click()
    grid=page.get_by_role('region',name='公司汇总',exact=True);expect(grid).to_be_visible(timeout=30000)
    projects=page.request.get(server+'/api/m01/projects?status=all').json()
    project=next(project for project in projects if project['warehouse_name']==warehouse)
    expect(grid.locator(f'[row-id="{project["id"]}"] [col-id="{column}"] button')).to_be_visible()
    grid.locator(f'[row-id="{project["id"]}"] [col-id="{column}"] button').click()
    preview=page.get_by_role('region',name=sheet_name,exact=True);expect(preview).to_be_visible()
    group=preview.locator('tbody tr').nth(body_row)
    expect(group).to_contain_text(project['disp'])
    expect(group).to_be_in_viewport()
    bounds=group.bounding_box();viewport=preview.bounding_box()
    assert viewport['y'] <= bounds['y'] < viewport['y']+viewport['height'],(bounds,viewport)
    assert preview.locator('thead').evaluate("head=>{const cell=head.querySelector('tr:last-child th');const r=cell.getBoundingClientRect();return head.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}")
    page.screenshot(path=str(output(f'399-review-jump-{column}-{warehouse}.png',kind='screenshots')),full_page=True)


def test_saved_empty_project_list_requires_explicit_selection_on_entry_and_reload(server,browser_page):
    page,_=browser_page;login(page,server)
    state=page.request.get(server+'/api/m06/workbench').json();original=state['settings']
    saved=page.request.post(server+'/api/m06/workbench/settings',data={**original,'shown_projects':[]});assert saved.ok,saved.text()
    reads=[]
    page.on('request',lambda request: reads.append(request.url) if '/api/m06/workbench/preview?' in request.url or '/api/m06/workbench/export?' in request.url else None)
    try:
        page.get_by_role('link',name='MOD-10 机械费',exact=True).click()
        expect(page.get_by_text('请选择项目查看报表。',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_role('button',name='报表项目',exact=True)).to_contain_text('已选 0 个项目')
        expect(page.get_by_role('button',name='四页报送预览',exact=True)).to_be_disabled()
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
