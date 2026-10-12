"""316:大表按需读取，机械屏障、失败恢复与写后真实读取。浏览器出口全隔离。"""
import pytest

from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401


def setup(p):
    p.evaluate("""() => {
      window.calls=[];BOOTING=false;VIEW='m07';LOADED.clear();IVs=[];ADs=[];
      window.month=bjMonth(-1);window.previous=bjMonth(-2);
      window.big={selected:['乙仓','测试仓库'],mat_available:true,manual:{
        [previous]:{'测试仓库':{mech_est:'100.00',oil:'9.99',note:'带入'}},
        [month]:{'测试仓库':{oil:'0'}}}};
      window.extract={amounts:{焊材:{测试仓库:{[month]:'12.34'}}},balances:{焊材:{测试仓库:'0'}},
        annual_totals:{[month.slice(0,4)]:{焊材:{测试仓库:'22.35'},气体:{测试仓库:'0'}}},
        annual:{焊材:{rows:[{warehouse:'测试仓库',prior:'0',cells:[null,'0','12.34'],total:'22.35',balance:'0'}],sum_row:[null,'0','12.34']},气体:{rows:[]}}};
      API.m06Mech=async()=>{calls.push('mech');return {mech:{测试仓库:{[month]:[999,5,10,20,999,999]}}};};
      API.m07Settlement=async ym=>{calls.push(['settlement',ym]);return {ym,rows:[{name:'测试仓库',rows:2,begin:'1.01',in:'12.34',out:'3.00',end:'10.35'}]};};
      API.m07Big=async()=>{calls.push('big');return big;};
      API.m07Extract=async(year,status)=>{calls.push(['extract',year,status]);return extract;};
      API.m08Inventory=async()=>{calls.push('inventory');return {rows:[],adjustments:[]};};
      JCs.splice(0,JCs.length,{tag:'纳入台账',proj:'测试仓库',settle:50.01});
    }""")


@acc()
def test_first_visit_waits_for_mechanical_columns_without_inventory_and_keeps_values(ui_page):
    p = ui_page
    setup(p)
    p.evaluate("""() => {
      const mech=API.m06Mech;
      API.m06Mech=()=>new Promise(resolve=>window.finishMech=async()=>resolve(await mech()));
      window.loading=loadPaths(PAGE_LOAD.m07);render();
    }""")
    assert p.evaluate('calls') == []
    assert '正在读取' in p.inner_text('#view')
    p.evaluate('async () => {await finishMech();await loading;}')
    assert p.evaluate('calls[0]') == 'mech'
    assert 'inventory' not in p.evaluate('calls')
    assert p.evaluate('IVs.length') == 0
    assert p.evaluate('BIGSET') == ['乙仓', '测试仓库']
    assert p.evaluate("bigRows(month)[1].rent") == 30
    assert p.evaluate("bigRows(month)[1].lease") == 5
    assert p.evaluate("bigRows(month)[1].totC") == 35
    assert p.evaluate("bigRows(month)[1].hw") == 12.34
    assert p.evaluate("bigRows(month)[1].hwc") == 22.35
    assert p.evaluate("bigRows(month)[1].matC") == 50.01
    assert p.evaluate("bigCell('测试仓库',month,4)") == {'v': 0, 'from': None}
    assert p.evaluate("bigCell('测试仓库',month,1)") == {'v': 100, 'from': p.evaluate('previous')}
    assert p.evaluate("bigCell('乙仓',month,1)") == {'v': None, 'from': None}
    assert p.evaluate("EXT_ANNUAL['焊材'].rows[0].cells") == [None, '0', '12.34']
    before = p.evaluate('calls.length')
    p.evaluate('async () => {await loadPaths(PAGE_LOAD.m07);}')
    assert p.evaluate('calls.length') == before


@acc()
@pytest.mark.parametrize('endpoint,label', [('m06Mech', '机械 6 列'), ('m07Big', '收发结存与大表'), ('m07Extract', '收发结存与大表')])
def test_failure_is_named_pending_cleared_and_retry_reads_real_state(ui_page, endpoint, label):
    p = ui_page
    setup(p)
    p.evaluate("""async endpoint => {
      window.saved=API[endpoint];API[endpoint]=async()=>{throw Error('隔离读取失败');};
      await loadPaths(PAGE_LOAD.m07);
    }""", endpoint)
    assert p.evaluate('PENDING.size') == 0
    assert p.evaluate('pageState().kind') == 'error'
    assert label in p.inner_text('#view')
    assert '隔离读取失败' in p.inner_text('#view')
    p.evaluate("""async endpoint => {API[endpoint]=saved;await retryPage();}""", endpoint)
    assert p.evaluate('pageState().kind') == 'ready'
    assert p.evaluate('FAILED.size') == 0
    assert 'inventory' not in p.evaluate('calls')


@acc()
def test_filters_exports_write_refresh_and_cross_page_navigation(ui_page):
    p = ui_page
    setup(p)
    # The actual API write wrapper dirties every page. No request reaches a database.
    p.route('**/api/m07/big/cell', lambda route: route.fulfill(
        content_type='application/json', body='{"ok":true,"value":"77.77"}'))
    p.evaluate('async () => {await loadPaths(PAGE_LOAD.m07);calls.length=0;}')
    p.evaluate("""async () => {
      big.manual[month]['测试仓库'].mech_est='77.77';
      await ACT.bigEdit({dataset:{p:'测试仓库',i:'1'},value:'77.77'});
    }""")
    assert p.evaluate('LOADED.size') == 0
    assert p.evaluate("bigCell('测试仓库',month,1)") == {'v': 77.77, 'from': None}
    assert len(p.evaluate('calls')) == 3
    assert 'inventory' not in p.evaluate('calls')
    p.evaluate("""async () => {
      calls.length=0;fWhYm='2025-12';await reloadM07();
      await ACT.fExtYear({value:'2025'});await ACT.fExtStatus({value:'全部'});
      window.exports=[];dlExport=async url=>{exports.push(url);return '隔离文件';};
      await ACT.zipSfjc();await ACT.saveExt();await ACT.bigExport();
    }""")
    assert p.evaluate('calls[0]') == ['settlement', '2025-12']
    assert p.evaluate('calls.slice(-1)[0]') == ['extract', '2025', '全部']
    urls = p.evaluate('exports')
    assert urls[0] == '/api/m07/settlement/export?period=2025-12'
    assert urls[1] == '/api/m07/extract/export?status=%E5%85%A8%E9%83%A8&period=2025'
    assert urls[2] == '/api/m07/big/export?period=' + p.evaluate('month')
    p.evaluate("""() => {calls.length=0;go('m08');}""")
    p.wait_for_function("() => !PENDING.size && VIEW==='m08'")
    assert p.evaluate('calls') == ['inventory']
    p.evaluate("""() => {calls.length=0;go('m07');}""")
    p.wait_for_function("() => !PENDING.size && VIEW==='m07'")
    assert p.evaluate('calls[0]') == 'mech'
    assert 'inventory' not in p.evaluate('calls')
