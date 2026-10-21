"""真实壳内直接编辑历史行；接口均拦截，不写正式数据。"""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from tests.ui_helpers import ui_page  # noqa: F401


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
    folder=Path(__file__).parents[2]/'.artifacts/active/historical-ledger-prototype/20261021/screenshots'
    folder.mkdir(parents=True,exist_ok=True);p.screenshot(path=str(folder/f'ledger-{width}-{scale}.png'),full_page=True)


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
    folder=Path(__file__).parents[2]/'.artifacts/active/historical-ledger-prototype/20261021/screenshots'
    folder.mkdir(parents=True,exist_ok=True);p.screenshot(path=str(folder/'archive-colors.png'))
