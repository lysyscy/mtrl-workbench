"""A: independent export dialogs against synthetic schema and real files."""
import re
from urllib.parse import quote_plus
import openpyxl
from playwright.sync_api import expect
from test_preview import server, browser_page
from test_ledger import open_ledger
from tools.audit.workspace_paths import output, output_dir


def test_two_independent_dialogs_preserve_scope_and_real_debt_file(server, browser_page):
    page, _ = browser_page
    open_ledger(page, server)
    page.get_by_role('button', name='逐月台账导出…', exact=True).click()
    dialog = page.get_by_role('dialog', name='逐月台账导出', exact=True)
    expect(dialog).to_be_visible()
    dialog.get_by_role('button', name='取消', exact=True).click()
    page.get_by_role('button', name='总欠款汇总导出…', exact=True).click()
    dialog = page.get_by_role('dialog', name='总欠款汇总导出', exact=True)
    expect(dialog).to_be_visible()
    expect(page.locator('dialog[open]')).to_have_count(1)
    dialog.get_by_role('button', name='清空', exact=True).click()
    expect(dialog.get_by_role('button', name='确认清单', exact=True)).to_be_disabled()
    for name in ['长项目名验收', '隔离项目']:
        dialog.get_by_role('button', name=re.compile('^☐ '+name)).click()
    dialog.get_by_role('button', name='确认清单', exact=True).click()
    expect(dialog.get_by_role('row')).to_have_count(3)
    assert dialog.locator('tbody tr td:nth-child(2)').all_text_contents() == ['长项目名验收','隔离项目']
    requests=[]
    page.on('request', lambda request: requests.append(request.url) if '/api/m05/debt/export?' in request.url else None)
    with page.expect_download() as event:
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
    download=event.value
    path=output(download.suggested_filename,kind='exports');download.save_as(path)
    assert 'projects='+quote_plus('长名称验收仓库,隔离验收仓库') in requests[-1]
    workbook=openpyxl.load_workbook(path,data_only=True)
    rows=list(workbook.active.values);workbook.close()
    assert rows[0] == ('序号','项目','集采','辅材','机械')
    assert [row[1] for row in rows[1:3]] == ['长项目名验收','隔离项目']
    assert rows[1][2:5] == (0,270,0)
    assert rows[2][2:5] == (0,1890,-75)
    assert list(output_dir('exports').glob('总欠款/*.xlsx')), 'server file must use this run export root'
    expect(page.get_by_role('button',name='总欠款汇总导出…',exact=True)).to_be_focused()
    page.get_by_role('button',name='逐月台账导出…',exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('button',name=re.compile('^☑ 隔离项目'))).to_be_visible()
    expect(page.get_by_role('dialog').get_by_role('button',name=re.compile('^☐ 长项目名验收'))).to_be_visible()


def test_export_errors_stay_in_dialog_and_retry_without_history_lock(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    page.get_by_role('button',name='总欠款汇总导出…',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.get_by_role('button',name='确认清单',exact=True).click()
    calls=[]
    def fail(route):
        calls.append(route.request.url);route.fulfill(status=500,json={'message':'合成导出故障，请重试。'})
    page.route('**/api/m05/debt/export?**',fail)
    dialog.get_by_role('button',name='保存到本地',exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('合成导出故障')
    expect(dialog.get_by_role('button',name='保存到本地',exact=True)).to_be_enabled()
    assert len(calls)==1
    page.unroute('**/api/m05/debt/export?**')
    with page.expect_download() as event:dialog.get_by_role('button',name='保存到本地',exact=True).click()
    download=event.value;path=output(download.suggested_filename,kind='exports');download.save_as(path)
    workbook=openpyxl.load_workbook(path,data_only=True);rows=list(workbook.active.values);workbook.close()
    assert [row[1] for row in rows if isinstance(row[0],int)] == ['隔离项目']
    assert next(row[2:5] for row in rows if row[1]=='隔离项目') == (0,1890,-75)
    expect(page.get_by_role('button',name='总欠款汇总导出…',exact=True)).to_be_focused()


def test_draft_feedback_is_inside_each_export_dialog(server,browser_page):
    from test_ledger import history_row,select_project
    page,_=browser_page;open_ledger(page,server)
    paid=history_row(page).locator('[col-id="payment"] input')
    paid.fill('invalid');paid.press('Tab')
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('输入已保留')
    exports=[];page.on('request',lambda request:exports.append(request.url) if '/export?' in request.url else None)
    # A dirty project stays protected after switching the single-project viewer.
    select_project(page,'长项目名验收')
    for title in ['逐月台账导出','总欠款汇总导出']:
        page.get_by_role('button',name=title+'…',exact=True).click()
        dialog=page.get_by_role('dialog',name=title,exact=True)
        dialog.get_by_role('button',name=re.compile('^☐ 隔离项目')).click()
        dialog.get_by_role('button',name='确认清单',exact=True).click()
        dialog.get_by_role('button',name='保存到本地',exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('请先处理未保存输入')
        dialog.get_by_role('button',name='取消',exact=True).click()
    assert not exports


def test_empty_data_and_unbuilt_project_cannot_expand_export_scope(server,browser_page):
    page,_=browser_page;open_ledger(page,server)
    page.get_by_role('button',name='总欠款汇总导出…',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.get_by_role('button',name='清空',exact=True).click()
    expect(dialog.get_by_role('button',name='确认清单',exact=True)).to_be_disabled()
    dialog.get_by_role('button',name=re.compile('^☐ 归档样例')).click()
    dialog.get_by_role('button',name='确认清单',exact=True).click()
    dialog.get_by_role('button',name='保存到本地',exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('一个项目的欠款都算不出来')
    dialog.get_by_role('button',name='返回选择',exact=True).click()
    expect(dialog.get_by_role('button',name=re.compile('^☑ 归档样例'))).to_be_visible()
    dialog.get_by_role('button',name='取消',exact=True).click()
    def no_warehouse(route):
        response=route.fetch();rows=response.json()
        for row in rows:
            if row['disp']=='隔离项目':row['warehouse_name']=None
        route.fulfill(response=response,json=rows)
    page.route('**/api/m01/projects?**',no_warehouse);page.reload()
    expect(page.get_by_role('region',name='辅材欠款台账')).to_be_visible()
    page.get_by_role('button',name='总欠款汇总导出…',exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('尚未建仓')
    expect(page.get_by_role('dialog').get_by_role('button',name='确认清单',exact=True)).to_be_disabled()
