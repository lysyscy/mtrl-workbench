"""292 四条引用导航：真实虚拟表、歧义、失联与临时筛选返回。"""

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir
from pathlib import Path

import pytest
from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
from tests.test_tail282_pay_draft import _setup


def setup(p):
    _setup(p)
    from app.mod03_notice.page import render_theme
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate("""async()=>{
      window.SRV=Array.from({length:550},(_,i)=>({...SRV[0],notice_id:1000+i,bill_no:'DOC-SAME'}));
      await reloadNotices();
      Object.values(PAGE_LOAD).flat().forEach(l=>LOADED.add(l));FAILED.clear();PENDING.clear();
      window.contractRows=[{id:11,date:'2026-10-01',material:'目标材料',supplier:'目标供应商',project_key:'仓A',tag:'不纳入',arch:'未存档',contract_amt:'0',project_seq:3,contract_no:'00HT',notice_ids:[1540]}];
      API.m11List=async()=>({rows:contractRows});await reloadM11();
      API.flows=async()=>({rows:[]});
      API.m11Detail=async()=>({ok:true,data:{supplier_invoices:[],trade_invoices:[],payments:[],payment_display_rows:[{id:1,source:'notice',notice_id:1540,date:'2026-10-01',amount:'200',display_kind:'flow'}]}});
      FLs=[{id:'31',nid:'1540',doc:'DOC-SAME',flowNo:'FL292',amt:200,date:'2026-10-01',voided:false,reason:'',method:'现汇'}];
      window.invRows=Array.from({length:550},(_,i)=>({id:2000+i,doc_no:'IV'+i,seq:i,direction:'出库',material:'材料'+i,warehouse:'仓A',doc_date:'2020-01-01',amount:i}));
      API.m08Inventory=async()=>({rows:invRows,adjustments:[]});
    }""")


@acc()
def test_contract_id_conflicting_filters_and_return(ui_page):
    p=ui_page;setup(p)
    p.evaluate("() => {VIEW='m03';fJc={tag:'纳入台账',arch:'已存档',sup:'无命中',projs:['别仓'],amt:'filled'};window.oldJC=JSON.stringify(fJc);render();}")
    p.evaluate("ACT.ntTrace({dataset:{id:'1540'}})")
    p.wait_for_selector('[data-act="jcContract"]')
    assert '项目内序号' in p.inner_text('.mask') and '00HT' in p.inner_text('.mask')
    p.click('[data-act="jcContract"]')
    p.wait_for_selector('tr.nt-focus[data-jc-id="11"]')
    assert p.evaluate('VIEW')=='m11'
    assert p.evaluate('jcVisible().map(j=>j.id)')==['11']
    p.evaluate('render()')
    assert p.locator('tr.nt-focus[data-jc-id="11"]').count()==1
    p.click('[data-act="refBack"]')
    assert p.evaluate('VIEW')=='m03' and p.evaluate('JSON.stringify(fJc)===oldJC')
    p.evaluate("ACT.jcContract({dataset:{id:'999'}})")
    p.wait_for_function("document.body.innerText.includes('找不到这份集采合同')")
    assert p.evaluate('VIEW')=='m03'


@acc()
@pytest.mark.parametrize('entry',['flow','jc'])
def test_notice_exact_id_in_550_virtual_rows(ui_page,entry):
    p=ui_page;setup(p)
    p.evaluate("() => {VIEW='m05';fNt={month:'2020-01',cat:'剔除',astat:'未批',stat:'已付清',projs:['别仓'],q:'无命中'};window.oldNT=JSON.stringify(fNt);render();}")
    if entry=='flow':
        p.click('[data-act="flNotice"]')
    else:
        p.evaluate("() => {window.navCalls=0;const original=ACT.jcPayNotice;ACT.jcPayNotice=async t=>{navCalls++;await original(t);};ACT.jcPayDlg({dataset:{id:'11'}});}")
        p.wait_for_selector('.jc-pay-ref [data-act="jcPayNotice"]')
        p.click('.jc-pay-ref [data-act="jcPayNotice"]')
    p.wait_for_selector('tr.nt-focus[data-notice-id="1540"]')
    assert p.evaluate('VS_TS.length>0 && ntHit(fNt).length===550')
    row=p.locator('tr.nt-focus')
    box=row.bounding_box();assert box and 0<=box['y']<1000
    assert row.get_attribute('data-notice-id')=='1540'
    if entry=='flow': p.screenshot(path=str(Path(__file__).resolve().parents[2] / _run_output('tmp-20261011-292-notice-focus.png', kind='screenshots')))
    if entry=='jc': assert p.evaluate('navCalls')==1
    p.click('[data-act="refBack"]')
    assert p.evaluate('VIEW')=='m05' and p.evaluate('JSON.stringify(fNt)===oldNT')
    p.evaluate("ACT.jcPayNotice({dataset:{nid:'9999'}})")
    p.wait_for_function("document.body.innerText.includes('当前无法找到')")
    assert p.evaluate('VIEW')=='m05'


@acc()
def test_plan_unique_ambiguous_and_orphan_flow(ui_page):
    p=ui_page;setup(p)
    p.evaluate("() => {VIEW='m05';FLs[0].nid='';render();}")
    assert p.locator('[data-act="flNotice"]').count()==0
    assert p.locator('span[title="找不到对应通知书"]').count()==1


@acc()
def test_inventory_original_id_virtual_and_return(ui_page):
    p=ui_page;setup(p)
    p.evaluate("() => {VIEW='m06';LOADED.delete('库存单据');fIvYm='2026-10';invWhs=['别仓'];fIvDir='入库';invOnlyAdj=true;fIvCol={2:{v:['无命中']}};window.oldIV=JSON.stringify([fIvYm,invWhs,fIvDir,invOnlyAdj,fIvCol]);}")
    p.evaluate("ACT.goInvAdj({dataset:{iv:'2540',wh:'仓A'}})")
    p.wait_for_selector('tr.nt-focus[data-inv-id="2540"]')
    assert p.evaluate("VIEW==='m08' && VS_TS.length>0 && !invOnlyAdj && fIvYm==='全部'")
    box=p.locator('tr.nt-focus').bounding_box();assert box and 0<=box['y']<1000
    p.screenshot(path=str(Path(__file__).resolve().parents[2] / _run_output('tmp-20261011-292-inventory-focus.png', kind='screenshots')))
    p.click('[data-act="refBack"]')
    assert p.evaluate("VIEW==='m06' && JSON.stringify([fIvYm,invWhs,fIvDir,invOnlyAdj,fIvCol])===oldIV")
    p.evaluate("ACT.goInvAdj({dataset:{iv:'9999',wh:'仓A'}})")
    p.wait_for_function("document.body.innerText.includes('找不到这条库存原始行')")
    assert p.evaluate('VIEW')=='m06'
