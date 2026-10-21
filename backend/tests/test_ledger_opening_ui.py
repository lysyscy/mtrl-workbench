"""页面消费真实月行与分类默认截止月，无期初不出现付款编辑框。"""
from playwright.sync_api import expect
from app.mod03_notice.page import render_theme
from tests.ui_helpers import ui_page  # noqa: F401
import pytest


def test_无期初两侧历史月和自动付款只读_录入默认沿当前项目(ui_page):
    p = ui_page
    p.add_style_tag(content=render_theme("默认"))
    p.evaluate("""() => {
      VIEW='m05'; ledProj='测试仓库';
      M05.ledger={project_id:1,sides:['辅材','机械'].map((label,i)=>({label,
        category:i?'mechanical':'material',opening_id:null,
        opening_default:{cutoff_ym:i?'2024-05':'2024-06'},
        display_rows:[{seq:1,month:'',month_label:'未填单据日期付款',row_kind:'opening_auto',
          other_expense:'0.00',payment:'25.12',is_opening:false},
          {seq:2,month:'2024-07',row_kind:'month',other_expense:'100.00',payment:'10.00',is_opening:false}]
      }))}; render();
    }""")
    for label in ("辅材", "机械"):
        side = p.get_by_role('region', name=label+'欠款台账')
        expect(side.get_by_text('未填单据日期付款', exact=True)).to_be_visible()
        expect(side.get_by_text('2024-07', exact=True)).to_be_visible()
        expect(side.locator('[data-act="ledOpeningPay"]')).to_have_count(0)
        expect(side.locator('[data-act="delLg"]')).to_have_count(0)
    p.get_by_role('button', name='＋ 录入机械期初', exact=True).click()
    p.wait_for_function("lgOn && lgCut==='2024-05'", timeout=3000)
    p.locator('#lgCat').select_option('辅材')
    p.wait_for_function("lgCut==='2024-06'", timeout=3000)
    p.get_by_role('button', name='取消', exact=True).click()
    expect(p.locator('#lgCat')).to_have_count(0)


def test_期初默认月异步切项目不串响应_失败取消不改项目且等待中不可保存(ui_page):
    p = ui_page
    p.evaluate("""async() => {
      VIEW='m05';ledProj='测试仓库';
      M05.ledger={project_id:1,sides:[{label:'机械',opening_default:{cutoff_ym:'2024-05'},display_rows:[]}]};
      await ACT.addLg({dataset:{sc:'机械'}});
      PJs.push({id:'2',name:'乙仓',disp:'乙',full:'乙',type:'normal',status:'在建'},
               {id:'3',name:'丙仓',disp:'丙',full:'丙',type:'normal',status:'在建'});
      window.cutoffResolvers={};window.savedOpening=0;
      API.ledger=id=>new Promise(resolve=>{cutoffResolvers[id]=resolve;});
      API.send=async()=>{savedOpening++;return {ok:true};};
      window.firstCut=ACT.lgPjPick({dataset:{pj:'乙仓'}});
      window.secondCut=ACT.lgPjPick({dataset:{pj:'丙仓'}});
      ACT.addLgOk();
    }""")
    assert p.evaluate('lgCutPending && savedOpening===0 && lgPjName==="测试仓库"')
    result = p.evaluate("""async()=>{
      cutoffResolvers['3']({sides:[{label:'机械',opening_default:{cutoff_ym:'2022-03'}}]});
      await secondCut;
      cutoffResolvers['2']({sides:[{label:'机械',opening_default:{cutoff_ym:'2021-02'}}]});
      await firstCut;return [lgPjName,lgCut,lgCutPending];
    }""")
    assert result == ['丙仓', '2022-03', False]
    assert p.evaluate("""async()=>{
      API.ledger=async()=>{throw new Error('隔离失败');};
      await ACT.lgPjPick({dataset:{pj:'乙仓'}});return [lgPjName,lgCut];
    }""") == ['丙仓', '2022-03']
    assert p.evaluate("""async()=>{
      API.ledger=id=>new Promise(resolve=>{cutoffResolvers[id]=resolve;});
      const pending=ACT.lgPjPick({dataset:{pj:'乙仓'}});ACT.lgCancel();
      cutoffResolvers['2']({sides:[{label:'机械',opening_default:{cutoff_ym:'2021-02'}}]});
      await pending;return [lgOn,lgCutPending,lgPjName,lgCut,savedOpening];
    }""") == [False, False, '丙仓', '2022-03', 0]


@pytest.mark.parametrize('accepted', [True, False])
def test_opening_receipt_closes_only_saved_draft(ui_page, accepted):
    p = ui_page
    p.route('**/m05/opening', lambda r: r.fulfill(status=200 if accepted else 400,
        json={'ok': accepted, 'message': '已录入期初' if accepted else '金额不能为负数'}))
    p.evaluate('''async()=>{
      VIEW='m05';ledProj='测试仓库';
      M05.ledger={project_id:1,sides:[{label:'辅材',opening_default:{cutoff_ym:'2025-11'},display_rows:[]}]};
      reloadM05=async()=>{Object.keys(LOADERS).forEach(x=>LOADED.add(x));render();};
      await ACT.addLg({dataset:{sc:'辅材'}});
    }''')
    p.locator('#lgS').fill('1510869.33')
    p.locator('#lgP').fill('1510869.33')
    p.locator('[data-act="addLgOk"]').click()
    if accepted:
        expect(p.locator('#lgS')).to_have_count(0)
        expect(p.locator('.toast').last).to_contain_text('期初占位行已录入')
    else:
        expect(p.locator('#lgS')).to_have_value('1510869.33')
        expect(p.locator('.toast').last).to_contain_text('金额不能为负数')


def test_saved_opening_refresh_failure_is_not_reported_as_rejected(ui_page):
    p = ui_page
    p.route('**/m05/opening', lambda r: r.fulfill(json={'ok': True, 'message': '已保存'}))
    p.evaluate('''async()=>{
      VIEW='m05';ledProj='测试仓库';
      M05.ledger={project_id:1,sides:[{label:'辅材',opening_default:{cutoff_ym:'2025-11'},display_rows:[]}]};
      await ACT.addLg({dataset:{sc:'辅材'}});
      BOOTING=false; m05Sync=()=>{};
      reloadM05=async()=>{throw new Error('隔离读取失败');};
    }''')
    p.locator('[data-act="addLgOk"]').click()
    expect(p.locator('.toast').last).to_contain_text('已保存，但页面数据未能刷新')
    expect(p.locator('#lgS')).to_have_count(0)
