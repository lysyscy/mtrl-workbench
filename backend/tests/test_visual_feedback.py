"""已批准精修：身份事实、费用入口前置与执行记录可读性（假接口）。"""
from pathlib import Path

from tests.ui_helpers import ui_page  # noqa: F401
from app.mod03_notice.page import DEFAULT_THEME, render_theme


def styled(page):
    page.add_style_tag(content=render_theme(DEFAULT_THEME))
    page.set_viewport_size({'width': 1280, 'height': 720})


def test_身份变化如实显示且账号操作仍按角色禁用(ui_page):
    p = ui_page
    styled(p)
    p.evaluate('''() => {
      USERS.splice(0,USERS.length,
        {id:'1',acc:'admin',name:'管理员',role:'admin',status:'在用',last:''},
        {id:'2',acc:'member',name:'材料员',role:'user',status:'在用',last:''});
      applyWho({me:null});VIEW='m15';render();
    }''')
    assert '未登录' in p.locator('.users-workspace h4').inner_text()
    assert '当前登录' not in p.locator('.users-workspace h4').inner_text()
    assert p.locator('[data-act="userAdd"]').is_disabled()
    assert p.locator('[data-act="logout"]').count() == 0
    p.evaluate("applyWho({me:{id:2,name:'材料员',role:'user'}});render()")
    assert '材料员' in p.locator('.users-workspace h4').inner_text()
    assert p.locator('[data-act="userPwd"][data-id="2"]').is_enabled()
    assert p.locator('[data-act="userPwd"][data-id="1"]').is_disabled()
    assert p.locator('[data-act="userToggle"][data-id="2"]').is_disabled()
    p.evaluate("applyWho({me:{id:1,name:'管理员',role:'admin'}});render()")
    assert p.locator('[data-act="userAdd"]').is_enabled()
    assert p.locator('[data-act="userToggle"][data-id="2"]').is_enabled()
    assert p.locator('[data-act="userToggle"][data-id="1"]').is_disabled()
    p.evaluate("applyWho({me:null});render()")
    assert p.locator('[data-act="userAdd"]').is_disabled()


def test_费用批量入口提前反映当前月份的手填项(ui_page):
    p = ui_page
    styled(p)
    p.evaluate("VIEW='m09';awfPj='测试仓库';awfYm='2026-09';AWF_ROWS=[];AWF_AUTO=12;AWF_TOTAL=12;render()")
    assert p.locator('[data-act="awfBatch"]').is_disabled()
    assert '先增加手填项' in p.locator('#awfBatchReason').inner_text()
    p.evaluate("AWF_ROWS=[{item:'试验费',amount:100}];AWF_TOTAL=112;render()")
    assert p.locator('[data-act="awfBatch"]').is_enabled()
    p.locator('[data-act="awfBatch"]').click()
    assert p.locator('#awfTbl input[data-nm="试验费"]').count() == 3
    assert p.locator('#awfTbl input[data-nm="安全文明施工费"]').count() == 0
    p.locator('#modalRoot [data-act="closeModal"]').first.click()
    p.evaluate("awfYm='2026-10';AWF_ROWS=[];AWF_TOTAL=12;render()")
    assert p.locator('[data-act="awfBatch"]').is_disabled()
    assert p.locator('#modalRoot').inner_text() == ''


def test_当前结果优先且长错误可展开(ui_page):
    p = ui_page
    styled(p)
    p.evaluate('''() => {
      M02_RECS=[{id:1,type:'fetch',target:'付款通知书 2026-09',status:'failed',ok:0,fail:1,
        err:'归属未走完。'+ '请核对项目全名与关键词。'.repeat(30),at:'2026-10-20T09:12:03',fin:'2026-10-20T09:12:05'}];
      VIEW='m02';render();
    }''')
    assert p.locator('.m02-workspace .kv').is_visible()
    assert p.locator('.m02-history').evaluate('(element)=>element.open')
    assert not p.locator('.m02-error div').first.is_visible()
    p.locator('.kv .m02-error summary').click()
    assert p.locator('.kv .m02-error div').is_visible()
    p.locator('.m02-history>summary').click()
    assert not p.locator('[data-sort-key="m02:logs"] tbody').is_visible()
    p.locator('.m02-history>summary').click()
    assert p.locator('[data-sort-key="m02:logs"] tbody').is_visible()
    assert p.locator('[data-sort-key="m02:logs"] td').first.evaluate('(e)=>getComputedStyle(e).whiteSpace') == 'nowrap'
    p.evaluate("M02_RECS=[];render()")
    assert '还没有执行记录' in p.locator('.kv').inner_text()
    p.evaluate("M02_ERR='读取失败，请刷新重试';render()")
    assert p.locator('.m02-history').get_attribute('open') is not None
    assert '读取失败' in p.locator('.m02-history').inner_text()


def test_规则长值分项且原编辑与取消保留(ui_page):
    p = ui_page
    styled(p)
    p.evaluate("RULE_KINDS=[{kind:'pay_project',label:'付款项目名'}];RULE_RAW=[{id:1,kind:'pay_project'}];RULE_EX=[['付款项目名','长项目名称安装工程 ｜ 另一个项目','原业务含义']];VIEW='m14';render()")
    assert p.locator('.rule-values>span').count() == 2
    assert p.locator('.section-nav a').count() == 3
    p.locator('[data-act="ruleEdit"]').click()
    assert p.locator('#modalRoot input').count() > 0
    p.locator('#modalRoot [data-act="closeModal"]').first.click()
    assert p.evaluate('RULE_EX[0][1]') == '长项目名称安装工程 ｜ 另一个项目'
