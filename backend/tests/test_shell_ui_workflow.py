"""真实浏览器加载壳，隔离写出口，保护供应商提交和导入向导的状态。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright
from tests.shell_src import SHELL_PATH
from tests.acc_plugin import acc


@pytest.fixture
def ui_page():
    web = Path(os.environ.get('MTRL_UI_FIXTURE_WEB', str(SHELL_PATH.parent)))
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'C:/ProgramData/ms-playwright')
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})

        def route(req):
            path = urlparse(req.request.url).path
            if path == '/app':
                html = (web / 'index.html').read_text(encoding='utf-8')
                assert html.count('<script>boot();</script>') == 1
                req.fulfill(body=html.replace('<script>boot();</script>', '<script>window.testReady=true;</script>'), content_type='text/html')
            elif path.startswith('/static/shell/'):
                req.fulfill(body=(web / 'shell' / path.rsplit('/', 1)[-1]).read_text(encoding='utf-8'), content_type='application/javascript')
            else:
                req.fulfill(body='', content_type='text/css')

        page.route('http://fixture.test/**', route)
        page.goto('http://fixture.test/app', wait_until='load')
        page.wait_for_function('window.testReady')
        page.evaluate('''() => {
          CUR.role='admin'; CUR.name='测试';
          FAILED.clear(); PENDING.clear(); Object.keys(LOADERS).forEach(x=>LOADED.add(x));
          PJs=[{id:'1',type:'normal',name:'测试仓库',disp:'测试项目',full:'测试项目全名',status:'在建',phid:'1',kw:''}];
          NO=[{id:'101',date:bjMonth()+'-02',code:'DOC-101',proj:'测试项目全名',cat:'集采',astat:'已审批',doc:'甲乙材料',biz:'业务列唯一词',recv:'收款列唯一词',sup:'',entry:'录入列唯一词',approve:12345.67,pay:12345.67,ss:12345.67,sp:12345.67,excl:false,manual:false}];
          PLs.splice(0); JCs.splice(0); FLs.splice(0); VIEW='m03'; fNt.month='全部';fNt.stat='全部';
          API.jcSupplier=async b=>{window.savedSupplier=b;return {ok:false,message:'隔离写出口已捕获'};};
          render();
        }''')
        yield page
        browser.close()


@acc()
def test_供应商首项直接确定与人工回车(ui_page):
    p=ui_page
    p.evaluate('''async () => {
      API.m03SupMatch=async()=>({ok:true,pool:['甲供应商','乙供应商'],cands:['甲供应商','乙供应商'],level:1,level_name:'全名'});
      await ACT.supMatchRun({dataset:{id:'101'}});
    }''')
    p.click('[data-act="supOk"]')
    p.wait_for_function('window.savedSupplier')
    assert p.evaluate('savedSupplier.supplier') == '甲供应商'
    p.evaluate('closeModal();window.savedSupplier=null;render();')
    p.click('[data-act="supEditOpen"]')
    p.fill('#supManualValue','手录供应商')
    p.press('#supManualValue','Enter')
    p.wait_for_function('window.savedSupplier')
    assert p.evaluate('savedSupplier.supplier') == '手录供应商'
    assert p.input_value('#supManualValue') == '手录供应商'
    assert '隔离写出口已捕获' in p.inner_text('#supManualError')


@acc()
def test_搜索各展示列并重置(ui_page):
    p=ui_page
    for q in ['DOC-101','业务列唯一词','收款列唯一词','录入列唯一词','测试项目','12,345.67','集采']:
        p.fill('#ntSearch',q)
        assert p.evaluate('ntHit(fNt).length') == 1, q
        assert p.evaluate('document.activeElement.id') == 'ntSearch'
    p.fill('#ntSearch','不存在的值')
    assert p.evaluate('ntHit(fNt).length') == 0
    p.click('[data-act="filterReset"]')
    assert p.input_value('#ntSearch') == ''
    assert p.evaluate('ntHit(fNt).length') == 1


@acc()
def test_过程资料历史候选月份金额与后端一致(ui_page):
    p = ui_page
    p.evaluate('''async () => {
      const row={ym:'2025-01',in_主辅材:'12.34',out_主辅材:'4.00',mech_0:'56.78'};
      const totals={in_主辅材:'12.34',out_主辅材:'4.00',mech_0:'56.78'};
      API.m06Matrix=async()=>({projects:['只有历史仓'],matrices:{'只有历史仓':{
        raw:[row],adjusted:[{...row,in_主辅材:'22.34'}],
        totals:{raw:totals,adjusted:{...totals,in_主辅材:'22.34'}},
        segments:{raw:[{total:'12.34'},{total:'4.00'},{total:'56.78'},{total:'0.00'}],
          adjusted:[{total:'22.34'},{total:'4.00'},{total:'56.78'},{total:'0.00'}]}}}});
      IVs=[];ADs=[];VIEW='m06'; await reloadProc();render();
    }''')
    assert p.evaluate('procPj') == '只有历史仓'
    assert p.evaluate('procMonths(procPj)') == ['2025-01']
    assert p.evaluate('procRows(procPj,true)[0].inC[IVC5[0]]') == 22.34
    assert p.evaluate('procAgg(procPj,false).m[0]') == 56.78
    assert '2025-01' in p.inner_text('#view')
    assert '22.34' in p.inner_text('#view')
    p.evaluate('''async () => {
      API.m08Inventory=async()=>({rows:[],adjustments:[]});await reloadInv();
    }''')
    assert p.evaluate('procPj') == '只有历史仓'
    result = p.evaluate('''async () => {
      API.m06Matrix=async()=>({ok:false,message:'读取过程资料失败，请重试'});
      try {await reloadProc();return '错误被隐藏';} catch(e) {return e.message;}
    }''')
    assert result == '读取过程资料失败，请重试'


@acc()
def test_截止月返回修改使旧预览无法确认(ui_page):
    p = ui_page
    p.evaluate('''() => {
      VIEW='imp';Object.assign(IMP,{step:2,preview:{writable:8},hasCut:true,
        domain:'m06_proc',cutoff:'2025-11',cols:[{src:'时间',field:'核算月'}],report:null});
      ACT.impStep({dataset:{step:'0'}});ACT.impCutEdit({value:'2025-10'});
      API.impCommit=async()=>{window.staleCommitted=true;return {ok:true};};
    }''')
    p.evaluate('ACT.impCommit()')
    assert p.evaluate('IMP.preview===null && !window.staleCommitted')


@acc()
def test_导入只显示当前步骤并保留范围(ui_page):
    p=ui_page
    p.evaluate('''() => {
      VIEW='imp';Object.assign(IMP,{domain:'fixture',domains:[{domain:'fixture',title:'测试导入'}],
        schema:{title:'测试导入',required:['项目'],fields:[{label:'项目',required:true}]},hasPj:true,hasYm:true,hasCut:true,
        org:['测试仓库'],wrap:'测试仓库',ym:'2026-08',cutoff:'2026-07',fileName:'测试.xlsx',
        cols:[{src:'项目',field:'项目'}],mapping:{项目:'项目'},token:'isolation',step:1,preview:null,report:null});
      API.impPreview=async(d,b)=>{window.previewOptions=b.options;return {ok:true,total:2,writable:1,problem_count:1,problems:[],preview:[{_row:2,项目:'正常'},{_row:3,项目:'错误'}],skipped:[{row:3,why:'日期认不出',kind:'bad'}]};};
      API.impCommit=async(d,b)=>{window.commitOptions=b.options;return {ok:true,report:{message:'已导入',kpis:{写入:1}}};};
      render();
    }''')
    assert p.locator('#impYm').count() == 0
    assert p.locator('[data-act="impMap"]').count() == 1
    p.click('[data-act="impPreview"]')
    p.wait_for_function('IMP.step===2')
    assert p.locator('[data-act="impMap"]').count() == 0
    assert '日期认不出' in p.inner_text('#view .skiprow')
    assert p.evaluate('previewOptions.year_month') == '2026-08'
    assert p.evaluate('previewOptions.cutoff_ym') == '2026-07'
    p.click('[data-act="impStep"][data-step="1"]')
    assert p.locator('[data-act="impMap"]').count() == 1
    p.click('[data-act="impPreview"]')
    p.wait_for_function('IMP.step===2')
    p.click('[data-act="impCommit"]')
    p.wait_for_function('IMP.step===3')
    assert p.evaluate('JSON.stringify(commitOptions)===JSON.stringify(previewOptions)')
    assert p.locator('[data-act="impCommit"]').count() == 0
    assert p.locator('[data-act="impMap"]').count() == 0


@acc()
def test_修改范围或列对应使旧预览失效(ui_page):
    p=ui_page
    p.evaluate('''() => {
      VIEW='imp';Object.assign(IMP,{domain:'fixture',schema:{title:'测试',required:[],fields:[]},hasPj:false,hasYm:true,
        ym:'2026-08',hasCut:false,cols:[{src:'原列',field:'项目'}],mapping:{原列:'项目'},step:2,preview:{total:1,preview:[]},report:null});render();
    }''')
    p.click('[data-act="impStep"][data-step="0"]')
    p.fill('#impYm','2026-09')
    p.locator('#impYm').blur()
    assert p.evaluate('IMP.preview===null')
    p.click('[data-act="impStep"][data-step="1"]')
    p.evaluate('IMP.preview={total:1};ACT.impMap({dataset:{src:"原列"},value:""});')
    assert p.evaluate('IMP.preview===null')


@acc()
def test_合同候选显示日期金额且仍按编号排序(ui_page):
    p=ui_page
    p.evaluate('''() => {
      JCs.push({id:'12',proj:'测试仓库',date:'2024-01-01',material:'钢材',supplier:'甲供应商',contractAmt:12000,pay:0,settle:0},
        {id:'2',proj:'测试仓库',date:'2026-10-01',material:'铝材',supplier:'乙供应商',contractAmt:20000,pay:0,settle:0});
      ACT.jcLink({dataset:{id:'101'}});
    }''')
    options=p.locator('#jcLinkId option')
    assert options.evaluate_all('els=>els.map(x=>x.value)') == ['2','12']
    assert options.nth(0).inner_text().startswith('2026-10-01')
    assert '合同金额 20,000.00' in options.nth(0).inner_text()


@acc()
def test_审查颜色与看板删减(ui_page):
    p=ui_page
    tones=p.evaluate("['完全匹配','无单据号','单据号查不到','重复上报','超过未付','金额不符'].map(revTag)")
    assert len(set(tones)) == 6
    p.evaluate("VIEW='home';render();")
    text=p.inner_text('#view')
    for removed in ['怎么看这一页','只列「需要你处理的事」','状态一览']:
        assert removed not in text
    assert p.locator('[data-todo]').count() == 6


@acc()
def test_空库也能验证空态和正常合计且样本恢复(ui_page, monkeypatch):
    sys.path.insert(0, str(SHELL_PATH.parents[3] / 'tools' / 'probe'))
    import _shell_common
    import _shell_empty
    monkeypatch.setattr(_shell_common, 'goto', lambda p, key: p.evaluate("VIEW='m04';render();"))
    before=ui_page.evaluate('JSON.stringify(PLs)')
    errors=[]
    _shell_empty.check(ui_page,errors)
    assert not errors, errors
    assert ui_page.evaluate('JSON.stringify(PLs)') == before

@acc()
def test_系统设置精简主题无障碍与尺寸切换(ui_page):
    p=ui_page
    p.evaluate('''() => {
      THEME_PALETTE = [
        {name:'明亮主题',bg:'#fff',tx:'#222',pri:'#3366cc',bd:'#ddd'},
        {name:'深色主题',bg:'#222',tx:'#eee',pri:'#ffaa55',bd:'#555'}];
      UI_SCALES = [{key:'normal',label:'标准',css:'1'},{key:'large',label:'大一点',css:'1.12'},
        {key:'larger',label:'更大',css:'1.25'},{key:'largest',label:'最大',css:'1.4'}];
      CUR_THEME='明亮主题';CUR_UI_SCALE='normal';
      SET.msg='';SET.errs=[];SET.tips=['已撤说明'];SET.logs=[{at:'旧记录'}];
      API.m15ThemeSet=async name=>{window.savedTheme=name;return {ok:true};};
      API.m15UiScaleSet=async key=>{window.savedScale=key;return {ok:true};};
      VIEW='set';render();applyUiScale('1');
    }''')
    assert ''.join(p.inner_text('#view').split()) == '外观主题界面大小标准大一点更大最大'
    assert p.locator('#view .card').count() == 2
    assert p.locator('#view [data-act="themeSet"]').count() == 2
    assert p.get_attribute('[data-theme="明亮主题"]','aria-pressed') == 'true'
    p.get_by_role('button',name='深色主题',exact=True).click()
    p.wait_for_function("window.savedTheme === '深色主题' && CUR_THEME === '深色主题'")
    assert p.get_attribute('[data-theme="深色主题"]','aria-pressed') == 'true'
    for label,key,css in [('大一点','large','1.12'),('更大','larger','1.25'),('最大','largest','1.4'),('标准','normal','1')]:
        p.get_by_role('button',name=label,exact=True).click()
        p.wait_for_function('(k)=>window.savedScale===k && CUR_UI_SCALE===k',arg=key)
        assert p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim()") == css
        assert p.get_attribute(f'[data-key="{key}"]','aria-pressed') == 'true'
        assert p.evaluate('VIEW') == 'set'
    p.evaluate("SET.msg='没有保存成功，请重试';SET.kind='err';render();")
    assert '没有保存成功，请重试' in p.inner_text('#view .tip.dg')


@acc()
def test_默认页删说明保留操作与反馈(ui_page):
    p=ui_page
    assert p.evaluate("!NAV.some(g=>g.items.some(x=>x[0]==='m13')) && !TITLE.m13 && !V.m13")
    for key in ['m04','m05','m06','m07','m08','m09','m11','m15']:
        p.evaluate('(key)=>{VIEW=key;render();}',key)
        assert p.locator('#view .tip').count() == 0, key
        assert p.locator('#view button').count() > 0, key
        assert p.locator('#view table').count() > 0, key
        assert not p.evaluate("[...document.querySelectorAll('#view .bd,#view .grid2,#view .grid3')].some(e=>!e.textContent.trim()&&!e.querySelector('input,button,table'))"), key
    p.evaluate("VIEW='m04';render();")
    assert '当前筛选条件下没有付款计划' in p.inner_text('#view')
    assert p.locator('[data-act="plImport"]').count() == 1
    p.evaluate("VIEW='m07';render();")
    assert '输出产物' not in p.inner_text('#view')
    assert p.locator('[data-act="bigExport"]').count() == 1
    p.evaluate("VIEW='m14';render();")
    assert p.locator('#view > .card:has([data-act="ruleAdd"]), #view > .card:has([data-act="jciAdd"])').count() == 2
    assert ''.join(p.inner_text('#view .tip').split()) == '剔除规则中不得配置「收款单位=资产处集中采购」：集采不走剔除，而是参与分类。'
    assert p.locator('[data-act="ruleAdd"]').count() == 1
    assert p.locator('[data-act="jciAdd"]').count() == 1
    p.evaluate("VIEW='m06';FAILED.set('过程资料','读取失败，请刷新重试');LOADED.delete('过程资料');render();")
    assert '读取失败，请刷新重试' in p.inner_text('#view')


@acc()
def test_项目页实际待办与错误保留(ui_page):
    p=ui_page
    p.evaluate("ARCP=[];ARCP_ERR='';ARCP_DROP=[{full_name:'其他同步数据',why_text:'保留数据'}];VIEW='m01';render();")
    assert p.locator('#archBox').count()==0
    assert p.evaluate('ARCP_DROP.length')==1
    p.evaluate("ARCP=[{full:'需建档全名',whs:['仓库甲','仓库乙'],reason:'需要选择仓库'}];render();")
    assert p.locator('[data-act="pjArchOpen"]').count()==1
    assert '需建档全名' in p.inner_text('#archBox')
    assert '其他同步条目' not in p.inner_text('#view')
    p.evaluate("ARCP=[];ARCP_ERR='获取失败，请重试';render();")
    assert '待建档清单没取到' in p.inner_text('#archBox')
    assert '获取失败，请重试' in p.inner_text('#archBox')
