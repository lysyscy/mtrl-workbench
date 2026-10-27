"""First painted UI uses ready fonts/theme; real-copy reads only."""
import json
import pytest
from pathlib import Path
from playwright.sync_api import expect
from test_preview import server, browser_page, login


def test_first_page_waits_for_fonts_and_return_keeps_page(server, browser_page, real_preview):
    page, context = browser_page
    login(page, server)
    delayed, held = [], []
    def slow_font(route):
        if not delayed:
            delayed.append(route.request.url)
            held.append(route)
        else:
            route.continue_()
    context.route('**/static/fonts/**/*.woff2', slow_font)
    page.add_init_script("""window.__firstPaint=[];function sample(){
      const page=document.querySelector('.page-view:not([hidden])');
      const title=document.querySelector('#page-title');
      if(page && title && getComputedStyle(page).visibility!=='hidden' && page.getBoundingClientRect().width){
        const walker=document.createTreeWalker(page,NodeFilter.SHOW_TEXT);let ready=true;
        while(walker.nextNode()){
          const node=walker.currentNode,parent=node.parentElement;
          if(!parent || !node.textContent.trim() || parent.closest('style,script,[hidden]') || !parent.checkVisibility({checkVisibilityCSS:true}))continue;
          ready &&= document.fonts.check(getComputedStyle(parent).fontWeight+' 14px MiSans',node.textContent);
        }
        window.__firstPaint.push({at:performance.now(),ready});
      }
      window.__paintFrame=requestAnimationFrame(sample);
    }requestAnimationFrame(sample);""")
    try:
        with page.expect_request('**/api/m03/notice-list?*', timeout=10000):
            page.goto(server + '/preview/notices', wait_until='domcontentloaded')
        assert held, 'Cold-font condition was not exercised'
        assert not page.get_by_role('region', name='付款通知书列表', exact=True).is_visible()
    finally:
        for route in held: route.continue_()
        context.unroute('**/static/fonts/**/*.woff2')
    expect(page.get_by_role('region',name='付款通知书列表',exact=True)).to_be_visible()
    page.wait_for_function('window.__firstPaint.length > 3')
    samples=page.evaluate('window.__firstPaint')
    assert all(sample['ready'] for sample in samples), samples[:12]
    assert delayed, 'Cold-font condition was not exercised'
    timing = page.evaluate("performance.getEntriesByType('resource').map(e=>({name:e.name,start:e.startTime,end:e.responseEnd}))")
    font = next(entry for entry in timing if entry['name'] == delayed[0])
    data = next(entry for entry in timing if '/api/m03/notice-list?' in entry['name'])
    assert data['start'] < font['end'], 'First data read waited behind the font download'
    (Path(real_preview[0]).parent / 'startup-style-first-frame.json').write_text(json.dumps({
        'product_digest': real_preview[1]['product_digest'], 'font_released_after': 'first business data request',
        'held_font_duration_ms': font['end'] - font['start'],
        'first_visible_frame_ms': samples[0]['at'], 'visible_frames_checked': len(samples),
        'visible_frames_with_unready_fonts': sum(not sample['ready'] for sample in samples),
        'data_request_start_ms': data['start'], 'delayed_font_response_ms': font['end'],
        'note': 'Browser navigation timing with a held font until the data request; not a production TTI benchmark.'
    }, indent=2), encoding='utf-8')
    page.get_by_role('link',name='项目档案',exact=True).click()
    expect(page.locator('#page-title')).to_have_text('项目档案')
    page.get_by_role('link',name='付款通知书',exact=True).click()
    expect(page.get_by_role('region',name='付款通知书列表',exact=True)).to_be_visible()
    assert page.locator('.page-view:not([hidden])').evaluate("e=>getComputedStyle(e).visibility") == 'visible'


def test_font_failure_has_retry_and_theme_is_not_reloaded_after_identity(server,browser_page):
    page, context = browser_page
    login(page,server)
    theme=[]
    page.on('request',lambda request: theme.append(request.url) if '/static/theme.css' in request.url else None)
    context.route('**/static/fonts/**/*.woff2',lambda route:route.abort('failed'))
    page.goto(server + '/preview/notices')
    expect(page.locator('.page-loading[role=alert]')).to_contain_text('字体')
    context.unroute('**/static/fonts/**/*.woff2')
    assert len(theme)==1, theme
    page.get_by_role('button',name='重试字体加载',exact=True).click()
    expect(page.get_by_role('region',name='付款通知书列表',exact=True)).to_be_visible()
    assert len(theme)==2, theme


def test_shared_style_entry_and_first_display_cover_every_route(server, browser_page):
    page, _ = browser_page
    me = login(page, server)
    css_requests = []
    page.on('request', lambda request: css_requests.append(request.url) if '/preview/assets/' in request.url and request.url.endswith('.css') else None)
    for title in ['首页', 'i8 接入层', '付款通知书', '欠款台账', '付款流水', '集采台账', '过程资料', '收发结存与提取', '月度会大表', '库存单据与调整单', '特殊费用', '机械费', '规则配置', '用户管理', '项目档案']:
        page.get_by_role('link', name=title, exact=True).click()
        expect(page.locator('#page-title')).to_have_text(title)
        expect(page.locator('.page-view:not([hidden])')).to_be_visible(timeout=15000)
        expect(page.locator('.page-loading')).to_have_count(0)
        assert page.locator('html').evaluate("e=>getComputedStyle(e).getPropertyValue('--fscale').trim()") == me['ui_scale_css']
    assert not css_requests, css_requests


def test_debt_tables_publish_without_waiting_for_the_other_side(server, browser_page):
    page, _ = browser_page
    login(page, server)
    # Hold one real font dependency, without replacing any business response or geometry.
    page.add_init_script("""const load = document.fonts.load.bind(document.fonts);
      window.__sideFontHeld = false;
      const release = new Promise(resolve => { window.__releaseSideFont = resolve; });
      document.fonts.load = async (font, text) => {
        if (text?.includes('机械结算金额')) { window.__sideFontHeld = true; await release; }
        return load(font, text);
      };""")
    page.goto(server + '/preview/debt', wait_until='domcontentloaded')
    page.wait_for_function('window.__sideFontHeld')
    material = page.locator('[data-ledger-side=material] .ledger-grid')
    mechanical = page.locator('[data-ledger-side=mechanical] .ledger-grid')
    expect(material).to_be_visible()
    expect(mechanical).to_be_hidden()
    project = page.get_by_role('combobox', name='选择项目', exact=True)
    project.click()
    expect(project).to_be_focused()
    page.keyboard.press('Escape')
    before = mechanical.bounding_box()
    page.evaluate('window.__releaseSideFont()')
    expect(mechanical).to_be_visible()
    assert mechanical.bounding_box() == before, 'Revealing the side changed its allocated table box'
    field = mechanical.locator('[col-id=remark] input').first
    field.click()
    expect(field).to_be_focused()


def test_notice_tools_are_usable_while_first_data_is_pending(server, browser_page):
    page, _ = browser_page
    login(page, server)
    held = []
    page.route('**/api/m03/notice-list?*', lambda route: held.append(route))
    page.goto(server + '/preview/notices', wait_until='domcontentloaded')
    search = page.get_by_role('searchbox', name='通知书搜索', exact=True)
    search.click()
    expect(search).to_be_focused()
    assert held, 'The actual first data request was not held'
    expect(page.get_by_role('button', name='手动新增', exact=True)).to_be_disabled()
    expect(page.get_by_role('region', name='付款通知书列表', exact=True)).to_have_count(0)
    before = page.locator('.notice-grid').bounding_box()
    for route in held:
        route.continue_()
    page.unroute('**/api/m03/notice-list?*')
    table = page.get_by_role('region', name='付款通知书列表', exact=True)
    expect(table).to_be_visible()
    assert table.bounding_box() == before, 'First table publication changed its reserved box'
    expect(search).to_be_focused()


def test_fee_tools_publish_while_first_fee_data_is_pending(server,browser_page):
    page,_=browser_page;login(page,server);held=[]
    page.route('**/api/m09/fee/year?*',lambda route:held.append(route))
    try:
        with page.expect_request('**/api/m09/fee/year?*'):
            page.get_by_role('link',name='特殊费用',exact=True).click()
        expect(page.get_by_label('费用年份',exact=True)).to_be_visible()
        expect(page.get_by_label('费用年份',exact=True)).to_be_enabled()
        assert held
        assert not page.locator('.fees-grid').count()
    finally:
        for route in held:route.continue_()
        page.unroute('**/api/m09/fee/year?*')
    expect(page.locator('.fees-grid')).to_have_attribute('data-layout-state','ready')


def test_process_module_does_not_wait_for_retained_i8_read(server,browser_page):
    page,_=browser_page;login(page,server);held=[]
    page.route('**/api/m02/fetch/records*',lambda route:held.append(route))
    try:
        with page.expect_request('**/api/m02/fetch/records*'):
            page.get_by_role('link',name='i8 接入层',exact=True).click()
        page.get_by_role('link',name='过程资料',exact=True).click()
        expect(page.locator('.process-matrix')).to_be_visible()
        expect(page.get_by_label('过程资料项目',exact=True)).to_be_enabled()
        assert held
    finally:
        for route in held:route.continue_()
        page.unroute('**/api/m02/fetch/records*')


def test_inventory_does_not_wait_for_retained_i8_read(server,browser_page):
    page,_=browser_page;login(page,server);held=[]
    page.route('**/api/m02/fetch/records*',lambda route:held.append(route))
    try:
        with page.expect_request('**/api/m02/fetch/records*'):
            page.get_by_role('link',name='i8 接入层',exact=True).click()
        with page.expect_response('**/api/m08/inventory') as inventory:
            page.get_by_role('link',name='库存单据与调整单',exact=True).click()
        assert inventory.value.ok
        assert held, 'The unrelated local records read was not held'
        expect(page.get_by_role('button',name='库存核算期间',exact=True)).to_be_visible()
        expect(page.locator('.inventory-grid')).to_be_visible()
    finally:
        for route in held:route.continue_()
        page.unroute('**/api/m02/fetch/records*')


@pytest.mark.parametrize('read',['**/api/m08/inventory','**/api/m01/projects'])
def test_inventory_waits_for_its_own_first_reads(server,browser_page,read):
    page,_=browser_page;login(page,server);held=[]
    page.route(read,lambda route:held.append(route))
    try:
        with page.expect_request(read):
            page.get_by_role('link',name='库存单据与调整单',exact=True).click()
        expect(page.locator('.page-loading')).to_contain_text('库存')
        expect(page.get_by_role('button',name='库存核算期间',exact=True)).to_be_hidden()
        assert held
    finally:
        for route in held:route.continue_()
        page.unroute(read)
    expect(page.get_by_role('button',name='库存核算期间',exact=True)).to_be_visible()
    expect(page.locator('.inventory-grid')).to_be_visible()


def test_focus_burst_shares_verification_and_resumes_workspace(server,browser_page):
    page,_=browser_page
    login(page,server)
    expect(page.locator('.page-view:not([hidden])')).to_be_visible()
    held=[]
    page.route('**/api/m15/users',lambda route:held.append(route))
    try:
        with page.expect_request('**/api/m15/users'):
            page.evaluate("for(let i=0;i<5;i++)window.dispatchEvent(new Event('focus'))")
        expect(page.locator('.workspace')).to_have_attribute('inert','')
        assert len(held)==1,'Overlapping focus events started duplicate identity verifications'
    finally:
        for route in held:route.continue_()
        page.unroute('**/api/m15/users')
    expect(page.locator('.workspace')).not_to_have_attribute('inert','')
    expect(page.get_by_role('heading',name='项目档案',exact=True)).to_be_visible()


@pytest.mark.parametrize('target,title',[('projects','项目档案'),('','首页'),('i8','i8 接入层')])
def test_local_read_page_does_not_wait_for_unrelated_read(server,browser_page,target,title):
    page,_=browser_page;login(page,server);held=[]
    pattern='**/api/m01/trails?*' if target=='i8' else '**/api/m02/fetch/records*'
    page.route(pattern,lambda route:held.append(route))
    try:
        with page.expect_request(pattern):
            page.goto(server+'/preview/'+('projects' if target=='i8' else 'i8'),wait_until='domcontentloaded')
        page.get_by_role('link',name=title,exact=True).click()
        expect(page.locator('.page-view:not([hidden])')).to_be_visible()
        if target=='projects':expect(page.get_by_label('项目搜索',exact=True)).to_be_enabled()
        elif target=='i8':expect(page.get_by_role('region',name='各来源最近结果',exact=True)).to_be_visible()
        else:expect(page.locator('.home-todos')).to_be_visible()
        assert held
    finally:
        for route in held:route.continue_()
        page.unroute(pattern)
