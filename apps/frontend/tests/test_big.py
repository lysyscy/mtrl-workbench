"""Real monthly rows, stable edit width and per-month selection/export writes."""
from decimal import Decimal
import openpyxl
from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,grid_row,money,open_page


def choose_month(page,ym):
    picker=page.get_by_label('大表核算月',exact=True)
    picker.fill(ym);picker.press('Enter')
    expect(picker).to_have_value(ym)
    page.wait_for_load_state('networkidle')


def test_real_month_rows_and_totals_match_api(server,browser_page,api):
    page,_=browser_page
    data=get(api,'/api/m07/big')
    assert data['rows'],'真实副本没有大表项目，显示代表未覆盖'
    page.add_init_script("""window.__bigFirstRows=[];function sample(){
      const grid=document.querySelector('.big-month:not([hidden]) .big-grid');
      if(grid?.checkVisibility({checkVisibilityCSS:true})&&!grid.inert&&!grid.closest('.page-view')?.inert&&window.__bigFirstRows.length<30){
        const ids=[...new Set([...grid.querySelectorAll('.ag-row[row-id]')].map(row=>row.getAttribute('row-id')))];
        if(ids.length)window.__bigFirstRows.push(ids);
      }window.__bigRowFrame=requestAnimationFrame(sample);
    }requestAnimationFrame(sample);""")
    open_page(page,server,'big','月度会大表')
    choose_month(page,data['month'])
    row=data['rows'][0]
    dom=grid_row(page,'.big-month:not([hidden]) .big-grid',row['warehouse'])
    expect(dom.locator('[col-id="display"]')).to_have_text(row['display'])
    expected='—' if row['auto']['hw_cum'] is None else money(row['auto']['hw_cum'])
    expect(dom.locator('[col-id="hw_cum"]')).to_have_text(expected)
    expect(page.get_by_label('定位大表项目',exact=True)).to_have_count(0)
    assert page.locator('.big-month:not([hidden]) .ag-cell[col-id="hw_cum"]').evaluate_all('cells=>cells.every(c=>c.scrollWidth<=c.clientWidth+1)')
    page.wait_for_function('window.__bigFirstRows.length>=30')
    samples=page.evaluate('window.__bigFirstRows')
    page.evaluate('cancelAnimationFrame(window.__bigRowFrame)')
    expected={r['warehouse'] for r in data['rows']}|{'__total'}
    assert all(set(ids)==expected for ids in samples),samples


def test_real_month_cell_focus_width_and_save_identity(server,browser_page,api,disposable):
    page,_=browser_page
    data=get(api,'/api/m07/big');row=data['rows'][0]
    open_page(page,server,'big','月度会大表');choose_month(page,data['month'])
    grid=page.locator('.big-month:not([hidden]) .big-grid')
    grid.locator('.ag-body-horizontal-scroll-viewport').evaluate('e=>e.scrollLeft=e.scrollWidth')
    field=grid_row(page,'.big-month:not([hidden]) .big-grid',row['warehouse']).locator('[col-id="oil"] input')
    expect(field).to_be_visible()
    widths=lambda:grid.locator('.ag-header-cell').evaluate_all('cells=>cells.map(c=>[c.getAttribute("col-id"),c.getBoundingClientRect().width])')
    before=widths();field.click();assert widths()==before
    value=Decimal(row['manual']['oil']['value'] or '0')+Decimal('1.25')
    field.fill(str(value));assert widths()==before;page.get_by_role('heading',name='月度会大表',exact=True).click()
    expect(page.locator('.big-month:not([hidden]) .big-feedback')).to_contain_text('已保存到本月')
    fresh=get(api,'/api/m07/big',period=data['month'])
    assert Decimal(next(r for r in fresh['rows'] if r['warehouse']==row['warehouse'])['manual']['oil']['value'])==value


def test_real_selection_freezes_by_month_and_post_export(server,browser_page,api,disposable,tmp_path):
    page,_=browser_page
    baseline=get(api,'/api/m07/big');month=baseline['month']
    year,number=map(int,month.split('-'))
    def following(offset):
        y,m=divmod(year*12+number-1+offset,12);return f'{y:04d}-{m+1:02d}'
    pair=next(((following(n),following(n+1)) for n in range(1,25)
               if not get(api,'/api/m07/big',period=following(n))['selection']['fixed']
               and not get(api,'/api/m07/big',period=following(n+1))['selection']['fixed']),None)
    assert pair,'真实副本最近24个月均已固定，继承到首次固定场景未覆盖'
    first,second=pair
    original=get(api,'/api/m07/big',period=month)['selected']
    open_page(page,server,'big','月度会大表');choose_month(page,first)
    page.get_by_role('button',name='选择项目与排序…',exact=True).click()
    dialog=page.locator('.big-order-dialog')
    dialog.get_by_role('button',name='保存项目与顺序',exact=True).click()
    expect(dialog).not_to_be_visible()
    fixed=get(api,'/api/m07/big',period=first)
    assert fixed['selection']=={'fixed':True,'source':first}
    choose_month(page,second)
    inherited=get(api,'/api/m07/big',period=second)
    assert inherited['selected']==fixed['selected']
    page.get_by_role('button',name='导出文件…',exact=True).click()
    with page.expect_request(lambda r:'/api/m07/big/export?' in r.url and r.method=='POST'):
        with page.expect_download() as event:
            page.locator('.settlement-export-dialog').get_by_role('button',name='保存到本地',exact=True).click()
    path=tmp_path/'big.xlsx';event.value.save_as(path)
    workbook=openpyxl.load_workbook(path,data_only=True);assert workbook.sheetnames;workbook.close()
    assert get(api,'/api/m07/big',period=second)['selection']=={'fixed':True,'source':second}
    assert get(api,'/api/m07/big',period=month)['selected']==original


def test_real_post_export_pause_and_lost_response_lock_until_readback(server,browser_page,api,disposable):
    page,_=browser_page;base=get(api,'/api/m07/big');row=base['rows'][0]
    value=Decimal(row['manual']['oil']['value'] or '0')+Decimal('1.25')
    assert api.post('/api/m07/big/cell',json={'month':base['month'],'warehouse':row['warehouse'],'key':'oil','raw':str(value)}).json()['ok']
    year,month=map(int,base['month'].split('-'))
    candidates=[]
    for offset in range(1,25):
        y,m=divmod(year*12+month-1+offset,12);ym=f'{y:04d}-{m+1:02d}'
        if not get(api,'/api/m07/big',period=ym)['selection']['fixed']:candidates.append(ym);break
    assert candidates,'真实副本最近24个月均固定，首次导出未知状态未覆盖'
    ym=candidates[0];open_page(page,server,'big','月度会大表');choose_month(page,ym)
    pending=[];downloads=[];history=[];export_url='**/api/m07/big/export?period='+ym;read_url='**/api/m07/big?period='+ym
    page.route(export_url,lambda route:pending.append(route));page.route(read_url,lambda route:route.abort('failed'))
    page.on('download',lambda download:downloads.append(download));page.on('request',lambda request:history.append(request) if request.url.endswith('/api/history/undo') else None)
    page.get_by_role('button',name='导出文件…',exact=True).click();page.locator('.settlement-export-dialog').get_by_role('button',name='保存到本地',exact=True).click();assert len(pending)==1
    page.evaluate("document.querySelector('a[href=\"/preview/projects\"]').click()")
    expect(page.locator('#page-title')).to_have_text('项目档案');page.get_by_role('button',name='撤销',exact=True).click();assert not history
    expect(page.locator('.history-tools')).to_contain_text('正在导出')
    route=pending.pop();response=route.fetch();assert response.status==200;route.abort('failed')
    assert get(api,'/api/m07/big',period=ym)['selection']=={'fixed':True,'source':ym}
    page.get_by_role('link',name='月度会大表',exact=True).click();scope=page.locator('.big-month:not([hidden])')
    expect(scope.get_by_role('alert').first).to_contain_text('待核实');expect(scope.get_by_role('button',name='选择项目与排序…',exact=True)).to_be_disabled();assert not downloads
    page.unroute(export_url);page.unroute(read_url);scope.get_by_role('button',name='重读核对',exact=True).click();expect(scope.get_by_role('button',name='已核对，继续',exact=True)).to_be_enabled();scope.get_by_role('button',name='已核对，继续',exact=True).click()
    expect(scope.get_by_role('button',name='选择项目与排序…',exact=True)).to_be_enabled();assert not history and not downloads
