"""Real project filtering, composition and delayed-read continuity."""
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login


def test_real_project_search_composition_and_filter_are_local(server, browser_page, projects):
    page, _ = browser_page
    login(page, server)
    row = next(p for p in projects if p['status']=='active' and p['disp'])
    reads = []
    page.on('request', lambda request: reads.append(request.url) if '/api/m01/projects?' in request.url else None)
    field = page.get_by_label('项目搜索', exact=True)
    field.dispatch_event('compositionstart')
    field.fill(row['disp'])
    field.dispatch_event('compositionend')
    expect(page.get_by_label('展示名：'+row['disp'], exact=True)).to_be_visible()
    assert not reads
    field.fill('')
    expect(field).to_have_value('')
    expect(page.get_by_label('展示名：'+row['disp'], exact=True)).to_be_visible()


def test_delayed_real_project_response_preserves_search(server, browser_page, projects):
    page, _ = browser_page
    login(page, server)
    row = next(p for p in projects if p['status']=='active' and p['disp'])
    pending = []
    page.route('**/api/m01/projects?status=all', lambda route: pending.append(route))
    try:
        with page.expect_request('**/api/m01/projects?status=all'):
            page.reload(wait_until='domcontentloaded')
        field = page.get_by_label('项目搜索', exact=True)
        expect(field).to_be_visible()
        field.fill(row['disp'])
        expect(page.get_by_role('button',name='＋ 手工建档',exact=True)).to_be_disabled()
        expect(page.locator('.projects-page .result')).to_have_count(0)
        page.wait_for_function('document.readyState === "complete"')
        assert pending
    finally:
        for route in pending: route.continue_()
        page.unroute('**/api/m01/projects?status=all')
    expect(field).to_have_value(row['disp'])
    expect(page.get_by_label('展示名：'+row['disp'], exact=True)).to_be_visible()


def test_notice_reread_retains_active_payment_draft(server, browser_page):
    """A harmless reread must not replace an uncommitted payment input."""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='付款通知书', exact=True).click()
    grid = page.locator('.notice-grid');expect(grid).to_be_visible()
    expect(grid).to_have_attribute('aria-busy', 'false', timeout=30000)
    first = grid.locator('[col-id=pay_amount] input:not(:disabled)').first
    expect(first).to_be_visible()
    field = page.get_by_label(first.get_attribute('aria-label'), exact=True)
    field.fill('321.09');field.focus()
    held=[]
    page.route('**/api/m03/notice-list?*', lambda route: held.append(route))
    with page.expect_request('**/api/m03/notice-list?*'):
        page.evaluate("window.dispatchEvent(new Event('offline'));window.dispatchEvent(new Event('online'))")
    try:
        expect(field).to_have_value('321.09');expect(field).to_be_focused()
        assert held
    finally:
        for route in held:route.continue_()
        page.unroute('**/api/m03/notice-list?*')
    page.wait_for_load_state('networkidle')
    expect(field).to_have_value('321.09');expect(field).to_be_focused()


def test_notice_checkbox_tracks_selection_without_blur(server, browser_page):
    """Selection and its visible checkbox must agree before focus leaves the grid."""
    page, _ = browser_page
    login(page, server)
    page.get_by_role('link', name='付款通知书', exact=True).click()
    grid = page.locator('.notice-grid')
    expect(grid).to_have_attribute('aria-busy', 'false', timeout=30000)
    first = grid.locator('.ag-row:not(.ag-row-pinned) [col-id="pick"] input[type="checkbox"]:not(:disabled)').first
    expect(first).to_be_visible()
    label = first.get_attribute('aria-label')
    assert label and label.startswith('勾选')
    page.get_by_label('通知书搜索', exact=True).fill(label[2:])
    checkbox = grid.get_by_label(label, exact=True).first
    selection = page.locator('.notice-selection > span').first
    expect(checkbox).not_to_be_checked()
    checkbox.click()
    expect(selection).to_contain_text('已勾选 1 行')
    expect(checkbox).to_be_checked(timeout=2000)
    checkbox.click()
    expect(selection).to_contain_text('已勾选 0 行')
    expect(checkbox).not_to_be_checked(timeout=2000)
    header = grid.get_by_role('checkbox', name='全选当前筛选结果', exact=True)
    header.click()
    expect(header).to_be_checked(timeout=2000)
    expect(checkbox).to_be_checked(timeout=2000)
    header.click()
    expect(header).not_to_be_checked(timeout=2000)
    expect(checkbox).not_to_be_checked(timeout=2000)


@pytest.mark.parametrize('press_ms', [0, 80])
def test_notice_amount_blur_keeps_first_mouse_selection(server, browser_page, press_ms):
    """One physical click must survive the amount blur; never retry the click."""
    page, _ = browser_page
    writes = []
    page.on('request', lambda request: writes.append(request.url) if '/api/' in request.url and request.method != 'GET' else None)
    login(page, server)
    page.get_by_role('link', name='付款通知书', exact=True).click()
    grid = page.locator('.notice-grid')
    expect(grid).to_have_attribute('data-layout-state', 'ready', timeout=30000)
    first = grid.locator('.ag-row:not(.ag-row-pinned) [col-id="pick"] input[type="checkbox"]:not(:disabled)').first
    expect(first).to_be_visible()
    label = first.get_attribute('aria-label')
    assert label and label.startswith('勾选')
    search = page.get_by_label('通知书搜索', exact=True)
    search.fill(label[2:])
    checkbox = grid.get_by_label(label, exact=True).first
    row = grid.locator('.ag-row:not(.ag-row-pinned)').filter(has=page.get_by_label(label, exact=True)).first
    amount = row.locator('[col-id="pay_amount"] input:not(:disabled)')
    selection = page.locator('.notice-selection > span').first

    def click_once(target):
        expect(target).to_be_visible()
        box = target.bounding_box()
        assert box
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        if press_ms:
            page.wait_for_timeout(press_ms)
        page.mouse.up()

    amount.fill('321.09')
    expect(amount).to_be_focused()
    click_once(checkbox)
    expect(selection).to_contain_text('已勾选 1 行')
    expect(checkbox).to_be_checked()
    expect(amount).to_have_value('321.09')
    expect(amount).not_to_be_focused()
    expect(page.locator('.notice-selection > span').nth(2)).to_contain_text('321.09')
    search.fill(label[2:] + '-no-match')
    expect(grid.get_by_role('checkbox', name='全选当前筛选结果', exact=True)).to_be_disabled()
    expect(selection).to_contain_text('已勾选 1 行')
    search.fill(label[2:])
    expect(checkbox).to_be_checked()

    amount.fill('123.45')
    click_once(checkbox)
    expect(selection).to_contain_text('已勾选 0 行')
    expect(checkbox).not_to_be_checked()
    expect(amount).to_have_value('123.45')

    header = grid.get_by_role('checkbox', name='全选当前筛选结果', exact=True)
    amount.fill('234.56')
    click_once(header)
    expect(header).to_be_checked()
    expect(checkbox).to_be_checked()
    expect(amount).to_have_value('234.56')
    amount.fill('345.67')
    click_once(header)
    expect(header).not_to_be_checked()
    expect(checkbox).not_to_be_checked()
    expect(selection).to_contain_text('已勾选 0 行')
    expect(amount).to_have_value('345.67')
    expect(search).to_have_value(label[2:])
    assert not writes, 'Amount and selection changes must remain local'


def test_invalid_payment_draft_blocks_dialog_and_survives_filtered_remount(server, browser_page, api):
    from decimal import Decimal
    from live_data import get, open_page
    page, _ = browser_page
    rows = get(api, '/api/m03/notice-list', period='')['items']
    row = next((r for r in rows if not r['pay_block_reason'] and not r['is_excluded']
                and not r['is_revoked'] and Decimal(r['pay_amount']) > 1), None)
    assert row, '真实副本没有可付款通知书，非法金额入口未覆盖'
    open_page(page, server, 'notices', '付款通知书')
    search = page.get_by_label('通知书搜索', exact=True)
    search.fill(row['bill_no'])
    page.get_by_label('勾选' + row['bill_no'], exact=True).check()
    field = page.get_by_label(row['bill_no'] + '付款金额', exact=True)
    writes = []
    page.on('request', lambda req: writes.append(req.url) if '/api/' in req.url and req.method != 'GET' and '/payment-context' not in req.url else None)
    field.fill('10.001')
    page.locator('.notice-pay-action').click()
    expect(page.get_by_role('dialog', name='批量付款', exact=True)).to_have_count(0)
    expect(page.get_by_role('alert').filter(has_text='请修改后再付款')).to_be_visible()
    expect(field).to_have_value('10.001')
    expect(field).to_be_focused()
    search.fill('audit-no-match')
    expect(field).to_have_count(0)
    search.fill(row['bill_no'])
    expect(field).to_have_value('10.001')
    page.locator('.notice-pay-action').click()
    expect(page.get_by_role('dialog', name='批量付款', exact=True)).to_have_count(0)
    field.fill('1.25')
    page.locator('.notice-pay-action').click()
    dialog = page.get_by_role('dialog', name='批量付款', exact=True)
    expect(dialog.get_by_label(row['bill_no'] + '本次付款金额', exact=True)).to_have_value('1.25')
    dialog.get_by_role('button', name='取消', exact=True).click()
    field.fill('')
    page.locator('.notice-pay-action').click()
    expected = format(Decimal(row['amount_approved']) - Decimal(row['amount_paid']), '.2f')
    expect(dialog.get_by_label(row['bill_no'] + '本次付款金额', exact=True)).to_have_value(expected)
    dialog.get_by_role('button', name='取消', exact=True).click()
    assert not writes, '金额修正和打开确认窗口不得登记付款'
