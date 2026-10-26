"""An actual payment commit with lost response remains locked and is never called unregistered."""
from decimal import Decimal
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page


def test_actual_payment_commit_lost_response_never_resubmits(server,browser_page,api,disposable):
    page,_=browser_page;data=get(api,'/api/m03/notice-list',period='')
    row=next((r for r in data['items'] if not r['pay_block_reason'] and not r['is_excluded'] and not r['is_revoked'] and r['ownership_id'] and Decimal(r['amount_approved'])-Decimal(r['amount_paid'])>=Decimal('1.25')),None)
    assert row,'真实副本没有可付款通知书，付款未知结果浏览器路径未覆盖'
    open_page(page,server,'notices','付款通知书');page.get_by_label('通知书搜索',exact=True).fill(row['bill_no']);page.get_by_label('勾选'+row['bill_no'],exact=True).check();page.locator('.notice-pay-action').click()
    dialog=page.get_by_role('dialog',name='批量付款',exact=True);dialog.get_by_label(row['bill_no']+'本次付款金额',exact=True).fill('1.25');writes=[]
    def lose(route):
        response=route.fetch();assert response.ok and response.json()['ok'];writes.append(route.request.post_data_json);route.abort('failed')
    page.route('**/api/m03/actions/batch-pay',lose);dialog.get_by_role('button',name='确认付款',exact=True).click()
    expect(dialog.get_by_role('alert').filter(has_text='提交结果尚未核实')).to_be_visible();expect(dialog.get_by_text('整批未登记',exact=False)).to_have_count(0);expect(dialog.get_by_role('button',name='确认付款',exact=True)).to_have_count(0)
    current=next(r for r in get(api,'/api/m03/notice-list',period='')['items'] if r['notice_id']==row['notice_id'])
    assert Decimal(current['amount_paid'])==Decimal(row['amount_paid'])+Decimal('1.25') and len(writes)==1
    dialog.get_by_role('button',name='重读列表核对',exact=True).click();expect(dialog.get_by_role('button',name='确认付款',exact=True)).to_have_count(0);assert len(writes)==1
