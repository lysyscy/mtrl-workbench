"""主题名称与导入确认的浏览器回归；所有读写出口使用页面内假接口。"""
from pathlib import Path

from playwright.sync_api import expect

from tests.ui_helpers import ui_page  # noqa: F401


def _capture(page, name):
    import os
    root = Path(__file__).resolve().parents[2]
    target = root / '.artifacts/active' / os.environ.get('MTRL_EFFORT', 'frontend-visual-audit') / os.environ.get('MTRL_RUN_ID', 'implementation-20261020') / 'screenshots'
    target.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target / f'theme-import-{name}.png'), full_page=True)


def test_theme_names_selection_keyboard_and_mock_preference_restore(ui_page):
    from app.mod03_notice.page import DEFAULT_THEME, render_theme
    p = ui_page
    p.add_style_tag(content=render_theme(DEFAULT_THEME))
    p.set_viewport_size({'width': 1280, 'height': 720})
    p.evaluate('''async () => {
      window.preference={theme:'明亮主题',ui_scale:'normal'};
      window.fixturePalette=[
        {name:'明亮主题',bg:'#fff',tx:'#222',pri:'#3366cc',bd:'#ddd'},
        {name:'深色主题',bg:'#222',tx:'#eee',pri:'#ffaa55',bd:'#555'},
        {name:'用于核对长名称的主题',bg:'#fafafa',tx:'#222',pri:'#774488',bd:'#ddd'}];
      window.fixtureScales=[{key:'normal',label:'标准',css:'1'},
        {key:'largest',label:'最大',css:'1.4'}];
      API.m15Theme=async()=>({...preference,themes:fixturePalette.map(p=>p.name),
        palette:fixturePalette,scales:fixtureScales});
      API.m15ThemeSet=async theme=>{preference.theme=theme;return {ok:true};};
      API.m15UiScaleSet=async ui_scale=>{preference.ui_scale=ui_scale;return {ok:true};};
      VIEW='set';await reloadTheme();render();
    }''')
    for name in ['明亮主题', '深色主题', '用于核对长名称的主题']:
        card = p.get_by_role('button', name=name, exact=True)
        expect(card.locator('.set-theme-caption b')).to_have_text(name)
    expect(p.locator('[data-theme="明亮主题"] .set-theme-state')).to_have_text('已选')
    dark = p.get_by_role('button', name='深色主题', exact=True)
    dark.focus()
    expect(dark).to_be_focused()
    _capture(p, 'theme-keyboard')
    dark.press('Enter')
    expect(dark).to_have_attribute('aria-pressed', 'true')
    expect(p.locator('.set-theme-state').filter(has_text='已选')).to_have_count(1)
    p.get_by_role('button', name='最大', exact=True).click()
    p.wait_for_function("CUR_UI_SCALE==='largest'")
    p.evaluate("async()=>{CUR_THEME='';CUR_UI_SCALE='';await reloadTheme();render();}")
    expect(dark).to_have_attribute('aria-pressed', 'true')
    expect(p.get_by_role('button', name='最大', exact=True)).to_have_attribute('aria-pressed', 'true')
    assert p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim()") == '1.4'
    assert p.evaluate("[...document.querySelectorAll('.set-theme-caption')].every(e=>e.scrollWidth<=e.clientWidth)")
    _capture(p, 'theme-largest')


def test_import_disabled_reasons_preview_confirmation_cancel_and_mock_write(ui_page):
    from app.mod03_notice.page import DEFAULT_THEME, render_theme
    p = ui_page
    p.add_style_tag(content=render_theme(DEFAULT_THEME))
    p.set_viewport_size({'width': 1280, 'height': 720})
    p.evaluate('''() => {
      VIEW='imp';Object.assign(IMP,{domain:'fixture',domains:[{domain:'fixture',title:'测试导入'}],
        schema:{title:'测试导入',note:'原始数据保留，先核对列再预览。',required:['项目'],
          fields:[{label:'项目',required:true}],rule_note:'核对每列去向。'},
        hasPj:true,hasYm:false,hasCut:false,hasMechCut:false,org:['测试仓库'],wrap:'',
        file:null,fileName:'',token:'isolated',cols:[],mapping:{},preview:null,report:null,step:0});
      window.writeCalls=0;
      API.impPreview=async()=>({ok:true,total:1,writable:1,preview:[{_row:2,项目:'测试项目'}],
        confirmation:{title:'确认本批导入',message:'确认后写入这批数据。'},blocks:[]});
      API.impCommit=async()=>{writeCalls++;return {ok:true,report:{message:'隔离导入完成',kpis:{写入:1}}};};
      render();
    }''')
    expect(p.locator('.steps .st')).to_have_count(4)
    expect(p.locator('.steps')).to_have_count(1)
    parse = p.locator('[data-act="impParse"]')
    expect(parse).to_be_disabled()
    assert '还没选文件' in parse.get_attribute('title')
    _capture(p, 'import-initial')
    p.evaluate("Object.assign(IMP,{step:1,cols:[{src:'项目',field:'项目'}],mapping:{}});render();")
    expect(p.locator('[data-act="impPreview"]')).to_be_disabled()
    expect(p.locator('.imp-readiness')).to_contain_text('缺少必填列')
    p.evaluate("IMP.mapping={项目:'项目'};render();")
    p.click('[data-act="impPreview"]')
    p.wait_for_function('IMP.step===2')
    expect(p.locator('[data-act="impCommit"]')).to_be_disabled()
    assert '没选就没法写入' in p.locator('[data-act="impCommit"]').get_attribute('title')
    p.evaluate("IMP.wrap='测试仓库';render();")
    assert p.evaluate('writeCalls') == 0
    _capture(p, 'import-preview')
    p.click('[data-act="impCommit"]')
    expect(p.locator('#modalRoot')).to_contain_text('确认本批导入')
    assert p.evaluate('writeCalls') == 0
    p.get_by_role('button', name='取消', exact=True).click()
    assert p.evaluate('IMP.step===2 && writeCalls===0')
    p.click('[data-act="impCommit"]')
    p.get_by_role('button', name='确认导入', exact=True).click()
    p.wait_for_function('IMP.step===3')
    assert p.evaluate('writeCalls') == 1
    expect(p.locator('#view')).to_contain_text('隔离导入完成')
