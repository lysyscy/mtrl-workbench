"""Independent real project scopes and actual ledger workbook download."""
import openpyxl
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import ledger_sample
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
