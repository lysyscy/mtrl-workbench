"""Real contract subtable draft and normal add/delete wiring, isolated copy only."""
from decimal import Decimal
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page,contract_sample


def open_payment(page,server,row,label):
    open_page(page,server,'contracts','集采台账')
    page.get_by_label('搜索',exact=True).fill(label)
    page.get_by_role('button',name=label+' 付款子表',exact=True).click()
    modal=page.locator('.contract-subtable-dialog');expect(modal).to_be_visible();return modal


def test_actual_subtable_draft_survives_navigation_and_close_confirm(server,browser_page,api):
    page,_=browser_page;row,label=contract_sample(api);modal=open_payment(page,server,row,label)
    amount=modal.get_by_label('手工付款金额（元）',exact=True);amount.fill('1.25')
    page.go_back();page.get_by_role('link',name='集采台账',exact=True).click()
    expect(modal).to_be_visible();expect(amount).to_have_value('1.25')
    modal.get_by_role('button',name='关闭',exact=True).click();expect(modal.get_by_role('heading',name='放弃未保存的修改？')).to_be_visible()
    modal.get_by_role('button',name='继续编辑',exact=True).click();expect(amount).to_have_value('1.25')
    modal.get_by_role('button',name='关闭',exact=True).click();modal.get_by_role('button',name='放弃并关闭',exact=True).click();expect(modal).not_to_be_visible()


def test_actual_manual_payment_add_delete_roundtrip(server,browser_page,api,disposable):
    page,_=browser_page;row,label=contract_sample(api);before=get(api,'/api/m11/detail',id=row['id'])['data'];modal=open_payment(page,server,row,label)
    amount=modal.get_by_label('手工付款金额（元）',exact=True);amount.fill('1.25');writes=[]
    def damaged(route):
        response=route.fetch();assert response.ok and response.json()['ok'];writes.append(route.request.post_data);route.fulfill(response=response,body='{')
    page.route('**/api/m11/payment/add',damaged);modal.get_by_role('button',name='新增手工付款',exact=True).click()
    expect(modal.get_by_role('alert')).to_contain_text('未取得保存确认');expect(modal.get_by_role('button',name='新增手工付款',exact=True)).to_be_disabled();assert len(writes)==1
    page.unroute('**/api/m11/payment/add');modal.get_by_role('button',name='重读明细',exact=True).click();expect(modal.get_by_role('button',name='已核对结果，继续处理',exact=True)).to_be_enabled()
    assert len(writes)==1;modal.get_by_role('button',name='已核对结果，继续处理',exact=True).click()
    expect(modal.get_by_role('button',name='新增手工付款',exact=True)).to_be_enabled()
    after=get(api,'/api/m11/detail',id=row['id'])['data'];assert Decimal(after['pay_sum'])==Decimal(before['pay_sum'])+Decimal('1.25')
    ids={p['id'] for p in before['payments']};added=next(p for p in after['payments'] if p['id'] not in ids)
    dom=modal.locator('.ag-row').filter(has=page.locator('[data-subtable="payment"][data-row="'+str(added['id'])+'"]'))
    dom.get_by_role('button',name='删除手工付款',exact=True).click()
    confirm=modal.get_by_role('group',name='确认删除子行');confirm.get_by_role('button',name='取消删除',exact=True).click()
    assert Decimal(get(api,'/api/m11/detail',id=row['id'])['data']['pay_sum'])==Decimal(after['pay_sum'])
    dom.get_by_role('button',name='删除手工付款',exact=True).click();modal.get_by_role('group',name='确认删除子行').get_by_role('button',name='确认删除',exact=True).click()
    expect(page.get_by_text('已删除。',exact=True)).to_be_visible()
    assert get(api,'/api/m11/detail',id=row['id'])['data']['pay_sum']==before['pay_sum']
