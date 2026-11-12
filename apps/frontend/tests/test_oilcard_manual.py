"""Manual invoice recovery keeps one real row after a lost receipt."""
from uuid import uuid4

from playwright.sync_api import expect
from live_data import get, open_page, grid_row
from preview_select import pick_popup_option, pick_option
from test_preview import server, browser_page  # noqa: F401


def test_manual_invoice_lost_reply_and_same_row_number(server, browser_page, api, disposable, projects):
    page, _ = browser_page
    archives = get(api, '/api/m13/archives')
    account = next(a for a in archives['accounts'] if a['status'] == 'active')
    project = next(p for p in projects if p['id'] == account['project_id'])
    mark = 'QA-' + uuid4().hex
    writes = []

    def lose_reply(route):
        response = route.fetch()
        assert response.ok and response.json()['ok']
        writes.append(response.json()['item'])
        route.fulfill(response=response, body='{')

    open_page(page, server, 'oilcard', '油卡管理')
    page.get_by_role('tab', name='充值与发票', exact=True).click()
    page.get_by_role('button', name='手动增行', exact=True).click()
    dialog = page.get_by_role('dialog', name='手动增行', exact=True)
    dialog.get_by_label('手工登记价税合计').fill('1.23')
    dialog.get_by_label('手工登记日期或原标记', exact=True).fill('2026-11-12')
    dialog.get_by_label('手工登记备注').fill(mark)
    picker = dialog.get_by_label('分配项目 1', exact=True)
    picker.fill(project['disp'])
    pick_popup_option(page, project['disp'])
    if sum(a['project_id'] == account['project_id'] for a in archives['accounts']) > 1:
        pick_option(page, '分配账户 1', account['name'])
    expect(dialog.get_by_label('分配账户 1').locator('xpath=ancestor::div[contains(@class,"ant-select")][last()]')).to_contain_text(account['name'])
    page.route('**/api/m13/invoices/manual', lose_reply)
    dialog.get_by_role('button', name='登记已开金额', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button', name='手动增行', exact=True)).to_be_disabled()
    confirm = page.get_by_role('button', name='已核对，保留输入继续', exact=True)
    expect(confirm).to_be_disabled()
    page.get_by_role('button', name='重读核对', exact=True).click()
    expect(confirm).to_be_enabled()
    confirm.click()
    expect(page.get_by_role('button', name='手动增行', exact=True)).to_be_enabled()
    assert len(writes) == 1
    saved = writes[0]
    matches = [r for r in get(api, '/api/m13/invoices')['invoices'] if r['manual_request_id'] == saved['manual_request_id']]
    assert len(matches) == 1 and matches[0]['amount'] == '1.23'
    row = grid_row(page, '.oilcard-grid-frame', saved['id'])
    row.get_by_role('button', name='修改', exact=True).click()
    edit = page.get_by_role('dialog', name='修改手工登记', exact=True)
    number = str(uuid4().int)[:20]
    edit.get_by_label('手工登记发票号码').fill(number)
    edit.get_by_role('button', name='保存修改', exact=True).click()
    expect(edit).not_to_be_visible()
    expect(page.get_by_role('button', name='手动增行', exact=True)).to_be_enabled()
    matches = [r for r in get(api, '/api/m13/invoices')['invoices'] if r['manual_request_id'] == saved['manual_request_id']]
    assert len(matches) == 1 and matches[0]['id'] == saved['id'] and matches[0]['invoice_no'] == number
    assert matches[0]['amount'] == '1.23' and matches[0]['remark'] == mark
