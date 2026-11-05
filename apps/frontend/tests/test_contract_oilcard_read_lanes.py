"""Contract and oilcard reads report inside their own region.

A first or failed read keeps the region's reserved box, is announced once, and is
never shown as a real empty result or as a real zero. The page shell, its toolbar
and its tabs stay usable meanwhile.
"""

from playwright.sync_api import expect

from live_data import contract_sample, open_page
from test_preview import browser_page, login, server  # noqa: F401 (fixtures)


def test_contract_list_keeps_its_reserved_box_while_the_first_read_lands(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m11/list', lambda route: held.append(route))
    page.goto(server + '/preview/contracts', wait_until='domcontentloaded')

    # Wait for the lane to report the read instead of guessing how long mounting takes.
    expect(page.locator('.contract-read-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, 'The actual first contract read was not held'

    # The page publishes and its toolbar is usable while the list read is in flight.
    expect(page.locator('#page-title')).to_have_text('集采台账')
    expect(page.locator('.page-loading')).to_have_count(0)
    expect(page.get_by_label('搜索', exact=True)).to_be_enabled()

    # A running read is announced once, and it is not an empty table.
    expect(page.locator('.contract-read-status [role=status]')).to_have_count(1)
    expect(page.locator('.contracts-grid.contract-read-reserve .read-placeholder')).to_have_count(1)
    expect(page.locator('.contracts-grid .ag-root')).to_have_count(0)
    # An unread list is not a list of zero contracts.
    count = page.locator('.contract-filter-count')
    expect(count).to_contain_text('正在读取…')
    expect(count).not_to_contain_text('显示 0 条')
    before = page.locator('.contracts-grid').bounding_box()

    for route in held:
        route.continue_()
    page.unroute('**/api/m11/list')

    expect(page.locator('.contracts-grid .ag-root')).to_have_count(1)
    after = page.locator('.contracts-grid').bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)
    expect(page.locator('.contract-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.contract-read-reserve')).to_have_count(0)
    # The real count replaces the unread wording once the list is there.
    expect(count).to_contain_text('显示')
    expect(count).not_to_contain_text('正在读取…')


def test_contract_list_failure_reports_in_place_and_is_not_an_empty_table(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.route('**/api/m11/list', lambda route: route.fulfill(status=503, content_type='application/json', body='{"detail": "合同读取暂时失败"}'))
    page.goto(server + '/preview/contracts', wait_until='domcontentloaded')
    expect(page.locator('#page-title')).to_have_text('集采台账')

    failure = page.locator('.contract-read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    # A failed read is neither a running read nor an empty result.
    expect(page.locator('.contract-read-status [role=status]')).to_have_count(0)
    expect(page.locator('.contracts-grid.contract-read-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(page.locator('.contracts-grid .ag-root')).to_have_count(0)
    expect(page.locator('.contract-filter-count')).not_to_contain_text('显示 0 条')


def test_contract_project_read_failure_is_announced_and_blocks_writes(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    # Hold only this page's project read: login already visited the project archive.
    page.route('**/api/m01/projects?*', lambda route: held.append(route))
    with page.expect_request('**/api/m01/projects?*'):
        page.goto(server + '/preview/contracts', wait_until='domcontentloaded')
    expect(page.locator('.contracts-grid .ag-root')).to_have_count(1)
    assert held, 'The actual project read was not held'

    # Necessary project data is not merged yet, so the writes that need it stay closed
    # rather than offering an action the page cannot complete.
    fetch = page.get_by_role('button', name='抓取采购合同信息', exact=True)
    create = page.get_by_role('button', name='＋ 手工新增合同', exact=True)
    expect(fetch).to_be_disabled()
    expect(create).to_be_disabled()

    for route in held:
        route.fulfill(status=503, content_type='application/json', body='{"detail": "项目清单暂时失败"}')
    page.unroute('**/api/m01/projects?*')

    lane = page.locator('.contract-read-status')
    expect(lane.locator('.notice')).to_have_count(1)
    expect(lane.locator('.notice')).to_contain_text('项目清单')
    expect(fetch).to_be_disabled()
    expect(create).to_be_disabled()


def test_contract_subtable_reads_inside_the_dialog_without_moving_the_summary(server, browser_page, api):
    page, _ = browser_page
    row, label = contract_sample(api)
    held = []
    page.route('**/api/m11/detail*', lambda route: held.append(route))
    # The real, already-covered subtable entry: search the list, then its named button.
    open_page(page, server, 'contracts', '集采台账')
    page.get_by_label('搜索', exact=True).fill(label)
    page.get_by_role('button', name=label + ' 付款子表', exact=True).click()
    modal = page.locator('.contract-subtable-dialog')
    expect(modal).to_be_visible()
    # Measure the open dialog, not a scaled frame of Ant Design's entrance motion.
    modal.locator('xpath=ancestor::div[contains(concat(" ", normalize-space(@class), " "), " ant-modal ")]').evaluate("async e => { await Promise.all(e.getAnimations({subtree:true}).filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))); }")
    expect(modal.locator('.subtable-read-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, 'The actual subtable read was not held'

    expect(modal.locator('.subtable-read-status [role=status]')).to_have_count(1)
    expect(modal.locator('.subtable-read-reserve .read-placeholder')).to_have_count(1)
    expect(modal.locator('.subtable-detail-scroll')).to_have_count(0)
    summary = modal.locator('.subtable-summary').bounding_box()
    reserved = modal.locator('.subtable-read-reserve').bounding_box()
    assert reserved['height'] > 100, reserved

    for route in held:
        route.continue_()
    page.unroute('**/api/m11/detail*')

    expect(modal.locator('.subtable-read-reserve')).to_have_count(0)
    expect(modal.locator('.subtable-detail-scroll')).to_have_count(1)
    landed = modal.locator('.subtable-summary').bounding_box()
    assert abs(landed['y'] - summary['y']) < 1, (summary, landed)
    expect(modal.locator('.subtable-read-status [role=status]')).to_have_count(0)


def test_oilcard_tabs_stay_usable_while_the_archive_read_lands(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m13/archives', lambda route: held.append(route))
    page.goto(server + '/preview/oilcard', wait_until='domcontentloaded')

    # The tab strip publishes and accepts a click while the archive read is in flight.
    expect(page.locator('#page-title')).to_have_text('油卡管理')
    expect(page.locator('.page-loading')).to_have_count(0)
    archives_tab = page.get_by_role('tab', name='账户与油卡', exact=True)
    expect(archives_tab).to_be_enabled()
    archives_tab.click()
    expect(archives_tab).to_have_attribute('aria-selected', 'true')
    # The page reports the unread archive once, in its own lane.
    expect(page.locator('.oilcard-page > .read-status[data-read-phase="reading"]')).to_have_count(1, timeout=20000)
    expect(page.locator('.oilcard-page > .read-status [role=status]')).to_have_count(1)
    assert held, 'The actual first archive read was not held'

    # The unread archive replaces only the pane content, and it is not an empty account list.
    panel = page.locator('#oilcard-panel-archives:not([hidden])')
    expect(panel).to_have_count(1)
    expect(panel.locator('.oilcard-read-reserve .read-placeholder')).to_have_count(2)
    # Section headings can appear immediately; no business empty-state conclusion is invented.
    expect(page.get_by_text('尚无符合条件的用卡账户。')).to_have_count(0)
    before = [heading.bounding_box() for heading in panel.get_by_role('heading').all()]

    for route in held:
        route.continue_()
    page.unroute('**/api/m13/archives')

    panel = page.locator('#oilcard-panel-archives:not([hidden])')
    expect(panel).to_have_count(1)
    expect(panel.locator('.read-reserve')).to_have_count(0)
    expect(panel.get_by_role('status')).to_have_count(0)
    after = [heading.bounding_box() for heading in panel.get_by_role('heading').all()]
    assert len(before) == len(after) == 2
    assert all(abs(a['y'] - b['y']) < 1 for a, b in zip(before, after)), (before, after)


def test_oilcard_successful_archive_remains_readable_when_projects_fail(server, browser_page):
    page, _ = browser_page
    login(page, server)
    page.route('**/api/m01/projects?status=all&keyword=', lambda route: route.fulfill(
        status=503, content_type='application/json', body='{"detail":"项目清单暂时失败"}'))
    page.goto(server + '/preview/oilcard', wait_until='domcontentloaded')
    expect(page.locator('.oilcard-page > .read-status .notice')).to_contain_text('读取失败')
    overview = page.locator('#oilcard-panel-overview')
    expect(overview.locator('.oilcard-read-reserve')).to_have_count(0, timeout=30000)
    page.get_by_role('tab', name='账户与油卡', exact=True).click()
    archives = page.locator('#oilcard-panel-archives')
    expect(archives.locator('.oilcard-read-reserve')).to_have_count(0, timeout=30000)
    expect(archives.get_by_role('button', name='新增账户', exact=True)).to_be_disabled()
    expect(archives.get_by_role('button', name='新增油卡', exact=True)).to_be_disabled()


def test_oilcard_reconciliation_failure_keeps_its_box_and_is_not_an_empty_account_list(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    # The overview tab reads its own totals once the archive and project lists are there.
    page.route('**/api/m13/reconciliation', lambda route: held.append(route))
    page.goto(server + '/preview/oilcard', wait_until='domcontentloaded')
    expect(page.locator('#page-title')).to_have_text('油卡管理')
    expect(page.get_by_role('tab', name='账户核对', exact=True)).to_have_attribute('aria-selected', 'true')

    overview = page.locator('#oilcard-panel-overview')
    expect(overview.locator('.read-status')).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, 'The actual reconciliation read was not held'
    before = overview.locator('.oilcard-read-reserve').bounding_box()

    for route in held:
        route.fulfill(status=503, content_type='application/json', body='{"detail": "账户累计暂时失败"}')
    page.unroute('**/api/m13/reconciliation')

    # The failed region keeps its own box and offers its own retry; it is not "no accounts".
    failure = overview.locator('.read-status .notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重读账户累计', exact=True)).to_be_visible()
    expect(overview.locator('.oilcard-read-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(overview.get_by_text('尚无符合条件的用卡账户。')).to_have_count(0)
    expect(overview.get_by_role('heading', name='充值与开票核对', exact=True)).to_be_visible()
    # Reporting the failure in the lane does not push the table area down.
    after = overview.locator('.oilcard-read-reserve').bounding_box()
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)
