"""子表写后保留真实重载，只替换请求回包，验证新行对象、明细和草稿。"""
import pytest
from playwright.sync_api import expect

from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS
from app.mod03_notice.page import render_theme
from tests.ui_helpers import ui_page  # noqa: F401
from tools.audit.workspace_paths import output


@pytest.fixture
def subtable(ui_page):
    p = ui_page
    p.add_style_tag(content=render_theme('默认'))
    p.evaluate("""async columns => {
      window.subWrites=[]; window.subReads=0; window.listReads=0; window.subResult='ok';
      window.subRows=[];
      window.subContract={id:11,project_key:'测试仓库',project_seq:1,date:'2026-10-01',
        material:'钢材',supplier:'测试供应商',trade_co:'贸易公司',tag:'纳入台账',
        contract_amt:'100.00',trade_contract_amt:'100.00',inv_sum:'0.00',
        trade_inv_sum:'0.00',pay_sum:'0.00',settle:'0.00',debt:'0.00',notice_ids:[]};
      API.m11List=async()=>{listReads++;return {...columns,rows:[{...subContract}]};};
      API.m11Detail=async()=>{subReads++;return {data:{supplier_invoices:subRows,
        trade_invoices:subRows,payments:subRows,payment_display_rows:subRows}};};
      API.m11InvAdd=API.m11PayAdd=async body=>{
        subWrites.push(body);
        if(subResult==='reject')return {ok:false,message:'隔离保存被拒绝'};
        if(subResult==='throw')throw new Error('隔离请求失败');
        Object.assign(subContract,window.updatedAmounts);
        subRows=[{id:21,date:body.date,amount:body.amount,source:'manual'}];
        return {ok:true};
      };
      VIEW='m11'; fJc.tag='全部'; fJc.arch='全部'; fJc.sup=''; fJc.projs=[];
      await reloadM11();
      window.priorContract=JCs[0];
    }""", {'columns': list(JC_COLUMNS), 'sum_keys': list(SUM_KEYS)})
    return p


@pytest.mark.parametrize('kind,open_act,amounts', [
    ('inv', 'jcInvDlg', {'inv_sum': '12.34'}),
    ('tinv', 'jcTInvDlg', {'trade_inv_sum': '12.34', 'settle': '12.34', 'debt': '12.34'}),
    ('pay', 'jcPayDlg', {'pay_sum': '12.34', 'debt': '-12.34'}),
])
def test_保存后新合同行与弹窗明细一致且只重拉一次(subtable, kind, open_act, amounts):
    p = subtable
    p.evaluate('amounts=>{window.updatedAmounts=amounts;}', amounts)
    p.evaluate('async act=>{await ACT[act]({dataset:{id:"11"}});}', open_act)
    p.locator(f'[data-act="jcSubAdd"][data-kind="{kind}"]').click()
    p.locator('[data-act="jcSubSet"][data-k="date"]').fill('2026-10-02')
    p.locator('[data-act="jcSubSet"][data-k="amt"]').fill('12.34')
    if kind == 'pay':
        p.screenshot(path=str(output('jc-payment-draft.png', kind='screenshots')))
    before = p.evaluate('({list:listReads,detail:subReads})')
    p.locator('[data-act="jcSubSave"]').click()
    expect(p.locator('#modalRoot .draftrow')).to_have_count(0)
    expect(p.locator('#modalRoot tbody')).to_contain_text('12.34')
    expect(p.locator('#modalTitle')).to_be_focused()
    expect(p.locator('.toast').last).to_contain_text({
        'inv': '发票合计 12.34', 'tinv': '结算金额 12.34', 'pay': '欠款 -12.34',
    }[kind])
    assert p.evaluate('JCs[0]!==priorContract')
    assert p.evaluate('listReads') == before['list'] + 1
    assert p.evaluate('subReads') == before['detail'] + 1
    assert p.evaluate('subWrites[0].date') == '2026-10-02'
    table = p.locator('table[data-sort-key="m11:jc"] tbody tr').first
    for key, value in amounts.items():
        index = next(i for i, col in enumerate(JC_COLUMNS, 1) if col['key'] == key)
        expect(table.locator('td').nth(index)).to_contain_text(value)
    if kind == 'pay':
        p.screenshot(path=str(output('jc-payment-after-save.png', kind='screenshots')))


@pytest.mark.parametrize('result,message', [('reject', '隔离保存被拒绝'), ('throw', '隔离请求失败')])
def test_保存拒绝或异常仍重载真实列表并保留草稿(subtable, result, message):
    p = subtable
    p.evaluate('value=>{subResult=value;}', result)
    p.evaluate('async()=>{await ACT.jcInvDlg({dataset:{id:"11"}});}')
    p.locator('[data-act="jcSubAdd"][data-kind="inv"]').click()
    p.locator('[data-act="jcSubSet"][data-k="amt"]').fill('12.34')
    before = p.evaluate('listReads')
    p.locator('[data-act="jcSubSave"]').click()
    expect(p.locator('.toast').last).to_contain_text(message)
    expect(p.locator('[data-act="jcSubSet"][data-k="amt"]')).to_have_value('12.34')
    assert p.evaluate('listReads') == before + 1
    assert p.evaluate('JCs[0]!==priorContract')
    assert p.evaluate('subRows') == []


def test_删除已有行保留未保存的草稿(subtable):
    p = subtable
    p.evaluate("""async()=>{
      subRows=[{id:21,date:'2026-10-01',amount:'10.00',source:'manual'}];
      API.m11InvDel=async()=>{subRows=[];return {ok:true};};
      await ACT.jcInvDlg({dataset:{id:'11'}});
    }""")
    p.locator('[data-act="jcSubAdd"][data-kind="inv"]').click()
    p.locator('[data-act="jcSubSet"][data-k="amt"]').fill('9.99')
    p.locator('[data-act="jcInvDel"]').click()
    expect(p.locator('[data-act="jcInvDel"]')).to_have_count(0)
    expect(p.locator('[data-act="jcSubSet"][data-k="amt"]')).to_have_value('9.99')
    assert p.evaluate('JCs[0]!==priorContract')
    assert p.evaluate('subWrites') == []
