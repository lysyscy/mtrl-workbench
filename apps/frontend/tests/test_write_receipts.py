"""An actual payment commit with lost response remains locked and is never called unregistered."""
from decimal import Decimal
from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page


def test_actual_payment_commit_lost_response_never_resubmits(server,browser_page,api,disposable):
    page,_=browser_page;data=get(api,'/api/m03/notice-list',period='')
    page.add_init_script("Object.defineProperty(Crypto.prototype, 'randomUUID', {value: undefined, configurable: true})")
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


def test_real_notice_stat_save_is_silent_and_does_not_move_grid(server,browser_page,api,disposable):
    page,_=browser_page;data=get(api,'/api/m03/notice-list',period='')
    row=next((r for r in data['items'] if not r['is_excluded'] and not r['is_revoked']
              and r['pay_status']=='未付清' and Decimal(r['amount_approved'])>0),None)
    assert row,'真实副本没有可编辑统计金额的未付清通知书'
    value='0.00' if Decimal(row['stat_settle']) else row['amount_approved']
    open_page(page,server,'notices','付款通知书');page.get_by_label('通知书搜索',exact=True).fill(row['bill_no'])
    field=page.get_by_label(row['bill_no']+'统计结算金额',exact=True);field.fill(value)
    grid=page.locator('.notice-grid');before=grid.bounding_box();pending=[];reads=[]
    page.route('**/api/m03/actions/stat',lambda route:pending.append(route))
    page.on('request',lambda request:reads.append(request.url.split('/api/',1)[1].split('?',1)[0])
            if request.method=='GET' and '/api/' in request.url else None)
    with page.expect_request('**/api/m03/actions/stat'):
        field.blur()
    expect(page.get_by_text('正在保存，请稍候…',exact=True)).to_have_count(0)
    current=grid.bounding_box()
    assert all(abs(current[key]-before[key])<1 for key in ('y','height'))
    route=pending.pop();response=route.fetch();assert response.ok and response.json()['ok'];route.fulfill(response=response)
    expect(field).to_be_enabled()
    expect(page.locator('.ant-message-notice')).to_have_count(0)
    assert not set(reads)-{'m03/notice-list','history/status'},reads
    fresh=next(r for r in get(api,'/api/m03/notice-list',period='')['items'] if r['notice_id']==row['notice_id'])
    assert Decimal(fresh['stat_settle'])==Decimal(value)


def test_payment_date_recheck_keeps_dialog_and_input_positions(server,browser_page,api):
    page,_=browser_page;rows=get(api,'/api/m03/notice-list',period='')['items']
    row=next(r for r in rows if not r['pay_block_reason'] and not r['is_excluded'] and not r['is_revoked'] and Decimal(r['pay_amount'])>0)
    open_page(page,server,'notices','付款通知书');page.get_by_label('通知书搜索',exact=True).fill(row['bill_no'])
    page.get_by_label('勾选'+row['bill_no'],exact=True).check();page.locator('.notice-pay-action').click()
    dialog=page.get_by_role('dialog',name='批量付款',exact=True);confirm=dialog.get_by_role('button',name='确认付款',exact=True)
    expect(confirm).to_be_enabled();expect(dialog.locator('[data-layout-state]').first).to_have_attribute('data-layout-state','ready')
    page.evaluate('async()=>{await Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))}')
    note=dialog.get_by_label('本批付款备注',exact=True);note.fill('保留备注');note.blur()
    page.evaluate('''()=>{window.dateFrames=[];window.dateTrace=true;const tick=()=>{if(!window.dateTrace)return;const d=document.querySelector('.notice-pay-dialog'),f=d.querySelector('input[aria-label="付款日期"]'),b=d.getBoundingClientRect(),r=f.getBoundingClientRect();window.dateFrames.push({x:b.x,y:b.y,w:b.width,h:b.height,fx:r.x,fy:r.y});requestAnimationFrame(tick)};tick()}''')
    pending=[];page.route('**/api/m03/payment-context',lambda route:pending.append(route))
    date=dialog.get_by_label('付款日期',exact=True);date.click()
    page.locator('.ant-picker-dropdown').filter(visible=True).locator('td.ant-picker-cell-in-view:not(.ant-picker-cell-selected)').nth(8).click()
    expect(confirm).to_be_disabled();assert len(pending)==1
    page.wait_for_timeout(100)
    route=pending.pop();assert route.request.post_data_json['pay_date']==date.input_value()
    response=route.fetch();assert response.ok;route.fulfill(response=response)
    expect(confirm).to_be_enabled();expect(note).to_have_value('保留备注')
    expect(dialog.get_by_text('正在核对合同账期…',exact=True)).to_have_count(0)
    page.wait_for_timeout(100);page.evaluate('window.dateTrace=false');frames=page.evaluate('window.dateFrames')
    assert len(frames)>3
    assert all(abs(frame[key]-frames[0][key])<1 for frame in frames for key in ('x','y','w','h','fx','fy')),frames
