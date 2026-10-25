"""Local project filters keep input while whole-list reads finish or retry."""
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from preview_select import pick_option


def test_projects_local_filters_keep_chinese_input_without_requests(server, browser_page):
    page, _ = browser_page
    login(page, server)
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='刷新', exact=True)).to_have_count(0)
    expect(page.get_by_role('button', name='查询', exact=True)).to_have_count(0)
    reads = []
    page.on('request', lambda request: reads.append(request.url) if '/api/m01/projects?' in request.url else None)
    field = page.get_by_label('项目搜索', exact=True)
    field.dispatch_event('compositionstart')
    field.fill('ge')
    expect(field).to_have_value('ge')
    field.fill('隔离')
    field.dispatch_event('compositionend', {'data': '隔离'})
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    field.fill('不'); field.fill('不存在'); field.fill('不存在的项目')
    expect(page.get_by_text('没有符合条件的项目。可调整筛选，或手工建档、同步名单。', exact=True)).to_be_visible()
    field.fill('')
    pick_option(page, '项目状态筛选', '归档')
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
    assert reads == [], reads


def test_projects_filters_survive_delayed_read_failure_and_retry(server, browser_page):
    page, _ = browser_page
    login(page, server)
    rows = page.request.get(server + '/api/m01/projects?status=all').json()
    pending = []
    page.route('**/api/m01/projects?status=all', lambda route: pending.append(route))
    page.reload()
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    field = page.get_by_label('项目搜索', exact=True)
    field.fill('older'); field.fill('长项目名验收')
    assert pending
    pending.pop(0).fulfill(status=200, json=rows)
    expect(page.get_by_role('cell', name='长项目名验收', exact=True)).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_have_count(0)
    page.reload()
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    field = page.get_by_label('项目搜索', exact=True)
    field.fill('长项目名验收')
    assert pending
    pending.pop(0).fulfill(status=500, json={'message': '项目重读失败样例'})
    expect(page.get_by_text('项目重读失败样例', exact=False)).to_be_visible()
    expect(field).to_have_value('长项目名验收')
    page.get_by_role('button', name='重读项目', exact=True).click()
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    assert pending
    pending.pop(0).fulfill(status=200, json=rows)
    expect(page.get_by_role('cell', name='长项目名验收', exact=True)).to_be_visible()
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_have_count(0)
