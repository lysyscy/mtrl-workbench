"""Real four-sheet report, snapshot and stable project jump; no synthetic projects."""
import json
import re
from decimal import Decimal
from urllib.parse import parse_qs,urlparse
import openpyxl
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page,grid_row


def test_actual_company_summary_and_four_sheet_snapshot_download(server,browser_page,api,projects,disposable,tmp_path):
    page,_=browser_page;state=get(api,'/api/m06/workbench');assert state['projects']
    project=next(p for p in projects if p['project_type']=='normal' and p['status']=='active' and p['warehouse_name'] in [v['warehouse'] for v in state['projects']])
    open_page(page,server,'mechanical','机械费')
    page.get_by_role('button',name='显示项目',exact=True).click();dialog=page.get_by_role('dialog',name='选择显示项目及顺序',exact=True)
    dialog.get_by_role('button',name='全不选',exact=True).click();dialog.get_by_role('checkbox',name=project['disp'],exact=True).check();dialog.get_by_role('button',name='应用项目选择',exact=True).click()
    expect(page.get_by_role('region',name='公司汇总',exact=True)).to_be_visible()
    page.get_by_role('button',name='导出预览',exact=True).click();dialog=page.get_by_role('dialog',name='选择本次报送项目',exact=True);dialog.get_by_role('button',name='全不选',exact=True).click();dialog.get_by_role('checkbox',name=project['disp'],exact=True).check()
    ym=page.get_by_label('月份',exact=True).input_value()
    preview=get(api,'/api/m06/workbench/preview',ym=ym,projects=json.dumps([project['warehouse_name']],ensure_ascii=False))
    dialog.get_by_role('button',name='生成报送预览',exact=True).click()
    download=page.get_by_role('button',name='下载四页Excel',exact=True);expect(download).to_be_enabled(timeout=30000)
    requests=[];page.on('request',lambda request:requests.append(request.url) if '/workbench/export?' in request.url else None)
    with page.expect_download() as event:download.click()
    path=tmp_path/'mechanical.xlsx';event.value.save_as(path)
    params=parse_qs(urlparse(requests[-1]).query);assert params['snapshot_token']==[preview['snapshot_token']] and json.loads(params['projects'][0])==[project['warehouse_name']]
    workbook=openpyxl.load_workbook(path,data_only=True);assert workbook.sheetnames==[sheet['name'] for sheet in preview['sheets']];assert len(workbook.sheetnames)==4
    assert all(sheet.print_area and sheet.print_title_rows for sheet in workbook)
    sheet=preview['sheets'][0];position=next(item['row'] for item in sheet['project_rows'] if item['warehouse']==project['warehouse_name'])
    assert workbook.worksheets[0].cell(position,2).value==project['disp']
    checked=0
    for cell in sheet['rows'][position-1]:
        if cell['column']>=4 and re.fullmatch(r'-?\d+(?:\.\d+)?',cell['value']):
            assert Decimal(str(workbook.worksheets[0].cell(position,cell['column']).value))==Decimal(cell['value']);checked+=1
    assert checked,'真实报送项目没有金额格，API到文件金额未覆盖'
    workbook.close()


def test_actual_company_summary_layout_and_amounts_readonly(server,browser_page,api,projects):
    page,_=browser_page;page.set_viewport_size({'width':2400,'height':1200})
    open_page(page,server,'mechanical','机械费');grid=page.get_by_role('region',name='公司汇总',exact=True)
    expect(grid).to_be_visible();ym=page.get_by_label('月份',exact=True).input_value()
    state=get(api,'/api/m06/workbench',ym=ym);warehouses=state['settings']['shown_projects'];assert warehouses
    preview=get(api,'/api/m06/workbench/preview',ym=ym,projects=json.dumps(warehouses,ensure_ascii=False))
    count=len(preview['sheets'][0]['project_rows']);assert count
    page.wait_for_function("""count=>{const g=document.querySelector('.mechanical-grid');const last=g?.querySelector('[row-index="'+(count-1)+'"]');const total=g?.querySelector('.ag-row-pinned');return last&&total&&Math.abs(total.getBoundingClientRect().top-last.getBoundingClientRect().bottom)<2;}""",arg=count)
    scale=page.evaluate("Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))")
    assert grid.locator('.ag-header-cell[col-id="c1"]').bounding_box()['width']<=200*scale+1
    assert grid.locator('.ag-header-cell[col-id="c14"]').bounding_box()['width']<=144*scale+1
    project=next(p for p in projects if p['warehouse_name']==warehouses[0])
    position=next(item['row'] for item in preview['sheets'][0]['project_rows'] if item['warehouse']==warehouses[0])
    row=grid_row(page,'.mechanical-grid',project['id'])
    for dom,cells in [(row,preview['sheets'][0]['rows'][position-1]),(grid.locator('.ag-row-pinned'),preview['sheets'][0]['rows'][-1])]:
        values={cell['column']-1:cell['value'] for cell in cells}
        for column in [4,5,7,8,9,10,12,13]:
            expected=values[column].replace(',','');cell=dom.locator('[col-id="c'+str(column)+'"]')
            actual=(cell.locator('input').input_value() if cell.locator('input').count() else cell.inner_text()).replace(',','')
            if re.fullmatch(r'-?\d+(?:\.\d+)?',expected):assert Decimal(actual)==Decimal(expected)
            else:assert actual=='—'
    page.set_viewport_size({'width':2400,'height':500})
    page.wait_for_function("document.querySelector('.mechanical-grid').getBoundingClientRect().height<340")
    header=grid.locator('.ag-header').bounding_box();grid.locator('[row-index="'+str(count-1)+'"]').scroll_into_view_if_needed()
    assert abs(grid.locator('.ag-header').bounding_box()['y']-header['y'])<1
