"""Existing contract real field write, corrupted receipt and unified search."""
from uuid import uuid4

from playwright.sync_api import expect
from test_preview import server,browser_page
from live_data import get,open_page,contract_sample,grid_row


def test_fetch_receipt_handles_pending_items_in_its_window(server, browser_page, api, disposable):
    page, _ = browser_page
    suffix = uuid4().hex
    small = next(row for row in get(api, '/api/m01/projects', status='all') if row['project_type'] == 'small')
    shell = small['name_full']
    keyword = 'QA-' + suffix
    other_project = '测试剔除项目-' + suffix
    pending = [
        {'contract_no': 'QA-1-' + suffix, 'project_name': shell, 'doc_name': keyword, 'kind': 'needs_keyword'},
        {'contract_no': 'QA-2-' + suffix, 'project_name': other_project, 'doc_name': '按号处理合同', 'kind': 'not_archived'},
        {'contract_no': 'QA-3-' + suffix, 'project_name': other_project, 'doc_name': '按项目处理合同', 'kind': 'not_archived'},
        {'contract_no': 'QA-4-' + suffix, 'project_name': '暂未处理项目', 'doc_name': '暂未处理合同', 'kind': 'not_archived'},
    ]
    written = []
    receipt = {
        'id': 12, 'started_at': '2026-11-12T10:06:00', 'status': 'success', 'matched': 4,
        'scope': '全部合同', 'unsettled_count': 4, 'ignored_count': 0,
        'unsettled': pending, 'ignored': [],
        'summary': {'source_count': 8, 'identified_count': 8, 'inserted': 0, 'changed': 1, 'unchanged': 3},
    }

    def save(route):
        response = route.fetch()
        assert response.ok and response.json()['ok']
        written.append(route.request.post_data_json)
        route.fulfill(response=response)

    me = get(api, '/api/m15/users')['me']
    page.route('**/api/m02/config', lambda route: route.fulfill(json={
        'ready': True, 'account': me['account'], 'i8_user': 'offline-test', 'message': '',
    }))
    page.route('**/api/m11/fetch', lambda route: route.fulfill(json={'ok': True, 'receipt': receipt}))
    page.route('**/api/m11/unsettled?run_id=12', lambda route: route.fulfill(json={'items': pending[len(written):]}))
    page.route('**/api/m01/ownership', lambda route: route.fulfill(json={
        'kind': 'needs_keyword', 'reason': '缺少识别词', 'candidates': [
            {'key': small['warehouse_name'], 'display': small['disp'], 'archived': False},
        ],
    }))
    page.route('**/api/m03/notices/ownership-assign', save)
    page.route('**/api/m14/jc-ignore', save)
    page.set_viewport_size({'width': 900, 'height': 760})
    open_page(page, server, 'contracts', '集采台账')
    page.get_by_role('button', name='抓取采购合同信息').click()
    dialog = page.get_by_role('dialog', name='抓取采购合同', exact=True)
    dialog.get_by_role('button', name='确认抓取').click()
    expect(dialog.get_by_text('i8 返回 8 条')).to_be_visible()
    expect(dialog.get_by_text('实际变更 1 条')).to_be_visible()
    dialog.get_by_role('button', name='补归属关键词').click()
    editor = page.get_by_role('dialog', name='指定项目归属')
    editor.get_by_label('归属小微').select_option(str(small['id']))
    editor.get_by_label('关键词', exact=True).fill(keyword)
    editor.get_by_role('button', name='确认补充档案').click()
    expect(editor).not_to_be_visible()
    expect(dialog.get_by_text(pending[0]['contract_no'], exact=True)).not_to_be_visible()

    number = dialog.get_by_role('listitem').filter(has_text=pending[1]['contract_no'])
    number.get_by_role('button', name='仅剔除这份合同').click()
    number.get_by_role('button', name='确认加入剔除规则').click()
    expect(number).not_to_be_visible()
    project = dialog.get_by_role('listitem').filter(has_text=pending[2]['contract_no'])
    project.get_by_role('button', name='剔除这个项目').click()
    project.get_by_role('button', name='确认加入剔除规则').click()
    expect(project).not_to_be_visible()
    assert written == [
        {'doc_name': keyword, 'keyword': keyword, 'small_id': small['id']},
        {'kind': 'contract', 'contract_no': pending[1]['contract_no']},
        {'kind': 'project', 'name_full': other_project},
    ]
    expect(dialog.get_by_text(pending[3]['contract_no'], exact=True)).to_be_visible()
    dialog.get_by_role('button', name='关闭', exact=True).click()
    page.get_by_role('button', name='抓取采购合同信息').click()
    expect(dialog.get_by_role('button', name='确认抓取')).to_be_visible()
    expect(dialog.get_by_text(pending[3]['contract_no'], exact=True)).to_have_count(0)


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
