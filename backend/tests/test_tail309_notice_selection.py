"""TAIL-309：真实壳 + 隔离回包，保护搜索选择、可见全选及付款批次。"""
from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401
import os
from pathlib import Path
import pytest


def _setup(p):
    p.evaluate("""async () => {
      window.SRV = [101,102,103,104,105].map((id,i) => ({
        notice_id:id,doc_date:'2026-10-02',bill_no:'DOC-'+String.fromCharCode(65+i),
        project_name:i===2?'另一个项目全名':'测试项目全名',ownership_id:i===2?2:1,
        category_label:'辅材',amount_approved:'1000',pay_amount:'1000',amount_paid:'0',
        stat_settle:'0',stat_paid:'0',approve_status:'已批',is_excluded:i===3,
        is_revoked:i===4,bill_name:'通知书'+String.fromCharCode(65+i),
        edited_fields:[],jc_supplier:'',is_manual:false
      }));
      PJs.push({id:'2',name:'另一个仓库',full:'另一个项目全名',disp:'另一个项目',
        status:'在建',type:'normal'});
      API.notices=async()=>({items:JSON.parse(JSON.stringify(SRV))});
      FLs.splice(0);JCs.splice(0);pickSet.clear();
      Object.assign(fNt,{month:'全部',cat:'全部',astat:'全部',stat:'全部',projs:[],q:''});
      VIEW='m03';await reloadNotices();
    }""")


def _pick(p, nid):
    return p.locator(f'[data-act="pick"][data-id="{nid}"]')


def _ids(p):
    return p.evaluate('[...pickSet].sort()')


@acc()
def test_搜索改词清空保留勾选且隐藏数量可见(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    assert _ids(p) == ['101'], '搜索隐藏行不应取消勾选'
    assert '当前列表外 1 条' in p.inner_text('.selbar')
    assert '1 行' in p.inner_text('.selbar')
    assert '1,000.00' in p.inner_text('.selbar')
    assert p.evaluate('document.activeElement.id') == 'ntSearch'
    p.fill('#ntSearch', '不存在')
    assert _ids(p) == ['101']
    p.fill('#ntSearch', '')
    assert _pick(p, '101').is_checked()
    assert '当前列表外' not in p.inner_text('.selbar')


@acc()
def test_多次搜索加选取消及全选只改当前可见候选(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    _pick(p, '102').check()
    p.fill('#ntSearch', 'DOC-C')
    assert not p.locator('#pickAllBox').is_checked()
    assert not p.locator('#pickAllBox').evaluate('e=>e.indeterminate')
    p.locator('#pickAllBox').check()
    assert _ids(p) == ['101', '102', '103']
    p.locator('#pickAllBox').uncheck()
    assert _ids(p) == ['101', '102'], '取消全选不应删掉搜索外选择'
    p.fill('#ntSearch', 'DOC-A')
    _pick(p, '101').uncheck()
    assert _ids(p) == ['102']
    p.fill('#ntSearch', '')
    assert p.locator('#pickAllBox').evaluate('e=>e.indeterminate')
    p.locator('#pickAllBox').check()
    assert _ids(p) == ['101', '102', '103'], '剔除/撤单的隐藏行不应被全选'
    p.locator('#pickAllBox').uncheck()
    assert _ids(p) == []


@acc()
def test_重复渲染同页导航不清选择离页及整页刷新清空(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    p.evaluate('render();render();go("m03");')
    assert _ids(p) == ['101']
    p.evaluate('go("m04");go("m03");')
    assert _ids(p) == [], '选择不能跨页面串入别的批次'
    p.fill('#ntSearch', '')
    _pick(p, '102').check()
    p.reload()
    p.wait_for_function('window.testReady')
    assert _ids(p) == [], '没有整页刷新持久化的业务约定'


@acc()
def test_项目等业务筛选仍裁剪选择搜索不参与裁剪(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    _pick(p, '103').check()
    p.fill('#ntSearch', 'DOC-B')
    p.evaluate('ACT.pjPick({dataset:{pj:"测试仓库"}});')
    assert _ids(p) == ['101'], '项目范围仍按原约定，搜索不得附带取消'
    p.fill('#ntSearch', '')
    assert _pick(p, '101').is_checked()


@acc()
def test_重新拉取清理删除撤单保留搜索隐藏及恢复用剔除选择(ui_page):
    p = ui_page
    _setup(p)
    p.locator('#pickAllBox').check()
    p.fill('#ntSearch', '不存在')
    p.evaluate("""async () => {
      SRV=SRV.filter(n=>n.notice_id!==101);SRV.find(n=>n.notice_id===102).is_revoked=true;
      await reloadNotices();
    }""")
    assert _ids(p) == ['103']
    p.fill('#ntSearch', '')
    assert _pick(p, '103').is_checked()
    p.select_option('#fCat', '剔除')
    assert _ids(p) == []
    _pick(p, '104').check()
    p.fill('#ntSearch', '不存在')
    p.evaluate('async()=>{await reloadNotices();}')
    assert _ids(p) == ['104'], '恢复剔除需要可选的剔除行'
    p.fill('#ntSearch', '')
    assert _pick(p, '104').is_checked()
    assert _pick(p, '105').is_disabled()


@acc()
def test_付款窗口列全体已选含隐藏行提交对应金额(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    _pick(p, '102').check()
    p.evaluate("API.batchPay=async b=>{window.payRequest=b;return {ok:false,message:'隔离捕获'};};")
    p.click('[data-act="batchPay"]')
    assert p.locator('#modalRoot [data-act="batchPayDel"]').count() == 2
    assert 'DOC-A' in p.inner_text('#modalRoot') and 'DOC-B' in p.inner_text('#modalRoot')
    p.fill('#ba0', '111')
    p.fill('#ba1', '222')
    p.click('[data-act="batchPayOk"]')
    p.wait_for_function('window.payRequest')
    assert p.evaluate('payRequest.ids') == [101, 102]
    assert p.evaluate('payRequest.drafts["101"].amount') == '111'
    assert p.evaluate('payRequest.drafts["102"].amount') == '222'


@acc()
def test_付款弹窗后删除或撤单不能错用剩余行金额(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    _pick(p, '102').check()
    p.click('[data-act="batchPay"]')
    p.fill('#ba0', '111')
    p.fill('#ba1', '222')
    p.evaluate("""async () => {
      API.batchPay=async b=>{window.payRequest=b;return {ok:false,message:'隔离捕获'};};
      SRV=SRV.filter(n=>n.notice_id!==101);await reloadNotices();
    }""")
    p.click('[data-act="batchPayOk"]')
    assert p.evaluate('!window.payRequest'), '批次变化后应先重新核对，不能把111提交给第二行'
    assert p.locator('#modalRoot [data-act="batchPayDel"]').count() == 1
    assert p.input_value('#ba0') == '222'
    p.evaluate("async()=>{SRV.find(n=>n.notice_id===102).is_revoked=true;await reloadNotices();}")
    p.click('[data-act="batchPayOk"]')
    assert p.evaluate('!window.payRequest')


@acc()
def test_直接批量动作须看清隐藏选择且只读取有效选择(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    _pick(p, '102').check()
    p.evaluate("""() => {
      window.requests=[];
      for(const k of ['setCategory','exclude','restore'])
        API[k]=async ids=>{requests.push({k,ids});return {ok:false,message:'隔离捕获'};};
      m03RunBatch=async(rows,mode)=>{requests.push({k:mode,ids:rows.map(n=>n.id)});};
    }""")
    for action in ['batchCatApply', 'batchEx', 'batchUnEx', 'ntPrint', 'ntPdf']:
        assert p.locator(f'[data-act="{action}"]').first.is_disabled(), action
    p.evaluate("""async () => {
      await ACT.batchCatApply({dataset:{c:'机械'}});await ACT.batchEx();
      await ACT.batchUnEx();await ACT.ntPrint();await ACT.ntPdf();
    }""")
    assert p.evaluate('requests') == [], '隐藏选择未核对前不应直接改数据或发打印'
    p.click('[data-act="pickSearchClear"]')
    assert _pick(p, '101').is_checked() and _pick(p, '102').is_checked()
    p.evaluate("""async () => {
      await ACT.batchCatApply({dataset:{c:'机械'}});await ACT.batchEx();
      await ACT.batchUnEx();await ACT.ntPrint();await ACT.ntPdf();
    }""")
    assert [r['ids'] for r in p.evaluate('requests')] == [['101', '102']] * 5
    p.click('[data-act="pickClear"]')
    assert _ids(p) == []


@acc()
def test_按计划仍尊重项目范围不受搜索裁剪(ui_page):
    p = ui_page
    _setup(p)
    p.fill('#ntSearch', 'DOC-B')
    p.evaluate("""() => {
      fNt.projs=['测试仓库'];planYm='2026-10';
      PLs.push({ym:planYm,docNo:'DOC-A'},{ym:planYm,docNo:'DOC-C'});
      ACT.planPickRun();
    }""")
    assert _ids(p) == ['101']
    assert p.input_value('#ntSearch') == 'DOC-B'
    assert '当前列表外 1 条' in p.inner_text('.selbar')


@acc()
def test_重拉失败和重置搜索不丢选择事实改为剔除才清理(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    p.fill('#ntSearch', 'DOC-B')
    error = p.evaluate("""async () => {
      const old=API.notices;API.notices=async()=>{throw Error('隔离读取失败');};
      try {await reloadNotices();} catch(e) {return e.message;}
      finally {API.notices=old;}
    }""")
    assert error == '隔离读取失败'
    assert _ids(p) == ['101']
    p.click('[data-act="filterReset"]')
    assert p.input_value('#ntSearch') == ''
    assert _pick(p, '101').is_checked()
    p.evaluate("async()=>{SRV.find(n=>n.notice_id===101).is_excluded=true;await reloadNotices();}")
    assert _ids(p) == [], '剔除事实变化后不能留在普通业务范围的批次里'


@acc()
def test_批量出口清理未重绘的删除项不把陈旧ID提交(ui_page):
    p = ui_page
    _setup(p)
    _pick(p, '101').check()
    _pick(p, '102').check()
    p.evaluate("""async () => {
      NO=NO.filter(n=>n.id!=='101'); // 尚未重画的真实列表变化
      window.requests=[];
      for(const k of ['setCategory','exclude','restore'])
        API[k]=async ids=>{requests.push({k,ids});return {ok:false,message:'隔离捕获'};};
      m03RunBatch=async(rows,mode)=>{requests.push({k:mode,ids:rows.map(n=>n.id)});};
      await ACT.batchCatApply({dataset:{c:'机械'}});await ACT.batchEx();
      await ACT.batchUnEx();await ACT.ntPrint();await ACT.ntPdf();
    }""")
    assert _ids(p) == ['102']
    assert [r['ids'] for r in p.evaluate('requests')] == [['102']] * 5


@acc()
@pytest.mark.parametrize('width,scale', [(1440, 'standard'), (1024, 'largest')])
def test_虚拟长表搜索保留选择且放大核对条可操作(ui_page, width, scale):
    """550行真实虚拟表与最大字号，核对隐藏范围、金额和窄屏操作位置。"""
    from app.mod03_notice.page import render_theme
    from app.mod15_user.domain import UI_SCALES

    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1000})
    p.add_style_tag(content=render_theme('默认'))
    factor = '1' if scale == 'standard' else str(max(float(css) for _, _, css in UI_SCALES))
    p.evaluate('(value)=>document.documentElement.style.setProperty("--fscale",value)', factor)
    _setup(p)
    p.evaluate("""async () => {
      SRV=Array.from({length:550},(_,i)=>({...SRV[0],notice_id:1000+i,bill_no:'LONG-'+i}));
      await reloadNotices();
    }""")
    assert p.evaluate('VS_TS.length>0 && ntHit(fNt).length===550')
    _pick(p, '1000').check()
    p.fill('#ntSearch', 'LONG-549')
    p.locator('#pickAllBox').check()
    assert _ids(p) == ['1000', '1549']
    assert '当前列表外 1 条' in p.inner_text('.selbar')
    assert '2,000.00' in p.inner_text('.selbar')
    metrics = p.locator('.selbar').evaluate("""e=>({width:e.clientWidth,scroll:e.scrollWidth,
      right:e.getBoundingClientRect().right})""")
    assert metrics['scroll'] <= metrics['width'] + 1
    assert metrics['right'] <= width + 1
    pay = p.locator('[data-act="batchPay"]')
    assert pay.is_visible() and pay.is_enabled()
    box = pay.bounding_box()
    assert box and 0 <= box['x'] and box['x'] + box['width'] <= width
    output = os.environ.get('TAIL309_EVIDENCE_PATH')
    if output:
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        p.screenshot(path=str(folder / f'hidden-{width}-{scale}.png'))
    pay.click()
    assert p.locator('#modalRoot [data-act="batchPayDel"]').count() == 2
    assert 'LONG-0' in p.inner_text('#modalRoot') and 'LONG-549' in p.inner_text('#modalRoot')
    if output:
        p.screenshot(path=str(folder / f'payment-{width}-{scale}.png'))
