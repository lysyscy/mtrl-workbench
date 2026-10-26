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
