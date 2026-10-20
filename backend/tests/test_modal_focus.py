"""TAIL-356：共用弹窗真实键盘回归，全部通过假接口加载，无业务写入。"""
import pytest
from playwright.sync_api import expect

from tests.ui_helpers import ui_page  # noqa: F401
from tools.audit.workspace_paths import output


@pytest.fixture(autouse=True)
def modal_styles(ui_page):
    from app.mod03_notice.page import render_theme

    ui_page.add_style_tag(content=render_theme('默认'))
    ui_page.set_viewport_size({'width':1280,'height':720})


def open_rule(p):
    p.evaluate("""() => {
      RULE_KINDS=[{kind:'business',label:'业务类型'}];
      RULE_RAW=[{id:1,kind:'business'}]; RULE_EX=[['业务类型','测试命中','测试含义']];
      VIEW='m14'; render();
    }""")
    opener=p.locator('[data-act="ruleEdit"]').first
    opener.click()
    return opener


def test_审计F01打开规则弹窗后Tab留在弹窗(ui_page):
    p=ui_page
    open_rule(p)
    p.keyboard.press('Tab')
    assert p.evaluate("document.querySelector('#modalRoot').contains(document.activeElement)"), p.evaluate(
        "({text:document.activeElement.textContent,action:document.activeElement.dataset.act})")


def test_规则编辑初焦点名称背景隔离与键盘归还(ui_page):
    p=ui_page
    opener=open_rule(p)
    dialog=p.get_by_role('dialog',name='编辑剔除规则 · 业务类型',exact=True)
    expect(dialog).to_be_visible()
    expect(p.locator('#rxKind')).to_be_focused()
    assert p.locator('.app').evaluate('(el)=>el.inert')
    p.screenshot(path=str(output('modal-rules.png',kind='screenshots')))
    for _ in range(9):
        p.keyboard.press('Tab')
        assert p.evaluate("document.querySelector('#modalRoot').contains(document.activeElement)")
    close=dialog.locator('.x')
    close.focus()
    p.keyboard.press('Shift+Tab')
    expect(dialog.locator('[data-act="ruleSave"]')).to_be_focused()
    p.keyboard.press('Tab')
    expect(close).to_be_focused()
    p.keyboard.press('Enter')
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()
    assert not p.locator('.app').evaluate('(el)=>el.inert')


def test_集采子表重绘保留排序焦点及原触发位置(ui_page):
    p=ui_page
    p.evaluate("""() => {
      JCs.push({id:'11',proj:'测试仓库',supplier:'测试供应商',material:'钢材',date:'2026-10-01',
        tag:'纳入台账',arch:'未存档',tradeCo:'',remark:'',inv_sum:100,pay_sum:0,
        invoices:[],payments:[],tradeInvoices:[]});
      API.m11Detail=async()=>({data:{supplier_invoices:[{id:1,date:'2026-10-01',amount:'100'}]}});
      JC_COLUMNS.push({key:'inv_sum',label:'供应商发票金额',type:'num'});
      VIEW='m11';render();
    }""")
    opener=p.locator('[data-act="jcInvDlg"]').first
    opener.click()
    dialog=p.get_by_role('dialog')
    expect(dialog).to_be_visible()
    expect(dialog.locator('#modalTitle')).to_be_focused()
    head=dialog.locator('th[data-act="headSort"]').first
    head.focus()
    p.keyboard.press('Enter')
    expect(dialog.locator('th[data-act="headSort"]').first).to_be_focused()
    p.screenshot(path=str(output('modal-jc-sorted.png',kind='screenshots')))
    p.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()


def test_嵌套月份选择器重绘及逐层Esc(ui_page):
    p=ui_page
    opener=p.locator('[data-act="fetchNt"]').first
    opener.click()
    dialog=p.get_by_role('dialog')
    toggle=dialog.locator('[data-act="mpToggle"]')
    toggle.click()
    year=dialog.locator('[data-act="mpYear"][data-d="1"]')
    year.focus()
    p.keyboard.press('Enter')
    expect(year).to_be_focused()
    p.screenshot(path=str(output('modal-month-picker.png',kind='screenshots')))
    p.keyboard.press('Escape')
    expect(dialog).to_be_visible()
    expect(dialog.locator('.pjpop')).to_have_count(0)
    expect(toggle).to_be_focused()
    toggle.click()
    dialog.locator('[data-act="mpPick"]').first.click()
    expect(toggle).to_be_focused()
    p.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()


def test_长内容可滚动鼠标关闭及已有inert状态恢复(ui_page):
    p=ui_page
    p.evaluate("""() => {
      document.querySelector('.app').setAttribute('aria-hidden','false');
      const aside=document.createElement('div');aside.id='alreadyInert';aside.inert=true;
      document.body.append(aside);
      document.querySelector('#ntSearch').focus();
      modal({title:'长内容',body:'<p>核对内容</p>'.repeat(90)});
    }""")
    dialog=p.get_by_role('dialog',name='长内容',exact=True)
    expect(dialog.locator('#modalTitle')).to_be_focused()
    assert dialog.locator('.mb').evaluate('(el)=>el.scrollHeight>el.clientHeight')
    dialog.locator('.mb').hover()
    p.mouse.wheel(0,700)
    p.wait_for_function("document.querySelector('.modal .mb').scrollTop>0")
    dialog.locator('.mf button').click()
    expect(p.locator('#ntSearch')).to_be_focused()
    assert p.locator('#alreadyInert').evaluate('(el)=>el.inert')
    assert p.locator('.app').get_attribute('aria-hidden') == 'false'


def test_触发按钮被背景重绘替换后仍可归还(ui_page):
    p=ui_page
    open_rule(p)
    p.evaluate('render()')
    p.keyboard.press('Escape')
    expect(p.locator('[data-act="ruleEdit"]').first).to_be_focused()


def test_月度会非首项目空格重绘保留同项目焦点与选择(ui_page):
    p=ui_page
    p.evaluate("""() => {
      PJs=Array.from({length:4},(_,i)=>({id:String(i+1),type:'normal',
        name:'仓库'+(i+1),disp:'项目'+(i+1),full:'项目全名'+(i+1),status:'在建'}));
      BIGSET=['仓库1','仓库2','仓库3','仓库4']; ACT.bigPick();
    }""")
    third=p.locator('[data-act="bigSelTog"][data-wh="仓库3"]')
    third.focus()
    p.keyboard.press('Space')
    expect(third).not_to_be_checked()
    expect(third).to_be_focused()
    assert p.evaluate('BIGDRAFT') == ['仓库1','仓库2','仓库4']
    p.keyboard.press('Space')
    expect(third).to_be_checked()
    expect(third).to_be_focused()
    assert p.evaluate('BIGDRAFT') == ['仓库1','仓库2','仓库4','仓库3']


def test_月度会项目移到首位后焦点安全回标题(ui_page):
    p=ui_page
    p.evaluate("""() => {
      PJs=Array.from({length:3},(_,i)=>({id:String(i+1),type:'normal',
        name:'仓库'+(i+1),disp:'项目'+(i+1),full:'项目全名'+(i+1),status:'在建'}));
      BIGSET=['仓库1','仓库2','仓库3']; ACT.bigPick();
    }""")
    up=p.locator('[data-act="bigSelUp"][data-wh="仓库2"]')
    up.focus()
    p.keyboard.press('Enter')
    expect(up).to_be_disabled()
    expect(p.locator('#modalTitle')).to_be_focused()
    assert p.evaluate('BIGDRAFT') == ['仓库2','仓库1','仓库3']


@pytest.mark.parametrize('open_act,delete_act',[
    ('jcInvDlg','jcInvDel'),('jcTInvDlg','jcTInvDel'),('jcPayDlg','jcPayDel'),
])
def test_子表删除中间行后回标题避免连续回车误删(ui_page,open_act,delete_act):
    p=ui_page
    p.evaluate("""async openAct => {
      JCs.push({id:'11',proj:'测试仓库',material:'钢材',supplier:'测试供应商',
        tradeCo:'贸易公司',remark:'',inv_sum:60,trade_inv_sum:60,pay_sum:60});
      window.modalSubRows=[1,2,3].map(id=>({id,date:'2026-10-01',amount:String(id*10),source:'manual'}));
      window.deletedModalRows=[];
      API.m11Detail=async()=>({data:{supplier_invoices:modalSubRows,
        trade_invoices:modalSubRows,payments:modalSubRows,payment_display_rows:modalSubRows}});
      const remove=async b=>{deletedModalRows.push(b.row_id);
        modalSubRows=modalSubRows.filter(r=>r.id!==b.row_id);return {ok:true};};
      API.m11InvDel=remove;API.m11PayDel=remove;reloadM11=async()=>{};
      await ACT[openAct]({dataset:{id:'11'}});
    }""",open_act)
    p.locator(f'[data-act="{delete_act}"]').nth(1).focus()
    p.keyboard.press('Enter')
    expect(p.locator(f'[data-act="{delete_act}"]')).to_have_count(2)
    expect(p.locator('#modalTitle')).to_be_focused()
    p.keyboard.press('Enter')
    p.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    assert p.evaluate('deletedModalRows') == [2]


def test_项目类型第二选项重绘保留同一按钮焦点(ui_page):
    p=ui_page
    p.evaluate("pjTypeCur=PJs[0];pjTypeNew='shell';pjTypeDlg()")
    option=p.locator('[data-act="pjTypePick"][data-t="normal"]')
    option.focus()
    p.keyboard.press('Enter')
    expect(option).to_be_focused()
    assert p.evaluate('pjTypeNew') == 'normal'


def test_甲方分类非首行保存重绘保留同一分类框(ui_page):
    p=ui_page
    p.evaluate("""async () => {
      window.modalPartyItems=[{name:'甲单位',kind:'normal'},{name:'乙单位',kind:'normal'}];
      API.m11PartyKinds=async()=>({items:modalPartyItems,kinds:['normal','trade'],kind_names:{normal:'正常',trade:'贸易公司'}});
      API.m11SetPartyKind=async b=>{modalPartyItems.find(it=>it.name===b.name).kind=b.kind;return {ok:true};};
      await ACT.jcPartyDlg();
    }""")
    second=p.locator('[data-act="jcPartySet"][data-name="乙单位"]')
    second.focus()
    second.evaluate('(el)=>{window.oldPartyField=el;}')
    p.keyboard.press('ArrowDown')
    p.wait_for_function('!oldPartyField.isConnected')
    expect(second).to_have_value('trade')
    expect(second).to_be_focused()
    assert p.evaluate('modalPartyItems[0].kind') == 'normal'
