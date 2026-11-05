"""浏览器会话通道在真实页面上的行为（`TAIL-476` 前端部分）。

这些用例只检查**前端自己的判断**，不安装真实扩展、不接触真实 i8：

* 通道停了而服务端还留着连接 ⇒ 页面必须显示未连接，并且抓取入口当场拦住；
* 同一账号登录失效后，「取数方式」仍停在用户选过的浏览器方式；
* 选了浏览器方式但连接不在 ⇒ 提交按钮不可用、一个请求都不发；
* 直连方式 ⇒ 仍按原来的载荷走（`session_mode=http` + 原有强踢授权）；
* i8 执行记录首次读取/失败/重试：占位保持区域、不报零、失败后可重读。

夹具与登录流程复用 `test_preview.py`（同一个已登记的预览，由主控在本机运行）。
"""

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


def record_and_accept(bucket, payload, status=200):
    """记下请求内容并正常回应，避免用例结束时还挂着未完成的请求。"""

    def handler(route):
        bucket.append(route.request.post_data_json)
        route.fulfill(status=status, content_type='application/json', body=json.dumps(payload))

    return handler


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


def choose_browser_mode(page):
    open_i8(page)
    item = page.locator('.i8-relay .ant-segmented-item').filter(has_text='浏览器已有会话')
    item.click()
    expect(item).to_have_class(re.compile('ant-segmented-item-selected'))


def test_relay_stop_wins_over_server_side_connected(server, browser_page):
    """通道自己停了，服务端仍回 connected=true ⇒ 页面必须判为未连接，且不自动恢复。"""
    page, _ = browser_page
    completed = []
    page.route('**/api/m02/browser/state*', json_route(CONNECTED_STATE))
    page.route('**/api/m02/browser/pending*', json_route({'request': MALFORMED_REQUEST}))
    page.route('**/api/m02/browser/complete', hold_and_record(completed))
    login(page, server)
    choose_browser_mode(page)

    relay = page.locator('.i8-relay')
    # 以本页实况为准：未连接，并如实说明停了的原因。
    expect(relay.get_by_text('未连接', exact=True)).to_be_visible(timeout=30000)
    expect(relay.get_by_role('status').filter(has_text='协议对不上')).to_be_visible()
    # 服务端那条连接还在，页面必须承认这个差异，而不是显示「已连接」。
    expect(relay.get_by_text(re.compile('工作台那边还留着这条连接记录'))).to_be_visible()
    expect(relay.get_by_text('已连接', exact=True)).to_have_count(0)
    page.wait_for_timeout(500)
    assert completed == [], '协议对不上时不应向服务端回帖'

    # 重新进入页面也不会把「已连接」顶回来（服务端仍返回 connected=true）。
    page.reload()
    expect(page.locator('.i8-relay').get_by_text('未连接', exact=True)).to_be_visible(timeout=30000)


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
    """选了浏览器方式但连接不在（服务端仍 connected，本页已停）⇒ 按钮不可用、零请求。"""
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
    page.route('**/api/m03/notices/fetch', hold_and_record(fetched))
    page.locator('a[href="/preview/notices"]').click()
    # 本页工具栏在列表读完之后才可用，先等它，避免把「列表未读完」当成「连接被拦」。
    fetch = page.get_by_role('button', name='按月抓取 i8')
    expect(fetch).to_be_enabled(timeout=30000)
    fetch.click()

    expect(page.get_by_role('alert').filter(has_text='本次不会改用工作台直连')).to_be_visible(timeout=20000)
    expect(page.locator('.i8-fetch-mode')).to_contain_text('浏览器已有会话')
    submit = page.get_by_role('button', name='确认抓取')
    expect(submit).to_be_disabled()
    submit.click(force=True)
    page.wait_for_timeout(500)
    assert fetched == [], '浏览器连接不在时不应发出抓取请求'


def test_http_mode_submit_keeps_the_original_payload(server, browser_page):
    """直连方式下提交的载荷与改动前一致：`session_mode=http` + 原有强踢授权。"""
    page, _ = browser_page
    login(page, server)
    me = page.request.get(server + '/api/m15/users').json()['me']
    page.route('**/api/m02/config*', json_route({
        'ready': True, 'account': me['account'], 'i8_user': 'tester001', 'message': '',
    }))
    fetched = []
    page.route('**/api/m03/notices/fetch', record_and_accept(fetched, {
        'fetched': 1, 'upserted': 1, 'ignored': [], 'year_month': '2026-11',
    }))
    page.locator('a[href="/preview/notices"]').click()
    page.get_by_role('button', name='按月抓取 i8').click()
    expect(page.locator('.i8-fetch-mode')).to_contain_text('工作台直连')
    submit = page.get_by_role('button', name='确认抓取')
    expect(submit).to_be_enabled(timeout=20000)
    submit.click()
    expect(page.get_by_text(re.compile('抓取 1 条'))).to_be_visible(timeout=20000)

    assert len(fetched) == 1, fetched
    body = fetched[0]
    assert body['session_mode'] == 'http', body
    assert body['allow_kick'] is True, body
    assert body['expected_account'] == me['account'], body
    assert 'device_id' not in body, body


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
    assert abs(after['y'] - before['y']) < 1, (before, after)
    assert abs(after['height'] - before['height']) < 1, (before, after)

    failure.get_by_role('button', name='重试读取').click()
    expect(page.locator('.i8-latest')).to_be_visible(timeout=30000)
    expect(page.locator('.i8-read-reserve')).to_have_count(0)
