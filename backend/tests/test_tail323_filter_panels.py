"""通用筛选浮层只改面板；展开不重画业务表或触发取数。"""
import pytest

from tests.ui_helpers import ui_page  # noqa: F401
from tests.test_tail282_pay_draft import _setup


def setup(p, count):
    _setup(p)
    p.evaluate('''count => {
      NO=Array.from({length:count},(_,i)=>({...NO[0],id:String(1000+i),code:'DOC-'+i}));
      render();window.panelTable=document.querySelector('table[data-sort-key="m03:notices"]');
      window.panelRenders=0;const original=render;
      render=function(...args){panelRenders++;return original(...args);};
    }''', count)


@pytest.mark.parametrize('count', [8, 800])
@pytest.mark.parametrize('action', ['pjToggle', 'mpToggle'])
def test_首次展开筛选不重画业务表(ui_page, count, action):
    p = ui_page
    setup(p, count)
    metrics = p.evaluate('''action => {
      const t=performance.now();document.querySelector('[data-act="'+action+'"]').click();
      return {ms:performance.now()-t,renders:panelRenders,sameTable:panelTable===document.querySelector('table[data-sort-key="m03:notices"]')};
    }''', action)
    print(f'{action}, {count} rows: {metrics}')
    assert p.locator('.pjpop').count() == 1
    assert metrics['sameTable'] and metrics['renders'] == 0


@pytest.mark.parametrize('view,action', [('m05','flPjToggle'),('m08','invWhToggle'),('m11','jcPjToggle')])
def test_各页项目筛选复用局部更新(ui_page, view, action):
    p = ui_page
    p.evaluate('''view=>{
      VIEW=view;render();window.panelRenders=0;const old=render;
      render=function(...args){panelRenders++;return old(...args);};
    }''', view)
    p.click(f'[data-act="{action}"]')
    assert p.locator('.pjpop[data-pj-panel]').count() == 1
    assert p.evaluate('panelRenders') == 0


def test_时间探索和收起只改浮层_确认范围才筛表(ui_page):
    p = ui_page
    setup(p, 800)
    p.click('[data-act="mpToggle"]')
    p.click('[data-act="mpMode"][data-m="跨月"]')
    p.click('[data-act="mpYear"][data-d="1"]')
    year = p.evaluate('mp.year')
    p.click(f'[data-act="mpPick"][data-val="{year}-01"]')
    assert p.evaluate('panelRenders') == 0
    assert p.evaluate("panelTable===document.querySelector('table[data-sort-key=\"m03:notices\"]')")
    p.click(f'[data-act="mpPick"][data-val="{year}-02"]')
    assert p.evaluate('fNt.month') == f'{year}-01~{year}-02'
    assert p.evaluate('panelRenders') > 0
    assert p.locator('.pjpop').count() == 0
    p.evaluate('panelRenders=0')
    p.click('[data-act="mpToggle"]')
    p.click('[data-act="mpClose"]')
    assert p.evaluate('panelRenders') == 0


def test_项目搜索归档新候选和外部关闭(ui_page):
    p = ui_page
    setup(p, 8)
    p.evaluate('''() => {
      PJs.push({id:'2',name:'归档仓',full:'归档项目全名',disp:'归档项目',type:'normal',status:'归档'});
      NO.push({...NO[0],id:'20',proj:'归档项目全名'});
    }''')
    p.click('[data-act="pjToggle"]')
    p.click('[data-act="pjArcToggle"]')
    assert p.evaluate("PJ_OPEN['pjArc']") is True
    p.fill('[data-act="pjSearch"]','归档项目')
    assert p.locator('[data-pj-arc]').is_visible()
    assert p.evaluate('panelRenders') == 0
    p.check('[data-act="pjPick"][data-pj="归档仓"]')
    assert p.evaluate('fNt.projs') == ['归档仓']
    assert p.input_value('[data-act="pjSearch"]') == '归档项目'
    p.evaluate('panelRenders=0')
    p.press('[data-act="pjSearch"]','Escape')
    assert p.locator('.pjpop').count() == 0
    assert p.evaluate('panelRenders') == 0
    p.evaluate('''() => {
      PJs.push({id:'3',name:'新仓',full:'新增项目全名',disp:'新增项目',type:'normal',status:'在建'});
      NO.push({...NO[0],id:'30',proj:'新增项目全名'});
    }''')
    p.click('[data-act="pjToggle"]')
    assert p.locator('[data-act="pjPick"][data-pj="新仓"]').count() == 1
    p.click('#ttl')
    assert p.locator('.pjpop').count() == 0
    assert p.evaluate('panelRenders') == 0


@pytest.mark.parametrize('count', [8, 800])
def test_新增按钮自动滚到草稿并聚焦(ui_page, count):
    p = ui_page
    setup(p, count)
    p.click('[data-act="ntRowAdd"]')
    p.wait_for_timeout(100)
    assert p.evaluate('''() => {
      const row=document.querySelector('tr.draftrow'),tw=row.closest('.tw');
      const a=row.getBoundingClientRect(),b=tw.getBoundingClientRect();
      return a.top>=b.top && a.bottom<=b.bottom;
    }''')
    assert p.evaluate("document.activeElement.dataset.k") == 'code'


def test_手动保存被拒保留草稿和原筛选(ui_page):
    p = ui_page
    _setup(p)
    p.evaluate('''() => {
      naEditId=NT_NEW_ID;naD={...ntBlank(),code:'RETRY',approve:'100'};
      fNt.projs=['测试仓库'];fNt.q='旧搜索词';window.beforeFilters=JSON.stringify(fNt);
      API.manualSave=async()=>({ok:false,message:'隔离拒绝'});render();
    }''')
    p.click('[data-act="ntRowSave"]')
    p.wait_for_function('!ntSaving')
    assert p.evaluate('naEditId===NT_NEW_ID && naD.code===\'RETRY\'')
    assert p.evaluate('JSON.stringify(fNt)===beforeFilters')


@pytest.mark.parametrize('count', [8, 550])
def test_保存新增通知书解除冲突筛选并精确定位(ui_page, count):
    p = ui_page
    _setup(p)
    p.evaluate('''count => {
      SRV=Array.from({length:count},(_,i)=>({...SRV[0],notice_id:1000+i,bill_no:'DOC-'+i}));
      NO=SRV.map(adaptNotice);
      PJs.push({id:'2',type:'normal',name:'另仓',disp:'另项目',full:'另项目全名',status:'在建'});
      naEditId=NT_NEW_ID;naD={...ntBlank(),pid:'2',code:'DOC-NEW',doc:'新增测试',approve:'100',date:'2026-10-13'};
      fNt.projs=['测试仓库'];fNt.q='旧搜索词';
      API.manualSave=async body=>{
        window.savedManual=body;
        SRV.push({...SRV[0],notice_id:9000,bill_no:body.bill_no,doc_date:body.doc_date,
          project_name:'另项目全名',ownership_id:2,is_manual:true});
        return {ok:true,row_id:'9000',message:'已新增'};
      };
      render();
    }''', count)
    p.click('[data-act="ntRowSave"]')
    p.wait_for_function("!ntSaving && NO.some(n=>n.id==='9000')")
    p.wait_for_timeout(100)
    row = p.locator('tr[data-notice-id="9000"]')
    assert row.count() == 1
    assert 'nt-focus' in row.get_attribute('class')
    assert p.evaluate('''() => {
      const row=document.querySelector('tr[data-notice-id="9000"]'),tw=row.closest('.tw');
      const a=row.getBoundingClientRect(),b=tw.getBoundingClientRect();
      return a.top>=b.top && a.bottom<=b.bottom;
    }''')
