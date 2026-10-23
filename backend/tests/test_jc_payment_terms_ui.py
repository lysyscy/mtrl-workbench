"""旧台账字段的浏览器回归；所有 API 写入均为脱敏夹具。"""
from pathlib import Path
import os
import pytest
from playwright.sync_api import expect
from app.mod11_jc.domain import JC_COLUMNS, SUM_KEYS, PAY_METHODS
from tests.ui_helpers import ui_page  # noqa: F401


def test_contract_payment_method_sort_uses_current_choice(ui_page):
    p = ui_page
    p.evaluate("""data=>{
      const methods=['现汇','供应链','其他','承兑',''];
      window.sortRows=methods.map((method,i)=>({id:21+i,date:'2026-01-01',material:'钢材',
        supplier:'测试供应商',contract_no:'TEST-'+(21+i),project_key:'测试仓库',
        tag:'纳入台账',contract_amt:'123.45',payment_method:method}));
      API.m11List=async()=>({...data,rows:sortRows});
      VIEW='m11';fJc.tag='全部';fJc.projs=[];return reloadM11();
    }""", {'columns': list(JC_COLUMNS), 'sum_keys': list(SUM_KEYS), 'payment_methods': list(PAY_METHODS)})
    header = p.locator('th[data-tk="m11:jc"]').filter(has_text='合同付款方式')
    choices = p.get_by_role('combobox', name='合同付款方式', exact=True)
    original = choices.evaluate_all('els=>els.map(e=>e.value)')
    header.click()
    assert choices.evaluate_all('els=>els.map(e=>e.value)') == ['承兑', '供应链', '其他', '现汇', '']
    header.click()
    assert choices.evaluate_all('els=>els.map(e=>e.value)') == ['现汇', '其他', '供应链', '承兑', '']
    header.click()
    assert choices.evaluate_all('els=>els.map(e=>e.value)') == original


def test_payment_warning_groups_contract_and_preserves_all_invoice_dates(ui_page):
    p = ui_page
    result = p.evaluate("""()=>{
      const row={contract_id:21,contract_no:'TEST-21',term_warning:{payment_term:'60±7天',
        invoices:[{invoice_date:'2026-08-01',remind_through:'2026-10-07'},
          {invoice_date:'2026-09-01',remind_through:'2026-11-07'}]}};
      const host=document.createElement('div');host.innerHTML=payTermsHtml([row,row]);
      return {contracts:host.querySelectorAll('td[rowspan="2"]').length,
        rows:host.querySelectorAll('tbody tr').length,dates:[...host.querySelectorAll('time')].map(t=>t.textContent)};
    }""")
    assert result == {'contracts': 2, 'rows': 2, 'dates': ['2026-08-01', '2026-10-07', '2026-09-01', '2026-11-07']}


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
    assert term.get_attribute('placeholder') is None
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
    expect(p.locator('#jcNTerm')).to_have_value('')
    assert p.locator('#jcNTerm').get_attribute('placeholder') is None
    p.locator('#jcNTerm').fill('30天')
    p.locator('#jcNMethod').select_option('其他')
    p.locator('[data-act="jcRowSave"]').click()
    p.wait_for_function('window.termsAdded')
    assert p.evaluate('termsAdded.payment_term') == '30天'
    assert p.evaluate('termsAdded.payment_method') == '其他'
    if output := os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        p.screenshot(path=str(out / f'contract-terms-{width}.png'), full_page=True)



@pytest.mark.parametrize("width,scale", [(1920, 1), (1280, 1.4)])
def test_payment_warning_tracks_date_without_overwriting_manual_method(ui_page, width, scale):
    p = ui_page
    p.set_viewport_size({'width': width, 'height': 1080})
    p.evaluate("scale=>document.documentElement.style.setProperty('--fscale',scale)", scale)
    p.evaluate("""()=>{
      SYS_TODAY='2026-04-11';NO[0].astat='已批';NO[0].paid=0;NO[0].amountPaid=0;
      NO.push({...NO[0],id:'102',code:'DOC-102'});
      JCs.push(adaptJc({id:21,notice_ids:[101,102],contract_no:'TEST-21',tag:'纳入台账'}));
      window.contextCalls=[];
      window.warning={message:'该合同存在未满账期的发票，请核对本次付款',payment_term:'90±10天',max_days:100,
        pay_date:'2026-04-11',invoice_side:'supplier',invoices:[{invoice_id:1,invoice_date:'2026-01-01',remind_through:'2026-04-11'}]};
      API.paymentContext=async body=>{contextCalls.push(body);return {ok:true,rows:[{notice_id:101,contract_id:21,
        contract_no:'TEST-21',default_pay_method:'承兑',default_pay_method_source:'contract',
        term_warning:body.pay_date==='2026-04-11'?warning:null},
        {notice_id:102,contract_id:22,contract_no:'TEST-22',default_pay_method:'现汇',term_warning:null}]};};
      API.batchPay=async body=>{window.contextPayment=body;return {ok:true,message:'已登记付款'};};
      reloadNotices=async()=>{};
      pickSet.clear();pickSet.add('101');pickSet.add('102');return ACT.batchPay();
    }""")
    expect(p.locator('#bm0')).to_have_value('承兑')
    row = p.locator('[data-pay-notice-id="101"]')
    expect(row).to_have_class('pay-term-warning')
    assert row.locator('td').evaluate_all('cells=>cells.every(c=>getComputedStyle(c).backgroundColor===getComputedStyle(cells[0]).backgroundColor)')
    normal = p.locator('[data-pay-notice-id="102"]')
    expect(normal).not_to_have_class('pay-term-warning')
    assert row.locator('td').first.evaluate('c=>getComputedStyle(c).backgroundColor') != normal.locator('td').first.evaluate('c=>getComputedStyle(c).backgroundColor')
    expect(p.get_by_role('dialog')).not_to_contain_text('确认后每条生成一笔付款流水')
    expect(p.locator('#batchPayTerms')).to_contain_text('2026-04-11')
    expect(p.locator('#batchPayTerms')).to_contain_text('90±10天')
    p.locator('#bm0').select_option('现汇')
    p.locator('#ba0').fill('100.00')
    p.locator('#ba0').blur()
    header = p.get_by_role('dialog').get_by_role('button', name='单据编码↕', exact=True)
    header.click()
    p.get_by_role('dialog').get_by_role('button', name='单据编码▲', exact=True).click()
    expect(p.get_by_role('dialog').locator('[data-pay-notice-id]').first).to_have_attribute('data-pay-notice-id', '102')
    p.locator('#bDate').fill('2026-04-12')
    p.locator('#bDate').blur()
    expect(p.locator('#batchPayTerms')).to_be_empty()
    expect(row).not_to_have_class('pay-term-warning')
    expect(p.locator('#bm0')).to_have_value('现汇')
    expect(p.locator('#ba0')).to_have_value('100.00')
    p.locator('#bDate').fill('2026-04-11')
    p.locator('#bDate').blur()
    expect(p.locator('#batchPayTerms')).to_contain_text('未满账期')
    expect(row).to_have_class('pay-term-warning')
    expect(p.locator('#bm0')).to_have_value('现汇')
    if output := os.environ.get('MTRL_UI_EVIDENCE_PATH'):
        out=Path(output)
        out.mkdir(parents=True,exist_ok=True)
        p.get_by_role('dialog').screenshot(path=str(out/f'payment-terms-warning-{width}.png'))
    p.on('dialog',lambda dialog:dialog.accept())
    p.locator('[data-act="batchPayOk"]').click()
    p.wait_for_function('window.contextPayment')
    assert p.evaluate('contextPayment.drafts["101"].pay_method') == '现汇'
    assert p.evaluate('contextPayment.pay_date') == '2026-04-11'
    assert p.evaluate('contextPayment.drafts["101"].amount') == '100.00'



def test_old_backend_without_terms_still_opens_payment_window(ui_page):
    p = ui_page
    p.route('**/api/m03/payment-context', lambda route: route.fulfill(status=404, json={'detail':'Not Found'}))
    p.evaluate("""()=>{
      API.paymentContext=window.originalPaymentContext;
      NO[0].code='FKTZS2026060313';NO[0].cat='辅材';NO[0].astat='已批';
      NO[0].plannedPayMethod='供应链';
      pickSet.clear();pickSet.add('101');return ACT.batchPay();
    }""")
    expect(p.locator('#bm0')).to_have_value('供应链')
    expect(p.locator('#batchPayTerms')).to_contain_text('暂未启用')
    expect(p.locator('#batchPayTerms')).to_contain_text('人工核对')
    p.locator('#bm0').select_option('承兑')
    p.locator('#bDate').fill('2026-04-12')
    p.locator('#bDate').blur()
    expect(p.locator('#batchPayTerms')).to_contain_text('人工核对')
    expect(p.locator('#bm0')).to_have_value('承兑')
    assert p.locator('[data-act="batchPayOk"]').is_enabled()


def test_terms_server_error_does_not_become_old_backend_fallback(ui_page):
    p=ui_page
    p.route('**/api/m03/payment-context',lambda route:route.fulfill(status=500,json={'detail':'failed'}))
    p.evaluate("""()=>{API.paymentContext=window.originalPaymentContext;
      pickSet.clear();pickSet.add('101');return ACT.batchPay();}""")
    expect(p.locator('.toast').last).to_contain_text('系统内部出错了')
    expect(p.locator('.toast').last).to_contain_text('请刷新页面重试')
    assert p.locator('#bm0').count()==0


@pytest.mark.parametrize('status,reason', [(401,'登录'),(403,'权限')])
def test_terms_auth_errors_keep_actionable_reason(ui_page,status,reason):
    p=ui_page
    p.route('**/api/m03/payment-context',lambda route:route.fulfill(status=status,json={'detail':'denied'}))
    p.evaluate("""()=>{API.paymentContext=window.originalPaymentContext;
      pickSet.clear();pickSet.add('101');return ACT.batchPay();}""")
    expect(p.locator('.toast').last).to_contain_text(reason)
    assert p.locator('#bm0').count()==0


def test_date_recheck_preserves_network_reason(ui_page):
    p=ui_page
    p.evaluate("""()=>{pickSet.clear();pickSet.add('101');return ACT.batchPay();}""")
    p.route('**/api/m03/payment-context',lambda route:route.abort('failed'))
    p.evaluate('()=>{API.paymentContext=window.originalPaymentContext;}')
    p.locator('#bDate').fill('2026-04-12')
    p.locator('#bDate').blur()
    expect(p.locator('#batchPayTerms')).to_contain_text('连不上服务器')
    expect(p.locator('#batchPayTerms')).to_contain_text('网络正常')
