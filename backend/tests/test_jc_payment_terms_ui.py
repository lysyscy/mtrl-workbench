"""旧台账字段的浏览器回归；所有 API 写入均为脱敏夹具。"""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS, PAY_METHODS
from tests.ui_helpers import ui_page  # noqa: F401


@pytest.mark.parametrize("width,scale", [(1920, 1), (1280, 1.4)])
def test_contract_terms_edit_and_create(ui_page, width, scale):
    p = ui_page
    p.set_viewport_size({"width": width, "height": 1080})
    p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
    p.evaluate("""data=>{
      window.termsRow={id:21,date:'2026-01-01',material:'钢材',supplier:'测试供应商',contract_no:'TEST-21',
        project_key:'测试仓库',tag:'纳入台账',contract_amt:'123.45',payment_term:'90±10天',payment_method:'承兑',remark:'5%质保金一年'};
      window.termsWrites=[];
      API.m11List=async()=>({...data,rows:[termsRow]});
      API.m11Fields=async body=>{termsWrites.push(body);Object.assign(termsRow,body.fields);return {ok:true};};
      API.m11Add=async body=>{window.termsAdded=body;return {ok:true,id:22};};
      VIEW='m11';fJc.tag='全部';fJc.projs=[];return reloadM11();
    }""", {'columns': list(JC_COLUMNS), 'sum_keys': list(SUM_KEYS), 'payment_methods': list(PAY_METHODS)})
    term = p.get_by_role('textbox', name='账期', exact=True)
    expect(term).to_have_value('90±10天')
    term.fill('60天')
    term.blur()
    expect(p.locator('.toast').last).to_contain_text('合同付款约定已保存')
    p.get_by_role('combobox', name='合同付款方式', exact=True).select_option('供应链')
    p.wait_for_function("termsWrites.length===2")
    assert p.evaluate('termsWrites') == [
        {'id': '21', 'fields': {'payment_term': '60天'}},
        {'id': '21', 'fields': {'payment_method': '供应链'}}]
    assert p.get_by_role('combobox', name='合同付款方式', exact=True).evaluate('e=>e.getBoundingClientRect().width') >= 100*scale
    p.evaluate('ACT.jcAdd()')
    p.locator('#jcNTerm').fill('30天')
    p.locator('#jcNMethod').select_option('其他')
    p.locator('[data-act="jcRowSave"]').click()
    p.wait_for_function('window.termsAdded')
    assert p.evaluate('termsAdded.payment_term') == '30天'
    assert p.evaluate('termsAdded.payment_method') == '其他'
    out = Path(__file__).resolve().parents[2] / '.artifacts/active/jc-payment-terms/20261023-implementation/screenshots'
    out.mkdir(parents=True, exist_ok=True)
    p.screenshot(path=str(out / f'contract-terms-{width}.png'), full_page=True)
