"""Real contract subtable draft and normal add/delete wiring, isolated copy only."""
import json
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
    page.reload()
    modal=open_payment(page,server,row,label)
    expect(modal.get_by_label('手工付款金额（元）',exact=True)).to_have_value('')


def test_actual_manual_payment_add_delete_roundtrip(server,browser_page,api,disposable):
    """请求未到达服务端：自动查询得"未找到"，重试沿用同一 request_id，最终只记一次。"""
    page,_=browser_page;row,label=contract_sample(api);before=get(api,'/api/m11/detail',id=row['id'])['data'];modal=open_payment(page,server,row,label)
    amount=modal.get_by_label('手工付款金额（元）',exact=True);amount.fill('1.25');writes=[];lookups=[]
    def lose(route):
        writes.append(json.loads(route.request.post_data))
        # 首次请求在浏览器侧断掉（服务端没收到）；重试放行到真实服务端。
        if len(writes)==1: route.abort('failed')
        else: route.continue_()
    def not_found(route):
        lookups.append(route.request.url);route.fulfill(status=200,content_type='application/json',body=json.dumps({'ok':True,'status':'not_found'}))
    page.route('**/api/m11/payment/add',lose);page.route('**/api/m11/subtable-operation?*',not_found)
    modal.get_by_role('button',name='新增手工付款',exact=True).click()
    # 结果未知 → 自动查询这次提交（无需手工"重读明细/已核对"）；确实未落地就明确说未保存。
    expect(modal.get_by_text('暂未查到上次手工付款操作的保存结果')).to_be_visible()
    assert len(writes)==1 and len(lookups)==1 and 'request_id=' in lookups[0]
    amount.fill('9.50')
    page.reload()
    modal=open_payment(page,server,row,label)
    expect(modal.get_by_label('手工付款金额（元）',exact=True)).to_have_value('9.50')
    retry=modal.get_by_role('button',name='重试上次手工付款',exact=True);expect(retry).to_be_enabled()
    assert len(writes)==1 and len(lookups)==2
    page.unroute('**/api/m11/subtable-operation?*');retry.click()
    expect(page.get_by_text('手工付款已新增。',exact=True)).to_be_visible()
    assert len(writes)==2 and writes[0]['request_id']==writes[1]['request_id']
    assert writes[1]==writes[0]
    expect(modal.get_by_label('手工付款金额（元）',exact=True)).to_have_value('9.50')
    after=get(api,'/api/m11/detail',id=row['id'])['data']
    assert Decimal(after['pay_sum'])==Decimal(before['pay_sum'])+Decimal('1.25') and len(after['payments'])==len(before['payments'])+1
    ids={p['id'] for p in before['payments']};added=next(p for p in after['payments'] if p['id'] not in ids)
    dom=modal.locator('.ag-row').filter(has=page.locator('[data-subtable="payment"][data-row="'+str(added['id'])+'"]'))
    dom.get_by_role('button',name='删除手工付款',exact=True).click()
    confirm=modal.get_by_role('group',name='确认删除子行');confirm.get_by_role('button',name='取消删除',exact=True).click()
    assert Decimal(get(api,'/api/m11/detail',id=row['id'])['data']['pay_sum'])==Decimal(after['pay_sum'])
    dom.get_by_role('button',name='删除手工付款',exact=True).click();modal.get_by_role('group',name='确认删除子行').get_by_role('button',name='确认删除',exact=True).click()
    expect(page.get_by_text('已删除。',exact=True)).to_be_visible()
    assert get(api,'/api/m11/detail',id=row['id'])['data']['pay_sum']==before['pay_sum']


def test_actual_lost_receipt_is_confirmed_without_second_write(server,browser_page,api,disposable):
    """请求已到服务端但回执丢失：自动查询得已完成，只写一次、不重投、不误报未保存。"""
    page,_=browser_page;row,label=contract_sample(api);before=get(api,'/api/m11/detail',id=row['id'])['data'];modal=open_payment(page,server,row,label)
    amount=modal.get_by_label('手工付款金额（元）',exact=True);amount.fill('2.50');writes=[]
    def lose_receipt(route):
        writes.append(json.loads(route.request.post_data));response=route.fetch();assert response.ok and response.json()['ok'];route.abort('failed')
    page.route('**/api/m11/payment/add',lose_receipt);modal.get_by_role('button',name='新增手工付款',exact=True).click()
    expect(page.get_by_text('手工付款已保存。',exact=True)).to_be_visible()
    assert len(writes)==1
    after=get(api,'/api/m11/detail',id=row['id'])['data'];assert Decimal(after['pay_sum'])==Decimal(before['pay_sum'])+Decimal('2.50')
    expect(modal.get_by_label('手工付款金额（元）',exact=True)).to_have_value('')
