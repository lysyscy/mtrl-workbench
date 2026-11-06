"""Reports and maintenance pages report their own read in place.

Each region announces a pending read without adding a visible line. A failure
appears near its reserved box or retained result and offers a retry. Neither
state stands in for a real empty result or a real zero count. Controls that need
the read stay disabled while it is unknown. Other controls stay usable.
"""
from playwright.sync_api import expect

from test_preview import server, browser_page, login  # noqa: F401 (fixtures)


HELD = '**/api/m07/big?*'


def hold(page, pattern):
    held = []
    page.route(pattern, lambda route: held.append(route))
    return held


def fail_held(held, detail):
    for route in held:
        route.fulfill(status=503, content_type='application/json',
                      body='{"detail": "%s"}' % detail)


def release_held(held):
    for route in held:
        route.continue_()


def test_big_month_read_keeps_its_reserved_table_box(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = hold(page, HELD)
    page.locator('a[href="/preview/big"]').click()
    expect(page.locator('#page-title')).to_have_text('月度会大表')
    month = page.locator('.big-month:not([hidden])')
    expect(month).to_be_visible()
    expect(month.locator('.big-read-reserve')).to_be_visible()
    assert held, 'The actual first month read was not held'

    # The month filter is published and the page is not held by the local read.
    expect(page.get_by_label('大表核算月', exact=True)).to_be_visible()
    expect(page.locator('.page-loading')).to_have_count(0)
    # One running read is announced once, in its own lane, over a reserved box.
    expect(page.locator('.big-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.big-read-reserve .read-placeholder')).to_have_count(1)
    # Nothing was read: no project count is invented, the count slot says so instead of showing 0.
    expect(month.locator('.big-count')).to_have_text('正在读取项目数…')
    expect(month.locator('.big-count')).not_to_contain_text('0 个项目')
    expect(month.locator('.big-grid:not(.big-read-reserve)')).to_have_count(0)
    # A control that needs the list stays disabled instead of acting on an unknown.
    expect(month.get_by_role('button', name='选择项目与排序…', exact=True)).to_be_disabled()
    assert page.locator('.big-read-status').bounding_box() is None
    reading_box = page.locator('.big-read-reserve').bounding_box()

    fail_held(held, '大表读取暂时失败')
    page.unroute(HELD)
    failure = page.locator('.big-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed read is neither a running read nor an empty table.
    expect(page.locator('.big-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.big-read-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(month.locator('.big-count')).to_have_text('项目数尚未读取')
    alert = failure.bounding_box()
    failed_box = page.locator('.big-read-reserve').bounding_box()
    assert failed_box['y'] >= alert['y'] + alert['height'] - 1, (alert, failed_box)
    assert abs(failed_box['height'] - reading_box['height']) < 1, (reading_box, failed_box)

    failure.get_by_role('button', name='重试读取').click()
    grid = month.locator('.big-grid:not(.big-read-reserve)')
    expect(grid).to_be_visible(timeout=30000)
    expect(page.locator('.big-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.big-read-reserve')).to_have_count(0)
    expect(page.locator('.big-read-status .notice')).to_have_count(0)
    expect(month.locator('.big-count')).to_contain_text('个项目')


def test_settlement_month_read_failure_reports_in_place(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = hold(page, '**/api/m07/settlement?*')
    page.locator('a[href="/preview/settlement"]').click()
    expect(page.locator('#page-title')).to_have_text('收发结存与提取')
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve')).to_be_visible()
    assert held, 'The actual settlement read was not held'

    expect(page.locator('.page-loading')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve .read-placeholder')).to_have_count(1)
    # No summary line and no table are invented before the month is known.
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-summary')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-grid:not(.settlement-read-reserve)')).to_have_count(0)
    before = page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve').bounding_box()

    fail_held(held, '收发结存读取暂时失败')
    page.unroute('**/api/m07/settlement?*')
    failure = page.locator('.settlement-page > div:not([hidden]) .settlement-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve .read-placeholder-quiet')).to_have_count(1)
    after = page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve').bounding_box()
    alert = failure.bounding_box()
    assert after['y'] >= alert['y'] + alert['height'] - 1, (alert, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)

    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-summary')).to_be_visible(timeout=30000)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-grid')).to_be_visible()


def test_settlement_switching_the_month_drops_the_previous_month(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.locator('a[href="/preview/settlement"]').click()
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-grid')).to_have_attribute('aria-busy', 'false', timeout=30000)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-summary')).to_be_visible()

    # A new month is a different read: the old month's summary and rows leave the
    # screen at once and the reserved box waits for the matching result.
    held = hold(page, '**/api/m07/settlement?*')
    field = page.get_by_label('收发结存核算月', exact=True)
    field.fill('2020-01')
    field.press('Enter')
    expect(page.locator('.ant-picker-dropdown:visible')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve')).to_be_visible()
    assert held, 'The read for the new month was not issued'
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-summary')).to_have_count(0)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve .read-placeholder')).to_have_count(1)

    release_held(held)
    page.unroute('**/api/m07/settlement?*')
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve')).to_have_count(0, timeout=30000)
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-summary')).to_contain_text('2020-01')


def test_settlement_extract_read_failure_is_not_an_empty_year(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.locator('a[href="/preview/settlement"]').click()
    page.get_by_text('焊材 / 气体提取', exact=True).click()
    expect(page.get_by_role('region', name='焊材年度汇总', exact=True)).to_be_visible(timeout=30000)

    # A new year is a different read; failing it must not read as "no rows".
    page.route('**/api/m07/extract-screen?*', lambda route: route.fulfill(
        status=503, content_type='application/json', body='{"detail": "年度汇总读取暂时失败"}'))
    field = page.get_by_label('提取年份', exact=True)
    field.fill('2020')
    field.press('Enter')
    expect(page.locator('.ant-picker-dropdown:visible')).to_have_count(0)
    failure = page.locator('.settlement-page > div:not([hidden]) .settlement-read-status .notice').first
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.settlement-page > div:not([hidden]) .settlement-read-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(page.get_by_role('region', name='焊材年度汇总', exact=True)).to_have_count(0)


def test_fees_switching_the_year_keeps_no_previous_amounts(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.locator('a[href="/preview/fees"]').click()
    expect(page.get_by_label('特殊费用年度表', exact=True)).to_be_visible(timeout=30000)

    held = hold(page, '**/api/m09/fee/year?*')
    field = page.get_by_label('费用年份', exact=True)
    field.fill('2020')
    field.press('Enter')
    field.press('Escape')
    expect(page.locator('.ant-picker-dropdown:visible')).to_have_count(0)
    expect(page.locator('.fees-read-reserve')).to_be_visible()
    assert held, 'The read for the new year was not issued'
    # The previous year's table and totals are gone while the new year is unknown.
    expect(page.get_by_label('特殊费用年度表', exact=True)).to_have_count(0)
    expect(page.locator('.fees-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.fees-read-reserve .read-placeholder')).to_have_count(1)
    # Editing controls that need the year's rows stay unavailable.
    expect(page.get_by_role('button', name='增加手填项', exact=True)).to_be_disabled()

    release_held(held)
    page.unroute('**/api/m09/fee/year?*')
    expect(page.get_by_label('特殊费用年度表', exact=True)).to_be_visible(timeout=30000)
    expect(page.locator('.fees-read-reserve')).to_have_count(0)
    expect(page.locator('.fees-read-status [role=status]')).to_have_count(0)


def test_users_list_reports_its_own_read_and_gates_the_actions(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = hold(page, '**/api/m15/users')
    page.locator('a[href="/preview/users"]').click()
    expect(page.locator('#page-title')).to_have_text('用户管理')
    expect(page.locator('.users-read-reserve')).to_be_visible()
    assert held, 'The actual account list read was not held'

    expect(page.locator('.page-loading')).to_have_count(0)
    expect(page.locator('.users-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.users-read-reserve .read-placeholder')).to_have_count(1)
    # Counts and rows are unknown: neither a zero count nor a table appears.
    expect(page.locator('.users-count')).to_have_count(0)
    expect(page.locator('.users-table:not(.users-read-reserve)')).to_have_count(0)
    # An action that needs the roster stays unavailable.
    expect(page.get_by_role('button', name='＋ 新增账号', exact=True)).to_be_disabled()
    before = page.locator('.users-read-reserve').bounding_box()

    fail_held(held, '账号列表读取暂时失败')
    page.unroute('**/api/m15/users')
    failure = page.locator('.users-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.users-read-status [role=status]')).to_have_count(0)
    after = page.locator('.users-read-reserve').bounding_box()
    alert = failure.bounding_box()
    assert after['y'] >= alert['y'] + alert['height'] - 1, (alert, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)

    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.users-count')).to_have_count(1, timeout=30000)
    expect(page.locator('.users-read-reserve')).to_have_count(0)
    expect(page.locator('.users-table')).to_have_count(1)


def test_rules_blocks_read_independently_and_report_in_place(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.route('**/api/m14/rules', lambda route: route.fulfill(
        status=503, content_type='application/json', body='{"detail": "剔除规则读取暂时失败"}'))
    page.locator('a[href="/preview/rules"]').click()
    expect(page.locator('#page-title')).to_have_text('规则配置')

    blocks = page.locator('.rules-block')
    expect(blocks).to_have_count(3)
    first = blocks.first
    failure = first.locator('.rules-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(first.locator('.rules-read-reserve .read-placeholder-quiet')).to_have_count(1)
    # The failed block does not hold the other two lists back.
    expect(blocks.nth(1).locator('.rules-read-reserve')).to_have_count(0, timeout=30000)
    expect(blocks.nth(2).locator('.rules-read-reserve')).to_have_count(0, timeout=30000)
    # Adding a rule needs the kinds that the failed read would have supplied.
    expect(first.get_by_role('button', name='＋ 增加规则', exact=True)).to_be_disabled()

    page.unroute('**/api/m14/rules')
    failure.get_by_role('button', name='重试读取').click()
    expect(first.locator('.rules-read-reserve')).to_have_count(0, timeout=30000)
    expect(first.locator('.rules-read-status .notice')).to_have_count(0)


def test_projects_export_waits_for_real_publication_after_a_failed_read(server, browser_page):
    page, _ = browser_page
    pending = hold(page, '**/api/m01/promote-pending')
    page.route('**/api/m01/projects?status=all', lambda route: route.fulfill(
        status=503, content_type='application/json', body='{"detail":"项目读取暂时失败"}'))
    login(page, server)
    failure = page.locator('.project-read-status .notice')
    expect(failure).to_be_visible()
    page.unroute('**/api/m01/projects?status=all')
    with page.expect_response(lambda response: '/api/m01/projects?status=all' in response.url and response.ok):
        failure.get_by_role('button', name='重试读取').click()
    expect(failure).to_have_count(0)
    export = page.get_by_role('button', name='导出 Excel', exact=True)
    expect(export).to_be_disabled()
    assert pending, '未覆盖可选待办仍在读取时的导出门控'
    for route in pending:
        route.fulfill(response=route.fetch())
    page.unroute('**/api/m01/promote-pending')
    expect(page.get_by_role('region', name='项目列表', exact=True)).to_be_visible(timeout=30000)
    expect(export).to_be_enabled()


def test_projects_first_read_publishes_the_page_and_keeps_the_list_box(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = hold(page, '**/api/m01/projects?status=all')
    page.reload()
    expect(page.locator('#page-title')).to_have_text('项目档案')
    expect(page.locator('.project-first-reserve')).to_be_visible()
    assert held, 'The actual project list read was not held'

    # The page is published with usable filters, not held by its list read.
    expect(page.locator('.page-loading')).to_have_count(0)
    expect(page.locator('.project-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.project-first-reserve .read-placeholder')).to_have_count(1)
    expect(page.get_by_label('项目搜索', exact=True)).to_be_enabled()
    # The count line, the table and the export are not invented before the read.
    expect(page.locator('.projects-page .result')).to_have_count(0)
    expect(page.locator('.project-table:not(.project-read-reserve)')).to_have_count(0)
    expect(page.get_by_role('button', name='导出 Excel', exact=True)).to_be_disabled()
    before = page.locator('.project-first-reserve').bounding_box()

    fail_held(held, '项目档案读取暂时失败')
    page.unroute('**/api/m01/projects?status=all')
    failure = page.locator('.project-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.projects-page .result')).to_have_count(0)
    after = page.locator('.project-first-reserve').bounding_box()
    alert = failure.bounding_box()
    assert after['y'] >= alert['y'] + alert['height'] - 1, (alert, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)

    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.projects-page .result')).to_have_count(1, timeout=30000)
    expect(page.locator('.project-read-reserve')).to_have_count(0)
    expect(page.locator('.project-table')).to_have_count(1)
