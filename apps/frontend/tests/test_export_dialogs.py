"""Independent real project scopes and actual ledger workbook download."""
import openpyxl
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get, ledger_sample, open_page
from test_ledger import open_sample


def test_real_ledger_export_scope_is_independent_and_downloads(server,browser_page,api,projects,tmp_path):
    page,_=browser_page;project,_,_,_=ledger_sample(api,projects);open_sample(page,server,project)
    page.get_by_role('button',name='逐月台账导出…',exact=True).click();dialog=page.locator('.ledger-export-dialog')
    expect(dialog).to_be_visible();dialog.get_by_role('button',name='全不选',exact=True).click();dialog.get_by_role('checkbox',name=project['disp'],exact=True).check()
    with page.expect_request(lambda request:'/api/m05/ledger/export?' in request.url) as requested,page.expect_download() as event:
        dialog.get_by_role('button',name='保存到本地',exact=True).click()
    params=parse_qs(urlparse(requested.value.url).query);assert params['projects']==[project['warehouse_name']]
    path=tmp_path/'ledger.xlsx';event.value.save_as(path);workbook=openpyxl.load_workbook(path,data_only=True);assert set(workbook.sheetnames)=={'辅材','机械','特殊费用月报表'}
    assert workbook['辅材']['A1'].value==project['disp']+'辅材欠款'
    assert workbook['特殊费用月报表']['A1'].value==project['disp']+'费用汇总表'
    workbook.close()
    page.get_by_role('button',name='总欠款汇总导出…',exact=True).click();dialog=page.locator('.ledger-export-dialog')
    dialog.get_by_role('button',name='全不选',exact=True).click();expect(dialog.get_by_role('button',name='保存到本地',exact=True)).to_be_disabled();dialog.get_by_role('button',name='关闭',exact=True).click()
    page.get_by_role('button',name='逐月台账导出…',exact=True).click();expect(dialog.get_by_role('checkbox',name=project['disp'],exact=True)).to_be_checked()
    dialog.get_by_role('button',name='关闭',exact=True).click()


def test_notice_excel_downloads_the_filtered_rows_with_one_click(server,browser_page,api,tmp_path):
    page,_=browser_page
    rows=get(api,'/api/m03/notice-list',period='')['items']
    row=next(r for r in rows if r['bill_no'].startswith('FKTZS') and not r['is_excluded'] and not r['is_revoked']
             and r['pay_status']=='未付清' and sum(other['bill_no']==r['bill_no'] for other in rows)==1)
    open_page(page,server,'notices','付款通知书')
    page.get_by_label('通知书搜索',exact=True).fill(row['bill_no'])
    expect(page.get_by_label(f"勾选{row['bill_no']}",exact=True)).to_be_visible()
    with page.expect_request('**/api/m03/notices/export') as request,page.expect_download() as download:
        page.get_by_role('button',name='导出 Excel',exact=True).click()
    assert request.value.post_data_json == {'ids': [row['notice_id']]}
    expect(page.get_by_role('dialog')).to_have_count(0)
    path=tmp_path/'notices.xlsx'
    download.value.save_as(path)
    workbook=openpyxl.load_workbook(path,read_only=True,data_only=True)
    try:
        assert any(cell == row['bill_no'] for cells in workbook.active.values for cell in cells)
    finally:
        workbook.close()
