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
