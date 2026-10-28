"""项目写后历史头协调：只写disposable中的合成项目/账号。"""
from uuid import uuid4
import time

from playwright.sync_api import expect, Error as PlaywrightError
from test_preview import server, browser_page, login


def synthetic(api):
    token = uuid4().hex[:10]
    response = api.post('/api/m01/projects', json={'project_type': 'normal', 'name_full': '合成历史核验'+token,
        'disp': '合成核验'+token, 'warehouse_name': '合成仓'+token})
    response.raise_for_status()
    return response.json()


def field_for(page, row):
    page.get_by_label('项目搜索', exact=True).fill(row['warehouse_name'])
    return page.locator('.project-table .ag-row[row-id="'+str(row['id'])+'"]').locator('input[aria-label^="展示名："]')


def undo(page):
    return page.locator('.history-tools').get_by_role('button', name='撤销', exact=True)


def test_project_confirmed_save_refreshes_actual_history_head(server, browser_page, api, disposable):
    row = synthetic(api); page, _ = browser_page; login(page, server)
    expect(undo(page)).to_be_disabled()
    field = field_for(page, row); value = row['disp']+'甲'
    field.fill(value)
    with page.expect_response(lambda response: response.url.endswith(f'/api/m01/projects/{row["id"]}') and response.request.method=='PUT') as written:
        field.press('Enter')
    assert written.value.status==200 and written.value.json()['disp']==value
    expect(field).to_be_editable(); expect(field).to_have_value(value)
    assert api.get('/api/history/status').json()['undo']
    expect(undo(page)).to_be_enabled()
    expect(undo(page)).to_have_attribute('title', '修改项目展示资料')


def test_project_unknown_readback_refreshes_history_without_resubmission(server, browser_page, api, disposable):
    row = synthetic(api); page, _ = browser_page; login(page, server)
    expect(undo(page)).to_be_disabled(); calls = []
    def lose(route):
        response = route.fetch(); assert response.ok; calls.append(route.request.post_data_json); route.abort('failed')
    page.route(f'**/api/m01/projects/{row["id"]}', lose)
    field = field_for(page, row); value = row['disp']+'乙'
    field.fill(value); field.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_be_visible()
    expect(field).not_to_be_editable()
    page.unroute(f'**/api/m01/projects/{row["id"]}', lose)
    page.get_by_role('button', name='重读核对：展示名：'+row['disp'], exact=True).click()
    expect(field).to_be_editable(); expect(field).to_have_value(value)
    expect(undo(page)).to_be_enabled(); assert len(calls) == 1


def test_project_rejection_keeps_draft_and_confirmed_history_read_error_is_separate(server, browser_page, api, disposable):
    row = synthetic(api); page, _ = browser_page; login(page, server); expect(undo(page)).to_be_disabled()
    field = field_for(page, row); value = row['disp']+'丙'
    def reject(route):
        route.fulfill(status=409, json={'ok':False,'message':'合成明确拒绝'})
    page.route(f'**/api/m01/projects/{row["id"]}', reject)
    field.fill(value); field.press('Enter')
    expect(page.get_by_role('alert').filter(has_text='未保存，已保留输入')).to_be_visible()
    expect(field).to_be_editable(); expect(field).to_have_value(value); expect(undo(page)).to_be_disabled()
    assert api.get('/api/history/status').json()['undo'] is None
    page.unroute(f'**/api/m01/projects/{row["id"]}', reject)
    def fail_history(route):
        route.fulfill(status=503, json={'ok':False,'message':'合成历史读取失败'})
    page.route('**/api/history/status', fail_history)
    field.press('Enter')
    expect(page.locator('.history-tools [role=status]')).to_contain_text('操作历史未能读取')
    expect(field).to_be_editable(); expect(field).to_have_value(value)
    expect(page.get_by_role('alert').filter(has_text='保存结果待核实')).to_have_count(0)
    page.unroute('**/api/history/status', fail_history)
    page.locator('.history-tools').get_by_role('button', name='重读核对', exact=True).click()
    expect(undo(page)).to_be_enabled()


def test_old_account_history_read_cannot_restore_old_head_after_switch(server, browser_page, api, disposable):
    other='__history_'+uuid4().hex
    assert api.post('/api/m15/actions/create',json={'account':other,'name':'合成切换账号','password':''}).json()['ok']
    row=synthetic(api);page,_=browser_page;login(page,server);expect(undo(page)).to_be_disabled()
    expect(page.locator('.history-tools [role=status]')).to_contain_text('不支持撤销')
    held=[]
    def hold_first(route):
        if held:
            route.continue_();return
        response=route.fetch();assert response.ok;held.append((route,response))
    page.route('**/api/history/status',hold_first)
    try:
        field=field_for(page,row);field.fill(row['disp']+'丁')
        with page.expect_request('**/api/history/status'):
            field.press('Enter')
        deadline=time.monotonic()+5
        while not held and time.monotonic()<deadline:
            page.wait_for_timeout(10)
        assert held and held[0][1].json()['undo']
        assert page.request.post(server+'/m15/login',form={'account':other,'password':''},max_redirects=0).status == 303
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        expect(page.locator('.account-pill')).to_contain_text('合成切换账号')
        expect(undo(page)).to_be_disabled()
        try:
            held[0][0].fulfill(response=held[0][1])
        except PlaywrightError as exc:
            assert 'already' in str(exc).lower() or 'closed' in str(exc).lower() or 'cancel' in str(exc).lower() or 'intercept' in str(exc).lower()
        page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        expect(undo(page)).to_be_disabled()
        expect(page.locator('.project-cell-error')).to_have_count(0)
        assert page.request.get(server+'/api/history/status').json()['undo'] is None
    finally:
        for route, _ in held:
            try:route.abort('failed')
            except PlaywrightError:pass
        page.unroute('**/api/history/status',hold_first)
