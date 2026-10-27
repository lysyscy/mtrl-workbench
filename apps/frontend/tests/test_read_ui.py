"""Real project filtering, composition and delayed-read continuity."""
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
