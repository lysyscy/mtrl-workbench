"""Real exclusion rules and recovery of their write results."""
from uuid import uuid4

from playwright.sync_api import expect
from test_preview import server,browser_page,login
from live_data import get,open_page


def test_actual_rules_and_anonymous_write_protection(server,browser_page,api):
    page,_=browser_page
    data=get(api,'/api/m14/rules')
    assert data['ok'] and data['rules']
    open_page(page,server,'rules','规则配置',authenticated=False)
    expect(page.locator('.rules-block').first).to_be_visible()
    expect(page.get_by_role('button',name='＋ 增加规则',exact=True)).to_be_disabled()
    assert page.request.post(server+'/api/m14/rules',data={}).status==401
    page.get_by_role('navigation', name='规则所属业务').get_by_role('button', name='集采台账').click()
    expect(page.get_by_role('heading', name='集采合同抓取剔除', exact=False)).to_be_visible()
    expect(page.get_by_role('button', name='＋ 新增剔除规则', exact=True)).to_be_disabled()
    assert page.request.delete(server+'/api/m14/jc-ignore/1').status==401


def test_procurement_rule_create_search_filter_delete_and_receipt(server, browser_page, api, disposable):
    page, _ = browser_page
    number = 'QA-' + uuid4().hex
    receipt_calls = []
    page.on('request', lambda request: receipt_calls.append(request.url) if '/api/m14/jc-ignore/receipt' in request.url else None)
    open_page(page, server, 'rules', '规则配置')
    nav = page.get_by_role('navigation', name='规则所属业务')
    expect(nav.get_by_role('button')).to_have_text(['付款通知书', '集采台账'])
    nav.get_by_role('button', name='集采台账').click()
    page.get_by_role('button', name='＋ 新增剔除规则').click()
    add = page.get_by_role('dialog', name='新增集采剔除规则')
    add.get_by_label('匹配条件').select_option('contract')
    add.get_by_label('完整合同编号').fill(number)
    add.get_by_label('业务理由（选填）').fill('浏览器自检')
    add.get_by_role('button', name='新增', exact=True).click()
    expect(add).not_to_be_visible()
    page.get_by_label('条件类型').select_option('project')
    expect(page.get_by_text(number, exact=True)).to_have_count(0)

    nav.get_by_role('button', name='付款通知书').click()
    page.get_by_role('searchbox', name='搜索全部规则').fill(number)
    page.get_by_role('button', name='搜索全部规则', exact=True).click()
    search = page.get_by_role('dialog', name='搜索全部规则')
    search.get_by_role('button', name=number, exact=False).click()
    expect(search).not_to_be_visible()
    expect(page.locator('.rules-located')).to_contain_text(number)
    page.get_by_label('条件类型').select_option('contract')
    row = page.get_by_role('row').filter(has_text=number)
    row.get_by_role('button', name='删除').click()
    delete = page.get_by_role('dialog', name='删除集采剔除规则')
    delete.get_by_role('button', name='删除', exact=True).click()
    expect(row).to_have_count(0)
    assert all(rule['contract_no'] != number for rule in get(api, '/api/m14/jc-ignore')['items'])

    assert not receipt_calls
    page.get_by_role('button', name='最近抓取结果', exact=True).click()
    receipt = page.get_by_role('dialog', name='最近一次集采抓取结果')
    expect(receipt.locator('.jc-receipt-summary, .state').first).to_be_visible()
    assert len(receipt_calls) == 1
    receipt.get_by_role('link', name='i8 接入层 · 执行记录').click()
    expect(page.locator('#page-title')).to_have_text('i8 接入层')
    expect(page.locator('#execution-records')).to_be_visible()


def test_receipt_shows_recorded_contracts_and_conditions_from_i8_history(server, browser_page):
    page, _ = browser_page
    rule = {
        'id': 8, 'kind': 'keyword', 'name_full': '回执测试项目',
        'contract_no': '', 'bill_name_keyword': '排除样例', 'reason': '当时的剔除理由',
        'operator': '', 'created_at': '',
    }
    receipt = {
        'id': 12, 'started_at': '2026-11-12T10:06:00', 'status': 'success', 'matched': 3,
        'unsettled': [{'contract_no': 'QA-01', 'project_name': '待归属项目',
                       'doc_name': '材料采购合同', 'kind': 'not_archived'}],
        'ignored': [{'contract_no': 'QA-02', 'project_name': '回执测试项目',
                     'doc_name': '排除样例合同', 'matches': [rule]},
                    {'contract_no': 'QA-03', 'project_name': '旧回执项目'}],
        'unsettled_count': 1, 'ignored_count': 2,
    }
    page.route('**/api/m14/jc-ignore/receipt?run_id=12', lambda route: route.fulfill(json={'receipt': receipt}))
    page.route('**/api/m02/fetch/records*', lambda route: route.fulfill(json=[{
        'id': 12, 'run_type': 'fetch', 'target': 'jc_contract 全量', 'status': 'success',
        'success_count': 3, 'fail_count': 0, 'error_message': '',
        'started_at': receipt['started_at'], 'finished_at': None, 'triggered_by': '验看账号', 'duration_seconds': None,
    }]))
    open_page(page, server, 'i8', 'i8 接入层')
    page.get_by_role('button', name='查看明细', exact=True).click()
    dialog = page.get_by_role('dialog', name='集采抓取明细')
    expect(dialog.get_by_role('row').filter(has_text='QA-01')).to_contain_text('项目未建档')
    matched = dialog.get_by_role('row').filter(has_text='QA-02')
    expect(matched).to_contain_text('排除样例合同')
    expect(matched).to_contain_text('当时的剔除理由')
    expect(dialog.get_by_role('row').filter(has_text='QA-03')).to_contain_text('旧记录未保存命中条件')


def test_actual_rule_edit_preserves_notice_exclusion_flags(server,browser_page,api,disposable):
    page,_=browser_page
    before={r['notice_id']:r['is_excluded'] for r in get(api,'/api/m03/notice-list',period='')['items']}
    open_page(page,server,'rules','规则配置')
    block=page.locator('.rules-block').first
    block.get_by_role('button',name='编辑',exact=True).first.click()
    dialog=page.locator('.rules-dialog')
    meaning=dialog.get_by_label('剔除的业务含义')
    original=meaning.input_value()
    meaning.fill(original+'校验')
    dialog.get_by_role('button',name='保存修改',exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(block.get_by_role('status')).to_contain_text('已更新')
    after={r['notice_id']:r['is_excluded'] for r in get(api,'/api/m03/notice-list',period='')['items']}
    assert before==after


def test_actual_rule_add_lost_response_never_resubmits(server, browser_page, api, disposable):
    page, _ = browser_page
    before = get(api, '/api/m14/rules')
    before_ids = {row['id'] for row in before['rules']}
    notice_flags = {row['notice_id']: row['is_excluded'] for row in get(api, '/api/m03/notice-list', period='')['items']}
    value = f'丢回执核对-{uuid4().hex}'
    posted = []
    read_mode = 'earlier'

    def fault(route):
        if route.request.method == 'POST':
            response = route.fetch()
            assert response.ok and response.json()['ok']
            posted.append(route.request.post_data_json)
            route.abort('failed')
        elif read_mode == 'earlier':
            route.fulfill(json=before)
        elif read_mode == 'failed':
            route.fulfill(status=503, json={'message': '规则列表暂不可读'})
        else:
            route.continue_()

    open_page(page, server, 'rules', '规则配置')
    page.route('**/api/m14/rules', fault)
    new = page.get_by_role('button', name='＋ 增加规则', exact=True)
    new.click()
    form = page.get_by_role('dialog', name='新增剔除规则', exact=True)
    form.get_by_label('命中值', exact=False).fill(f' {value}，二号｜{value} ')
    form.get_by_label('剔除的业务含义').fill('待核对')
    form.get_by_role('button', name='新增', exact=True).evaluate('(button) => { button.click(); button.click(); }')
    review = page.get_by_role('dialog', name='核对剔除规则新增结果', exact=True)
    expect(review).to_be_visible()
    expect(review.get_by_role('button', name='新增', exact=True)).to_have_count(0)
    finish = review.get_by_role('button', name='结束本次新增，不再提交', exact=True)
    expect(finish).to_have_count(0)
    actual = [row for row in get(api, '/api/m14/rules')['rules'] if row['id'] not in before_ids]
    assert len(posted) == len(actual) == 1
    assert actual[0]['values'] == f'{value}｜二号'

    read = review.get_by_role('button', name='重新读取', exact=True)
    read.click()
    expect(review.get_by_role('status')).to_contain_text('原提交仍可能稍后写入')
    expect(finish).to_be_enabled()
    read_mode = 'failed'
    read.click()
    expect(review.get_by_text('列表读取失败', exact=False)).to_be_visible()
    expect(finish).to_have_count(0)

    review.get_by_role('button', name='先返回列表', exact=True).click()
    expect(review).not_to_be_visible()
    expect(new).to_be_disabled()
    block = page.locator('.rules-block').first
    expect(block.get_by_role('button', name='编辑', exact=True).first).to_be_disabled()
    expect(block.get_by_role('button', name='删除', exact=True).first).to_be_disabled()
    page.locator('a[href="/preview/projects"]').click()
    expect(page.locator('#page-title')).to_have_text('项目档案')
    page.locator('a[href="/preview/rules"]').click()
    expect(new).to_be_disabled()
    block.get_by_role('button', name='核对新增结果', exact=True).click()
    expect(review.get_by_label('剔除的业务含义')).to_have_value('待核对')
    read_mode = 'actual'
    read.click()
    expect(review.get_by_role('status')).to_contain_text('无法确认是否来自本次提交')
    finish.click()
    expect(review).not_to_be_visible()
    new.click()
    expect(form.get_by_label('命中值', exact=False)).to_have_value('')
    expect(form.get_by_label('剔除的业务含义')).to_have_value('')
    assert len(posted) == 1
    assert {row['id'] for row in get(api, '/api/m14/rules')['rules']} == before_ids | {actual[0]['id']}
    assert {row['notice_id']: row['is_excluded'] for row in get(api, '/api/m03/notice-list', period='')['items']} == notice_flags


def test_rejected_rule_stays_editable_and_confirmed_rule_retries_only_the_read(server, browser_page, api, disposable):
    page, _ = browser_page
    open_page(page, server, 'rules', '规则配置')
    before = len(get(api, '/api/m14/rules')['rules'])
    value = f'确认后读取核对-{uuid4().hex}'
    outcomes = []

    def fault(route):
        if route.request.method == 'POST':
            response = route.fetch()
            assert response.ok
            outcomes.append(response.json()['ok'])
            route.fulfill(response=response)
        elif outcomes == [False, True]:
            route.fulfill(status=503, json={'message': '规则列表暂不可读'})
        else:
            route.continue_()

    page.route('**/api/m14/rules', fault)
    new = page.get_by_role('button', name='＋ 增加规则', exact=True)
    new.click()
    form = page.get_by_role('dialog', name='新增剔除规则', exact=True)
    values = form.get_by_label('命中值', exact=False)
    submit = form.get_by_role('button', name='新增', exact=True)
    values.fill('｜ |')
    submit.click()
    expect(form.get_by_role('alert')).to_contain_text('没有任何命中值')
    expect(values).to_have_value('｜ |')
    expect(values).to_be_editable()
    assert outcomes == [False] and len(get(api, '/api/m14/rules')['rules']) == before

    values.fill(value)
    submit.click()
    expect(form).not_to_be_visible()
    failure = page.locator('.rules-block').first.get_by_role('alert').filter(has_text='已新增剔除规则。列表更新失败')
    expect(failure).to_be_visible()
    expect(new).to_be_disabled()
    page.unroute('**/api/m14/rules', fault)
    failure.get_by_role('button', name='重新读取', exact=True).click()
    expect(failure).to_have_count(0)
    expect(new).to_be_enabled()
    current = get(api, '/api/m14/rules')['rules']
    assert outcomes == [False, True]
    assert len(current) == before + 1 and sum(row['values'] == value for row in current) == 1
