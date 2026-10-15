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
    assert '2026-10-01' in options.nth(0).inner_text()
    assert options.nth(0).inner_text().startswith('序号 — · 合同编号 — · ')
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


@acc()
def test_付款流水默认只看生效且随时能看全部(ui_page):
    """⭐ 2026-10-10 用户裁定：状态**初始与重置都默认「生效」**；「全部 / 已撤销」仍随时可手动切。

    ⚠️ 这里同时钉住"默认收紧"最容易踩的两头：
      ① **默认确实生效**（初始进页面只看到 1 条生效、已撤销那条不在屏幕上）；
      ② **没有把已撤销藏起来**（切「全部」两条都在、切「已撤销」能看到它与撤销原因；「重置」回「生效」）。
    ⛔ 数据本身一条没少 —— `FLs` 仍是后端给的全量（壳内筛，不是后端改口径）。
    """
    p=ui_page
    # ⚠️ **刻意不设 `flf.state`** —— 这一条要验的就是**页面自己的初始值**；
    #   在这里摆上 `flf.state='生效'` 会把"初始默认"这半变成自证（变异成「全部」也照样绿）。
    p.evaluate('''() => {
      const ym=bjMonth();
      FLs.splice(0);
      FLs.push({id:'F1',nid:'101',date:ym+'-05',amt:'100.00',method:'现汇',remark:'第一笔',op:'测试',voided:false,reason:''},
                {id:'F2',nid:'101',date:ym+'-08',amt:'50.00',method:'现汇',remark:'撤掉的那笔',op:'测试',voided:true,reason:'付错了'});
      flf.ym=ym;flf.projs=[];flf.method='全部';flf.q='';
      VIEW='m05';render();
    }''')
    assert p.evaluate('flf.state') == '生效', "付款流水的初始状态不是「生效」"
    assert p.evaluate('flVisible().map(f=>f.id)') == ['F1'], "初始不是「只看生效」"
    assert p.input_value('#flState') == '生效'
    assert p.locator('[data-sort-key="m05:flows"] tbody tr:not(.sumrow)').count() == 1
    assert '合计（生效 1 条 · 不含已撤销）' in p.inner_text('#view')
    p.select_option('#flState', '全部')
    assert p.evaluate('flVisible().map(f=>f.id)') == ['F1', 'F2']
    p.select_option('#flState', '已撤销')
    rows = p.locator('[data-sort-key="m05:flows"] tbody tr:not(.sumrow)')
    assert rows.count() == 1 and '付错了' in rows.first.inner_text()
    p.click('[data-act="flReset"]')
    assert p.evaluate('flVisible().map(f=>f.id)') == ['F1']
    assert p.input_value('#flState') == '生效'
    assert p.evaluate('FLs.length') == 2, "默认收紧不该动数据（后端仍是全量）"


@acc()
def test_撤销付款跳转只定位生效流水(ui_page):
    """「撤销付款」有**多条**生效流水时跳 `MOD-05` 并逐条撤 ⇒ 落地页必须**只定位生效的那些**。

    ⚠️ 反面情形一起钉：那条**已撤销**的流水不该混进这屏（用户要撤的是生效的那几条，
    混进来等于让他自己再筛一遍）；关键词仍按单据编码定位。

    ⚠️ 2026-10-11（本轮发现并修）：本用例原先只往 `FLs` 里塞三行 —— 而 `ntRevoke` 走的是
       `ntLoadFlows`（**先经 `API.flows()` 从后端读回这一单的流水**，再决定"直接开弹窗"还是"跳页筛选"）
       ⇒ 替身必须给在**取数出口**上，否则取数失败、它当场 return，本用例恒红。
       实测：本用例在**改动前的壳**上同样红（`MTRL_UI_FIXTURE_WEB` 指 HEAD 版壳跑过）
       ⇒ 这是**既有**的用例缺陷（`TAIL-281` 改走 `ntLoadFlows` 时漏改），与 `TAIL-283` 无关。
    """
    p=ui_page
    p.evaluate('''(rows) => {
      API.flows = async () => ({rows: rows});
      VIEW='m03';render();
    }''', [dict(id='F1', notice_id=101, flow_no='FL-1', doc_no='DOC-101', pay_date='2026-10-05',
                amount='100.00', pay_method='现汇', status='effective'),
           dict(id='F2', notice_id=101, flow_no='FL-2', doc_no='DOC-101', pay_date='2026-10-06',
                amount='60.00', pay_method='现汇', status='effective'),
           dict(id='F3', notice_id=101, flow_no='FL-3', doc_no='DOC-101', pay_date='2026-10-07',
                amount='20.00', pay_method='现汇', status='revoked', revoke_reason='上月已撤')])
    p.evaluate("ACT.ntRevoke({dataset:{id:'101'}})")
    assert p.evaluate('VIEW') == 'm05'
    assert p.evaluate('flf.q') == 'DOC-101'
    assert p.evaluate('flf.state') == '生效'
    assert p.evaluate('flVisible().map(f=>f.id)') == ['F1', 'F2'], "跳转过来混进了已撤销的流水"
    assert p.input_value('#flState') == '生效'


@acc()
def test_发票子表新增草稿默认北京时间当日且可改(ui_page):
    """⭐ 2026-10-10 用户裁定：**供应商发票 / 贸易公司发票 / 付款**三张子表新增草稿的日期
    都默认取**北京时间当日**、**可改**；「历史未结金额」那行仍按**核对截至日**（日期语义不同，不可同日）。

    ⚠️ 三条钉：① 默认值取的是 `SYS_TODAY`（⛔ 不写死日期字面量，`ACC-I8-TIME` 也钉着这条）；
      ② 改的是**草稿层**、保存时按改后的日期发出去（不是改完就当落库，也不是发默认值）；
      ③ **校验不变**（日期仍必填、金额仍须 > 0）。
    """
    p=ui_page
    p.evaluate('''() => {
      window.pushJc=()=>{JCs.push(
               {id:'J1',proj:'测试仓库',date:'2026-01-01',material:'钢材',supplier:'甲供应商',contractAmt:12000,
                inv_sum:'100.00',trade_inv_sum:'0.00',pay_sum:'0.00',tradeCo:'',remark:''},
               {id:'J2',proj:'测试仓库',date:'2026-01-01',material:'铝材',supplier:'乙供应商',contractAmt:20000,
                inv_sum:'0.00',trade_inv_sum:'50.00',pay_sum:'0.00',tradeCo:'某贸易公司',remark:''},
               {id:'J3',proj:'测试仓库',date:'2026-01-01',material:'历史材料',supplier:'丙供应商',contractAmt:300,
                inv_sum:'300.00',trade_inv_sum:'0.00',pay_sum:'0.00',tradeCo:'',
                remark:JC_HISTORY_PREFIX+'2025-06-30'});};
      window.saved=[];
      API.m11Detail=async()=>({data:{supplier_invoices:[],trade_invoices:[],payments:[]}});
      API.m11InvAdd=async b=>{saved.push(b);return {ok:true};};
      API.m11PayAdd=async b=>{saved.push(b);return {ok:true};};
      API.m11List=async()=>({rows:[]});
      window.TODAY=SYS_TODAY;
      pushJc();
    }''')
    today = p.evaluate('TODAY')
    assert len(today) == 10 and today[4] == '-' and today[7] == '-', f"不是 YYYY-MM-DD：{today}"
    # ① 供应商发票
    p.evaluate("ACT.jcInvDlg({dataset:{id:'J1'}})")
    p.click('[data-act="jcSubAdd"][data-kind="inv"]')
    assert p.input_value('[data-act="jcSubSet"][data-k="date"]') == today
    # ② 可改：改的是草稿层，保存按改后的日期发出去
    p.fill('[data-act="jcSubSet"][data-k="date"]', '2026-02-03')
    p.locator('[data-act="jcSubSet"][data-k="date"]').dispatch_event('change')
    assert p.evaluate('jcSubD.date') == '2026-02-03'
    p.fill('[data-act="jcSubSet"][data-k="amt"]', '888')
    p.locator('[data-act="jcSubSet"][data-k="amt"]').dispatch_event('change')
    p.click('[data-act="jcSubSave"]')
    p.wait_for_function('saved.length===1')
    assert p.evaluate('saved[0]') == {'id': 'J1', 'kind': 'supplier', 'date': '2026-02-03', 'amount': '888'}
    # ③ 贸易公司发票（同款）—— ⚠️ 保存会 `reloadM11()` 重拉（`JCs` 被清空）⇒ 先把合同放回去
    p.evaluate("closeModal();pushJc();ACT.jcTInvDlg({dataset:{id:'J2'}})")
    p.click('[data-act="jcSubAdd"][data-kind="tinv"]')
    assert p.input_value('[data-act="jcSubSet"][data-k="date"]') == today
    # ④ 付款子表（原有行为不许被这次改动带坏）
    p.evaluate("closeModal();ACT.jcPayDlg({dataset:{id:'J1'}})")
    p.click('[data-act="jcSubAdd"][data-kind="pay"]')
    assert p.input_value('[data-act="jcSubSet"][data-k="date"]') == today
    # ⑤ 例外：历史未结金额仍按核对截至日（那一行的日期含义 = 结转核对日，不是"今天开的票"）
    p.evaluate("closeModal();ACT.jcInvDlg({dataset:{id:'J3'}})")
    p.click('[data-act="jcSubAdd"][data-kind="inv"]')
    assert p.input_value('[data-act="jcSubSet"][data-k="date"]') == '2025-06-30'
    # ⑥ 校验不变：日期清空后不许落库（必填这条口径没动）
    p.evaluate("jcSubD.date='';jcSubD.amt='100';ACT.jcSubSave()")
    assert p.evaluate('saved.length') == 1, "日期为空也写进去了 —— 必填校验被改坏了"


# ============================================================== `TAIL-283` 付款流水列义
# ⚠️ 这些用例**替换 `API.notices` 的回包**（= 后端真事实），⛔ 不整体覆写 `reloadNotices` ——
#   那样会把被测函数绕开（同 `test_tail282_pay_draft.py` 的纪律）。


#: 一条**后端形状**的流水（`service._flow_dict` 那套键名）—— 用例里一律交给**真实 `adaptFlow`**
#: 转形（⛔ 别手摆壳字段）：这样"后端给什么、页面显示什么"这条链才是真的。
FL0 = dict(id=71, notice_id=101, flow_no='FL-X9', pay_date='2026-09-05', amount='300.00',
           pay_method='现汇', remark='', created_by='乙', status='effective', revoke_reason='',
           project_key='测试仓库', project_display='测试项目', doc_no='DOC-101',
           doc_date='2026-09-01', bill_name='钢材付款', payee='甲公司',
           amount_approved='1000.00', category_label='集采')


@acc()
def test_付款流水补通知书五列并改对操作人与流水号(ui_page):
    """票面验收：五项通知书信息上身；「操作人」= `created_by`（⛔ 不是创建时间）；
    「流水号」= 真 `flow_no`（⛔ 不是数据库行号）；**失联流水照样整条可查**、审批金额未知画「—」
    （⛔ 不伪 0）；`notice_id` 指向已删除通知书的流水也不消失。"""
    p = ui_page
    p.evaluate('''(f0) => {
      const ym = bjMonth();
      FLs.splice(0);
      FLs.push(adaptFlow({...f0, pay_date: ym+'-05'}));
      FLs.push(adaptFlow({...f0, id:72, notice_id:null, flow_no:'', pay_date: ym+'-06',
        amount:'200.00', pay_method:'', created_by:'', project_key:'', project_display:'', doc_no:'',
        doc_date:'', bill_name:'', payee:'', amount_approved:null, category_label:''}));
      FLs.push(adaptFlow({...f0, id:73, notice_id:999, flow_no:'FL-3', pay_date: ym+'-07',
        amount:'100.00', status:'revoked', revoke_reason:'冲正', project_key:'', project_display:'',
        doc_no:'', doc_date:'', bill_name:'', payee:'', amount_approved:null, category_label:''}));
      flf.ym=ym; flf.projs=[]; flf.method='全部'; flf.q=''; flf.state='全部';
      VIEW='m05'; render();
    }''', FL0)
    rows = p.locator('[data-sort-key="m05:flows"] tbody tr[data-flow-id]')
    assert rows.count() == 3, "失联 / 通知书已删除的流水被丢掉了"
    assert p.locator('[data-sort-key="m05:flows"] tbody tr[data-flow-id]:first-child td').count() == 15, \
        "流水行的格子数不是 15（表头、行、合计三处的列序必须逐字对应）"

    def cell(i: int, j: int) -> str:
        return rows.nth(i).locator('td').nth(j).inner_text().strip()

    # 第 1 行：数据齐全 —— 逐格对账（0 流水号 / 1 编码 / 2 单据日期 / 3 名称 / 4 项目 / 5 收款单位
    #           / 6 分类 / 7 审批金额 / 8 付款日期 / 9 付款金额 / 12 操作人 / 13 状态）
    assert [cell(0, j) for j in (0, 1, 2, 3, 5, 6, 7, 12)] == \
        ['FL-X9', 'DOC-101', '2026-09-01', '钢材付款', '甲公司', '集采', '1,000.00', '乙'], \
        "通知书五项 / 流水号 / 操作人的取值不对"
    assert cell(0, 9) == '300.00' and '生效' in cell(0, 13)
    # 第 2 行：`notice_id` 为空（历史/导入的失联流水）—— 新列留白/—，**付款金额与流水号仍在**
    assert cell(1, 0) == '—' and cell(1, 7) == '—', "失联流水的新列没有如实留空 / 留「—」"
    assert cell(1, 9) == '200.00', "失联流水的付款金额被吞了"
    # 第 3 行：`notice_id` 指向已删除的通知书 —— 同样照常显示，且带撤销原因
    assert cell(2, 7) == '—', "通知书失联时审批金额被伪成了别的数"
    assert cell(2, 9) == '100.00' and '已撤销' in cell(2, 13) and '冲正' in cell(2, 13)
    # ⭐「未知」与「真是 0」必须分开：未知的排序值留空（`data-v=""`），真实的 0 才写 0
    assert p.evaluate('''() => [...document.querySelectorAll(
        '#view table[data-sort-key="m05:flows"] tbody tr[data-flow-id] td:nth-child(8)')]
        .map(td => td.dataset.v).join('|')''') == '1000||', \
        "审批金额未知时被写成了 0（拿 0 冒充「没有这个数」）"
    # ⭐ 票面 #3 的**第三处**口径：关键词搜的就是**流水号 / 单据编码**（页面列 · 搜索 · Excel 三处同一个东西）。
    #   ⚠️ 这个 fixture 里 `NO` 是空的 ⇒ 只有**不依赖 NO 缓存**才可能搜到；
    #   反过来，拿**数据库行号** `71` 必须**搜不到**（它从来不是流水号 —— 那是"说错话"的那一版）。
    assert p.evaluate("flf.q='fl-x9';flVisible().map(f=>f.id)") == ['71'], \
        "关键词搜不到「流水号」（来源可能又回到数据库行号或 NO 缓存）"
    assert p.evaluate("flf.q='doc-101';flVisible().map(f=>f.id)") == ['71'], "关键词搜不到「单据编码」"
    assert p.evaluate("flf.q='71';flVisible().map(f=>f.id)") == [], \
        "拿数据库行号当流水号也搜出了行 —— 「流水号」这一列又说错话了"


@acc()
def test_付款流水合计只加实付且导出按屏幕行序(ui_page):
    """票面验收：**合计只加实付金额**（审批金额是每笔重复的对照数 ⇒ ⛔ 不纵向求和）；
    导出取的是**屏幕上真实的行序**（表头点击排序后行序只在 DOM 里 ⇒ ⛔ 不是数组原序）。"""
    p = ui_page
    p.evaluate('''(f0) => {
      const ym = bjMonth();
      FLs.splice(0);
      FLs.push(adaptFlow({...f0, pay_date: ym+'-05'}));
      FLs.push(adaptFlow({...f0, id:72, notice_id:null, flow_no:'FL-2', pay_date: ym+'-06',
        amount:'200.00', amount_approved:'20.00', doc_no:'', project_key:'', project_display:''}));
      FLs.push(adaptFlow({...f0, id:73, notice_id:null, flow_no:'FL-3', pay_date: ym+'-07',
        amount:'100.00', amount_approved:null, status:'revoked', revoke_reason:'冲正',
        doc_no:'', project_key:'', project_display:''}));
      flf.ym=ym; flf.projs=[]; flf.method='全部'; flf.q=''; flf.state='全部';
      API.post = async (url, body) => { window.__post = {url:url, ids:body.ids};
                                        return {ok:true, filename:'x.xlsx', content_b64:''}; };
      VIEW='m05'; render();
    }''', FL0)
    # ① 合计行：只加**生效**的实付（300＋200），已撤销那笔不进；审批金额那一列**根本不参与**
    sumcells = p.locator('[data-sort-key="m05:flows"] tbody tr.sumrow td')
    assert sumcells.count() == 7, "合计行的跨列数变了（leadSpan 该是 9：9 格合并 + 6 个数据格）"
    assert sumcells.nth(0).get_attribute('colspan') == '9', "合计行首格的 colspan 不是 9"
    assert sumcells.nth(1).inner_text().strip() == '500.00', \
        "合计不是「只加生效实付」（300＋200=500）—— 多加了或口径变了"
    assert '2,000.00' not in sumcells.all_inner_texts().__str__(), \
        "审批金额被纵向求和了（同一张单的每笔是**对照数**，加起来是假数）"

    # ② 点表头「审批金额」升序 ⇒ DOM 行序 = 20 → 1000 → 未知（空值恒排最后）
    p.click('[data-sort-key="m05:flows"] thead th:nth-child(8)')
    dom = p.evaluate('''() => [...document.querySelectorAll(
        '#view table[data-sort-key="m05:flows"] tbody tr[data-flow-id]')].map(tr => tr.dataset.flowId)''')
    assert dom == ['72', '71', '73'], f"表头排序后的屏幕行序不对：{dom}（未知值必须排最后）"
    assert p.evaluate('flVisible().map(f=>f.id)') == ['71', '72', '73'], \
        "数组序本来就不该被排序改动（它是筛选结果，不是屏幕行序）"
    # ③ 导出走的 id 顺序 = **屏幕行序**
    p.evaluate("async () => { await ACT.exp({dataset:{t:'付款流水'}}); }")
    assert p.evaluate('window.__post') == {'url': '/api/m05/flows/export', 'ids': [72, 71, 73]}, \
        "导出没按屏幕上看到的行序取 id（点过表头排序后 Excel 与屏幕对不上）"


@acc()
def test_通知书名含合计词的行不被排序钉到表尾(ui_page):
    """⭐ `TAIL-283` 附带发现：全站排序的「合计行」判定原先是**扫整行文本**里的「合计/总计/小计」——
    而通知书的「名称」是**自由文本**（`fields['BillName']`，来自 i8）⇒ 一张叫「…合计…」的单会让
    **普通数据行**被钉到表尾（不报错，只是排序后它不跟着走）。

    ⚠️ 这里**直接调真实实现** `applySorts`（纯函数：HTML 字符串 → HTML 字符串）＋ 隔离输入，
    不去动正式页面数据（纪律同"判据用隔离靶"）。"""
    p = ui_page
    order = p.evaluate('''() => {
      SORT['t'] = {i:0, d:1};                       /* 强制：按第 0 列升序 */
      const h = applySorts('<table data-sort data-sort-key="t"><thead><tr><th>金额</th><th>名称</th></tr></thead>'
        + '<tbody><tr><td class="num">100</td><td>项目合计材料请款</td></tr>'
        + '<tr><td class="num">200</td><td>普通单据</td></tr></tbody></table>', 'x');
      return [...h.matchAll(/<td class="num">(\\d+)<\\/td>/g)].map(m => m[1]);
    }''')
    assert order == ['100', '200'], \
        f"名称里带「合计」的**普通数据行**被当成合计行钉到表尾了：{order}"
    assert p.evaluate('''() => {
      SORT['t2'] = {i:0, d:1};
      const h = applySorts('<table data-sort data-sort-key="t2"><thead><tr><th>金额</th><th>名称</th></tr></thead>'
        + '<tbody><tr><td class="num">100</td><td>甲</td></tr>'
        + '<tr class="sumrow"><td>合计</td><td>200</td></tr></tbody></table>', 'x');
      return [...h.matchAll(/<td(?: class="num")?>(\\d+)<\\/td>/g)].map(m => m[1]);
    }''') == ['100', '200'], "真合计行（带 sumrow 类、首格写「合计」）没有被钉到表尾"



@acc()
def test_当前错误同路替换逐页恢复与唯一横幅(ui_page):
    p = ui_page
    p.evaluate("""async () => {
      BOOTING=false; VIEW='m15';
      window.userError='第一次读取失败，请重试';
      window.userTech='GET /api/first → HTTP 500';
      LOADERS['用户管理']=async()=>{throw {message:window.userError,tech:window.userTech};};
      LOADERS['规则配置']=async()=>{throw {message:'配置读取失败，请重试',tech:'GET /api/config → HTTP 503'};};
      LOADED.delete('用户管理'); LOADED.delete('规则配置');
      await loadPaths(['用户管理','规则配置']);
      window.firstBanner=document.getElementById('boot-error-banner');
    }""")
    banner = p.locator('#boot-error-banner')
    assert banner.count() == 1
    assert '第一次读取失败' in banner.inner_text()
    assert '配置读取失败' in banner.inner_text()
    assert 'HTTP' not in banner.inner_text()
    assert p.locator('#view [data-act="retryPage"]').is_visible()
    assert p.evaluate("pageState().kind") == 'error'
    assert banner.locator('details').evaluate('(el)=>el.open') is False
    assert p.evaluate("""() => {
      const el=document.getElementById('boot-error-banner'), view=document.getElementById('view');
      return el.parentElement===document.querySelector('.app > main') && el.nextElementSibling===view
        && getComputedStyle(el).position!=='fixed' && el.getBoundingClientRect().bottom<=view.getBoundingClientRect().top;
    }""")

    # 同路再失败只留最新两半；HTML样式的错误文本仍按文字显示。
    p.evaluate("""async () => {
      window.userError='第二次读取失败 <img src=x onerror="window.errorInjected=true">，请重试';
      window.userTech='GET /api/latest <script>window.errorInjected=true</script> → HTTP 502';
      LOADED.delete('用户管理'); await loadPaths(['用户管理']);
      syncBootErrors(); syncBootErrors();
    }""")
    assert banner.count() == 1
    assert p.evaluate("document.getElementById('boot-error-banner')===window.firstBanner")
    assert '第二次读取失败' in banner.inner_text() and '第一次读取失败' not in banner.inner_text()
    assert 'GET /api/first' not in banner.text_content()
    assert p.evaluate('window.errorInjected || false') is False
    assert banner.locator('img,script').count() == 0
    assert p.locator('#view img,#view script').count() == 0
    banner.locator('summary').click()
    assert 'GET /api/latest' in banner.inner_text()
    assert 'GET /api/config' in banner.inner_text()
    banner.locator('summary').click()

    # 真点页级重试：读取期间为loading，恢复后无关错误及其明细仍在。
    p.evaluate("""() => {
      LOADERS['用户管理']=()=>new Promise(resolve=>{window.finishUserRetry=resolve;});
    }""")
    p.locator('#view [data-act="retryPage"]').click()
    p.wait_for_function("pageState().kind==='loading'")
    p.evaluate('render()')  # 以既有渲染出口核对 pageState/pageGate 的 loading 契约
    assert '正在读取' in p.locator('#view').inner_text()
    p.evaluate('window.finishUserRetry()')
    p.wait_for_function("pageState().kind==='ready'")
    assert banner.count() == 1
    assert '用户管理' not in banner.text_content()
    assert '配置读取失败' in banner.inner_text()
    assert 'GET /api/config' in banner.text_content()
    assert p.evaluate("[...FAILED.keys()]") == ['规则配置']
    assert p.evaluate("[...FAILED_TECH.keys()]") == ['规则配置']

    # 恢复最后一路后节点和两份快照都消失，重复同步也不再生成空横幅。
    p.evaluate("""async () => {
      VIEW='m14'; LOADERS['规则配置']=async()=>{}; await retryPage();
      syncBootErrors(); syncBootErrors();
    }""")
    assert banner.count() == 0
    assert p.evaluate("[BOOT_ERROR,typeof BOOT_ERROR,fails.length,failsTech.length,FAILED.size,FAILED_TECH.size,pageState().kind]") == ['', 'string', 0, 0, 0, 0, 'ready']


@acc()
def test_启动身份错误晚于页面加载且恢复保留其它错误(ui_page):
    p = ui_page
    # 首屏路径已缓存；身份失败晚于loadPaths收尾，boot必须收进当前横幅。
    p.evaluate("""() => {
      VIEW='m03'; BOOTING=true;
      API.users=()=>new Promise((resolve,reject)=>{window.rejectWho=reject;});
      window.bootRun=boot();
    }""")
    p.evaluate("window.rejectWho({message:'身份读取失败，请刷新重试',tech:'GET /api/users → HTTP 500'})")
    p.evaluate('window.bootRun')
    banner = p.locator('#boot-error-banner')
    assert banner.count() == 1 and '当前登录用户' in banner.inner_text()
    assert 'HTTP' not in banner.inner_text()
    assert p.evaluate("pageState().kind") == 'ready'
    p.evaluate("""async () => {
      await soft('规则配置',async()=>{throw {message:'配置读取失败，请重试',tech:'GET /api/config → HTTP 503'};});
      API.users=async()=>({me:{id:'1',username:'test',name:'测试',role:'admin'}});
      await boot();
    }""")
    assert banner.count() == 1
    assert '当前登录用户' not in banner.text_content()
    assert '配置读取失败' in banner.inner_text()
    assert p.evaluate("FAILED_TECH.has('当前登录用户')") is False
    p.evaluate("""async () => {
      await soft('规则配置',async()=>{}); await boot();
    }""")
    assert banner.count() == 0
    assert p.evaluate('[BOOT_ERROR,fails.length,failsTech.length]') == ['', 0, 0]


@acc()
@pytest.mark.parametrize('count', [8, 450])
def test_集采推进后保留横向位置_普通表与虚拟表(ui_page, count):
    from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS

    p = ui_page
    p.evaluate('''async ({count,columns,sumKeys}) => {
      window.jcRowsFixture=Array.from({length:count},(_,i)=>({
        id:i+1,project_seq:i+1,project_key:'测试仓库',date:'2026-01-01',
        material:'钢材',supplier:'供应商',contract_amt:'100',tag:'纳入台账',arch:'未存档'
      }));
      API.m11List=async()=>({rows:jcRowsFixture,columns,sum_keys:sumKeys});
      API.m11Fields=async b=>{Object.assign(jcRowsFixture.find(r=>r.id===Number(b.id)),b.fields);return {ok:true};};
      VIEW='m11';await reloadM11();
    }''', {'count': count, 'columns': list(JC_COLUMNS), 'sumKeys': list(SUM_KEYS)})
    button = p.locator('[data-act="jcArch"][data-id="1"]')
    button.scroll_into_view_if_needed()
    before = p.evaluate('''() => {
      const tw=document.querySelector('table[data-sort-key="m11:jc"]').closest('.tw');
      return tw.scrollLeft;
    }''')
    assert before > 100, '夹具没有产生横向滚动'
    button.click()
    p.wait_for_function("JCs.find(j=>j.id==='1').arch==='资产处'")
    p.wait_for_timeout(100)
    after = p.evaluate("document.querySelector('table[data-sort-key=\"m11:jc\"]').closest('.tw').scrollLeft")
    assert abs(after - before) < 2


@acc()
@pytest.mark.parametrize('count', [8, 450])
@pytest.mark.parametrize('width', [1440, 6000])
def test_集采推进后保留纵向位置_有无横向溢出(ui_page, count, width):
    from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS

    p = ui_page
    p.set_viewport_size({'width': width, 'height': 270})
    p.evaluate('''async ({count,columns,sumKeys}) => {
      window.jcRowsFixture=Array.from({length:count},(_,i)=>({
        id:i+1,project_seq:i+1,project_key:'测试仓库',date:'2026-01-01',
        material:'钢材',supplier:'供应商',contract_amt:'100',tag:'纳入台账',arch:'未存档'
      }));
      API.m11List=async()=>({rows:jcRowsFixture,columns,sum_keys:sumKeys});
      API.m11Fields=async b=>{Object.assign(jcRowsFixture.find(r=>r.id===Number(b.id)),b.fields);return {ok:true};};
      VIEW='m11';await reloadM11();
    }''', {'count': count, 'columns': list(JC_COLUMNS), 'sumKeys': list(SUM_KEYS)})
    button = p.locator('[data-act="jcArch"][data-id="6"]')
    button.scroll_into_view_if_needed()
    snapshot = '''() => {
      const v=document.querySelector('#view');
      const tw=v.querySelector('table[data-sort-key="m11:jc"]').closest('.tw');
      return {viewTop:v.scrollTop,tableTop:tw.scrollTop,viewHeight:v.clientHeight,
        viewContent:v.scrollHeight,wide:tw.scrollWidth>tw.clientWidth+1};
    }'''
    before = p.evaluate(snapshot)
    assert before['wide'] == (width == 1440), before
    assert before['viewTop'] > 20, before
    button.click()
    p.wait_for_function("JCs.find(j=>j.id==='6').arch==='资产处'")
    p.evaluate('() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    after = p.evaluate(snapshot)
    assert abs(after['viewTop'] - before['viewTop']) < 2, (before, after)
    assert abs(after['tableTop'] - before['tableTop']) < 2, (before, after)


@acc()
@pytest.mark.parametrize('action', ['jcArch', 'jcArchNo'])
@pytest.mark.parametrize('count', [30, 450])
def test_集采保存后不被重画锚定向上拉动(ui_page, action, count):
    from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS

    p = ui_page
    p.set_viewport_size({'width': 1920, 'height': 900})
    p.evaluate('''async ({count,columns,sumKeys}) => {
      window.jcRowsFixture=Array.from({length:count},(_,i)=>({
        id:i+1,project_seq:i+1,project_key:'测试仓库',date:'2026-01-01',
        material:'材料材料',supplier:'供应商名称供应商名称',trade_co:'贸易公司贸易公司贸易公司',
        contract_no:'合'.repeat(16),contract_amt:'100',tag:'纳入台账',arch:'未存档'
      }));
      API.m11List=async()=>({rows:jcRowsFixture,columns,sum_keys:sumKeys});
      API.m11Fields=async b=>{Object.assign(jcRowsFixture.find(r=>r.id===Number(b.id)),b.fields);return {ok:true};};
      VIEW='m11';await reloadM11();
    }''', {'count': count, 'columns': list(JC_COLUMNS), 'sumKeys': list(SUM_KEYS)})
    p.locator('[data-act="jcArch"][data-id="16"]').scroll_into_view_if_needed()
    p.set_viewport_size({'width': 2560, 'height': 900})
    p.evaluate('async()=>await reloadM11()')
    target = p.locator(f'[data-act="{action}"][data-id="16"]')
    target.scroll_into_view_if_needed()
    p.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    metrics = '''() => {
      const t=document.querySelector('table[data-sort-key="m11:jc"]').closest('.tw');
      return {top:t.scrollTop,wide:t.scrollWidth>t.clientWidth+1};
    }'''
    before = p.evaluate(metrics)
    assert not before['wide'] and before['top'] > 100, before
    if action == 'jcArch':
        target.click()
        p.wait_for_function("JCs.find(j=>j.id==='16').arch==='资产处'")
    else:
        target.fill('7')
        target.press('Tab')
        p.wait_for_function("JCs.find(j=>j.id==='16').archNo==='7'")
    p.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    after = p.evaluate(metrics)
    assert abs(after['top'] - before['top']) < 2, (before, after)


@acc()
def test_集采存档号提示按项目最大值且不受筛选影响(ui_page):
    from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS
    from app.mod03_notice.page import render_theme

    p = ui_page
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate('''async ({columns,sumKeys}) => {
      window.jcRowsFixture=[
        {id:1,project_key:'测试仓库',arch_no:'2',tag:'纳入台账'},
        {id:2,project_key:'测试仓库',arch_no:'5',tag:'不纳入'},
        {id:3,project_key:'测试仓库',arch_no:'',tag:'纳入台账'},
        {id:4,project_key:'测试仓库',arch_no:'',tag:'纳入台账'},
        {id:5,project_key:'另一个项目',arch_no:'',tag:'纳入台账'}
      ].map(r=>({...r,date:'2026-01-01',material:'钢材',supplier:'供应商',arch:'未存档'}));
      API.m11List=async()=>({rows:jcRowsFixture,columns,sum_keys:sumKeys});
      API.m11Fields=async b=>{
        window.archiveSaved=b;
        window.archiveWrites=(window.archiveWrites||0)+1;
        Object.assign(jcRowsFixture.find(r=>r.id===Number(b.id)),b.fields);return {ok:true};
      };
      fJc.tag='纳入台账';VIEW='m11';await reloadM11();
    }''', {'columns': list(JC_COLUMNS), 'sumKeys': list(SUM_KEYS)})
    field = p.locator('[data-act="jcArchNo"][data-id="3"]')
    assert field.input_value() == ''
    assert field.get_attribute('placeholder') == '6'
    assert '已填最大号 + 1' in field.get_attribute('title')
    assert p.locator('[data-act="jcArchNo"][data-id="1"]').input_value() == '2'
    assert p.locator('[data-act="jcArchNo"][data-id="5"]').get_attribute('placeholder') == '1'
    assert p.evaluate('window.archiveSaved === undefined')
    field.click()
    field.press('Enter')
    assert field.input_value() == '6'
    assert p.evaluate('window.archiveSaved === undefined')
    field.press('Enter')
    p.wait_for_function("JCs.find(j=>j.id==='3').archNo==='6'")
    assert p.locator('[data-act="jcArchNo"][data-id="4"]').get_attribute('placeholder') == '7'
    assert p.locator('[data-act="jcArchNo"][data-id="5"]').get_attribute('placeholder') == '1'
    assert p.evaluate('window.archiveWrites') == 1
    p.screenshot(path=str(Path(__file__).resolve().parents[2] / 'artifacts/jc-archive-hint-20261014.png'))


@acc()
def test_集采默认合同日期升序且表头仍可倒序(ui_page):
    from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS

    p = ui_page
    p.evaluate('''async ({columns,sumKeys}) => {
      API.m11List=async()=>({columns,sum_keys:sumKeys,rows:[
        {id:9,date:'2026-09-01',tag:'纳入台账',material:'新合同'},
        {id:2,date:'2024-01-01',tag:'纳入台账',material:'旧合同'},
        {id:3,date:'2024-01-01',tag:'纳入台账',material:'同日合同'}]});
      VIEW='m11';await reloadM11();
    }''', {'columns': list(JC_COLUMNS), 'sumKeys': list(SUM_KEYS)})
    ids = lambda: p.locator('tr[data-jc-id]').evaluate_all('rows=>rows.map(r=>r.dataset.jcId)')
    assert ids() == ['2', '3', '9']
    p.evaluate("() => {API.m11Export=async b=>{window.exportedIds=b.ids;return {ok:false,message:'隔离导出捕获'};};}")
    p.evaluate('ACT.jcExport()')
    assert p.evaluate('exportedIds') == [2, 3, 9]
    assert p.evaluate('JCs.map(j=>j.id)') == ['9', '2', '3'], '默认排序不应修改共享数组'
    header = p.locator('th[data-act="headSort"]').filter(has_text='合同日期')
    header.click()
    header.click()
    assert ids()[0] == '9'
    p.evaluate('ACT.jcExport()')
    assert str(p.evaluate('exportedIds[0]')) == ids()[0]


@acc()
def test_付款流水备注显示与编码链接键盘入口(ui_page):
    p = ui_page
    p.evaluate('''row => {
      FLs.push(adaptFlow({...row,remark:'本批付款备注'}));
      VIEW='m05';flf.ym='全部';render();
      window.openedNotice='';ACT.flNotice=t=>{window.openedNotice=t.dataset.fid;};
    }''', FL0)
    assert '本批付款备注' in p.locator('tr[data-flow-id="71"]').inner_text()
    link = p.locator('button[data-act="flNotice"]')
    assert link.get_attribute('class') == 'doc-link'
    assert link.inner_text() == 'DOC-101'
    assert link.evaluate('e=>getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)'
    link.focus()
    link.press('Enter')
    assert p.evaluate('openedNotice') == '71'


@acc()
def test_历史初始化从导入类型隐藏且旧选中项恢复到可用域(ui_page):
    p = ui_page
    p.evaluate('''async () => {
      API.impDomains=async()=>({domains:[
        {domain:'m04_plan',title:'付款计划',batch:false},
        {domain:'m06_proc',title:'过程资料',batch:true},
        {domain:'m06_mech_report',title:'机械费报表',batch:false}]});
      API.impSchema=async domain=>({domain,title:domain,fields:[],required:[]});
      API.impOptions=async()=>({ok:true});
      IMP.domain='m05_flow'; IMP.working=''; IMP.busy=false;
      await reloadImp(); VIEW='imp'; render();
    }''')
    select = p.locator('select[data-act="impDomain"]')
    assert select.locator('option').evaluate_all('(items)=>items.map(x=>x.value)') == ['m04_plan', 'm06_proc', 'm06_mech_report']
    assert select.input_value() == 'm04_plan'
    assert p.evaluate('IMP.schema.domain') == 'm04_plan'
    assert '历史付款流水' not in select.inner_text() and '集采台账' not in select.inner_text()
