"""机械费工作区的金额、草稿隔离和动作契约；Node中不连接业务服务。"""

from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from pathlib import Path
import shutil
import subprocess


@acc("ACC-RPT-MECH-001", "001-01")
@acc("ACC-RPT-MECH-001", "001-02")
@acc("ACC-RPT-MECH-001", "001-03")
@acc("ACC-RPT-MECH-001", "001-04")
@acc("ACC-RPT-MECH-001", "001-10")
def test_mechanical_workbench_public_behaviour():
    node = shutil.which('node')
    assert node, '机械费壳行为核验需要 Node.js'
    source = Path(__file__).resolve().parents[1] / 'app/web/shell/mechanical-workbench.js'
    program = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={console,assert,structuredClone,crypto:require('node:crypto').webcrypto};
vm.createContext(context);
vm.runInContext(`
 const V={},ACT={go:()=>{VIEW='m06';}},calls=[],notifications=[];
 let VIEW='m10',html='',latestModal=null,selected=[],resolveOld=null;
 const bjMonth=()=> '2026-09',pjLabel=x=>x,esc=x=>String(x??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
 const render=()=>{html=V.m10();},toast=x=>notifications.push(x),modal=x=>{latestModal=x;},closeModal=()=>{latestModal=null;};
 const errHuman=message=>new Error(message);
 const document={querySelectorAll:selector=>selector==='[data-mw-confirm]:checked'?selected:[],querySelector:()=>null};
 const $=()=>({value:''}),navigator={clipboard:{writeText:async()=>{}}};
 const reloadMech=async()=>{},reloadProc=async()=>{},dlExport=async()=> 'report.xlsx';
 const API={get:async url=>{calls.push(['GET',url]);return structuredClone(MW.data);},post:async(url,body)=>{calls.push(['POST',url,structuredClone(body)]);return {ok:true};}};
`,context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext(`(async()=>{
 assert.equal(mwMoney('0'),'0.00');assert.equal(mwMoney(null),'—');assert.equal(mwMoney('9007199254740993.12'),'9,007,199,254,740,993.12');
 assert.equal(mwCents('1.001'),100n);assert.equal(mwMoney('-0.12'),'-0.12');assert.equal(mwMoney('1.005'),'1.01');assert.equal(mwMoney('-1.005'),'-1.01');
 assert.equal(mwInternalValid('1.001'),false,'直接内租录入仍限制分精度');assert.equal(mwInternalValid('1.01'),true);
 assert.equal(mwNet({amount:'109.00',tax:'专票9%'}),'100.00');
 assert.equal(mwNet({amount:'109.00',tax:'未知9%说明'}),null);
 assert.equal(mwNet({amount:'109.00',tax:'专票9%',original:'109.00',originalTax:'专票9%',sourceNet:'99.99'}),'99.99');
 assert.equal(mwTotals(Array.from({length:3},()=>({amount:'0.004',tax:'普票',net:'0.004'}))).amount,'0.01');
 assert.equal(mwTotals(Array.from({length:3},()=>({amount:'0.004',tax:'普票',net:'0.004'}))).net,'0.01');
 assert.equal(mwNet({amount:'109.1234567890123456',tax:'专票9%',net:'100.1132631082679336'}),'100.1132631082679336');
 assert.equal(mwNet({amount:'109.0000000000000001',tax:'专票9%',original:'109.0000000000000002',originalTax:'专票9%',sourceNet:'99.99'}),'100.00','原金额比较保留全精度');
 assert.equal(mwTotals([{amount:null,tax:''}]).amount,null);
 MW.data={ok:true,settings:{shown_projects:['A'],plate_keywords:['升降'],revision:7},projects:[{warehouse:'A',name:'项目甲'},{warehouse:'B',name:'项目乙'}],
 details:[{warehouse:'A',ym:'2026-09',category:'zero',revision:4,rows:[{id:'one',device:'升降平台',amount:'109.00',tax:'专票9%',rate:'9.00',qty:'',plate:''},{id:'two',device:'汽车',amount:'21.00',tax:'普票',plate:''}],totals:{gross:'130.00',net:'121.00'},issues:[{id:'two',fields:['车牌']}]}],
 effective:[{warehouse:'A',ym:'2026-09',signature:'sept',values:{mech_0:'2.00',mech_1:'3.00',mech_2:'100.00',mech_3:'60.00'},source:{}},{warehouse:'A',ym:'2026-08',signature:'aug',values:{mech_0:'1.00'},source:{}}],
 summary:[{warehouse:'A',ym:'2026-09',cumulative:{zero:'200.00',monthly:'300.00',weekly:'0.00',internal:'400.00',company:'500.00'}}],
 reconciliations:[{warehouse:'A',relation:'report',left:'100.12',right:'100.00',raw:'0.12',pending:'0.00',ignored:'0.12',revision:8,i8_revision:9},{warehouse:'A',relation:'internal',left:'100.00',right:'100.00',raw:'0.00',pending:'0.00',ignored:'0.00',revision:1}],
 billDifferences:[{warehouse:'A',document_id:'bill',bill:'单1',settlement:'12816.08',approval:'12816.00',ignored:false,fact:'f',revision:3}],discoveries:[],matters:[],histories:[]};
 MW.data.discoveries=[{id:'unmapped',warehouse:'',projectId:'shared',projectName:'待核实的小微壳',kind:'unmapped',status:'pending',totals:{usage:'125.00',project:'25.00',team:null}}];
 MW.filter='findings';const unmappedHTML=mwWork();assert.ok(unmappedHTML.includes('待核实的小微壳'));assert.ok(unmappedHTML.includes('125.00'));assert.ok(unmappedHTML.includes('data-id="unmapped"'));assert.ok(unmappedHTML.includes('核实发现'));assert.ok(!unmappedHTML.includes('data-pj="shared"'),'未明确映射不能把i8项目键当仓库采用');
 MW.filter='pending';MW.data.discoveries=[];
 const workflowData=MW.data;
 MW.data={projects:['国风','龙源','兰考','缺侧'],settings:{shown_projects:['国风','龙源','兰考','缺侧']},details:[],effective:[],matters:[],billDifferences:[],
   reconciliations:['国风','龙源','兰考','缺侧'].flatMap(warehouse=>['report','internal'].map(relation=>({warehouse,relation,left:warehouse==='兰考'?null:'0.00',right:['兰考','缺侧'].includes(warehouse)?null:'0.00',pending:['兰考','缺侧'].includes(warehouse)?null:'0.00'}))),
   discoveries:[{warehouse:'国风',id:'first',kind:'first',status:'pending'},{warehouse:'龙源',id:'changed',kind:'changed',status:'pending'}]};
 const workRecords=mwReconciliations();
 assert.equal(mwPending(workRecords[0]),false,'国风累计对平，首次取数不冒充差额');
 assert.equal(mwPending(workRecords[1]),false,'龙源累计对平，来源变化不冒充差额');
 assert.equal(mwPending(workRecords[2]),false,'兰考全空不能因null差额进入待处理');
 assert.equal(mwPending(workRecords[3]),true,'有报表数据缺核对侧仍须处理');
 assert.ok(mwWorkTable([workRecords[2]]).includes('尚未录入'));
 assert.ok(mwWorkTable([workRecords[3]]).includes('待取数'));
 MW.filter='pending';assert.ok(!mwWork().includes('data-id="first"'));
 MW.filter='findings';assert.ok(mwWork().includes('data-id="first"'));assert.ok(mwWork().includes('data-id="changed"'));assert.ok(!mwWork().includes('项目核查进度'));
 MW.data.matters=[{warehouse:'国风',text:'待确认税率 <script>',completed:false},{warehouse:'国风',text:'已完成',completed:true}];
 const followup=mwWorkTable([workRecords[0]]);assert.ok(followup.includes('1项未完成'));assert.ok(followup.includes('待确认税率 &lt;script&gt;'));assert.equal((followup.match(/data-act="mwMatters"/g)||[]).length,1,'跟进入口不重复');
 assert.ok(mwPending(workRecords[0]),'真实未完成跟进保留待处理');
 MW.data=workflowData;MW.filter='pending';
 MW.tab='zero';MW.data.effective[0].sources={mech_2:{mode:'detail'},mech_4:{mode:'manual'}};MW.data.effective[0].values.mech_4='91.00';
 MW.data.details[0].blocked_columns={mech_2:[],mech_4:[{id:'one',fields:['票种／税率']}]};mwConfirmDialog();
 assert.match(latestModal.body,/data-column="mech_2" checked/);assert.match(latestModal.body,/data-column="mech_4" disabled/,'净额待补不能禁用已齐备的含税列');
 MW.data.details[0].blocked_columns={mech_2:[],mech_4:[]};mwConfirmDialog();
 assert.match(latestModal.body,/data-column="mech_4"  aria-label/,'人工净额默认不勾选');
 selected=[{dataset:{mwConfirm:'0',column:'mech_2'}},{dataset:{mwConfirm:'0',column:'mech_4'}}];calls.length=0;await ACT.mwConfirmApply();
 const confirmCalls=calls.filter(c=>c[1].endsWith('/amounts-confirm'));assert.equal(confirmCalls.length,1);assert.equal(JSON.stringify(confirmCalls[0][2].columns),'["mech_2","mech_4"]');selected=[];
 assert.equal(mwPlateRequired(MW.data.details[0].rows[0]),false);
 MW.tab='zero';MW.onlyProblems=true;
 const detailHTML=mwDetails();assert.ok(detailHTML.includes('130.00'));assert.ok(detailHTML.includes('121.00'));assert.ok(!detailHTML.includes('value="升降平台"'));assert.ok(detailHTML.includes('value="汽车"'));
 assert.ok(mwDetails().includes('data-act="mwAdd"'));
 assert.equal(mwPending(mwReconciliations()[0]),true,'独立单据差额不能因两条累计对平而消失');
 assert.equal(mwCumulative('A').mech_1,'400.00');assert.equal(mwCumulative('A').mech_0,'500.00');
 const fakeInput={dataset:{pj:'A',index:'0',field:'rate'},value:'10.00',classList:{add:()=>{}},closest:()=>null};
 ACT.mwEdit(fakeInput);assert.equal(mwRows('A')[0].amount,'109.00','缺数量时改单价保留合价');assert.equal(MW.data.details[0].rows[0].rate,'9.00','编辑不修改系统已保存版本');
 ACT.mwEdit({...fakeInput,dataset:{pj:'A',index:'0',field:'qty'},value:'2小时'});ACT.mwEdit({...fakeInput,value:'0.004'});assert.equal(mwRows('A')[0].qty,'2小时');assert.equal(mwRows('A')[0].amount,'109.00','数量原文不被猜成数值');
 ACT.mwEdit({...fakeInput,dataset:{pj:'A',index:'0',field:'qty'},value:'3'});assert.equal(mwRows('A')[0].amount,'0.01','全精度单价先乘数量再舍分');
 ACT.mwEdit({...fakeInput,value:'10.00'});
 ACT.mwEdit({...fakeInput,dataset:{pj:'A',index:'0',field:'qty'},value:'1.125'});assert.equal(mwRows('A')[0].amount,'11.25');
 ACT.mwEdit({...fakeInput,dataset:{pj:'A',index:'0',field:'amount'},value:'109.1234567890123456'});assert.ok(mwInput(mwRows('A')[0],'amount','合价',0,'A').includes('value="109.1234567890123456"'),'金额输入完整展示源精度');
 mwRows('A')[0].usage='旧用途';ACT.mwEdit({...fakeInput,dataset:{pj:'A',index:'0',field:'use'},value:'新用途'});assert.equal(mwRows('A')[0].use,'新用途');assert.equal(mwRows('A')[0].usage,undefined,'编辑只保存一份规范用途字段');
 const savedEffective=JSON.stringify(MW.data.effective);calls.length=0;await ACT.mwSave();assert.ok(calls.some(c=>c[1].endsWith('/details-save')));assert.ok(!calls.some(c=>c[1].endsWith('/amounts-confirm')));assert.equal(JSON.stringify(MW.data.effective),savedEffective);
 MW.scope='A';ACT.mwTab({dataset:{tab:'monthly'}});assert.equal(MW.scope,'');
 MW.scope='A';ACT.go({dataset:{k:'m06'}});assert.equal(MW.scope,'');VIEW='m10';
 MW.tab='zero';MW.scope='A';mwEditDraft('A');ACT.mwTab({dataset:{tab:'summary'}});assert.equal(MW.drafts.size,1,'切页保留尚未保存的明细');
 ACT.mwInternalEdit({dataset:{pj:'A',field:'mech_0'},value:'12.00',classList:{add:()=>{}}});
 MW.month='2026-08';assert.equal(mwInternal('A').mech_0,undefined,'不同月份内租草稿隔离');
 ACT.mwInternalEdit({dataset:{pj:'A',field:'mech_0'},value:'15.00',classList:{add:()=>{}}});
 calls.length=0;await ACT.mwInternalApply();const internalCalls=calls.filter(c=>c[1].endsWith('/internal-save'));assert.equal(internalCalls.length,2);assert.equal(internalCalls[0][2].ym,'2026-09');assert.equal(internalCalls[0][2].effective_signature,'sept');assert.equal(internalCalls[1][2].ym,'2026-08');
 MW.month='2026-09';calls.length=0;await ACT.mwIgnore({dataset:{pj:'A',relation:'report'}});const ignoreCall=calls.find(c=>c[1].endsWith('/ignore'));assert.equal(ignoreCall[2].revision,8);assert.equal(ignoreCall[2].raw,'0.12');assert.equal(ignoreCall[2].i8_revision,9);
 calls.length=0;await ACT.mwDocument({dataset:{pj:'A',id:'bill',undo:'1'}});const billCall=calls.find(c=>c[1].endsWith('/document-ignore'));assert.equal(billCall[2].fact,'f');assert.equal(billCall[2].undo,true);
 MW.data.details=[];MW.tab='zero';MW.onlyProblems=false;MW.drafts.clear();assert.ok(mwDetails().includes('尚无明细'));ACT.mwAdd({dataset:{pj:'A'}});assert.equal(mwRows('A').length,1);
 MW.preview={sheets:[{name:'表1',rows:[[{value:'<script>bad</script>'}]]}],warnings:['待补'],projects:['A']};assert.ok(mwPreviewView().includes('&lt;script&gt;bad&lt;/script&gt;'));
 const oldPost=API.post;API.post=async()=>({ok:false,message:'明细已变化，请重新核对'});await ACT.mwSave();assert.equal(MW.drafts.size,1,'保存被拒时保留未保存草稿');assert.ok(notifications.some(message=>message.includes('明细已变化')));API.post=oldPost;
 let completeOld;const currentData=structuredClone(MW.data);API.get=url=>url.includes('2026-09')?new Promise(resolve=>{completeOld=resolve;}):Promise.resolve({...currentData,marker:'new'});
 MW.month='2026-09';const oldRequest=reloadMechanicalWorkbench();MW.month='2026-10';await reloadMechanicalWorkbench();completeOld({...currentData,marker:'old'});await oldRequest;assert.equal(MW.data.marker,'new','旧月份迟到的回包不能覆盖新月份');
})()`,context).catch(error=>{console.error(error);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program, str(source)], text=True,
                            encoding='utf-8', errors='strict', capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@acc()
def test_detail_sources_require_explicit_switch_and_confirmation_columns_are_independent(ui_page):
    from app.mod03_notice.page import render_theme
    from tests.test_tail315_proc import report

    p = ui_page
    p.add_style_tag(content=render_theme('默认'))
    p.add_style_tag(content=(Path(__file__).resolve().parents[1] / 'app/web/shell/mechanical-workbench.css').read_text(encoding='utf-8'))
    p.evaluate("""async data => {
      window.calls=[];BOOTING=false;VIEW='m06';
      data.matrices['测试仓库'].raw[0].mech_2='109.00';
      data.matrices['测试仓库'].adjusted[0].mech_2='109.00';
      window.sources={测试仓库:{'2026-01':{mech_2:{mode:'detail'},mech_4:{mode:'manual'}}}};
      API.m06Matrix=async()=>data;
      API.m06Mech=async()=>({mech:{测试仓库:{'2026-01':['0','0','109.00','0','91.00','0']}},
        sources,effective_signatures:{测试仓库:{'2026-01':'month-signature'}}});
      MW.data={ok:true,projects:[{warehouse:'测试仓库',name:'测试项目'}],settings:{shown_projects:['测试仓库']},
        details:[{warehouse:'测试仓库',ym:'2026-01',category:'zero',revision:4,rows:[{device:'车',amount:'109',net:'100'}],totals:{gross:'109',net:'100'},issues:[]}],
        effective:[{warehouse:'测试仓库',ym:'2026-01',signature:'month-signature',values:{mech_2:'109',mech_4:'91'},sources:{mech_2:{mode:'detail'},mech_4:{mode:'manual'}}}]};
      API.get=async()=>structuredClone(MW.data);
      API.post=async(url,body)=>{calls.push({url,body:structuredClone(body)});
        if(url.endsWith('/source-manual'))sources.测试仓库['2026-01'][body.columns[0]]={mode:'manual'};
        return {ok:true};};
      await reloadMech();await reloadProc();render();
    }""", report())
    assert p.locator('[data-act="procMechSave"][data-i="2"]').count() == 0
    assert p.locator('[data-act="procMechSave"][data-i="4"]').count() == 1
    assert '明细确认' in p.inner_text('#view')
    scratch = Path(__file__).resolve().parents[2] / '.artifacts/machinery-fee-workbench-fixes/20261019'
    scratch.mkdir(parents=True, exist_ok=True)
    p.locator('[data-act="procMechManual"]').evaluate("el=>{const table=el.closest('.tw');table.scrollLeft=table.scrollWidth;}")
    p.screenshot(path=str(scratch / 'mechanical-source-process-readonly.png'))
    before = p.evaluate('calls.length')
    switch = p.locator('[data-act="procMechManual"][data-i="2"]')
    switch.focus()
    p.keyboard.press('Enter')
    assert p.evaluate('calls.length') == before, '打开确认框不能修改来源'
    assert '109.00' in p.inner_text('#modalRoot')
    p.screenshot(path=str(scratch / 'mechanical-source-manual-dialog.png'))
    p.click('[data-act="closeModal"]')
    assert p.locator('[data-act="procMechSave"][data-i="2"]').count() == 0
    p.click('[data-act="procMechManual"][data-i="2"]')
    p.click('[data-act="procMechManualApply"]')
    p.wait_for_function("document.querySelector('[data-act=procMechSave][data-i=\"2\"]')!==null")
    assert p.locator('[data-act="procMechSave"][data-i="2"]').input_value() == '109'
    assert p.evaluate('calls') == [{'url': '/api/m06/workbench/source-manual', 'body': {
        'warehouse': '测试仓库', 'ym': '2026-01', 'columns': ['mech_2'],
        'effective_signature': 'month-signature', 'confirmed': True}}]

    p.evaluate("() => {MW.month='2026-01';MW.tab='zero';VIEW='m10';mwConfirmDialog();}")
    assert p.locator('[data-mw-confirm][data-column="mech_2"]').is_checked()
    assert not p.locator('[data-mw-confirm][data-column="mech_4"]').is_checked(), '已有人工净额默认保留'
    p.locator('[data-mw-confirm][data-column="mech_2"]').uncheck()
    p.locator('[data-mw-confirm][data-column="mech_4"]').check()
    p.screenshot(path=str(scratch / 'mechanical-source-confirm-columns.png'))
    p.click('[data-act="mwConfirmApply"]')
    p.wait_for_function("calls.some(c=>c.url.endsWith('/amounts-confirm')) && !MW.busy")
    assert p.evaluate("calls.find(c=>c.url.endsWith('/amounts-confirm')).body") == {
        'warehouse': '测试仓库', 'ym': '2026-01', 'category': 'zero', 'columns': ['mech_4'],
        'revision': 4, 'effective_signature': 'month-signature'}


@acc()
def test_workbench_pending_followups_shared_links_and_column_groups(ui_page):
    from app.mod03_notice.page import render_theme

    p = ui_page
    p.add_style_tag(content=render_theme('默认'))
    web = Path(__file__).resolve().parents[1] / 'app/web'
    p.add_style_tag(content=(web / 'shell/mechanical-workbench.css').read_text(encoding='utf-8'))
    p.evaluate("""() => {
      BOOTING=false;VIEW='m10';MW.tab='work';MW.month='2026-09';MW.filter='pending';
      const projects=['国风','龙源','兰考','有差额','待取数','待核对','有跟进'];
      const relation=(warehouse,kind)=>({warehouse,relation:kind,left:warehouse==='兰考'?null:'100.00',
        right:['兰考','待取数','待核对'].includes(warehouse)?null:'100.00',
        pending:['兰考','待取数','待核对'].includes(warehouse)?null:warehouse==='有差额'?'10.00':'0.00',
        ignored:'0.00',fetched_at:warehouse==='待核对'?'2026-10-19 10:00':null});
      MW.data={ok:true,projects:projects.map(warehouse=>({warehouse,name:warehouse})),settings:{shown_projects:projects},
        details:[],effective:projects.map(warehouse=>({warehouse,ym:MW.month,values:warehouse==='兰考'?{}:{mech_2:'100.00',mech_3:'200.00'}})),
        reconciliations:projects.flatMap(warehouse=>['report','internal'].map(kind=>relation(warehouse,kind))),billDifferences:[],
        histories:[],summary:[],i8:[],matters:[{id:'one',warehouse:'有跟进',text:'请核实十月租赁税率与凭据',completed:false},{id:'done',warehouse:'有跟进',text:'已办结事项',completed:true}],
        discoveries:[{id:'first',warehouse:'国风',kind:'first',status:'pending'},{id:'changed',warehouse:'龙源',kind:'changed',status:'pending'}]};
      window.writeCalls=[];API.post=async(url,body)=>{writeCalls.push({url,body});return {ok:true};};render();
    }""")
    main = p.locator('.mw-work').first
    assert main.locator('tbody tr').count() == 4
    assert '国风' not in main.inner_text() and '兰考' not in main.inner_text()
    assert '待取数' in main.inner_text() and '待核对' in main.inner_text()
    assert '项目核查进度' not in p.inner_text('#view')
    assert main.locator('[data-act="mwMatters"][data-pj="有跟进"]').inner_text() == '1项未完成'
    assert '请核实十月租赁税率与凭据' in main.inner_text()
    assert main.locator('tbody tr').first.locator('.vsep').count() == 5
    assert main.locator('thead tr').first.locator('.vsep').count() == 5
    assert main.locator('thead tr').nth(1).locator('.vsep').count() == 2
    p.click('[data-act="mwMatters"][data-pj="有跟进"]')
    assert '跟进事项 · 有跟进' in p.inner_text('#modalRoot')
    assert '已办结事项' in p.inner_text('#modalRoot')
    p.click('[data-act="closeModal"]')
    assert p.locator('.mw-actions [data-act="mwMatters"]').count() == 0
    assert p.locator('.mw-actions [data-act="mwHistory"]').inner_text() == 'i6历史数据'
    assert p.locator('.mw-actions [data-act="mwI8"]').inner_text() == '抓取i8'
    p.click('[data-act="mwHistory"]')
    assert 'i6历史数据' in p.inner_text('#modalRoot')
    p.click('[data-act="closeModal"]')
    scratch = Path(__file__).resolve().parents[2] / '.artifacts/mw-controls/20261019'
    scratch.mkdir(parents=True, exist_ok=True)
    for scale in ('1', '1.25'):
        p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
        month = p.locator('.mw-month').bounding_box()
        tabs = p.locator('.mw-tabs').bounding_box()
        assert month['x'] < tabs['x']
        assert month['x'] + month['width'] <= tabs['x'] or month['y'] + month['height'] <= tabs['y']
        p.screenshot(path=str(scratch / ('workbench-' + scale + '.png')))
    p.evaluate("document.documentElement.style.setProperty('--fscale','1')")
    p.click('[data-act="mwFilter"][data-filter="all"]')
    assert '尚未录入' in p.locator('.mw-work tbody tr').filter(has_text='兰考').inner_text()
    p.click('[data-act="mwFilter"][data-filter="findings"]')
    assert p.locator('[data-act="mwDiscovery"]').count() == 2
    p.click('[data-act="mwDiscovery"][data-id="first"]')
    assert p.locator('[data-act="mwDiscoveryResolve"]').count() == 1
    p.click('[data-act="closeModal"]')
    assert p.evaluate('writeCalls.length') == 0, '查看跟进和取数变化不能自动完成任何记录'
    p.click('[data-act="mwTab"][data-tab="summary"]')
    link = p.locator('[data-act="mwOpenDetail"][data-pj="国风"]').first
    assert link.get_attribute('class') == 'text-link'
    assert link.locator('svg').count() == 0
    assert link.evaluate('el=>getComputedStyle(el).borderTopWidth') == '0px'
    assert link.evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
    link.hover()
    assert link.evaluate('el=>getComputedStyle(el).backgroundColor') != 'rgba(0, 0, 0, 0)'
    assert link.locator('.text-link-label').evaluate('el=>getComputedStyle(el).textDecorationLine') == 'underline'
    link.focus()
    p.keyboard.press('Tab')
    p.keyboard.press('Shift+Tab')
    assert link.evaluate('el=>getComputedStyle(el).outlineStyle') == 'solid'
    assert p.locator('.mw-company thead tr').first.locator('.vsep').count() == 4
    assert p.locator('.mw-company thead tr').nth(1).locator('.vsep').count() == 3
    assert p.locator('.mw-company tbody tr').first.locator('.vsep').count() == 4
    assert p.locator('.mw-company .sumrow .vsep').count() == 3
    p.keyboard.press('Enter')
    assert p.evaluate('MW.tab') == 'zero'


@acc()
def test_agent_detail_file_preview_before_confirm_without_history_entry(ui_page):
    import json
    from app.mod03_notice.page import render_theme

    p=ui_page
    p.add_style_tag(content=render_theme('默认'))
    web=Path(__file__).resolve().parents[1]/'app/web'
    p.add_style_tag(content=(web/'shell/mechanical-workbench.css').read_text(encoding='utf-8'))
    p.evaluate("""() => {
      BOOTING=false;VIEW='m10';MW.tab='summary';window.importCalls=[];
      crypto.randomUUID=()=> 'isolated-request';
      MW.data={ok:true,projects:[{warehouse:'甲',name:'项目甲'}],settings:{shown_projects:['甲']},details:[],effective:[],summary:[],reconciliations:[],billDifferences:[],matters:[],discoveries:[],histories:[]};
      API.get=async()=>structuredClone(MW.data);reloadMech=async()=>{};reloadProc=async()=>{};
      API.post=async(url,body)=>{importCalls.push({url,body:structuredClone(body)});
        if(url.endsWith('/import-preview'))return {ok:true,preview_id:'isolated',batches:[{
          ...body.batches[0],incoming:body.batches[0].rows,key:'batch',conflicts:[],
          effective:{values:{mech_2:'99.00',mech_4:'90.00'}}}]};
        return {ok:true};};render();
    }""")
    p.click('[data-act="mwImport"]')
    assert p.locator('#mw-import-kind').count()==0
    assert '历史月值' not in p.inner_text('#modalRoot')
    row={'id':'a','device':'汽车吊','spec':'25吨','plate':'苏A12345','amount':'113.00','tax':'13%专票',
         'source':{'sheet':'零租原报','row':5}}
    payload={'detail_import':{'batches':[{'warehouse':'甲','ym':'2026-10','category':'zero','rows':[row],'source':{'file':'原报.xlsx'}}]}}
    p.set_input_files('#mw-import-file',{'name':'机械费录入.json','mimeType':'application/json','buffer':json.dumps(payload,ensure_ascii=False).encode()})
    p.click('[data-act="mwImportPreview"]')
    p.wait_for_selector('[data-act="mwImportConfirm"]')
    assert '99.00 → 113.00' in p.inner_text('#modalRoot')
    assert '90.00 → 100.00' in p.inner_text('#modalRoot')
    assert len(p.evaluate('importCalls'))==1
    assert p.evaluate('importCalls[0].url').endswith('/import-preview')
    p.click('#modalRoot details summary')
    assert '汽车吊' in p.inner_text('#modalRoot') and '零租原报 5' in p.inner_text('#modalRoot')
    assert all(box['height']<150 for box in p.locator('.mw-import-table').evaluate_all('els=>els.map(el=>({height:el.getBoundingClientRect().height}))'))
    scratch=Path(__file__).resolve().parents[2]/'.artifacts/mechanical-skill-import/20261019'
    scratch.mkdir(parents=True,exist_ok=True)
    p.screenshot(path=str(scratch/'detail-preview.png'))
    p.evaluate("document.documentElement.style.setProperty('--fscale','1.25')")
    p.screenshot(path=str(scratch/'detail-preview-1.25.png'))
    assert p.locator('[data-act="mwImportConfirm"]').bounding_box()['y']<p.viewport_size['height']
    p.click('[data-act="mwImportConfirm"]')
    p.wait_for_function('importCalls.length===2 && !MW.busy')
    assert p.evaluate('importCalls[1].body')=={'preview_id':'isolated','resolutions':{},'confirm_amounts':False}
