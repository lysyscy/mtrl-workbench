"""Native header resizing survives reload; reset keeps the reader's working state."""
import json
import pytest
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from live_data import open_page, contract_sample


def header(page, grid, column):
    return page.locator(f'{grid} .ag-header-cell[col-id="{column}"]')


def resize(page, grid, column, delta=64):
    target = header(page, grid, column)
    target.scroll_into_view_if_needed()
    before = target.bounding_box()['width']
    handle = target.locator('.ag-header-cell-resize')
    expect(handle).to_be_visible()
    box = handle.bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + delta, y, steps=8)
    page.mouse.up()
    page.wait_for_function('([selector,width])=>Math.abs(document.querySelector(selector).getBoundingClientRect().width-width)<.6', arg=[f'{grid} .ag-header-cell[col-id="{column}"]', before + delta])
    return target.evaluate('e=>getComputedStyle(e).width')


def storage_key(me, table):
    return 'mtrl:grid-widths:v1:' + json.dumps([f'{me["id"]}:{me["account"]}', table], separators=(',', ':'))


@pytest.mark.parametrize('route,title,grid,column,table', [
    ('contracts', '集采台账', '.contracts-grid', 'material', 'contracts'),
    ('notices', '付款通知书', '.notice-grid', 'project_display', 'notices'),
])
def test_native_resize_survives_reload_and_window_change(server, browser_page, route, title, grid, column, table):
    page, _ = browser_page
    open_page(page, server, route, title)
    page.wait_for_selector(grid + ' .ag-row')
    if route == 'notices':
        expect(page.locator(grid)).to_have_attribute('data-layout-state', 'ready')
    me = page.request.get(server + '/api/m15/users').json()['me']
    width = resize(page, grid, column)
    saved = page.evaluate('key=>JSON.parse(localStorage.getItem(key))', storage_key(me, table))
    assert list(saved['widths']) == [column], 'Automatic widths must not become overrides'
    page.reload()
    expect(header(page, grid, column)).to_have_css('width', width)
    if route == 'notices':
        expect(page.locator(grid)).to_have_attribute('data-layout-state', 'ready')
    other = 'bill_name' if route == 'notices' else 'supplier'
    before = header(page, grid, other).bounding_box()['width']
    page.set_viewport_size({'width': 3840, 'height': 1080})
    expect(header(page, grid, column)).to_have_css('width', width)
    page.wait_for_function('([selector,width])=>document.querySelector(selector).getBoundingClientRect().width>width+1', arg=[f'{grid} .ag-header-cell[col-id="{other}"]', before])
    page.set_viewport_size({'width': 900, 'height': 900})
    expect(header(page, grid, column)).to_have_css('width', width)
    assert page.locator(grid + ' .ag-body-horizontal-scroll-viewport').evaluate('e=>e.scrollWidth>e.clientWidth')


def test_account_isolation_and_width_reset_preserve_filter_sort_and_selection(server, browser_page, api):
    page, _ = browser_page
    _, label = contract_sample(api)
    me = login(page, server)
    page.locator('a[href="/preview/contracts"]').click()
    page.get_by_label('搜索', exact=True).fill(label)
    expect(page.locator('.contracts-grid .ag-row:not(.ag-row-pinned)').first).to_be_visible()
    automatic_width = header(page, '.contracts-grid', 'material').evaluate('e=>getComputedStyle(e).width')
    width = resize(page, '.contracts-grid', 'material')
    login(page, server, 'preview-user')
    page.locator('a[href="/preview/contracts"]').click()
    expect(page.locator('.contracts-page .grid-width-tools button')).to_be_disabled()
    resize(page, '.contracts-grid', 'material', 96)
    login(page, server)
    page.locator('a[href="/preview/contracts"]').click()
    expect(header(page, '.contracts-grid', 'material')).to_have_css('width', width)
    search = page.get_by_label('搜索', exact=True)
    search.fill(label)
    selected = page.locator('.contracts-grid .ag-row:not(.ag-row-pinned) input[type=checkbox]').first
    selected.check()
    header(page, '.contracts-grid', 'material').get_by_text('材料名',exact=True).click()
    expect(header(page, '.contracts-grid', 'material')).to_have_attribute('aria-sort', 'ascending')
    page.locator('.contracts-page').get_by_role('button', name='恢复自动列宽', exact=True).click()
    expect(search).to_have_value(label)
    expect(selected).to_be_checked()
    expect(header(page, '.contracts-grid', 'material')).to_have_attribute('aria-sort', 'ascending')
    expect(page.locator('.contracts-page').get_by_role('button', name='恢复自动列宽', exact=True)).to_be_disabled()
    expect(header(page, '.contracts-grid', 'material')).to_have_css('width', automatic_width)
    assert page.evaluate('key=>localStorage.getItem(key)', storage_key(me, 'contracts')) is None


def test_notice_amount_click_keeps_automatic_and_manual_widths(server, browser_page, preview_screenshot):
    page, _ = browser_page
    open_page(page, server, 'notices', '付款通知书')
    grid = page.locator('.notice-grid')
    expect(grid).to_have_attribute('data-layout-state', 'ready')
    first = grid.locator('.ag-row:not(.ag-row-pinned) [col-id="pick"] input[type="checkbox"]:not(:disabled)').first
    expect(first).to_be_visible()
    label = first.get_attribute('aria-label')
    assert label and label.startswith('勾选')
    page.get_by_label('通知书搜索', exact=True).fill(label[2:])
    checkbox = grid.get_by_label(label, exact=True).first
    row = grid.locator('.ag-row:not(.ag-row-pinned)').filter(has=page.get_by_label(label, exact=True)).first
    amount = row.locator('[col-id="pay_amount"] input:not(:disabled)')
    manual_width = resize(page, '.notice-grid', 'project_display')
    pay_header = header(page, '.notice-grid', 'pay_amount')
    before = pay_header.bounding_box()['width']
    before_css = pay_header.evaluate('e=>getComputedStyle(e).width')
    amount.fill('9876543210.12')
    # Editing freezes actual widths; blur must still publish the new amount minimum.
    expect(pay_header).to_have_css('width', before_css)
    box = checkbox.bounding_box()
    assert box
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.down()
    page.wait_for_timeout(80)
    page.mouse.up()
    expect(checkbox).to_be_checked()
    expect(amount).to_have_value('9876543210.12')
    page.wait_for_function('width=>document.querySelector(".notice-grid .ag-header-cell[col-id=pay_amount]").getBoundingClientRect().width>width+1', arg=before)
    expect(header(page, '.notice-grid', 'project_display')).to_have_css('width', manual_width)
    page.get_by_role('button', name='恢复自动列宽', exact=True).click()
    expect(checkbox).to_be_checked()
    expect(page.get_by_label('通知书搜索', exact=True)).to_have_value(label[2:])
    preview_screenshot('notice-amount-selection-widths')

    page.get_by_role('button', name='手动新增', exact=True).click()
    draft_pick = grid.locator('.ag-row[row-id="-2"] [col-id="pick"]')
    expect(draft_pick).to_have_text('草稿')
    expect(draft_pick.locator('input[type=checkbox]')).to_have_count(0)
    page.get_by_role('button', name='取消草稿', exact=True).click()
    expect(draft_pick).to_have_count(0)
