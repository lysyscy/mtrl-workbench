"""浏览器会话通道在真实页面上的行为（`TAIL-476` 前端部分）。

这些用例只检查**前端自己的判断**，不安装真实扩展、不接触真实 i8：

* 通道停了而服务端还留着连接 ⇒ 页面必须显示未连接，并且抓取入口当场拦住；
* 同一账号登录失效后，「取数方式」仍停在用户选过的浏览器方式；
* 选了浏览器方式但连接不在 ⇒ 确认后尝试连接，失败时不发抓取请求或回退直连；
* 主动选直连 ⇒ 发送原业务范围，遇到在线冲突须确认后才提交一次性令牌；
* i8 执行记录首次读取/失败/重试：占位保持区域、不报零、失败后可重读。

夹具与登录流程复用 `test_preview.py`（同一个已登记的预览，由主控在本机运行）。
"""

from datetime import datetime, timezone
import json
import re

from playwright.sync_api import expect

from test_preview import browser_page, login, server  # noqa: F401 (fixtures)

CONNECTED_STATE = {
    'connected': True,
    'mode': 'browser',
    'origin': 'https://i8.example.test',
    'i8_user': 'tester001',
    'expected_org': '3700000000000014',
    'expected_org_code': '109',
    'expected_org_name': '第四工程公司',
    'generation': 3,
    'message': '已连接',
}

# 有任务，但缺少 closure 要求的 `timeout_ms`：协议形状对不上，页面必须停下而不是空转。
MALFORMED_REQUEST = {
    'ticket': 't-1',
    'generation': 3,
    'method': 'GET',
    'url': 'https://i8.example.test/x',
    'headers': {},
    'body_b64': '',
}


def json_route(payload, status=200):
    body = json.dumps(payload)
    return lambda route: route.fulfill(status=status, content_type='application/json', body=body)


def hold_and_record(bucket, status=500):
    """记下请求内容并回一个中立错误，避免把浏览器请求挂在半空。"""

    def handler(route):
        bucket.append(route.request.post_data_json)
        route.fulfill(status=status, content_type='application/json', body='{"ok": false}')

    return handler


def mode_keys(page):
    """本页 `sessionStorage` 里记下的「取数方式」（按账号分开存）。"""
    return page.evaluate(
        "Object.entries(sessionStorage).filter(([key]) => key.indexOf('mtrl.i8.relay.mode.') === 0)"
    )


def open_i8(page):
    page.locator('a[href="/preview/i8"]').click()
    expect(page.locator('#page-title')).to_have_text('i8 接入层')


def select_mode(page, label):
    item = page.locator('.i8-relay .ant-segmented-item').filter(has_text=label)
    item.click()
    expect(item).to_have_class(re.compile('ant-segmented-item-selected'))


def choose_browser_mode(page):
    open_i8(page)
    select_mode(page, '工作台直连')
    select_mode(page, '浏览器已有会话')


def simulated_bridge(page, connects):
    """Mock only relay-control messages; no business response or external i8 request."""
    page.add_init_script("""(() => {
      window.chrome ??= {};
      Object.defineProperty(window.chrome, 'runtime', {configurable:true, value:{
        sendMessage(_id, message, reply) {
          if (message.type === 'i8-relay:identity') reply({ok:true,origin:'https://i8.example.test',sessionReady:true});
          else reply({ok:true,generation:message.generation});
        }
      }});
    })();""")

    def connect(route):
        connects.append(route.request.post_data_json)
        route.fulfill(content_type='application/json', body=json.dumps({**CONNECTED_STATE, 'generation': len(connects)}))

    page.route('**/api/m02/browser/connect', connect)
    page.route('**/api/m02/browser/disconnect*', json_route({**CONNECTED_STATE, 'connected': False, 'mode': 'http'}))


def test_relay_stop_wins_over_server_side_connected(server, browser_page):
    """通道自己停了，服务端仍回 connected=true ⇒ 页面必须判为未连接，且不自动恢复。"""
    page, _ = browser_page
    connects = []
    simulated_bridge(page, connects)
    completed = []
    page.route('**/api/m02/browser/state*', json_route(CONNECTED_STATE))
    page.route('**/api/m02/browser/pending*', json_route({'request': MALFORMED_REQUEST}))
    page.route('**/api/m02/browser/complete', hold_and_record(completed))
    login(page, server)
    choose_browser_mode(page)
    page.get_by_role('button', name='连接浏览器会话', exact=True).click()

    relay = page.locator('.i8-relay')
    # 以本页实况为准：未连接，并如实说明停了的原因。
    expect(relay.get_by_text('未连接', exact=True)).to_be_visible(timeout=30000)
    expect(relay.get_by_role('status').filter(has_text='协议不一致')).to_be_visible()
    expect(relay.get_by_text('已连接', exact=True)).to_have_count(0)
    page.wait_for_timeout(500)
    assert completed == [], '协议对不上时不应向服务端回帖'

    # 重新进入页面也不会把「已连接」顶回来（服务端仍返回 connected=true）。
    page.reload()
    expect(page.locator('.i8-relay').get_by_text('未连接', exact=True)).to_be_visible(timeout=30000)
    assert len(connects) == 1, '协议错误不得被刷新后的自动恢复掩盖'


def test_reload_recovers_selected_browser_but_explicit_disconnect_stays_off(server, browser_page):
    page, _ = browser_page
    connects = []
    simulated_bridge(page, connects)
    page.route('**/api/m02/browser/state*', json_route({**CONNECTED_STATE, 'connected': False}))
    page.route('**/api/m02/browser/pending*', json_route({'request': None}))
    login(page, server)
    choose_browser_mode(page)
    page.get_by_role('button', name='连接浏览器会话', exact=True).click()
    expect(page.locator('.i8-relay').get_by_text('已连接', exact=True)).to_be_visible()
    assert len(connects) == 1
    page.reload()
    expect(page.locator('.i8-relay').get_by_text('已连接', exact=True)).to_be_visible()
    assert len(connects) == 2
    assert connects[0]['device_id'] != connects[1]['device_id'], '刷新恢复仍使用新文档连接'
    page.get_by_role('button', name='断开', exact=True).click()
    expect(page.locator('.i8-relay').get_by_text(re.compile('已断开浏览器连接，刷新页面也不会自动重连'))).to_be_visible()
    with page.expect_response('**/api/m02/browser/state*'):
        page.reload()
    expect(page.locator('.i8-relay').get_by_text('未连接', exact=True)).to_be_visible()
    assert len(connects) == 2


def test_browser_mode_survives_session_loss_for_the_same_account(server, browser_page):
    """同账号登录失效/退出后，取数方式仍是浏览器 —— 不许默默改回直连。"""
    page, _ = browser_page
    login(page, server)
    choose_browser_mode(page)
    keys = mode_keys(page)
    assert keys, '选了浏览器方式后应按账号记下一项'
    assert all(value == 'browser' for _, value in keys), keys
    account_key = keys[0][0]

    # 账号事件（身份失效/退出）会换掉本页的连接标识，但不动用户选过的模式。
    page.evaluate("window.dispatchEvent(new Event('session-lost'))")
    expect(page.get_by_role('alert').filter(has_text='登录已失效，当前只读')).to_be_visible()
    keys = mode_keys(page)
    assert [key for key, value in keys if key == account_key and value == 'browser'], keys

    # 同一账号重新进入页面后仍是浏览器方式。
    page.reload()
    expect(page.locator('#page-title')).to_have_text('i8 接入层', timeout=30000)
    expect(page.locator('.i8-relay .ant-segmented-item').filter(has_text='浏览器已有会话')).to_have_class(
        re.compile('ant-segmented-item-selected')
    )


def test_browser_mode_without_connection_sends_nothing(server, browser_page):
    """服务端仍有旧连接时，本页连接失败也不能提交抓取或回退直连。"""
    page, _ = browser_page
    page.route('**/api/m02/browser/state*', json_route(CONNECTED_STATE))
    page.route('**/api/m02/browser/pending*', json_route({'request': MALFORMED_REQUEST}))
    login(page, server)
    choose_browser_mode(page)
    # 通道停在本页（服务端连接记录还在）。
    expect(page.locator('.i8-relay').get_by_text('未连接', exact=True)).to_be_visible(timeout=30000)

    me = page.request.get(server + '/api/m15/users').json()['me']
    page.route('**/api/m02/config*', json_route({
        'ready': True, 'account': me['account'], 'i8_user': 'tester001', 'message': '',
    }))
    fetched = []
    page.route(re.compile(r'/api/m03/notices/(fetch|fetch-jobs)$'), hold_and_record(fetched))
    page.locator('a[href="/preview/notices"]').click()
    # 本页工具栏在列表读完之后才可用，先等它，避免把「列表未读完」当成「连接被拦」。
    fetch = page.get_by_role('button', name='按月抓取 i8')
    expect(fetch).to_be_enabled(timeout=30000)
    fetch.click()

    dialog = page.get_by_role('dialog', name='抓取 i8 付款通知书', exact=True)
    expect(dialog.locator('.i8-fetch-mode')).to_contain_text('浏览器已有会话')
    submit = dialog.get_by_role('button', name='确认抓取')
    expect(submit).to_be_enabled()
    assert fetched == []
    with page.expect_request('**/api/m02/browser/state*'):
        submit.click()
    expect(dialog.get_by_role('status').filter(has_text='没有检测到浏览器扩展')).to_be_visible()
    expect(submit).to_have_count(0)
    assert fetched == []
    dialog.get_by_role('button', name='取消等待', exact=True).click()
    expect(submit).to_be_enabled()
    expect(dialog.locator('.i8-fetch-mode')).to_contain_text('浏览器已有会话')
    assert fetched == [], '浏览器连接不在时不应发出抓取请求'


def test_http_mode_submit_keeps_scope_and_requires_kick_confirmation(server, browser_page):
    """主动直连只在确认下线后带令牌重发同账号、同月份的抓取。"""
    page, _ = browser_page
    page.clock.set_fixed_time(datetime(2026, 11, 15, 12, tzinfo=timezone.utc))
    login(page, server)
    open_i8(page)
    select_mode(page, '工作台直连')
    me = page.request.get(server + '/api/m15/users').json()['me']
    page.route('**/api/m02/config*', json_route({
        'ready': True, 'account': me['account'], 'i8_user': 'tester001', 'message': '',
    }))
    fetched = []
    jobs = '**/api/m03/notices/fetch-jobs'
    month = '2026-11'
    time = '2026-11-15T12:00:00Z'
    job = {
        'id': 1971, 'account': me['account'], 'year_month': month, 'status': 'running',
        'stage': 'fetching_notices', 'stage_label': '正在抓取通知书', 'error_message': '',
        'created_at': time, 'updated_at': time, 'completed_at': None, 'acknowledged_at': None, 'result': None,
    }
    result = {
        'year_month': month, 'notices_saved': True, 'fetched': 1, 'saved': 1, 'upserted': 1, 'created': 1,
        'updated': 0, 'excluded': 0, 'ignored_count': 0, 'unresolved': 0, 'ignored': [], 'auto_linked': 0,
        'auto_linked_items': [], 'manual_review': 0, 'manual_review_items': [], 'payable_source_failed': False,
        'payable_source_error': '', 'fetch_error': '', 'matching_error': '',
    }

    def fetch_job(route):
        fetched.append(route.request.post_data_json)
        if len(fetched) == 1:
            route.fulfill(status=409, json={
                'ok': False, 'code': 'i8_online_conflict', 'message': 'i8 账号已有在线会话。', 'kick_token': 'synthetic-kick',
            })
        else:
            route.fulfill(status=202, json=job)

    page.route(jobs, fetch_job)
    page.route(f'{jobs}/{job["id"]}', json_route({
        **job, 'status': 'completed', 'stage': 'completed', 'stage_label': '抓取完成',
        'updated_at': '2026-11-15T12:00:01Z', 'completed_at': '2026-11-15T12:00:01Z', 'result': result,
    }))
    page.locator('a[href="/preview/notices"]').click()
    page.get_by_role('button', name='按月抓取 i8').click()
    expect(page.locator('.i8-fetch-mode')).to_contain_text('工作台直连')
    submit = page.get_by_role('button', name='确认抓取')
    expect(submit).to_be_enabled(timeout=20000)
    submit.click()
    confirm = page.get_by_role('button', name='让现有会话下线并继续', exact=True)
    expect(confirm).to_be_enabled()
    original = {'session_mode': 'http', 'expected_account': me['account'], 'year_month': month}
    assert fetched == [original]
    confirm.click()
    receipt = page.get_by_role('dialog', name='付款通知书抓取完成', exact=True)
    saved = receipt.locator('.i8-receipt-count').filter(has=page.get_by_text('已保存', exact=True))
    expect(saved.locator('dd')).to_have_text('1 条', timeout=20000)
    assert fetched == [original, {**original, 'kick_token': 'synthetic-kick'}]


def test_i8_records_first_read_failure_and_retry(server, browser_page):
    """执行记录：首次读取不报零、失败就地报告并保持区域，重试后可读。"""
    page, _ = browser_page
    held = []
    page.route('**/api/m02/fetch/records*', lambda route: held.append(route))
    login(page, server)
    open_i8(page)

    lane = page.locator('.i8-read-status')
    expect(lane).to_have_attribute('data-read-phase', 'reading', timeout=20000)
    assert held, '第一次执行记录读取没有被拦住'
    reserve = page.locator('.i8-read-reserve')
    expect(reserve.locator('.read-placeholder')).to_have_count(1)
    # 还没读到：既不说 0 条，也不说「还没有执行记录」。
    expect(page.get_by_text('还没有执行记录。')).to_have_count(0)
    before = reserve.bounding_box()

    for route in held:
        route.fulfill(status=503, content_type='application/json', body='{"detail": "执行记录读取暂时失败"}')
    page.unroute('**/api/m02/fetch/records*')

    failure = lane.locator('.notice')
    expect(failure).to_have_count(1)
    expect(failure).to_have_attribute('role', 'alert')
    expect(failure.get_by_role('button', name='重试读取')).to_be_visible()
    expect(page.locator('.i8-read-reserve .read-placeholder-quiet')).to_have_count(1)
    expect(page.get_by_text('还没有执行记录。')).to_have_count(0)
    after = page.locator('.i8-read-reserve').bounding_box()
    alert = failure.bounding_box()
    assert after['y'] >= alert['y'] + alert['height'] - 1, (alert, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)

    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.i8-latest')).to_be_visible(timeout=30000)
    expect(page.locator('.i8-read-reserve')).to_have_count(0)
