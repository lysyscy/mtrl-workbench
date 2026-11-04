"""Process and mechanical workspaces keep their own read state, in place, region by region."""

import re

from playwright.sync_api import expect

from live_data import get
from preview_select import pick_option
from test_preview import browser_page, login, server  # noqa: F401 (fixtures)

PROCESS_READS = ('**/api/m06/matrix', '**/api/m06/mech-screen')
MECHANICAL_READ = re.compile(r'/api/m06/workbench/page(\?|$)')


def open_route(page, address, route):
    """Open a page without waiting for network idle; one of its reads may be held."""
    login(page, address)
    page.goto(address + '/preview/' + route)


def lane_top(page, selector):
    return page.locator(selector).bounding_box()['y']


def hold(page, pattern):
    held = []
    page.route(pattern, lambda route: held.append(route))
    return held


def release_all(page, held, *patterns):
    """Let the real endpoints answer, then stop holding them."""
    for route in list(held):
        route.fulfill(response=route.fetch())
    held.clear()
    for pattern in patterns:
        page.unroute(pattern)


def test_process_tools_appear_before_the_matrix_read(server, browser_page, api, projects):
    page, _ = browser_page
    held = []
    for pattern in PROCESS_READS:
        page.route(pattern, lambda route: held.append(route))
    open_route(page, server, 'process')

    # The tool area is already usable while the matrix read is still running.
    expect(page.locator('.process-toolbar')).to_be_visible()
    expect(page.get_by_label('过程资料项目')).to_be_visible()
    expect(page.locator('.process-tabs')).to_be_visible()
    # The data region speaks for itself once, and not as an empty result.
    expect(page.locator('.process-read-status[data-read-phase="reading"]')).to_have_count(1)
    expect(page.locator('.process-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.process-read-status .notice')).to_have_count(0)
    expect(page.locator('.process-read-note')).to_have_count(0)
    expect(page.locator('.process-read-body .read-placeholder')).to_have_count(1)
    expect(page.locator('.process-matrix')).to_have_count(0)
    assert len(held) == 2, len(held)
    tabs_top = lane_top(page, '.process-tabs')

    release_all(page, held, *PROCESS_READS)
    expect(page.locator('.process-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.process-read-status .notice')).to_have_count(0)
    # The real matrix takes the placeholder's place; the tool area did not move.
    data = get(api, '/api/m06/matrix')
    project = next(p for p in projects if data['matrices'].get(p['warehouse_name'], {}).get('raw'))
    pick_option(page, '过程资料项目', project['disp'])
    expect(page.locator('.process-matrix')).to_have_attribute('data-layout-state', 'ready')
    expect(page.locator('.process-read-body')).to_have_count(0)
    expect(page.locator('.process-read-note')).to_have_count(0)
    assert abs(lane_top(page, '.process-tabs') - tabs_top) < 1, (tabs_top, lane_top(page, '.process-tabs'))


def test_process_read_failure_reports_in_place(server, browser_page):
    page, _ = browser_page
    held = []
    for pattern in PROCESS_READS:
        page.route(pattern, lambda route: held.append(route))
    open_route(page, server, 'process')
    expect(page.locator('.process-read-status[data-read-phase="reading"]')).to_have_count(1)
    tabs_top = lane_top(page, '.process-tabs')
    assert len(held) == 2, len(held)

    for route in list(held):
        route.fulfill(status=503, content_type='application/json', body='{"detail": "过程资料读取暂时失败"}')
    held.clear()
    for pattern in PROCESS_READS:
        page.unroute(pattern)

    failure = page.locator('.process-read-status .notice')
    expect(failure).to_be_visible()
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed read is neither a running read nor a genuine empty result.
    expect(page.locator('.process-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.process-read-note')).to_have_count(0)
    # Failure reports inside the fixed status lane, so the tool area keeps its place.
    assert abs(lane_top(page, '.process-tabs') - tabs_top) < 1, (tabs_top, lane_top(page, '.process-tabs'))
    expect(page.locator('.process-toolbar')).to_be_visible()


def test_mechanical_tools_appear_before_the_month_read(server, browser_page):
    page, _ = browser_page
    held = hold(page, MECHANICAL_READ)
    open_route(page, server, 'mechanical')

    expect(page.locator('.mechanical-toolbar')).to_be_visible()
    expect(page.get_by_label('月份')).to_be_visible()
    expect(page.get_by_role('button', name='表2 零租明细')).to_be_visible()
    expect(page.locator('.mechanical-read-status[data-read-phase="reading"]')).to_have_count(1)
    expect(page.locator('.mechanical-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.mechanical-read-status .notice')).to_have_count(0)
    # A read that has not landed is not an empty report and not a missing project choice.
    expect(page.get_by_role('status').filter(has_text='请选择项目查看报表')).to_have_count(0)
    expect(page.get_by_role('status').filter(has_text='暂无已保存月份')).to_have_count(0)
    expect(page.locator('.mechanical-read-body .read-placeholder')).to_have_count(1)
    assert len(held) == 1, len(held)
    toolbar_top = lane_top(page, '.mechanical-toolbar')

    release_all(page, held, MECHANICAL_READ)
    expect(page.locator('.mechanical-read-status:is([data-read-phase="ready"],[data-read-phase="empty"])')).to_have_count(1)
    expect(page.locator('.mechanical-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.mechanical-read-body')).to_have_count(0)
    # The real report takes the placeholder's place; the tool area did not move.
    expect(page.get_by_role('region', name='公司汇总').or_(page.get_by_role('status').filter(has_text='请选择项目查看报表'))).to_be_visible()
    assert abs(lane_top(page, '.mechanical-toolbar') - toolbar_top) < 1, (toolbar_top, lane_top(page, '.mechanical-toolbar'))


def test_mechanical_read_failure_reports_in_place(server, browser_page):
    page, _ = browser_page
    held = hold(page, MECHANICAL_READ)
    open_route(page, server, 'mechanical')
    expect(page.locator('.mechanical-read-status[data-read-phase="reading"]')).to_have_count(1)
    assert len(held) == 1, len(held)

    held.pop().fulfill(status=503, content_type='application/json', body='{"detail": "机械报表读取暂时失败"}')
    page.unroute(MECHANICAL_READ)

    failure = page.locator('.mechanical-read-status .notice')
    expect(failure).to_be_visible()
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.mechanical-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.mechanical-read-body .read-placeholder')).to_have_count(1)
    expect(page.get_by_role('status').filter(has_text='请选择项目查看报表')).to_have_count(0)
    # The report areas stay in the page; only their own region is held back.
    expect(page.locator('.mechanical-toolbar')).to_be_visible()
    expect(page.get_by_role('button', name='核对工作台')).to_be_visible()
