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
    with page.expect_request('**/api/m01/projects?status=all'):
        page.reload(wait_until='domcontentloaded')
    field = page.get_by_label('项目搜索', exact=True)
    field.fill(row['disp'])
    page.wait_for_function('document.readyState === "complete"')
    assert pending
    for route in pending: route.fulfill(response=route.fetch())
    page.unroute('**/api/m01/projects?status=all')
    expect(field).to_have_value(row['disp'])
    expect(page.get_by_label('展示名：'+row['disp'], exact=True)).to_be_visible()
