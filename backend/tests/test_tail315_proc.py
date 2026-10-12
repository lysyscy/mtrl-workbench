"""315: independent process-page reads, states and post-edit refresh in an isolated browser."""
from decimal import Decimal
from pathlib import Path

from app.mod06_proc import domain as D
from tests.acc_plugin import acc
from tests.test_shell_ui_workflow import ui_page  # noqa: F401


def report():
    raw = [{"ym": "2026-01", "in_主辅材": "10.01", **{f"mech_{i}": "0" for i in range(6)}}]
    adj = [{**raw[0], "in_主辅材": "0"}]
    diffs = [{"id": 101, "doc_no": "单据", "seq": "2", "material": "测试材料", "warehouse": "测试仓库",
              "before": "10.01", "after": "0", "delta": "-10.01", "remark": "原因", "operator": "测试",
              "at": "2026-01-02 03:04"}]
    def plain(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: plain(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [plain(v) for v in value]
        return value
    matrix = {"raw": raw, "adjusted": adj, "diffs": diffs, "diff_totals": D.diff_totals(diffs),
              "totals": {"raw": D.column_totals(raw), "adjusted": D.column_totals(adj)},
              "segments": {"raw": D.segment_totals(raw), "adjusted": D.segment_totals(adj)}}
    return plain({"ok": True, "projects": ["测试仓库", "无调整仓库"],
                  "matrices": {"测试仓库": matrix, "无调整仓库": {**matrix, "diffs": [], "diff_totals": D.diff_totals([])}}})


@acc()
def test_independent_reads_pending_failure_retry_difference_and_empty(ui_page):
    p = ui_page
    from app.mod03_notice.page import render_theme
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate("""data => {
      window.report=data;window.calls=[];BOOTING=false;LOADED.clear();IVs=[];ADs=[];
      API.m06Matrix=()=>{calls.push('matrix');return new Promise(resolve=>window.finishMatrix=()=>resolve(report));};
      API.m06Mech=async()=>{calls.push('mech');return {mech:{},columns:['标签保留']};};
      API.m08Inventory=async()=>{throw Error('inventory must not be preloaded');};
      window.loading=loadPaths(PAGE_LOAD.m06);VIEW='m06';render();
    }""", report())
    assert "正在读取" in p.inner_text('#view')
    p.evaluate('async () => {finishMatrix();await loading;}')
    assert p.evaluate('calls') == ['matrix', 'mech']
    assert p.evaluate("pageState().kind") == 'ready'
    assert p.evaluate('IVs.length===0 && MECH_LABELS[0]') == '标签保留'
    scratch = Path(__file__).resolve().parents[2] / '.codebuddy/work/00-scratch'
    p.screenshot(path=str(scratch / 'tmp-20261012-tail315-fixture-default.png'))
    p.click('[data-act="procTab"][data-i="2"]')
    assert '测试材料' in p.inner_text('#view') and '-10.01' in p.inner_text('#view')
    assert p.locator('[data-act="goInvAdj"]').get_attribute('data-iv') == '101'
    assert '2026-01-02 03:04' in p.inner_text('#view')
    p.screenshot(path=str(scratch / 'tmp-20261012-tail315-fixture-diff.png'))
    p.evaluate("() => {procPj='无调整仓库';render();}")
    assert '该项目无调整' in p.inner_text('#view')
    p.evaluate("""async () => {
      LOADED.clear();API.m06Matrix=async()=>({ok:false,message:'隔离读取失败'});
      await loadPaths(PAGE_LOAD.m06);
    }""")
    assert p.evaluate("pageState().kind") == 'error'
    assert '过程资料' in p.inner_text('#view') and '隔离读取失败' in p.inner_text('#view')
    p.evaluate('async () => {API.m06Matrix=async()=>report;await retryPage();}')
    assert p.evaluate("pageState().kind") == 'ready'
    assert p.evaluate('FAILED.size') == 0


@acc()
def test_mechanical_write_refreshes_only_own_sources_and_keeps_cross_page_stale(ui_page):
    p = ui_page
    p.evaluate("""async data => {
      window.calls=[];BOOTING=false;VIEW='m06';
      API.m06Matrix=async()=>{calls.push('matrix');return data;};
      API.m06Mech=async()=>{calls.push('mech');return {mech:{}};};
      API.m06MechSave=async payload=>{calls.push(payload);markCrossPageStale();return {ok:true};};
      API.m07Big=async()=>{throw Error('big must stay stale until navigation');};
      await reloadProc();render();calls.length=0;
    }""", report())
    p.evaluate("""async () => {
      const input=document.querySelector('[data-act="procMechSave"]');input.value='12.34';
      await ACT.procMechSave(input);
    }""")
    assert p.evaluate('calls') == [{"warehouse": "测试仓库", "ym": "2026-01", "values": {"mech_0": "12.34"}}, 'mech', 'matrix']
    assert p.evaluate('LOADED.size') == 0


@acc()
def test_inventory_adjustment_clear_dirties_process_and_navigation_reloads_its_two_routes(ui_page):
    p = ui_page
    p.route('**/api/m08/adjust/clear', lambda route: route.fulfill(
        content_type='application/json', body='{"ok":true}'))
    p.evaluate("""async data => {
      window.data=data;window.calls=[];BOOTING=false;VIEW='m06';
      API.m06Matrix=async()=>{calls.push('matrix');return data;};
      API.m06Mech=async()=>{calls.push('mech');return {mech:{}};};
      API.m08Inventory=async()=>{calls.push('inventory');return {rows:[],adjustments:[]};};
      await loadPaths(PAGE_LOAD.m06);
      VIEW='m08';await ivAct(()=>API.m08AdjustClear(101),'隔离撤销完成');
      data.matrices['测试仓库'].diffs=[];
      data.matrices['测试仓库'].adjusted=data.matrices['测试仓库'].raw;
      calls.length=0;procTab=2;go('m06');
    }""", report())
    p.wait_for_function("() => !PENDING.size && pageState().kind==='ready'")
    assert p.evaluate('calls') == ['matrix', 'mech']
    assert p.evaluate('PROC_MATRIX[procPj].diffs.length') == 0
    assert '该项目无调整' in p.inner_text('#view')
