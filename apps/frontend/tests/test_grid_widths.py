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
    return round(before + delta)


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
    expect(header(page, grid, column)).to_have_css('width', f'{width}px')
    if route == 'notices':
        expect(page.locator(grid)).to_have_attribute('data-layout-state', 'ready')
    other = 'bill_name' if route == 'notices' else 'supplier'
    before = header(page, grid, other).bounding_box()['width']
    page.set_viewport_size({'width': 3840, 'height': 1080})
    expect(header(page, grid, column)).to_have_css('width', f'{width}px')
    page.wait_for_function('([selector,width])=>document.querySelector(selector).getBoundingClientRect().width>width+1', arg=[f'{grid} .ag-header-cell[col-id="{other}"]', before])
    page.set_viewport_size({'width': 900, 'height': 900})
    expect(header(page, grid, column)).to_have_css('width', f'{width}px')
    assert page.locator(grid + ' .ag-body-horizontal-scroll-viewport').evaluate('e=>e.scrollWidth>e.clientWidth')


def test_account_isolation_and_width_reset_preserve_filter_sort_and_selection(server, browser_page, api):
    page, _ = browser_page
    _, label = contract_sample(api)
    me = login(page, server)
    page.locator('a[href="/preview/contracts"]').click()
    page.get_by_label('搜索', exact=True).fill(label)
    expect(page.locator('.contracts-grid .ag-row:not(.ag-row-pinned)').first).to_be_visible()
    width = resize(page, '.contracts-grid', 'material')
    login(page, server, 'preview-user')
    page.locator('a[href="/preview/contracts"]').click()
    expect(page.locator('.grid-width-tools button')).to_be_disabled()
    resize(page, '.contracts-grid', 'material', 96)
    login(page, server)
    page.locator('a[href="/preview/contracts"]').click()
    expect(header(page, '.contracts-grid', 'material')).to_have_css('width', f'{width}px')
    search = page.get_by_label('搜索', exact=True)
    search.fill(label)
    selected = page.locator('.contracts-grid .ag-row:not(.ag-row-pinned) input[type=checkbox]').first
    selected.check()
    header(page, '.contracts-grid', 'material').locator('.ag-header-cell-label').click()
    expect(header(page, '.contracts-grid', 'material')).to_have_attribute('aria-sort', 'ascending')
    page.get_by_role('button', name='恢复自动列宽', exact=True).click()
    expect(search).to_have_value(label)
    expect(selected).to_be_checked()
    expect(header(page, '.contracts-grid', 'material')).to_have_attribute('aria-sort', 'ascending')
    expect(page.get_by_role('button', name='恢复自动列宽', exact=True)).to_be_disabled()
    assert page.evaluate('key=>localStorage.getItem(key)', storage_key(me, 'contracts')) is None
