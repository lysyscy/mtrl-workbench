"""Financial workspaces remain readable without changing their data or actions."""
import pytest

from tests.ui_helpers import ui_page  # noqa: F401


@pytest.mark.parametrize('scale', [1, 1.25])
def test_notice_identity_amounts_and_batch_groups_remain_readable(ui_page, scale):
    p = ui_page
    p.set_viewport_size({'width': 1280, 'height': 720})
    p.evaluate('''scale=>{
      document.documentElement.style.setProperty('--fscale',scale);
      Object.assign(NO[0],{code:'FKTZS2026102000012345',doc:'四川材料采购合同审批通知书及长项目全名核对',
        recv:'四川省材料设备集中采购供应有限公司',sup:'四川省安装工程材料供应有限公司'});
      pickSet.add('101');render();
    }''', scale)
    assert p.locator('[data-act="pick"][data-id="101"]').is_checked()
    assert p.locator('[data-act="batchPay"]').is_enabled()
    assert p.locator('[data-act="ntPrint"]').is_enabled()
    assert p.locator('[data-act="ntPdf"]').count() == 1
    assert p.locator('[data-act="batchCatApply"]').count() > 0
    table = p.locator('table[data-sort-key="m03:notices"]')
    assert table.locator('tbody tr[data-notice-id="101"] td').nth(2).inner_text() == 'FKTZS2026102000012345'
    assert table.locator('tbody tr[data-notice-id="101"] td').nth(5).bounding_box()['width'] >= 140 * scale
    assert table.locator('tbody td.num').evaluate_all('cells=>cells.every(c=>c.scrollWidth<=c.clientWidth+1)')
    assert p.locator('[data-act="editss"][data-k="pay"]').input_value() == '12345.67'
    assert p.locator('.notice-workspace>h4').evaluate('e=>e.scrollWidth<=e.clientWidth')
    p.locator('[data-act="pick"][data-id="101"]').uncheck()
    assert p.locator('[data-act="batchPay"]').is_disabled()
    p.set_viewport_size({'width':2552,'height':1080})
    p.wait_for_timeout(150)
    assert table.evaluate('e=>e.getBoundingClientRect().width<=e.closest(".tw").clientWidth+1')


@pytest.mark.parametrize('width', [1280, 1920])
def test_debt_overviews_expand_align_and_ledgers_adapt(ui_page, width):
    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1080})
    p.evaluate('''()=>{
      NO=Array.from({length:30},(_,i)=>({...NO[0],id:String(100+i),proj:'项目全名'+i,cat:'辅材'}));
      PJs=NO.map((n,i)=>({id:String(i+1),name:'仓库'+i,full:n.proj,disp:'供应商及安装工程长项目名称'+i,type:'normal',status:'在建'}));
      LGs.splice(0,LGs.length,...PJs.map((p,i)=>({proj:p.name,cat:'辅材',settle:i===0?0:i===1?-100:1234567.89,paid:0})));
      MACH6={'仓库0':{'2026-10':[0,0,88,0,0,0]}};
      M05.ledger={sides:['辅材','机械'].map(label=>({label,rows:[
        {seq:1,month:'2026-08',other_expense:'0',payment:'0',remark:''},
        {seq:2,month:'2026-09',other_expense:'0',payment:'0',remark:'已核实无需支出'},
        {seq:3,month:'2026-10',other_expense:'1234567.89',payment:'234567.89',remark:'本项目当月结算与付款核对'}]}))};
      VIEW='m05';render();
    }''')
    overview = p.locator('.debt-overview').nth(1).locator('.bd')
    assert overview.evaluate('e=>e.scrollHeight<=e.clientHeight+1')
    assert overview.locator('.br').count() == 29
    assert '-100.00' in overview.inner_text()
    mechanical=p.locator('.debt-overview').nth(2)
    assert mechanical.locator('.br').count()==1 and '88.00' in mechanical.inner_text()
    bottoms=p.locator('.debt-overview').evaluate_all('cards=>cards.map(e=>e.getBoundingClientRect().bottom)')
    assert max(bottoms)-min(bottoms)<1
    first, second = p.locator('.debt-ledger').all()
    a, b = first.bounding_box(), second.bounding_box()
    if width == 1920:
        assert b['x'] >= a['x'] + a['width'] and abs(a['y'] - b['y']) < 1
    else:
        assert b['y'] >= a['y'] + a['height']
    assert '2026-08' not in first.inner_text() and '2026-09' in first.inner_text()
    assert first.locator('table').bounding_box()['width'] >= 520
    assert overview.locator('.br .tk').evaluate_all(
        'bars=>new Set(bars.map(b=>Math.round(b.getBoundingClientRect().x))).size===1')
    assert p.locator('[data-act="ledPjToggle"]').count() == 1
    assert p.locator('[data-act="ledExpToggle"]').count() == 1
    assert p.locator('table[data-sort-key="m05:flows"]').count() == 1


def test_procurement_supplier_and_sum_are_readable_and_exports_stay_distinct(ui_page):
    from app.mod11_jc import domain

    p = ui_page
    p.set_viewport_size({'width': 1280, 'height': 720})
    p.evaluate('''arg=>{
      JC_COLUMNS.splice(0,JC_COLUMNS.length,...arg.cols);
      JC_SUM_KEYS.splice(0,JC_SUM_KEYS.length,...arg.sumKeys);
      JCs.splice(0,JCs.length,adaptJc({id:1,project_key:'测试仓库',project_seq:1,date:'2026-10-20',
        material:'钢材',contract_no:'CGHT2026102000012345',supplier:'四川省安装工程材料设备供应有限公司',
        tag:'纳入台账',contract_amt:1234567.89,inv_sum:234567.89,settle:234567.89,pay_sum:34567.89,debt:200000}));
      VIEW='m11';fJc.projs=[];fJc.sup='';fJc.tag='全部';fJc.arch='全部';render();
    }''', {'cols': list(domain.JC_COLUMNS), 'sumKeys': list(domain.SUM_KEYS)})
    assert p.locator('[data-act="jcExport"]').count() == 1
    assert p.locator('[data-act="jcPrintOpen"]').count() == 1
    assert p.locator('.jc-supplier').first.bounding_box()['width'] >= 140
    assert p.locator('.procurement-table .sumrow>td').first.evaluate(
        'e=>getComputedStyle(e).whiteSpace') == 'nowrap'
    table = p.locator('table[data-sort-key="m11:jc"]')
    assert table.locator('.sumrow>td').count() == table.locator('thead th').count()
    assert '1,234,567.89' in table.locator('.sumrow').inner_text()
    table.evaluate("e=>e.closest('.tw').scrollLeft=600")
    total = table.locator('.sumrow>td').first
    assert total.inner_text() == '合计'
    assert total.evaluate('e=>e.getBoundingClientRect().left>=e.closest(".tw").getBoundingClientRect().left-1')
    assert table.locator('thead th.fl').evaluate_all('''ths=>ths.every(th=>{
      const r=th.getBoundingClientRect();
      return th.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
    })'''), 'Pinned identity headings must remain above scrolled columns'
    assert p.locator('[data-act="jcInvDlg"]').count() == 1
    assert p.locator('[data-act="jcPayDlg"]').count() == 1
    assert p.locator('.procurement-workspace>h4').evaluate('e=>e.scrollWidth<=e.clientWidth')
