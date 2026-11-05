"""Notices, inventory, payment flow and home report their own read in place.

Each page owns its read lane: a pending or failed read is expressed inside the
region it belongs to, keeps that region's reserved box, and never stands in for
a real empty result or a real zero count.
"""

import re
import pytest

from playwright.sync_api import expect

from test_preview import browser_page, login, server  # noqa: F401 (fixtures)


@pytest.mark.parametrize('route,endpoint,lane,success', [
    ('ledger','**/api/m05/stats?*','.payment-stats-status','.payment-stat-columns'),
    ('debt','**/api/m05/debt','.debt-overviews-status','.debt-overviews-grid'),
])
def test_malformed_success_uses_read_retry_instead_of_page_failure(server, browser_page, route, endpoint, lane, success):
    page, _ = browser_page
    login(page, server)

    def broken(request):
        response = request.fetch()
        assert response.ok
        data = response.json()
        if route == 'ledger':
            del data['selected']['projects']
        else:
            assert data['by_project_category'], '真实副本缺欠款汇总代表'
            del data['by_project_category'][0]['mech']
        request.fulfill(response=response, json=data)

    page.route(endpoint, broken)
    page.goto(server+'/preview/'+route, wait_until='domcontentloaded')
    failure = page.locator(lane+' [role=alert]')
    expect(failure).to_contain_text('读取不完整')
    expect(page.locator('[data-route-error]:visible')).to_have_count(0)
    page.unroute(endpoint)
    failure.get_by_role('button',name='重试读取').click()
    expect(failure).to_have_count(0)
    expect(page.locator(success)).to_be_visible()


def test_notice_list_keeps_its_reserved_box_while_the_first_read_lands(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m03/notice-list?*', lambda route: held.append(route))
    page.goto(server + '/preview/notices', wait_until='domcontentloaded')

    # The page is usable while its list read is still in flight.
    search = page.get_by_role('searchbox', name='通知书搜索', exact=True)
    search.click()
    expect(search).to_be_focused()
    # Wait for the lane to report the read instead of guessing how long mounting takes.
    expect(page.locator('.notice-read-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, 'The actual first notice read was not held'

    # A running read is announced once, and it is not an empty list.
    expect(page.locator('.notice-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.notice-read-reserve .read-placeholder')).to_have_count(1)
    expect(page.get_by_role('region', name='付款通知书列表', exact=True)).to_have_count(0)
    before = page.locator('.notice-grid').bounding_box()
    for route in held:
        route.continue_()
    page.unroute('**/api/m03/notice-list?*')

    table = page.get_by_role('region', name='付款通知书列表', exact=True)
    expect(table).to_be_visible()
    assert table.bounding_box() == before, 'First table publication changed its reserved box'
    expect(page.locator('.notice-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.notice-read-reserve')).to_have_count(0)
    expect(search).to_be_focused()


def test_notice_list_failure_reports_in_place_and_is_not_an_empty_list(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m03/notice-list?*', lambda route: held.append(route))
    page.goto(server + '/preview/notices', wait_until='domcontentloaded')
    # Wait for this page to actually start its read rather than guessing how long mounting takes:
    # the lane only says "reading" once the request exists.
    expect(page.locator('.notice-read-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, 'The actual first notice read was not held'
    before = page.locator('.notice-grid').bounding_box()
    for route in held:
        route.fulfill(status=503, content_type='application/json', body='{"detail": "通知书读取暂时失败"}')

    failure = page.locator('.notice-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed first read is neither a running read nor an empty list.
    expect(page.locator('.notice-read-status [role=status]')).to_have_count(0)
    expect(page.get_by_role('region', name='付款通知书列表', exact=True)).to_have_count(0)
    expect(page.locator('.notice-read-reserve .read-placeholder-quiet')).to_have_count(1)
    after = page.locator('.notice-grid').bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)


def test_inventory_first_read_failure_is_reported_in_place(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.route('**/api/m08/inventory', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail": "库存读取暂时失败"}'))
    page.goto(server + '/preview/inventory', wait_until='domcontentloaded')
    expect(page.locator('#page-title')).to_have_text('库存单据与调整单')

    # The page publishes with its own failure lane instead of staying blocked.
    expect(page.locator('.page-loading')).to_have_count(0)
    failure = page.locator('.inventory-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # Nothing was read, so the summary does not claim zero rows.
    expect(page.locator('.inventory-count-feedback')).to_have_text('尚未读取')
    expect(page.locator('.inventory-grid.inventory-read-reserve')).to_have_count(1)
    before = page.locator('.inventory-grid').bounding_box()

    page.unroute('**/api/m08/inventory')
    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.inventory-grid')).to_have_attribute('aria-busy', 'false', timeout=30000)
    expect(page.locator('.inventory-read-reserve')).to_have_count(0)
    after = page.locator('.inventory-grid').bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)


def test_flow_statistics_and_flows_publish_independently(server, browser_page):
    page, _ = browser_page
    login(page, server)
    stats, flows = [], []
    page.route('**/api/m05/stats?*', lambda route: stats.append(route))
    page.route('**/api/m05/flows?*', lambda route: flows.append(route))
    page.goto(server + '/preview/ledger', wait_until='domcontentloaded')
    expect(page.locator('#page-title')).to_have_text('付款流水')
    # Wait for each region to report its own in-flight read instead of assuming how long mounting
    # takes: a lane can only say "reading" once its request exists.
    expect(page.locator('.payment-stats-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    expect(page.locator('.flow-list-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert stats, 'The statistics read was not held'
    assert flows, 'The flow read was not held'

    # Each region reports for itself and keeps its own reserved area.
    expect(page.locator('.payment-stats-status [role=status]')).to_have_count(1)
    expect(page.locator('.flow-list-status [role=status]')).to_have_count(1)
    expect(page.locator('.payment-stat-reserve .read-placeholder')).to_have_count(1)
    expect(page.locator('.flow-grid.flow-read-reserve .read-placeholder')).to_have_count(1)
    flows_before = page.locator('.flow-grid').bounding_box()
    # The toolbar is usable while both reads are in flight.
    expect(page.get_by_label('流水关键词', exact=True)).to_be_enabled()

    for route in stats:
        route.continue_()
    page.unroute('**/api/m05/stats?*')

    # Statistics landing does not wait for the flow list.
    expect(page.locator('.payment-stat-columns')).to_be_visible()
    expect(page.locator('.payment-stat-reserve')).to_have_count(0)
    expect(page.locator('.payment-stats-status [role=status]')).to_have_count(0)
    expect(page.locator('.flow-grid.flow-read-reserve')).to_have_count(1)

    for route in flows:
        route.continue_()
    page.unroute('**/api/m05/flows?*')

    grid = page.locator('.flow-grid')
    expect(grid).to_have_attribute('aria-busy', 'false', timeout=30000)
    expect(page.locator('.flow-read-reserve')).to_have_count(0)
    expect(page.locator('.flow-list-status [role=status]')).to_have_count(0)
    after = grid.bounding_box()
    assert abs(after['y'] - flows_before['y']) < 1, (flows_before, after)
    assert abs(after['height'] - flows_before['height']) < 1, (flows_before, after)


def test_flow_statistics_failure_reports_in_place_without_moving_the_list(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.goto(server + '/preview/ledger', wait_until='domcontentloaded')
    grid = page.locator('.flow-grid')
    expect(grid).to_have_attribute('aria-busy', 'false', timeout=30000)
    before = grid.bounding_box()

    # A different statistics window is a different read; its failure stays in the
    # statistics region and the already published flow list keeps its box.
    page.route('**/api/m05/stats?*', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail": "统计读取暂时失败"}'))
    page.get_by_role('button', name='按月', exact=True).click()

    failure = page.locator('.payment-stats-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed statistics read is not a running read and invents no totals.
    expect(page.locator('.payment-stats-status [role=status]')).to_have_count(0)
    expect(page.locator('.payment-stat-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(page.locator('.payment-stat-columns')).to_have_count(0)
    expect(grid).to_have_attribute('aria-busy', 'false', timeout=30000)
    after = grid.bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)


def test_home_keeps_its_tiles_while_the_todo_read_is_in_flight(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m03/notice-list?*', lambda route: held.append(route))
    page.goto(server + '/preview', wait_until='domcontentloaded')
    expect(page.locator('.home-todos')).to_be_visible()
    assert held, 'The actual todo read was not held'

    # The tiles keep their shape, but no count is invented while reading.
    expect(page.locator('.home-tile')).to_have_count(3)
    expect(page.locator('.home-tile-count-reading')).to_have_count(3)
    expect(page.locator('.home-read-lane [role=status]')).to_have_count(1)
    before = page.locator('.home-todos').bounding_box()
    for route in held:
        route.continue_()
    page.unroute('**/api/m03/notice-list?*')

    expect(page.locator('.home-tile-count-reading')).to_have_count(0)
    expect(page.locator('.home-read-lane [role=status]')).to_have_count(0)
    expect(page.locator('.home-tile-count').first).to_have_text(re.compile(r'^\d+$'))
    after = page.locator('.home-todos').bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)
