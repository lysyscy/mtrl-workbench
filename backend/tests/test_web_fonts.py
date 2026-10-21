"""Local font delivery and real Chromium glyph use; no business writes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.mod03_notice.page import render_theme
from app.mod15_user.page import login_html
from tests.ui_helpers import ui_page  # noqa: F401
from tools.audit.workspace_paths import output


FONTS = Path(__file__).resolve().parents[1] / 'app/web/fonts'


def test_font_assets_and_license_are_public_and_revalidated():
    with TestClient(create_app(), client=('127.0.0.1', 50123)) as client:
        for file in FONTS.iterdir():
            if file.suffix not in {'.woff2', '.pdf', '.txt'}:
                continue
            response = client.get('/static/fonts/' + file.name)
            assert response.status_code == 200
            assert response.content == file.read_bytes()
            if file.suffix == '.woff2':
                assert response.headers['content-type'] == 'font/woff2'
            assert client.get('/static/fonts/' + file.name, headers={
                'If-None-Match': response.headers['etag'],
            }).status_code == 304
        assert client.get('/static/fonts/unknown.woff2').status_code == 404
        assert client.get('/static/fonts/%2e%2e%2fmain.py').status_code == 404


def platform_fonts(p, selector):
    session = p.context.new_cdp_session(p)
    try:
        session.send('DOM.enable')
        session.send('CSS.enable')
        root = session.send('DOM.getDocument')['root']['nodeId']
        node = session.send('DOM.querySelector', {'nodeId': root, 'selector': selector})['nodeId']
        fonts = session.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
        assert fonts and all(f['isCustomFont'] and f['familyName'].startswith('MiSans') for f in fonts), fonts
        return fonts
    finally:
        session.detach()


@pytest.mark.parametrize('theme', ['默认', '深色', '高对比', '松绿'])
def test_chinese_latin_digits_controls_weights_and_exclusion_badges(ui_page, theme):
    p = ui_page
    p.add_style_tag(content=render_theme(theme))
    p.evaluate('''() => {
      const probe=document.createElement('div');probe.id='font-probe';
      probe.innerHTML='<span id="font-body">审批金额 MiSans 123,456.78</span>'
        +'<span id="font-medium" style="font-weight:500">金额 123.45</span>'
        +'<strong id="font-total">合计 1,333,829.06</strong>'
        +'<button id="font-button">查看明细 123</button>'
        +'<input id="font-input" class="inp num" value="978,829.06">'
        +'<span id="font-manual">'+ntArchTag({excl:true,exsource:'manual',exrule:'人工批量剔除'})+'</span>'
        +'<span id="font-rule">'+ntArchTag({excl:true,exsource:'rule',exrule:'业务类型 <测试>'})+'</span>'
        +'<span id="font-unknown">'+ntArchTag({excl:true})+'</span>';
      document.querySelector('#view').prepend(probe);
    }''')
    p.evaluate('document.fonts.ready')
    for selector, face in [('#font-body', 'Regular'), ('#font-medium', 'Medium'),
                           ('#font-total', 'Semibold'), ('#font-button', 'Regular'),
                           ('#font-input', 'Regular')]:
        fonts = platform_fonts(p, selector)
        assert all(face in f['postScriptName'] for f in fonts), fonts
    assert p.locator('#font-input').input_value() == '978,829.06'
    assert p.locator('#font-manual .tag').get_attribute('class') == 'tag t-bl'
    assert p.locator('#font-rule .tag').get_attribute('class') == 'tag t-dg'
    assert p.locator('#font-rule .tag').get_attribute('title') == '业务类型 <测试>'
    assert p.locator('#font-unknown .tag').inner_text() == '剔除（来源未知）'
    widths = p.evaluate('''() => {
      const span=document.createElement('span');span.style.cssText='display:inline-block;font:13px MiSans;font-variant-numeric:tabular-nums';
      document.body.append(span);
      const widths=['111,111.11','888,888.88'].map(text=>{span.textContent=text;return span.getBoundingClientRect().width;});
      span.remove();return widths;
    }''')
    assert abs(widths[0] - widths[1]) < .1


def test_login_uses_same_local_font(ui_page):
    p = ui_page
    p.set_content(login_html())
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('document.fonts.ready')
    platform_fonts(p, 'h1')
    platform_fonts(p, 'label')
    platform_fonts(p, 'button')


@pytest.mark.parametrize('width,scale', [(1440, 1), (1024, 1.25)])
@pytest.mark.parametrize('count', [30, 450])
def test_notice_amounts_fit_after_font_load_and_horizontal_scroll(ui_page, width, scale, count):
    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1000})
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('''({scale,count}) => {
      document.documentElement.style.setProperty('--fscale',scale);
      const row=NO[0];NO=Array.from({length:count},(_,i)=>({...row,id:String(101+i),
        code:'FKTZS202610'+String(101+i).padStart(4,'0'),
        approve:111111111.11,pay:88888888.88,ss:111111111.11,sp:88888888.88}));
      render();
    }''', {'scale': scale, 'count': count})
    p.evaluate('document.fonts.ready')
    assert p.locator('.sb-i .c').evaluate_all('''items=>items.every(e=>
      e.scrollWidth<=e.clientWidth+1 && e.getBoundingClientRect().height<30)''')
    platform_fonts(p, 'tr[data-notice-id] td.num')
    sizes = p.locator('table[data-sort-key="m03:notices"] td.num').evaluate_all('''cells=>cells.map(c=>({
      text:c.textContent,width:c.clientWidth,content:c.scrollWidth,
    }))''')
    assert sizes and all(c['content'] <= c['width'] + 1 for c in sizes), sizes
    assert p.locator('table[data-sort-key="m03:notices"] input.num').evaluate_all(
        'inputs=>inputs.every(e=>e.scrollWidth<=e.clientWidth+1)')
    p.locator('table[data-sort-key="m03:notices"]').evaluate('''table=>{
      const tw=table.closest('.tw');tw.scrollLeft=500;
      if(VS_TS.length){tw.scrollTop=3000;tw.dispatchEvent(new Event('scroll'));}
    }''')
    if count == 450:
        p.wait_for_function('VS_TS.some(x=>x.a>0)')
    assert p.locator('table[data-sort-key="m03:notices"]').evaluate('t=>t.closest(".tw").scrollLeft') > 0
    assert p.locator('tr[data-notice-id]').first.locator('td.num').first.inner_text() == '111,111,111.11'
    if count == 30:
        p.screenshot(path=str(output(f'misans-notice-{width}.png', kind='screenshots')))
        p.evaluate('''() => {
          NO[0].excl=true;NO[0].exsource='manual';NO[0].exrule='人工批量剔除';
          NO[1].excl=true;NO[1].exsource='rule';NO[1].exrule='业务类型（付材料采购款）';
          fNt.cat='剔除';render();
          document.querySelector('table[data-sort-key="m03:notices"]').closest('.tw').scrollLeft=0;
        }''')
        assert p.locator('tr[data-notice-id="101"] .t-bl').inner_text() == '手动剔除'
        assert p.locator('tr[data-notice-id="102"] .t-dg').get_attribute('title') == '业务类型（付材料采购款）'
        p.screenshot(path=str(output(f'misans-exclusions-{width}.png', kind='screenshots')))
