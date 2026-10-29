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
    term.fill('31天');page.get_by_role('heading',name='集采台账',exact=True).click()
    expect(page.get_by_role('alert').first).to_contain_text('待核实');expect(term).to_be_disabled();assert len(writes)==1
    assert get(api,'/api/m11/detail',id=row['id'])['data']['payment_term']=='31±0天'
    page.unroute('**/api/m11/fields');page.get_by_role('button',name='重读核对',exact=True).click()
    expect(term).to_be_enabled()


def test_real_contract_inline_typing_and_readback_keep_next_input_stable(server,browser_page,api,disposable):
    page,_=browser_page;row,label=contract_sample(api);open_page(page,server,'contracts','集采台账')
    page.get_by_label('搜索',exact=True).fill(label)
    term=page.get_by_label(label+' 账期',exact=True);remark=page.get_by_label(label+' 备注',exact=True)
    original_remark=remark.input_value();value='32天' if row['payment_term']=='31±0天' else '31天'
    term.click();node=term.element_handle()
    for text in (value[:1],value[:2],value):
        term.fill(text)
        assert node.evaluate('e=>e.isConnected&&document.activeElement===e')
    pending=[]
    page.route('**/api/m11/fields',lambda route:pending.append(route))
    grid=page.locator('.contracts-grid');before=grid.bounding_box()
    with page.expect_request('**/api/m11/fields'):
        remark.fill('保留下一格输入')
    expect(page.locator('.contract-feedback')).to_have_count(0)
    expect(page.locator('.ant-message-notice')).to_have_count(0)
    current=grid.bounding_box()
    assert all(abs(current[key]-before[key])<1 for key in ('y','height'))
    next_node=remark.element_handle();route=pending.pop();response=route.fetch()
    assert response.ok and response.json()['ok'];route.fulfill(response=response)
    expect(term).to_have_value(value.replace('天','±0天'))
    expect(remark).to_have_value('保留下一格输入')
    assert next_node.evaluate('e=>e.isConnected&&document.activeElement===e')
    expect(page.locator('.ant-message-notice')).to_have_count(0)
    page.unroute('**/api/m11/fields');remark.fill(original_remark);remark.blur()
