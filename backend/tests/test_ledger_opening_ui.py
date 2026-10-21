"""真实壳内直接编辑历史行；接口均拦截，不写正式数据。"""
from pathlib import Path
import os
import pytest
from playwright.sync_api import expect
from tests.ui_helpers import ui_page  # noqa: F401
from tools.audit.workspace_paths import output


def setup(p):
    p.evaluate("""()=>{
      VIEW='m05';ledProj='测试仓库';M05.ledger={project_id:1,sides:['辅材','机械'].map((label,i)=>({label,
        category:i?'mechanical':'material',rows:[
          {seq:1,month:'2025-11',row_kind:i?'month':'manual',record_id:i?null:1,editable:true,token:'original',
           other_expense:'1510869.33',payment:'1510869.33',remark:'截至11月底累计，已付清'},
          {seq:2,month:'2025-12',row_kind:'month',record_id:null,editable:false,token:'next',
           other_expense:'131033.00',payment:'131033.00',remark:''}]}))};
      reloadM05=async()=>{Object.keys(LOADERS).forEach(x=>LOADED.add(x));render();};render();
    }""")


def test_historical_cells_are_inline_and_mechanical_settlement_readonly(ui_page):
    p=ui_page;setup(p)
    for label in ('辅材','机械'):
        side=p.get_by_role('region',name=label+'欠款台账')
        expect(side.locator('[data-field="paid_amount"]')).to_have_count(1)
        expect(side.get_by_text('2025-12',exact=True)).to_be_visible()
    expect(p.locator('[data-field="settle_amount"]')).to_have_count(1)
    expect(p.locator('[data-act="addLg"]')).to_have_count(1)
    expect(p.locator('[data-act="historyDelete"]')).to_have_count(1)
    assert '期初' not in p.get_by_role('region',name='辅材欠款台账').inner_text()
    expect(p.locator('[data-act="lgKind"]')).to_have_count(0)


@pytest.mark.parametrize('accepted',[True,False])
def test_inline_edit_receipt_carries_row_token_and_reports_failure(ui_page,accepted):
    p=ui_page;setup(p);writes=[]
    def save(route):
        writes.append(route.request.post_data_json)
        route.fulfill(status=200 if accepted else 400,json={'ok':accepted,'message':'已保存' if accepted else '这一行已变化'})
    p.route('**/api/m05/history/save',save)
    box=p.locator('[data-sc="辅材"][data-field="paid_amount"]')
    box.fill('1500000.00');box.press('Tab')
    expect(p.locator('.toast').last).to_contain_text('台账已保存' if accepted else '这一行已变化')
    assert writes[0]['token']=='original'
    assert writes[0]['paid_amount']=='1500000.00'
    assert writes[0]['settle_amount']=='1510869.33'
    assert writes[0]['entry_kind']=='manual'


def test_add_history_row_calls_save_once_without_reconciliation_dialog(ui_page):
    p=ui_page;setup(p);writes=[]
    p.route('**/api/m05/history/save',lambda route:(writes.append(route.request.post_data_json),route.fulfill(json={'ok':True,'id':2})))
    p.get_by_role('button',name='＋ 新增历史行',exact=True).click()
    expect(p.locator('.toast').last).to_contain_text('已新增历史行')
    assert len(writes)==1 and writes[0]['cutoff_ym']=='2025-11'
    expect(p.locator('#modalRoot .modal')).to_have_count(0)


def test_successful_save_refresh_failure_is_not_a_rejected_save(ui_page):
    p=ui_page;setup(p)
    p.route('**/api/m05/history/save',lambda route:route.fulfill(json={'ok':True,'id':2}))
    p.evaluate("()=>{reloadM05=async()=>{throw Error('隔离读取失败')};}")
    box=p.locator('[data-sc="辅材"][data-field="paid_amount"]');box.fill('100');box.press('Tab')
    expect(p.locator('.toast').last).to_contain_text('已保存，但页面数据未能刷新')


@pytest.mark.parametrize('width,scale',[(2320,'1'),(1440,'1.25'),(1024,'1.25')])
def test_ledger_layout_is_readable_at_supported_widths(ui_page,width,scale):
    p=ui_page;p.set_viewport_size({'width':width,'height':1100});setup(p)
    p.evaluate('(scale)=>document.documentElement.style.setProperty("--fscale",scale)',scale)
    for label in ('辅材','机械'):
        side=p.get_by_role('region',name=label+'欠款台账')
        expect(side.locator('[data-field="paid_amount"]')).to_be_visible()
        assert side.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    if output:=os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
        p.screenshot(path=str(folder/f'ledger-{width}-{scale}.png'),full_page=True)


def test_archive_states_use_distinct_readable_colors_in_existing_themes(ui_page):
    from app.mod03_notice.page import THEME_SEEDS,render_theme
    from app.mod11_jc.domain import JC_COLUMNS,SUM_KEYS
    p=ui_page;p.set_viewport_size({'width':2320,'height':1000})
    p.evaluate("""async({columns,sumKeys})=>{
      API.m11List=async()=>({rows:['资产处','已存档'].map((arch,i)=>({
        id:i+1,project_seq:i+1,project_key:'测试仓库',date:'2026-01-01',material:'钢材',
        supplier:'供应商',contract_amt:'100',tag:'纳入台账',arch})),columns,sum_keys:sumKeys});
      VIEW='m11';await reloadM11();
    }""",{'columns':list(JC_COLUMNS),'sumKeys':list(SUM_KEYS)})
    tags=p.locator('table[data-sort-key="m11:jc"] .tag')
    asset=tags.filter(has_text='资产处');done=tags.filter(has_text='已存档')
    for theme in THEME_SEEDS:
        style=p.add_style_tag(content=render_theme(theme))
        a=asset.evaluate('e=>({color:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor})')
        b=done.evaluate('e=>({color:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor})')
        assert a['color']!=b['color'] and a['bg']!=b['bg'],theme
        style.evaluate('e=>e.remove()')
    p.add_style_tag(content=render_theme('松绿'))
    asset.scroll_into_view_if_needed()
    if output:=os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
        p.screenshot(path=str(folder/'archive-colors.png'))


def project_server(p):
    """模拟按项目独立存储，使用真实reloadM05及项目选择动作。"""
    from urllib.parse import urlparse,parse_qs
    server={'rows':{1:[],2:[],3:[]},'writes':[],'hold':set(),'pending':[],'reads':[]}
    def ledger(pid):
        return {'project_id':pid,'sides':[{'label':label,'rows':server['rows'][pid] if i==0 else []}
            for i,label in enumerate(('辅材','机械'))]}
    def route(req):
        path=urlparse(req.request.url).path
        if path.endswith('/ledger'):
            pid=int(parse_qs(urlparse(req.request.url).query)['project_id'][0]);server['reads'].append(pid)
            if pid in server['hold']:
                server['pending'].append((pid,req))
                p.evaluate('n=>window.pendingLedgerReads=n',len(server['pending']))
            else:req.fulfill(json=ledger(pid))
        elif path.endswith('/history/save'):
            body=req.request.post_data_json;server['writes'].append(body);pid=body['project_id']
            server['rows'][pid]=[{'seq':1,'month':body['cutoff_ym'],'row_kind':'manual','record_id':501,
                'editable':True,'token':'saved','other_expense':body['settle_amount'],
                'payment':body['paid_amount'],'remark':body['remark']}]
            req.fulfill(json={'ok':True,'id':501})
        elif path.endswith('/flows'):req.fulfill(json={'rows':[]})
        elif path.endswith('/debt'):req.fulfill(json={'openings':[],'by_category':[]})
        else:req.fulfill(json={})
    p.route('**/api/m05/**',route)
    p.route('**/api/history/status',lambda req:req.fulfill(json={'undo':None,'redo':None}))
    p.evaluate("""()=>{
      PJs=[['乌兰仓','乌兰察布'],['乙仓','乙项目'],['丙仓','丙项目']].map(([name,disp],i)=>({
        id:String(i+1),name,disp,full:disp,type:'normal',status:'在建',phid:String(i+1)}));
      NO=[];VIEW='m05';ledProj='乌兰仓';BOOTING=false;render();
    }""")
    p.wait_for_function('M05.ledger?.project_id===1')
    return server,ledger


def pick_project(p,name):
    p.locator('[data-act="ledPjToggle"]').click()
    p.locator('[data-act="ledPjPick"][data-pj="'+name+'"]').click()


def test_previous_cell_save_keeps_next_cell_focus_and_draft(ui_page):
    p=ui_page;server,ledger=project_server(p)
    server['rows'][1]=[{'seq':1,'month':'2025-11','row_kind':'manual','record_id':501,
        'editable':True,'token':'original','other_expense':'10.00','payment':'1.00','remark':''}]
    p.evaluate('void reloadM05()')
    settle=p.locator('[data-sc="辅材"][data-field="settle_amount"]')
    paid=p.locator('[data-sc="辅材"][data-field="paid_amount"]')
    expect(settle).to_have_value('10.00')
    server['hold'].add(1)
    settle.fill('100');settle.press('Tab')
    expect(paid).to_be_focused();paid.fill('555')
    p.wait_for_function('window.pendingLedgerReads===1')
    assert len(server['writes'])==1 and server['writes'][0]['settle_amount']=='100'
    server['hold'].clear()
    _,req=server['pending'].pop();req.fulfill(json=ledger(1))
    expect(p.locator('.toast').last).to_contain_text('台账已保存')
    assert paid.evaluate('(el)=>({focused:document.activeElement===el,value:el.value})')=={
        'focused':True,'value':'555'}
    if folder:=os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        p.screenshot(path=str(Path(folder)/'ledger-focus-kept.png'),full_page=True)
    server['hold'].add(1);paid.press('Tab')
    p.wait_for_function('window.pendingLedgerReads===1')
    toggle=p.locator('[data-act="ledPjToggle"]');button=toggle.element_handle()
    toggle.hover();p.mouse.down()
    p.evaluate('()=>new Promise(requestAnimationFrame)')
    assert button.evaluate('el=>el.isConnected'), '离格补画不得吞掉下一次按钮点击'
    p.mouse.up()
    expect(p.locator('[data-act="ledPjPick"]').first).to_be_visible()
    server['hold'].clear();_,req=server['pending'].pop();req.fulfill(json=ledger(1))
    expect(paid).to_have_value('555.00')
    assert server['writes'][-1]['paid_amount']=='555'
    assert server['writes'][-1]['settle_amount']=='100.00'


def test_deferred_redraw_edits_record_id_after_month_reorders_rows(ui_page):
    p=ui_page;server,ledger=project_server(p)
    server['rows'][1]=[{'seq':i,'month':month,'row_kind':'manual','record_id':rid,
        'editable':True,'token':'original','other_expense':'10.00','payment':'1.00','remark':''}
        for i,month,rid in [(1,'2025-10',502),(2,'2025-11',501)]]
    def save(req):
        body=req.request.post_data_json;server['writes'].append(body)
        row=next(r for r in server['rows'][1] if r['record_id']==body['id'])
        row.update(month=body['cutoff_ym'],other_expense=body['settle_amount'],
            payment=body['paid_amount'],remark=body['remark'],token='saved')
        server['rows'][1].sort(key=lambda r:r['month'])
        for i,r in enumerate(server['rows'][1],1):r['seq']=i
        req.fulfill(json={'ok':True,'id':body['id']})
    p.route('**/api/m05/history/save',save)
    p.evaluate('void reloadM05()')
    month=p.locator('[data-sc="辅材"][data-field="cutoff_ym"]').nth(1)
    expect(month).to_have_value('2025-11')
    server['hold'].add(1);month.fill('2025-09')
    paid=p.locator('[data-sc="辅材"][data-field="paid_amount"]').nth(1)
    paid.click();paid.fill('777')
    p.wait_for_function('window.pendingLedgerReads===1')
    server['hold'].clear();_,req=server['pending'].pop();req.fulfill(json=ledger(1))
    expect(p.locator('.toast').last).to_contain_text('台账已保存')
    expect(paid).to_be_focused();expect(paid).to_have_value('777')
    paid.press('Tab');p.locator('#ttl').click()
    expect(p.locator('[data-sc="辅材"][data-field="paid_amount"]').first).to_have_value('777.00')
    assert server['writes'][-1]['id']==501
    assert next(r for r in server['rows'][1] if r['record_id']==502)['payment']=='1.00'


def test_deferred_redraw_does_not_silently_overwrite_changed_cell(ui_page):
    p=ui_page;server,ledger=project_server(p)
    server['rows'][1]=[{'seq':1,'month':'2025-11','row_kind':'manual','record_id':501,
        'editable':True,'token':'original','other_expense':'10.00','payment':'1.00','remark':''}]
    p.evaluate('void reloadM05()')
    settle=p.locator('[data-sc="辅材"][data-field="settle_amount"]')
    paid=p.locator('[data-sc="辅材"][data-field="paid_amount"]')
    expect(settle).to_have_value('10.00');server['hold'].add(1)
    settle.fill('100');settle.press('Tab');paid.fill('555')
    p.wait_for_function('window.pendingLedgerReads===1')
    server['rows'][1][0].update(payment='2.00',token='external')
    server['hold'].clear();_,req=server['pending'].pop();req.fulfill(json=ledger(1))
    expect(p.locator('.toast').last).to_contain_text('台账已保存')
    paid.press('Tab')
    expect(p.locator('.toast').last).to_contain_text('这一格已变化')
    assert len(server['writes'])==1
    p.locator('#ttl').click();expect(paid).to_have_value('2.00')


def test_saved_history_never_appears_under_another_project(ui_page):
    p=ui_page;server,ledger=project_server(p)
    p.get_by_role('button',name='＋ 新增历史行',exact=True).click()
    amount=p.locator('[data-sc="辅材"][data-field="settle_amount"]')
    expect(amount).to_have_count(1)
    amount.fill('1234.56');amount.press('Tab')
    expect(p.locator('.toast').last).to_contain_text('台账已保存')
    server['hold'].add(2)
    pick_project(p,'乙仓')
    # 新项目读取尚未返回时，也不能把旧项目历史行当成新项目可编辑行。
    expect(p.get_by_role('region',name='辅材欠款台账').locator('[data-act="ledHistoryCell"]')).to_have_count(0)
    p.wait_for_function("document.querySelector('[data-act=ledPjToggle]').textContent.includes('乙项目')")
    p.wait_for_function('window.pendingLedgerReads===1')
    assert len(server['pending'])==1
    p.locator('.debt-ledgers').screenshot(path=str(output('ledger-project-loading.png',kind='screenshots')))
    server['hold'].clear();pid,req=server['pending'].pop();req.fulfill(json=ledger(pid))
    p.wait_for_function('M05.ledger?.project_id===2')
    expect(p.get_by_role('region',name='辅材欠款台账')).not_to_contain_text('1,234.56')
    pick_project(p,'丙仓');p.wait_for_function('M05.ledger?.project_id===3')
    expect(p.locator('[data-act="ledHistoryCell"]')).to_have_count(0)
    pick_project(p,'乌兰仓');p.wait_for_function('M05.ledger?.project_id===1')
    expect(p.locator('[data-sc="辅材"][data-field="settle_amount"]')).to_have_value('1234.56')
    p.locator('.debt-ledgers').screenshot(path=str(output('ledger-project-restored.png',kind='screenshots')))
    assert [w['project_id'] for w in server['writes']]==[1,1]


def test_switch_during_inflight_ledger_read_finishes_at_latest_project(ui_page):
    p=ui_page;server,ledger=project_server(p)
    server['rows'][2]=[{'seq':1,'month':'2025-11','row_kind':'manual','record_id':602,
        'editable':True,'token':'other','other_expense':'987.65','payment':'0','remark':'仅乙项目'}]
    server['hold'].add(2)
    pick_project(p,'乙仓')
    p.wait_for_function('m05Refetching && window.pendingLedgerReads===1')
    pick_project(p,'丙仓')
    server['hold'].clear();pid,req=server['pending'].pop();req.fulfill(json=ledger(pid))
    p.wait_for_function('!m05Refetching')
    assert p.evaluate('M05.ledger.project_id')==3
    expect(p.get_by_role('region',name='辅材欠款台账')).not_to_contain_text('仅乙项目')
    assert server['reads'][-1]==3
    assert server['writes']==[]


def test_older_same_project_response_cannot_overwrite_newer_history(ui_page):
    p=ui_page;server,ledger=project_server(p)
    row={'seq':1,'month':'2025-11','row_kind':'manual','record_id':501,
        'editable':True,'token':'latest','other_expense':'4321.00','payment':'0','remark':'最新历史行'}
    server['hold'].add(1)
    p.evaluate('window.oldLedger=reloadM05();void 0')
    p.wait_for_function('window.pendingLedgerReads===1')
    p.evaluate('window.newLedger=reloadM05();void 0')
    p.wait_for_function('window.pendingLedgerReads===2')
    server['rows'][1]=[row]
    server['pending'][1][1].fulfill(json=ledger(1))
    p.evaluate('newLedger')
    # 较早的读在最后到达，仍不能把已显示的新历史行抹掉。
    server['rows'][1]=[]
    server['pending'][0][1].fulfill(json=ledger(1))
    p.evaluate('oldLedger')
    expect(p.locator('[data-sc="辅材"][data-field="settle_amount"]')).to_have_value('4321.00')
    assert server['writes']==[]
