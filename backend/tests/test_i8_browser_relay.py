"""浏览器会话通道（broker / transport / 工厂 / 连接路由）的离线协议覆盖。

`TAIL-476` 这一层的边界：连接只认**服务端认证身份**，一条请求只走一次往返，
目标/方法/头都在白名单内，会话材料（Cookie / Authorization）永远不出后端，
浏览器模式**结构上**不可能登录、强踢、写产品 Cache，缺连接时必须失败而不是回退 HTTP。

⚠️ 这里只验离线协议与行为；真实 Edge 安装与真实业务取数**不在**本文件证明范围。
"""

from __future__ import annotations

import base64
import json
import re
import threading
import time

import httpx
import pytest

from app.core import app_settings
from app.core.config import Settings, get_settings
from app.mod02_i8 import browser_broker, cookie_store
from app.mod02_i8 import client as clients
from app.mod02_i8.browser_broker import (
    BrowserBroker,
    BrowserRelayUnavailable,
    RELAY_WAIT_SECONDS,
)
from app.mod02_i8.browser_relay import (
    MODE_BROWSER,
    MODE_HTTP,
    BrowserRelayTransport,
    current_scope,
    expected_org_id,
    open_i8_client,
    relay_scope,
)
from app.mod02_i8.browser_session import (
    I8BrowserSessionClient,
    StrictRedirectStopped,
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
)

BASE = "https://i8.example.test"
OWNER = "tester"
DEVICE = "dev-abc123"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    """不读本机配置；把「产品配置的 i8 地址」固定成可比较的值。"""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: {"i8_base_url": BASE})
    monkeypatch.setattr(app_settings, "_CACHE", {"i8_base_url": BASE})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def store(monkeypatch):
    """把进程级 broker 换成新的，测试之间互不串状态。"""
    fresh = BrowserBroker()
    monkeypatch.setattr(browser_broker, "_BROKER", fresh)
    return fresh


@pytest.fixture
def guards(monkeypatch):
    """盯住登录函数与产品 Cookie 缓存：浏览器通道一次都不许碰。"""
    calls = {"login": 0, "cache": []}
    monkeypatch.setattr(clients, "http_login", lambda **kwargs: calls.__setitem__("login", calls["login"] + 1))
    for name in ("load", "save", "clear"):
        monkeypatch.setattr(cookie_store, name, lambda *a, _n=name, **k: calls["cache"].append(_n))
    return calls


def _pump(store: BrowserBroker, *, device: str = DEVICE, owner: str = OWNER, reply=None,
          status: int = 200, body: bytes = b'{"Success":true}', headers=None,
          declared_length: int | None = None):
    """在后台扮演"页面 + 扩展"：取活、回帖。返回线程，便于 join。"""

    def run():
        pending = store.take_pending(owner, device, timeout=5.0)
        assert pending is not None
        # 回帖必须带**这张票自己的**代号（服务端拒绝缺省/0/不匹配）。
        store.complete(owner, device, pending.ticket, status=status,
                       headers=headers or {"content-type": "application/json"}, body=body,
                       declared_length=declared_length if declared_length is not None else len(body),
                       generation=pending.generation)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _send(transport: BrowserRelayTransport, method: str, path: str, *,
          userinfo: str = "", body: bytes | None = None) -> httpx.Response:
    """按方法发一条到指定路径（用于白名单用例）。"""
    client = httpx.Client(transport=transport, base_url=BASE)
    # ⚠️ 原样拼：`//FC/...` 这类伪装写法必须真的到达白名单校验，不能在测试里被"修好"。
    url = f"https://{userinfo}i8.example.test{path}"
    try:
        return client.request(method, url, content=body)
    finally:
        client.close()


def _get(transport: BrowserRelayTransport, url: str = BASE + "/SUP/RichHelp/GetCommonUseList",
         headers: dict | None = None) -> httpx.Response:
    client = httpx.Client(transport=transport, base_url=BASE)
    try:
        return client.get(url, headers=headers or {})
    finally:
        client.close()


# --------------------------------------------------------------- broker：归属与隔离


def test_没有认证身份就不能登记连接(store):
    with pytest.raises(BrowserRelayUnavailable):
        store.connect("", DEVICE, BASE)


def test_缺少页面标识就不能登记连接(store):
    with pytest.raises(BrowserRelayUnavailable):
        store.connect(OWNER, "", BASE)


def test_标签地址不成形时拒绝登记(store):
    with pytest.raises(StrictTargetMismatch):
        store.connect(OWNER, DEVICE, "i8.example.test:8443")


def test_设备之间互不串请求(store):
    store.connect(OWNER, DEVICE, BASE)
    store.connect(OWNER, "dev-other", BASE)
    pending = store.enqueue(OWNER, DEVICE, method="POST", url=BASE + "/x", headers={}, body=b"")

    # 另一个设备取不到这条活；它自己的队列是空的（超时返回 None 是正常态）
    assert store.take_pending(OWNER, "dev-other", timeout=0.0) is None
    # 别人的回帖票也点不动这条请求
    assert store.complete(OWNER, "dev-other", pending.ticket, status=200, headers={}, body=b"", generation=pending.generation) is False
    assert pending.done.is_set() is False


def test_其他账号拿不到别人的连接与队伍(store):
    store.connect(OWNER, DEVICE, BASE)
    assert store.connection_of("someone-else", DEVICE) is None
    with pytest.raises(BrowserRelayUnavailable):
        store.enqueue("someone-else", DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")


def test_账号变化时清掉该账号的连接与队列(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")
    store.clear_owner(OWNER)

    assert store.connection_of(OWNER, DEVICE) is None
    assert pending.stopped == "switched"
    assert pending.done.is_set() is True


# --------------------------------------------------------------- broker：一次性与停止


def test_连接可用时一次往返就能拿到响应(store):
    store.connect(OWNER, DEVICE, BASE)
    thread = _pump(store)
    pending = store.enqueue(OWNER, DEVICE, method="POST", url=BASE + "/x", headers={}, body=b"a=1")
    store.wait(pending)
    thread.join(timeout=5)
    assert pending.status == 200
    assert pending.reply_body == b'{"Success":true}'


def test_同一张票只能回一次(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")
    # 票要先被页面取走（转入 inflight）才认；没取走就回帖 = 对不上
    assert store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"early", generation=pending.generation) is False
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is pending
    assert store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"ok", generation=pending.generation) is True
    assert store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"again", generation=pending.generation) is False


def test_断开连接时挂起请求立即判停且不重试(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")
    store.disconnect(OWNER, DEVICE)
    with pytest.raises(StrictSessionEnded) as caught:
        store.wait(pending, timeout=0.5)
    assert "浏览器连接已断开" in str(caught.value)
    assert pending.status is None       # 没有拿到任何响应 ⇒ 不存在"重发后成功"


def test_等不到回音时判超时而不是重发(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")
    started = time.time()
    with pytest.raises(StrictSessionEnded):
        store.wait(pending, timeout=0.05)
    assert time.time() - started < 2.0
    assert pending.stopped == "timeout"


def test_连接空闲超时后必须重新连接(store, monkeypatch):
    store.connect(OWNER, DEVICE, BASE)
    monkeypatch.setattr(browser_broker, "CONNECTION_IDLE_SECONDS", -1.0)
    assert store.connection_of(OWNER, DEVICE) is None


def test_同键换站点会把旧队列判停(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET", url=BASE + "/x", headers={}, body=b"")
    store.connect(OWNER, DEVICE, "https://other-i8.example.test")
    assert pending.stopped == "replaced"


# --------------------------------------------------------------- transport：只读白名单与脱敏


def test_每条请求都核目标而不是只核初始化地址(store):
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    with pytest.raises(StrictTargetMismatch):
        _get(transport, url="https://evil.example.test/FC/FM/PaymentBill/getList")
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is None


def test_会话材料不会被送去浏览器(store):
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    seen: dict = {}

    def run():
        pending = store.take_pending(OWNER, DEVICE, timeout=5.0)
        seen.update(pending.outbound_payload())
        store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}", generation=pending.generation)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    _get(transport, headers={"Cookie": "ASP.NET_SessionId=secret", "Authorization": "Bearer t",
                             "X-Requested-With": "XMLHttpRequest"})
    thread.join(timeout=5)

    lowered = {key.lower() for key in seen["headers"]}
    assert "cookie" not in lowered
    assert "authorization" not in lowered
    assert "x-requested-with" in lowered          # 取数确实需要的头仍要带上


def test_请求体按字节原样转交(store):
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    seen: dict = {}

    def run():
        pending = store.take_pending(OWNER, DEVICE, timeout=5.0)
        seen["body"] = pending.body
        store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}", generation=pending.generation)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    client = httpx.Client(transport=transport, base_url=BASE)
    try:
        client.post("/FC/FM/PaymentBill/getList", content="year_month=2026-09")
    finally:
        client.close()
    thread.join(timeout=5)
    assert seen["body"] == b"year_month=2026-09"


# --------------------------------------------------- transport：只读端点白名单


@pytest.mark.parametrize("method,path", [
    ("POST", "/SUP/Login/SupLogin"),                    # 登录
    ("POST", "/SUP/Login/KillOnlineUser"),              # 强踢
    ("POST", "/FC/FM/PaymentBill/save"),                # 保存
    ("GET", "/FC/FM/PaymentBill/getList"),              # 方法不对（这条是 POST 口）
    ("POST", "/SUP/RichHelp/GetCommonUseList"),         # 方法不对（这条是 GET 口）
    ("DELETE", "/FC/FM/PaymentBill/getList"),
    ("POST", "/FC/FM/PaymentBill/getList/"),            # 尾斜杠
    ("POST", "/FC/FM/PaymentBill/%2e%2e/getInfo"),      # 编码后的 ..
    ("POST", "//FC/FM/PaymentBill/getList"),            # 双斜杠
    ("POST", "/sup/customServer/GetList"),              # 大小写不同（真实口是小写 getList）
])
def test_不认识的端点与伪装路径一律不发出去(store, method, path):
    """白名单是"逐条允许"，不是"POST 就当只读"：登录/踢人/保存/伪装写法全部当场停。"""
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    with pytest.raises(StrictTargetMismatch):
        _send(transport, method, path)
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is None   # ⛔ 一个字节都没出去


def test_白名单里的读接口可以发出去(store):
    """对照组：白名单内的真实取数口必须还能走（否则通道等于不可用）。"""
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    _pump(store, body=b'{"Success":true}')
    response = _send(transport, "POST", "/FC/FM/PaymentBill/getList")
    assert response.status_code == 200


def test_带账号信息的地址不认(store):
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    with pytest.raises(StrictTargetMismatch):
        _send(transport, "POST", "/FC/FM/PaymentBill/getList", userinfo="u:p@")
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is None


# --------------------------------------------------------------- transport：响应完整性


def test_跳转响应一律停止(store):
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    _pump(store, status=302, body=b"", headers={"location": "https://evil.example.test/x"})
    with pytest.raises(StrictRedirectStopped):
        _get(transport)


def test_回帖长度对不上时停止(store):
    """浏览器自报的字节数与实际回帖不一致 ⇒ 当作传输被截断，停止（不解析半截响应）。"""
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)

    def run():
        pending = store.take_pending(OWNER, DEVICE, timeout=5.0)
        store.complete(OWNER, DEVICE, pending.ticket, status=200,
                       headers={"content-type": "application/json"},
                       body=b'{"truncated":', declared_length=4096, generation=pending.generation)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    with pytest.raises(StrictSessionUnavailable) as caught:
        _get(transport)
    thread.join(timeout=5)
    assert "长度对不上" in str(caught.value)


def test_二进制响应按字节完整回到调用方(store):
    """报表导出一类是二进制（xlsx）；通道必须原样传回，不能被当成文本截断。"""
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)
    payload = b"PK\x03\x04" + bytes(range(256)) * 4
    _pump(store, body=payload, headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
    client = httpx.Client(transport=transport, base_url=BASE)
    try:
        response = client.post("/reportcenter/reportExport/export", content="{}")
    finally:
        client.close()
    assert response.content == payload
    assert base64.b64encode(response.content)  # 长度与内容都无损


# --------------------------------------------------- broker：连接代号（generation）


def test_重连后代号只增不减(store):
    first = store.connect(OWNER, DEVICE, BASE)
    second = store.connect(OWNER, DEVICE, BASE)
    assert second.generation > first.generation


def test_过代回帖不会落到新连接上(store):
    """断开重连后，旧连接那次请求的回帖必须被丢掉（否则会拿旧身份的结果冒充新连接）。"""
    old = store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="POST",
                            url=BASE + "/FC/FM/PaymentBill/getList", headers={}, body=b"")
    store.connect(OWNER, DEVICE, BASE)          # 同键重连 ⇒ 新代号；旧队列被判停
    accepted = store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}",
                              generation=old.generation)
    assert accepted is False
    assert pending.stopped == "replaced"


def test_回帖代号与票不符时丢弃(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="POST",
                            url=BASE + "/FC/FM/PaymentBill/getList", headers={}, body=b"")
    accepted = store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}",
                              generation=pending.generation + 1)
    assert accepted is False


def test_出站消息带代号供页面回传(store):
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET",
                            url=BASE + "/SUP/RichHelp/GetCommonUseList", headers={}, body=b"")
    payload = pending.outbound_payload()
    assert payload["generation"] == pending.generation


# --------------------------------------------------------------- 工厂：模式与回退边界


def test_默认模式仍是产品原有客户端(guards):
    client = open_i8_client(allow_kick=True, owner=OWNER)
    assert type(client) is clients.I8Client
    assert client._allow_kick is True      # noqa: SLF001 — 显式核"原策略参数照旧传下去"


def test_浏览器模式缺连接时当场失败不回落登录(guards):
    with relay_scope(MODE_BROWSER, DEVICE):
        with pytest.raises(BrowserRelayUnavailable):
            open_i8_client(allow_kick=True, owner=OWNER)
    assert guards["login"] == 0
    assert guards["cache"] == []


def test_浏览器模式不登录不清缓存(guards, store):
    store.connect(OWNER, DEVICE, BASE)
    with relay_scope(MODE_BROWSER, DEVICE):
        client = open_i8_client(allow_kick=True, owner=OWNER)
        assert isinstance(client, I8BrowserSessionClient)

        def run():
            pending = store.take_pending(OWNER, DEVICE, timeout=5.0)
            store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b'{"Success":true}', generation=pending.generation)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        result = client.get_json(BASE + "/SUP/RichHelp/GetCommonUseList")
        thread.join(timeout=5)

        assert result == {"Success": True}
        assert guards["login"] == 0
        assert guards["cache"] == []


def test_连接站点与配置不一致时停止(guards, store):
    store.connect(OWNER, DEVICE, "https://other-i8.example.test")
    with relay_scope(MODE_BROWSER, DEVICE):
        with pytest.raises(StrictTargetMismatch):
            open_i8_client(owner=OWNER)


def test_作用域退出后回到直连(guards):
    with relay_scope(MODE_BROWSER, DEVICE):
        assert current_scope() == (MODE_BROWSER, DEVICE)
    assert current_scope() == (MODE_HTTP, "")
    assert type(open_i8_client()) is clients.I8Client


def test_组织范围取自既有取数表单(guards):
    """组织 id 只有一个来源：真实请求表单；不许另写一份常量。"""
    from app.mod02_i8.sources import WH_PARAMS

    assert expected_org_id() == "3700000000000014"
    assert expected_org_id() in str(WH_PARAMS["orgQuery"])


# --------------------------------------------------------------- 连接路由：工作台身份与站点


class _Session:
    """把 `current_name()` 固定成指定身份；空串表示未登录。"""

    def __init__(self, monkeypatch, name: str) -> None:
        from app.core import session as session_module

        monkeypatch.setattr(session_module, "current_name", lambda: name)


@pytest.fixture
def route(monkeypatch, store):
    """连接路由的最小可用环境：已登录、已配置站点、已绑定 i8 账号。"""
    from app.core import config as config_module
    from app.core import identity as identity_module

    _Session(monkeypatch, OWNER)
    monkeypatch.setattr(config_module, "i8_base_of", lambda settings: BASE)
    monkeypatch.setattr(identity_module, "current_i8_credentials", lambda: ("i8-tester", "pw"))
    return store


def _connect(origin: str = BASE, device: str = DEVICE):
    from app.mod02_i8.router import browser_connect
    from app.mod02_i8.schemas import BrowserConnectRequest

    return browser_connect(BrowserConnectRequest(device_id=device, i8_origin=origin))


def test_连接时站点不符即拒绝(route):
    with pytest.raises(StrictTargetMismatch):
        _connect(origin="https://other-i8.example.test")
    assert route.connection_of(OWNER, DEVICE) is None


def test_工作台账号未绑定i8时拒绝连接(route, monkeypatch):
    from app.core import identity as identity_module

    monkeypatch.setattr(identity_module, "current_i8_credentials", lambda: ("", ""))
    with pytest.raises(BrowserRelayUnavailable, match="绑定 i8 账号"):
        _connect()
    assert route.connection_of(OWNER, DEVICE) is None


def test_只提供站点即可登记连接并断开(route):
    from app.mod02_i8.router import browser_disconnect, browser_state

    state = _connect()
    assert state.connected is True
    assert state.mode == MODE_BROWSER
    assert state.i8_user == "i8-tester"                 # 工作台绑定账号
    assert state.expected_org == "3700000000000014"      # 内部机构号（取数表单里的那个）
    assert state.generation == 1
    assert route.connection_of(OWNER, DEVICE) is not None

    after = browser_disconnect(DEVICE)
    assert after.connected is False
    assert after.mode == MODE_HTTP
    assert browser_state(DEVICE).connected is False


def test_同一身份的不同设备各自独立连接(route):
    _connect(device=DEVICE)
    _connect(device="dev-other")
    assert route.connection_of(OWNER, DEVICE) is not None
    assert route.connection_of(OWNER, "dev-other") is not None
    route.disconnect(OWNER, DEVICE)
    assert route.connection_of(OWNER, "dev-other") is not None


def test_未登录时不允许连接(monkeypatch, store):
    from app.core import config as config_module
    from app.core import identity as identity_module

    _Session(monkeypatch, "")
    monkeypatch.setattr(config_module, "i8_base_of", lambda settings: BASE)
    monkeypatch.setattr(identity_module, "current_i8_credentials", lambda: ("i8-tester", "pw"))
    with pytest.raises(BrowserRelayUnavailable):
        _connect()


def test_回帖不接受别人的票(route):
    from app.mod02_i8.router import browser_complete
    from app.mod02_i8.schemas import BrowserCompleteRequest

    _connect()
    result = browser_complete(BrowserCompleteRequest(
        device_id=DEVICE, ticket="not-a-real-ticket", status=200, headers={}, body_b64=""),
    )
    assert result.accepted is False
    assert "作废" in result.message


def test_回帖的响应体解不开时明确忽略(route):
    from app.mod02_i8.router import browser_complete
    from app.mod02_i8.schemas import BrowserCompleteRequest

    _connect()
    result = browser_complete(BrowserCompleteRequest(
        device_id=DEVICE, ticket="whatever", status=200, headers={}, body_b64="***not base64***",
    ))
    assert result.accepted is False
    assert "无法读取" in result.message


@pytest.mark.parametrize("wait", [RELAY_WAIT_SECONDS])
def test_超时常量与既有HTTP超时同一口径(wait):
    """不自创业务预算：通道等待对齐 `httpx.Timeout(30.0, connect=10.0)`。"""
    assert wait == 30.0


# --------------------------------------------- 其它日常读取口：不许悄悄绕回旧客户端


def test_仓库名单在浏览器模式缺连接时当场失败(guards, monkeypatch):
    """`get_warehouse_rows()` 自建客户端时也必须走工厂。

    ⛔ 若这里仍是裸 `I8Client(...)`，选了浏览器模式却会**静默去登录/顶号** ——
       那正是本票要禁止的"悄悄回退"。
    """
    from app.mod02_i8 import router as m02

    _Session(monkeypatch, OWNER)          # 已登录、但没有浏览器连接
    monkeypatch.setattr(m02.wh_cache, "save", lambda *a, **k: None)
    with relay_scope(MODE_BROWSER, DEVICE):
        with pytest.raises(BrowserRelayUnavailable) as caught:
            m02.get_warehouse_rows()()
    assert "连接不在" in str(caught.value)   # 停因是"没连接"，不是别的
    assert guards["login"] == 0
    assert guards["cache"] == []


def test_常用项目在浏览器模式缺连接时当场失败(guards, monkeypatch):
    from app.mod02_i8 import router as m02

    _Session(monkeypatch, OWNER)
    with relay_scope(MODE_BROWSER, DEVICE):
        with pytest.raises(BrowserRelayUnavailable) as caught:
            m02.get_common_project_rows()()
    assert "连接不在" in str(caught.value)
    assert guards["login"] == 0
    assert guards["cache"] == []


def test_仓库名单在浏览器模式有连接时经通道取数且不登录(guards, store, monkeypatch):
    from app.mod02_i8 import router as m02

    saved: list = []
    monkeypatch.setattr(m02.wh_cache, "save", lambda rows, **k: saved.append(rows))

    _Session(monkeypatch, OWNER)
    store.connect(OWNER, DEVICE, BASE)
    payload = {"Success": True, "Record": [{"Whname": "一号仓", "PhidPc_EXName": "甲项目", "Nullify": "0"}]}
    with relay_scope(MODE_BROWSER, DEVICE):
        _pump(store, body=json.dumps(payload).encode("utf-8"))
        rows = m02.get_warehouse_rows()()

    assert rows == [{"warehouse_name": "一号仓", "owner_full_name": "甲项目"}]
    assert saved and saved[0] == rows
    assert guards["login"] == 0
    assert guards["cache"] == []


def test_日常直连模式仍用产品原有客户端(guards, monkeypatch):
    """默认 `http` 路径的产品行为不变：自建客户端仍是原类。"""
    from app.mod02_i8 import router as m02

    captured = {}

    def fake_fetch(self):
        captured["client"] = self._client
        return []

    monkeypatch.setattr(m02.WarehouseSource, "fetch", fake_fetch)
    monkeypatch.setattr(m02.wh_cache, "save", lambda *a, **k: None)
    assert m02.get_warehouse_rows()() == []
    assert type(captured["client"]) is clients.I8Client


# --------------------------- broker：幂等、代号、票与超时预算（第 6 轮 closure 项）


def test_断开一条不存在的连接是幂等的(store):
    """⛔ 复现过的崩溃：`disconnect()` 先 pop 了队列，`_fail_queue()` 又对 None 调 `clear()`
    ⇒ `AttributeError: 'NoneType' object has no attribute 'clear'`。

    断开一条本来就不在的连接（页面已关、重复点断开、空闲清理之后）必须是**无异常**的 False。
    """
    assert store.disconnect(OWNER, DEVICE) is False
    assert store.disconnect(OWNER, DEVICE) is False        # 再来一次也不许抛

    store.connect(OWNER, DEVICE, BASE)
    assert store.disconnect(OWNER, DEVICE) is True
    assert store.disconnect(OWNER, DEVICE) is False


def test_断开后重连的代号不会回到1(store):
    """代号必须由**进程内发号器**给。

    ⛔ 早先写成"当前连接代号 + 1"：断开时连接已摘掉 ⇒ 重连又从 1 开始，
       旧连接迟到的回帖会撞上新连接的代号并被当成有效。
    """
    first = store.connect(OWNER, DEVICE, BASE)
    store.disconnect(OWNER, DEVICE)
    second = store.connect(OWNER, DEVICE, BASE)
    assert second.generation > first.generation
    assert second.generation != 1


@pytest.mark.parametrize("generation", [None, 0, -1, "x"])
def test_回帖代号缺省或非正数一律拒绝(store, generation):
    """⛔ 早先写成 `if generation and generation != item.generation`：传 0 就把校验整个绕过。"""
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="POST",
                            url=BASE + "/FC/FM/PaymentBill/getList", headers={}, body=b"")
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is pending
    accepted = store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}",
                              generation=generation)
    assert accepted is False
    # 不是"收到回帖"：请求被判停（原因独立于"连接被替换"），状态码必须还是空的。
    assert pending.status is None
    assert pending.stopped == "rejected"
    with pytest.raises(StrictSessionEnded) as caught:
        store.wait(pending, timeout=0.1)
    assert "对不上这次连接" in str(caught.value)


def test_票是不透明的随机串(store):
    """票只是一次性令牌：不含时间戳/序号/对象地址，也不含身份或设备标识。"""
    store.connect(OWNER, DEVICE, BASE)
    first = store.enqueue(OWNER, DEVICE, method="GET",
                          url=BASE + "/SUP/RichHelp/GetCommonUseList", headers={}, body=b"")
    second = store.enqueue(OWNER, DEVICE, method="GET",
                           url=BASE + "/SUP/RichHelp/GetCommonUseList", headers={}, body=b"")

    assert first.ticket != second.ticket
    assert re.fullmatch(r"[A-Za-z0-9_-]{16,}", first.ticket) is not None
    for leak in (OWNER, DEVICE, "i8.example.test"):
        assert leak not in first.ticket


def test_超时预算按每条请求自己的读超时走(store):
    """合同列表 `post_json(..., timeout=200)` 的预算要一路传到扩展的 `AbortController`。

    ⛔ 若这里被压成全局 30s，一条 200s 的正常列表请求会被凭空判成"浏览器没回音"。
    """
    store.connect(OWNER, DEVICE, BASE)
    transport = BrowserRelayTransport(owner=OWNER, device=DEVICE, origin=BASE)

    def run():
        client = httpx.Client(transport=transport, base_url=BASE,
                              timeout=httpx.Timeout(200.0, connect=10.0))
        try:
            client.post("/FC/FM/PaymentBill/getList", content=b"a=1")
        finally:
            client.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    pending = store.take_pending(OWNER, DEVICE, timeout=5.0)
    assert pending is not None
    assert pending.timeout_seconds == 200.0
    assert pending.outbound_payload()["timeout_ms"] == 200_000
    store.complete(OWNER, DEVICE, pending.ticket, status=200,
                   headers={"content-type": "application/json"},
                   body=b'{"Success":true}', generation=pending.generation)
    thread.join(timeout=5)


def test_空闲清理不会误杀在途请求(store, monkeypatch):
    """120s 空闲清理只清**真的闲着**的连接：排队中或已在浏览器里跑着都不算空闲。"""
    store.connect(OWNER, DEVICE, BASE)
    pending = store.enqueue(OWNER, DEVICE, method="GET",
                            url=BASE + "/SUP/RichHelp/GetCommonUseList", headers={}, body=b"")
    monkeypatch.setattr(browser_broker, "CONNECTION_IDLE_SECONDS", -1.0)

    assert store.connection_of(OWNER, DEVICE) is not None     # 还在排队 ⇒ 不算空闲
    assert store.take_pending(OWNER, DEVICE, timeout=0.0) is pending
    assert store.connection_of(OWNER, DEVICE) is not None     # 已在执行 ⇒ 仍不算空闲

    store.complete(OWNER, DEVICE, pending.ticket, status=200, headers={}, body=b"{}",
                   generation=pending.generation)
    assert store.connection_of(OWNER, DEVICE) is None         # 真的闲下来了才清
