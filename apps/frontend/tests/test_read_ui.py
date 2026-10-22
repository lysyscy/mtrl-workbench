"""B: read interactions; synthetic server plus delayed read responses only."""
from playwright.sync_api import expect
from test_preview import server, browser_page, login


def test_projects_input_debounces_and_waits_for_chinese_composition(server, browser_page):
    page, _ = browser_page
    login(page, server)
    expect(page.get_by_role('button', name='刷新', exact=True)).to_have_count(0)
    expect(page.get_by_role('button', name='查询', exact=True)).to_have_count(0)
    reads = []
    page.on('request', lambda request: reads.append(request.url) if '/api/m01/projects?' in request.url else None)
    field = page.get_by_label('项目', exact=True)
    field.dispatch_event('compositionstart')
    field.fill('ge')
    page.wait_for_timeout(400)
    assert reads == [], reads
    field.fill('隔离')
    field.dispatch_event('compositionend', {'data': '隔离'})
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    page.wait_for_function("performance.getEntriesByType('resource').some(e => e.name.includes('keyword=%E9%9A%94%E7%A6%BB'))")
    assert len(reads) == 1, reads
    reads.clear()
    field.fill('不'); field.fill('不存在'); field.fill('不存在的项目')
    expect(page.get_by_text('没有符合条件的项目。可调整状态或关键词。', exact=True)).to_be_visible()
    assert len(reads) == 1, reads
    before = len(reads)
    page.wait_for_timeout(850)
    assert len(reads) == before
    field.fill('')
    expect(page.get_by_role('cell', name='隔离项目', exact=True)).to_be_visible()
    page.get_by_label('状态', exact=True).select_option('archived')
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()


def test_projects_old_success_and_failure_do_not_replace_new_filter(server, browser_page):
    page, _ = browser_page
    login(page, server)
    pending = []
    page.route('**/api/m01/projects?**keyword=older**', lambda route: pending.append(route))
    field = page.get_by_label('项目', exact=True)
    field.fill('older')
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    assert pending
    field.fill('长项目名验收')
    expect(page.get_by_role('cell', name='长项目名验收', exact=True)).to_be_visible()
    pending.pop().fulfill(status=500, json={'message':'旧筛选迟到失败'})
    expect(page.get_by_text('旧筛选迟到失败', exact=True)).to_have_count(0)
    expect(page.get_by_role('cell', name='长项目名验收', exact=True)).to_be_visible()
    field.fill('older')
    expect(page.get_by_text('正在读取项目…', exact=True)).to_be_visible()
    assert pending
    page.get_by_label('状态', exact=True).select_option('archived')
    field.fill('')
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
    pending.pop(0).fulfill(status=200, json=[])
    expect(page.get_by_role('cell', name='归档样例', exact=True)).to_be_visible()
