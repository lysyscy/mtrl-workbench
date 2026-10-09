"""TAIL-266：真实浏览器守年度列、读取失败、年筛选与独立结余，大表沿用全月累计。"""
from tests.test_tail264_ui import page
from tests.acc_plugin import acc
from app.mod15_user.domain import UI_SCALES
from pathlib import Path


@acc()
def test_annual_columns_balance_and_unread_state(page):
    page.evaluate('applyUiScale', max(UI_SCALES, key=lambda scale: float(scale[2]))[2])
    page.evaluate('''() => {
      closeModal();fExt.year='2026';fExt.status='全部';
      EXT_STATE.loaded=true;EXT_STATE.error='';
      EXTM={'2025-12':{'焊材':[['甲仓',100]]},'2026-01':{'焊材':[['甲仓',25]]},'2027-01':{'焊材':[['甲仓',900]]}};
      BAL_EX['焊材']={'甲仓':456};
      EXT_TOTALS={'2026':{'焊材':{'甲仓':'481'}}};
      EXT_ANNUAL={'焊材':{rows:[{warehouse:'甲仓',prior:'100',balance:'456',cells:['25',...Array(11).fill('0')],total:'481'}],sum_row:['100','25',...Array(11).fill('0'),'481']},'气体':{rows:[],sum_row:[]}};
      ACT.expExt();
    }''')
    head = page.locator('[data-sort-key="modal:expExt"] thead th')
    assert head.count() == 17
    assert head.nth(3).inner_text() == '2026-01'
    assert head.nth(14).inner_text() == '2026-12'
    cells = page.locator('[data-sort-key="modal:expExt"] tbody tr').first.locator('td')
    assert cells.nth(2).inner_text() == '100.00'
    assert cells.nth(3).inner_text() == '25.00'
    assert cells.nth(4).inner_text() == '0.00'
    assert cells.nth(15).inner_text() == '481.00'
    assert cells.last.locator('input').input_value() == '456'
    assert page.evaluate("bigHWCum('甲仓','2026')") == 481
    page.locator('[data-sort-key="modal:expExt"]').evaluate('(table)=>{table.parentElement.scrollLeft=400;}')
    first_box, second_box = cells.first.bounding_box(), cells.nth(1).bounding_box()
    assert abs(first_box['x'] + first_box['width'] - second_box['x']) <= 2
    head_boxes = [head.nth(i).bounding_box() for i in range(2)]
    assert abs(head_boxes[0]['x'] - first_box['x']) <= 2
    assert abs(head_boxes[1]['x'] - second_box['x']) <= 2
    page.screenshot(path=str(Path(__file__).resolve().parents[2] / '.codebuddy/work/00-scratch/tmp-20261009-annual.png'))
    page.evaluate('''async () => {
      API.m07Extract=async()=>{throw new Error('库存读取失败');};
      try{await reloadExtract();}catch(e){}
    }''')
    assert page.evaluate("extBlock('焊材')").find('库存读取失败') >= 0
    assert '0.00' not in page.evaluate("extBlock('焊材')")
    assert page.evaluate("bigHWCum('甲仓')") is None
    assert not page._tail_errors


@acc()
def test_only_latest_request_can_publish_after_year_roundtrip(page):
    result = page.evaluate('''async () => {
      const waits=[]; API.m07Extract=()=>new Promise((resolve,reject)=>waits.push({resolve,reject}));
      fExt.year='2026';const a=reloadExtract();fExt.year='2025';const b=reloadExtract();
      fExt.year='2026';const c=reloadExtract();
      const response=total=>({amounts:{},balances:{},annual:{'焊材':{rows:[{warehouse:'甲仓',prior:'0',cells:Array(12).fill('0'),total}],sum_row:[]}}});
      waits[2].resolve(response('300'));await c;
      waits[0].resolve(response('100'));await a;
      waits[1].reject(new Error('旧请求失败'));await b;
      return {total:EXT_ANNUAL['焊材'].rows[0].total,loaded:EXT_STATE.loaded,error:EXT_STATE.error};
    }''')
    assert result == {'total':'300','loaded':True,'error':''}


@acc()
def test_year_status_switch_reloads_and_empty_balance_stays_blank(page):
    page.evaluate('''async () => {
      closeModal();fExt.year='2026';fExt.status='全部';
      API.m07Extract=async(year,status)=>{saved.push({year,status});return {amounts:{},balances:{},annual:{'焊材':{rows:[],sum_row:[]},'气体':{rows:[],sum_row:[]}}};};
      await ACT.fExtYear({value:'2025'});
      await ACT.fExtStatus({value:'归档'});
    }''')
    assert page.evaluate('saved') == [{'year': '2025', 'status': '全部'}, {'year': '2025', 'status': '归档'}]
    assert page.evaluate('EXT_STATE.loaded')
    assert '没有焊材数据' in page.evaluate("extBlock('焊材')")
    assert page.evaluate("extBalOf('焊材','甲仓')") is None
    assert not page._tail_errors
