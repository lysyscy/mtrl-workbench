"""Real ledger continuity, one write per result and account-bound drafts."""
from decimal import Decimal
from playwright.sync_api import expect
from preview_select import pick_option
from test_preview import server,browser_page
from live_data import get,grid_row,ledger_sample,open_page


def open_sample(page,server,project):
    open_page(page,server,'debt','欠款台账')
    pick_option(page,'选择项目',project['disp'])
    expect(page.get_by_role('region',name='辅材欠款台账',exact=True)).to_be_visible()


def test_actual_ledger_edit_keeps_next_draft_and_reads_back(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,side,row,key=ledger_sample(api,projects,editable=True);open_sample(page,server,project)
    dom=grid_row(page,'.ledger-grid',key);first=dom.locator('[col-id="other_expense"] input');second=dom.locator('[col-id="payment"] input')
    before=Decimal(row['other_expense']);value=before+Decimal('1.25');next_value=Decimal(row['payment'])+Decimal('2.50');pending=[]
    page.route('**/api/m05/history/save',lambda route:pending.append(route))
    first.fill(str(value));second.click();second.fill(str(next_value));assert len(pending)==1
    route=pending.pop();response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('已保存');expect(second).to_have_value(str(next_value))
    page.unroute('**/api/m05/history/save')
    with page.expect_response(lambda response:response.url.endswith('/api/m05/history/save') and response.request.method=='POST') as paid:
        page.get_by_role('heading',name='欠款台账',exact=True).click()
    assert paid.value.ok
    expect(page.get_by_role('status',name='保存回执')).not_to_contain_text('正在保存')
    current=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    actual=next(r for s in current['sides'] if s['category']==side['category'] for r in s['rows'] if r['record_id']==row['record_id'] and r['month']==row['month'])
    assert Decimal(actual['other_expense'])==value and Decimal(actual['payment'])==next_value


def test_actual_ledger_lost_write_receipt_cannot_resubmit(server,browser_page,api,projects,disposable):
    page,_=browser_page;project,side,row,key=ledger_sample(api,projects,editable=True);open_sample(page,server,project)
    dom=grid_row(page,'.ledger-grid',key);field=dom.locator('[col-id="remark"] input');text=row['remark']+'核验';writes=[]
    def lose(route):
        response=route.fetch();assert response.ok and response.json()['ok'];writes.append(route.request.post_data);route.abort('failed')
    page.route('**/api/m05/history/save',lose);field.fill(text);page.get_by_role('heading',name='欠款台账',exact=True).click()
    expect(page.get_by_role('status',name='保存回执')).to_contain_text('未确认');assert len(writes)==1
    page.get_by_role('heading',name='欠款台账',exact=True).click();assert len(writes)==1
    page.unroute('**/api/m05/history/save');page.get_by_role('button',name='重新加载',exact=True).click()
    expect(field).to_be_enabled();assert len(writes)==1
    current=get(api,'/api/m05/ledger',project_id=project['id'],end_ym='')
    assert any(r['remark']==text for s in current['sides'] for r in s['rows'] if r['record_id']==row['record_id'] and r['month']==row['month'])
