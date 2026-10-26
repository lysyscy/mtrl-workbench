"""First painted UI uses ready fonts/theme; real-copy reads only."""
import json
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
          if(!parent || !node.textContent.trim() || parent.closest('style,script,[hidden]') || getComputedStyle(parent).display==='none')continue;
          ready &&= document.fonts.check(getComputedStyle(parent).fontWeight+' 14px MiSans',node.textContent);
        }
        window.__firstPaint.push({at:performance.now(),ready});
      }
      window.__paintFrame=requestAnimationFrame(sample);
    }requestAnimationFrame(sample);""")
    with page.expect_request('**/api/m03/notice-list?*', timeout=10000):
        page.goto(server + '/preview/notices', wait_until='domcontentloaded')
    assert held, 'Cold-font condition was not exercised'
    assert not page.locator('.page-view:not([hidden])').is_visible()
    for route in held:
        route.continue_()
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
    expect(page.get_by_role('alert').filter(has_text='字体')).to_be_visible()
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
