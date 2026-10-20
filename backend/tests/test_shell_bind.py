"""渲染后加工的登记、次序与普通/虚拟重画行为；只用隔离页面。"""
from tests.ui_helpers import ui_page  # noqa: F401
from tests.shell_src import bind_blocks


def test_登记按原顺序且每次重画只跑一次(ui_page):
    p = ui_page
    sizes = p.evaluate('Object.fromEntries(Object.entries(BIND).map(([k,v])=>[k,v.length]))')
    assert sizes == dict(m03=3, m11=3, m15=1, m06=1, m08=2, m09=1, m02=1, m01=1)
    for view, markers in dict(m03=['pickAllBox','m03More','refReturn'],
                              m11=['jcAllBox','m11Tools','refReturn'],
                              m08=['naive','refReturn']).items():
        source = p.evaluate('view=>BIND[view].map(step=>step.toString())', view)
        assert all(marker in step for marker,step in zip(markers,source))
    p.evaluate('''() => {
      window.trace=[];
      for(const [view,steps] of Object.entries(BIND))
        BIND[view]=steps.map((step,i)=>()=>{trace.push(view+':'+i);step();});
    }''')
    for view, count in sizes.items():
        for _ in range(2):
            got = p.evaluate('''view => {
              VIEW=view;refReturn=null;trace.length=0;render();return trace;
            }''', view)
            assert got == [f'{view}:{i}' for i in range(count)]
    # 加工中提前返回不阻断同页后续步骤；空页无加工也能运行。
    assert p.evaluate('''() => {
      window.calls=[];addBind('probe',()=>{calls.push('first');return;});
      addBind('probe',()=>calls.push('second'));runBind('probe');runBind('none');return calls;
    }''') == ['first', 'second']


def test_状态页不加工与引用工具不重复且事件只响应一次(ui_page):
    p = ui_page
    p.evaluate('''() => {
      VIEW='m03';refReturn={to:'m03'};render();render();render();
      window.events=0;const original=ACT.pickAll;
      ACT.pickAll=t=>{events++;return original(t);};
    }''')
    assert p.locator('[data-act="ntPdf"]').count() == 1
    assert p.locator('[data-act="m03PrinterOpen"]').count() == 1
    assert p.locator('[data-act="refBack"]').count() == 1
    p.locator('#pickAllBox').click()
    assert p.evaluate('events') == 1
    assert p.evaluate('pickSet.has("101")')
    assert p.locator('#pickAllBox').is_checked()
    p.evaluate('''() => {
      window.n=0;const steps=BIND.m03;
      BIND.m03=steps.map(step=>()=>{n++;step();});
      PENDING.add('付款通知书');render();
    }''')
    assert p.evaluate('n') == 0
    assert p.locator('[data-act="refBack"]').count() == 0
    p.evaluate("PENDING.clear();FAILED.set('付款通知书','隔离错误');render();")
    assert p.evaluate('n') == 0
    p.evaluate("FAILED.clear();PENDING.clear();refReturn=null;render();")
    assert p.evaluate('n') == 3
    assert p.locator('[data-act="refBack"]').count() == 0


def test_虚拟首画加工一次而滚动不重跑页加工(ui_page):
    p = ui_page
    p.evaluate('''() => {
      VIEW='m03';window.n=0;const original=V.m03;
      V.m03=()=>original()+'<div class="tw" style="height:200px;overflow:auto">'
        +'<table data-vs="bind-probe"><tbody data-vs="bind-probe">'
        +Array.from({length:500},(_,i)=>'<tr><td>'+i+'</td></tr>').join('')
        +'</tbody></table></div>';
      BIND.m03=BIND.m03.map(step=>()=>{n++;step();});
      refReturn={to:'m03'};render();
    }''')
    assert p.evaluate('n') == 3
    assert p.locator('[data-act="refBack"]').count() == 1
    p.locator('table[data-vs="bind-probe"]').evaluate('''table=>{
      const sc=table.closest('.tw');sc.scrollTop=4000;sc.dispatchEvent(new Event('scroll'));
    }''')
    p.wait_for_function('VS_TS.some(x=>x.key==="bind-probe" && x.a>0)')
    assert p.evaluate('n') == 3
    p.evaluate('render();')
    assert p.evaluate('n') == 6
    assert p.locator('[data-act="refBack"]').count() == 1


def test_集采回显隐藏钉列导出与返回逐次保持(ui_page):
    p = ui_page
    p.evaluate('''() => {
      VIEW='m11';fJc.tag='全部';refReturn={to:'m11'};
      JCs.push({id:'J1',proj:'测试仓库',material:'钢材',date:'2026-01-01',contractAmt:10},
               {id:'J2',proj:'测试仓库',material:'铝材',date:'2026-01-02',contractAmt:20});
      jcPick.add('J1');window.work=[];
      const hide=jcApplyHide,pin=jcApplyPin;
      jcApplyHide=()=>{work.push('hide');hide();};
      jcApplyPin=()=>{work.push('pin');pin();};
      render();render();
    }''')
    assert p.evaluate('work') == ['hide','pin','hide','pin']
    assert p.locator('#jcAllBox').evaluate('el=>el.indeterminate')
    assert not p.locator('#jcAllBox').is_checked()
    for selector in ['#jcTradeBtn','[data-act="jcExport"]','[data-act="refBack"]']:
        assert p.locator(selector).count() == 1
    p.evaluate("jcPick.add('J2');render();")
    assert p.locator('#jcAllBox').is_checked()
    assert not p.locator('#jcAllBox').evaluate('el=>el.indeterminate')
    p.locator('#jcTradeBtn').click()
    # 切隐列沿用旧行为：render 加工一次，动作随后再重量一次列宽。
    assert p.evaluate('work') == ['hide','pin']*5
    p.evaluate('refReturn=null;render();')
    assert p.locator('[data-act="refBack"]').count() == 0
    assert p.locator('#jcTradeBtn').count() == 1


def test_加工语义读取不吃下一个登记或注释伪登记():
    source = '''/* addBind('m03', bad); */
addBind('m03', ()=>{ const text=";)}"; });
addBind('m11', other);
addBind('m03', last);
'''
    assert bind_blocks('m03', source=source) == [
        'addBind(\'m03\', ()=>{ const text=";)}"; });', "addBind('m03', last);"]
