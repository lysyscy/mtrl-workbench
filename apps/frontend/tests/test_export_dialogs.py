"""Independent export scopes, recovery, account preferences and actual files."""
import re
from urllib.parse import quote_plus
import openpyxl
from playwright.sync_api import expect
from test_preview import server, browser_page
from test_ledger import open_ledger
from tools.audit.workspace_paths import output, output_dir


def open_export(page, title):
    button = page.get_by_role('button', name=title+'…', exact=True)
    expect(button).to_have_attribute('aria-disabled', 'false')
    button.click()
    dialog = page.get_by_role('dialog', name=title, exact=True)
    expect(dialog).to_be_visible()
    return dialog


def selected_names(dialog):
    return dialog.get_by_role('checkbox', checked=True).evaluate_all("items=>items.map(item=>item.closest('label').innerText.trim())")


def move_first(dialog, name):
    button = dialog.get_by_role('button', name='上移'+name, exact=True)
    while button.is_enabled():
        button.click()


def logout(page):
    page.get_by_role('button', name=re.compile('（(?:管理员|普通用户)）$')).click()
    page.get_by_role('menuitem', name='退出登录', exact=True).click()
    expect(page).to_have_url(re.compile('/login'))


def test_two_independent_dialogs_preserve_scope_and_real_debt_file(server, browser_page):
    page, _ = browser_page
    open_ledger(page, server)
    dialog = open_export(page, '逐月台账导出')
    dialog.get_by_role('button', name='关闭', exact=True).click()
    dialog = open_export(page, '总欠款汇总导出')
    expect(page.get_by_role('dialog')).to_have_count(1)
    dialog.get_by_role('button', name='全不选', exact=True).click()
    expect(dialog.get_by_role('button', name='保存到本地', exact=True)).to_be_disabled()
    for name in ['长项目名验收', '隔离项目']:
        dialog.get_by_role('checkbox', name=name, exact=True).check()
    move_first(dialog, '长项目名验收')
    dialog.get_by_role('button', name='关闭', exact=True).click()
    page.reload()
    expect(page.get_by_role('region', name='辅材欠款台账')).to_be_visible()
    dialog = open_export(page, '总欠款汇总导出')
    assert selected_names(dialog) == ['长项目名验收', '隔离项目']
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/m05/debt/export?' in request.url else None)
    with page.expect_download() as event:
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
    download = event.value
    path = output(download.suggested_filename, kind='exports'); download.save_as(path)
    assert 'projects='+quote_plus('长名称验收仓库,隔离验收仓库') in requests[-1]
    workbook = openpyxl.load_workbook(path, data_only=True)
    rows = list(workbook.active.values); workbook.close()
    assert rows[0] == ('序号', '项目', '集采', '辅材', '机械')
    assert [row[1] for row in rows[1:3]] == ['长项目名验收', '隔离项目']
    assert rows[1][2:5] == (0, 270, 0)
    assert rows[2][2:5] == (0, 1890, -75)
    assert list(output_dir('exports').glob('总欠款/*.xlsx'))
    expect(page.get_by_role('button', name='总欠款汇总导出…', exact=True)).to_be_focused()
    dialog = open_export(page, '逐月台账导出')
    expect(dialog.get_by_role('checkbox', name='隔离项目', exact=True)).to_be_checked()
    expect(dialog.get_by_role('checkbox', name='长项目名验收', exact=True)).not_to_be_checked()


def test_export_errors_stay_in_dialog_and_retry_without_history_lock(server, browser_page):
    page, _ = browser_page; open_ledger(page, server)
    dialog = open_export(page, '总欠款汇总导出')
    calls = []
    def fail(route):
        calls.append(route.request.url); route.fulfill(status=500, json={'message': '合成导出故障，请重试。'})
    page.route('**/api/m05/debt/export?**', fail)
    dialog.get_by_role('button', name='保存到本地', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('合成导出故障')
    expect(dialog.get_by_role('button', name='保存到本地', exact=True)).to_be_enabled()
    assert len(calls) == 1
    page.unroute('**/api/m05/debt/export?**')
    with page.expect_download() as event:
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
    download = event.value; path = output(download.suggested_filename, kind='exports'); download.save_as(path)
    workbook = openpyxl.load_workbook(path, data_only=True); rows = list(workbook.active.values); workbook.close()
    assert [row[1] for row in rows if isinstance(row[0], int)] == ['隔离项目']
    assert next(row[2:5] for row in rows if row[1] == '隔离项目') == (0, 1890, -75)
    expect(page.get_by_role('button', name='总欠款汇总导出…', exact=True)).to_be_focused()


def test_draft_feedback_is_inside_each_export_dialog(server, browser_page):
    from test_ledger import history_row, select_project
    page, _ = browser_page; open_ledger(page, server)
    paid = history_row(page).locator('[col-id="payment"] input')
    paid.fill('invalid'); paid.press('Tab')
    expect(page.get_by_role('status', name='保存回执')).to_contain_text('输入已保留')
    exports = []; page.on('request', lambda request: exports.append(request.url) if '/export?' in request.url else None)
    select_project(page, '长项目名验收')
    for title in ['逐月台账导出', '总欠款汇总导出']:
        dialog = open_export(page, title)
        dialog.get_by_role('checkbox', name='隔离项目', exact=True).check()
        dialog.get_by_role('button', name='保存到本地', exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('请先处理未保存输入')
        dialog.get_by_role('button', name='关闭', exact=True).click()
    assert not exports


def test_empty_data_and_unbuilt_project_cannot_expand_export_scope(server, browser_page):
    page, _ = browser_page; open_ledger(page, server)
    dialog = open_export(page, '总欠款汇总导出')
    dialog.get_by_role('button', name='全不选', exact=True).click()
    expect(dialog.get_by_role('button', name='保存到本地', exact=True)).to_be_disabled()
    dialog.get_by_role('checkbox', name='归档样例', exact=True).check()
    dialog.get_by_role('button', name='保存到本地', exact=True).click()
    expect(dialog.get_by_role('alert')).to_contain_text('一个项目的欠款都算不出来')
    expect(dialog.get_by_role('checkbox', name='归档样例', exact=True)).to_be_checked()
    dialog.get_by_role('button', name='全不选', exact=True).click()
    dialog.get_by_role('checkbox', name='隔离项目', exact=True).check()
    dialog.get_by_role('button', name='关闭', exact=True).click()
    def no_warehouse(route):
        response = route.fetch(); rows = response.json()
        for row in rows:
            if row['disp'] == '隔离项目': row['warehouse_name'] = None
        route.fulfill(response=response, json=rows)
    page.route('**/api/m01/projects?**', no_warehouse); page.reload()
    expect(page.get_by_role('region', name='辅材欠款台账')).to_be_visible()
    dialog = open_export(page, '总欠款汇总导出')
    expect(dialog.get_by_role('alert')).to_contain_text('尚未建仓')
    expect(dialog.get_by_role('button', name='保存到本地', exact=True)).to_be_disabled()


def test_export_preferences_restore_order_empty_selection_and_account_isolation(server, browser_page):
    page, _ = browser_page; open_ledger(page, server)
    ledger = open_export(page, '逐月台账导出')
    ledger.get_by_role('checkbox', name='长项目名验收', exact=True).check()
    move_first(ledger, '长项目名验收')
    ledger.press('Escape'); expect(page.get_by_role('dialog')).to_have_count(0)
    debt = open_export(page, '总欠款汇总导出')
    debt.get_by_role('button', name='全不选', exact=True).click()
    debt.get_by_role('button', name='关闭弹窗', exact=True).click()
    page.reload()
    expect(page.get_by_role('region', name='辅材欠款台账')).to_be_visible()
    ledger = open_export(page, '逐月台账导出')
    assert selected_names(ledger) == ['长项目名验收', '隔离项目']
    ledger.get_by_role('button', name='关闭', exact=True).click()
    debt = open_export(page, '总欠款汇总导出')
    expect(debt.get_by_role('button', name='保存到本地', exact=True)).to_be_disabled()
    expect(debt).to_contain_text('已选 0 个项目')
    debt.get_by_role('button', name='关闭', exact=True).click()
    logout(page); open_ledger(page, server, 'preview-user')
    ledger = open_export(page, '逐月台账导出')
    expect(ledger.get_by_role('checkbox', name='隔离项目', exact=True)).to_be_checked()
    expect(ledger.get_by_role('checkbox', name='长项目名验收', exact=True)).not_to_be_checked()
    ledger.get_by_role('button', name='全不选', exact=True).click()
    ledger.get_by_role('button', name='关闭', exact=True).click()
    logout(page); open_ledger(page, server)
    ledger = open_export(page, '逐月台账导出')
    expect(ledger.get_by_role('checkbox', name='长项目名验收', exact=True)).to_be_checked()
    ledger.get_by_role('button', name='关闭', exact=True).click()
    def changed_projects(route):
        response = route.fetch(); rows = response.json()
        rows = [row for row in rows if row['disp'] != '长项目名验收']
        rows.append({**rows[0], 'id': 999999, 'disp': '新项目不自动加入'})
        route.fulfill(response=response, json=rows)
    page.route('**/api/m01/projects?**', changed_projects); page.reload()
    expect(page.get_by_role('region', name='辅材欠款台账')).to_be_visible()
    ledger = open_export(page, '逐月台账导出')
    expect(ledger.get_by_role('checkbox', name='隔离项目', exact=True)).to_be_checked()
    expect(ledger.get_by_role('checkbox', name='新项目不自动加入', exact=True)).not_to_be_checked()
    assert selected_names(ledger) == ['隔离项目']
    ledger.get_by_role('button', name='关闭', exact=True).click()
