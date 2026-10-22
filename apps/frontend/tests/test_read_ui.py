"""B: read interactions; synthetic server plus delayed read responses only."""
from playwright.sync_api import expect
from test_preview import server, browser_page, login
from test_ledger import open_ledger
from tools.audit.workspace_paths import output


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


def test_picker_and_both_export_scopes_show_only_display_name_with_safe_fallback(server, browser_page):
    page, _ = browser_page
    def names(route):
        response = route.fetch()
        projects = response.json()
        for project in projects:
            project['name_full'] = '不可泄露全名'
            if project['disp'] == '长项目名验收': project['disp'] = '   '
        route.fulfill(response=response, json=projects)
    page.route('**/api/m01/projects?**', names)
    open_ledger(page, server)
    picker = page.get_by_role('button', name='选择项目', exact=True)
    picker.click()
    candidates = page.get_by_role('group', name='查看项目候选')
    expect(candidates.get_by_role('button', name='隔离项目', exact=True)).to_be_visible()
    assert candidates.locator('label>span').evaluate('e=>e.getBoundingClientRect().height<=e.nextElementSibling.getBoundingClientRect().height')
    expect(candidates.get_by_role('button', name='未设置展示名', exact=True)).to_be_visible()
    assert '仓库' not in candidates.inner_text() and '不可泄露' not in candidates.inner_text()
    page.screenshot(path=str(output('b-picker-display-only.png',kind='screenshots')),full_page=True)
    candidates.get_by_role('button', name='未设置展示名', exact=True).click()
    expect(candidates).to_have_count(0)
    expect(picker).to_contain_text('未设置展示名')
    picker.click()
    candidates.get_by_role('button', name='隔离项目', exact=True).click()
    for title in ['逐月台账导出', '总欠款汇总导出']:
        page.get_by_role('button', name=title+'…', exact=True).click()
        dialog=page.get_by_role('dialog', name=title, exact=True)
        dialog.get_by_role('button', name='☐ 未设置展示名', exact=True).click()
        dialog.get_by_role('button', name='确认清单', exact=True).click()
        assert dialog.locator('tbody tr td:nth-child(2)').all_text_contents() == ['隔离项目','未设置展示名']
        dialog.get_by_role('button', name='上移未设置展示名', exact=True).click()
        assert dialog.locator('tbody tr td:nth-child(2)').all_text_contents() == ['未设置展示名','隔离项目']
        assert '不可泄露' not in dialog.inner_text() and '仓库' not in dialog.inner_text()
        page.screenshot(path=str(output('b-display-only-'+('ledger' if title=='逐月台账导出' else 'debt')+'.png',kind='screenshots')),full_page=True)
        dialog.get_by_role('button', name='取消', exact=True).click()
    expect(picker).to_contain_text('隔离项目')


def test_type_labels_follow_legacy_semantic_colors_in_both_themes(server, browser_page):
    page, _ = browser_page
    def types(route):
        response = route.fetch()
        project = response.json()[0]
        route.fulfill(response=response, json=[dict(project, id=900+i, project_type=kind, disp=label) for i,(kind,label) in enumerate([('normal','隔离项目'),('shell','壳样例'),('small','小微样例')])])
    page.route('**/api/m01/projects?**', types)
    for account,width in [('preview-admin',1440),('preview-user',800)]:
        login(page, server, account)
        page.set_viewport_size({'width':width,'height':1000})
        for kind,label,tone in [('normal','普通项目','in'),('shell','小微壳','vi'),('small','具体小微','wn')]:
            badge=page.locator('.project-type-'+kind)
            expect(badge).to_have_text(label)
            assert badge.evaluate("(e,tone)=>{const probe=document.createElement('span');probe.style.color='var(--'+tone+'-d)';document.body.append(probe);const expected=getComputedStyle(probe).color;probe.remove();return getComputedStyle(e).color===expected}", tone)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(output('b-projects-'+account+'.png',kind='screenshots')),full_page=True)
