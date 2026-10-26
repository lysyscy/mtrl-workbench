"""Existing contract real field write, corrupted receipt and unified search."""
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page,contract_sample,grid_row


def test_real_unified_search_and_no_supplier_or_amount_control(server,browser_page,api):
    page,_=browser_page;row,label=contract_sample(api);open_page(page,server,'contracts','集采台账')
    search=page.get_by_label('搜索',exact=True);search.fill(label)
    expect(grid_row(page,'.contracts-grid',row['id'])).to_be_visible()
    expect(page.get_by_label('供应商',exact=True)).to_have_count(0)
    expect(page.get_by_label('合同金额筛选',exact=True)).to_have_count(0)
    page.locator('.contract-search-field .ant-input-clear-icon').click();expect(search).to_have_value('')


def test_real_contract_field_bad_receipt_locks_until_readback(server,browser_page,api,disposable):
    page,_=browser_page;row,label=contract_sample(api);open_page(page,server,'contracts','集采台账')
    page.get_by_label('搜索',exact=True).fill(label)
    term=page.get_by_label(label+' 账期',exact=True);writes=[]
    def damaged(route):
        response=route.fetch();assert response.ok and response.json()['ok'] is True
        writes.append(route.request.post_data);route.fulfill(response=response,body='{')
    page.route('**/api/m11/fields',damaged)
    term.fill('31天');term.press('Tab')
    expect(page.get_by_role('alert').first).to_contain_text('待核实');expect(term).to_be_disabled();assert len(writes)==1
    assert get(api,'/api/m11/detail',id=row['id'])['data']['payment_term']=='31±0天'
    page.unroute('**/api/m11/fields');page.get_by_role('button',name='重读核对',exact=True).click()
    expect(term).to_be_enabled()
