"""严格「仅复用已有会话」模式的离线行为覆盖（不连 i8、不读本机配置、不连库）。

守的是 `TAIL-476` / 规格里那条边界：**已有会话缺失、失效、或目标不对 ⇒ 立刻停止**；
停止前后都不许登录、不许强踢、不许读写产品的 Cookie 缓存、不许把会话材料落盘。

⚠️ 这里**只验离线行为**：真实浏览器会话复用**没有**在这里被证明（见证据件）。
"""

from __future__ import annotations

import importlib
import io
import json
import sys
import types
from pathlib import Path

import httpx
import pytest
from loguru import logger as loguru_logger

from app.core import app_settings
from app.core.config import Settings, get_settings
from app.core.errors import ExternalServiceError
from app.mod02_i8 import client as clients
from app.mod02_i8 import cookie_store
from app.mod02_i8.browser_session import (
    I8BrowserSessionClient,
    ReusedBrowserSession,
    StrictRedirectStopped,
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
    strict_payment_notice_by_bill_no,
)
from app.mod02_i8.client import I8_TAKE_FAILED
from app.mod02_i8.notice_source import BILL_TYPE_MATERIAL, _map_record

_TOOLS_DEV = Path(__file__).resolve().parents[2] / "tools" / "dev"

BASE = "https://i8.example.test"

REC = {
    "PhId": "3700000000000521",
    "BillNo": "FKTZS2026090001",
    "BillName": "付某某项目材料款",
    "BillDt": "2026-09-08 00:00:00",
    "PhidPc_EXName": "某某项目(XMCB2025080001)",
    "PhidRecPayType_EXName": "其他支出",
    "PhidBusType_EXName": "付材料款",
    "PhidPayOrg_EXName": "四公司",
    "user_skdw_EXName": "某某商贸有限公司",
    "ApproveAmt": "12345.67",
    "PhidFillPsn_EXName": "梁丽佳",
    "AppStatus": 1,
    "Remark": "备注",
}


class _Recorder:
    """记请求次数与请求头；按队列回放响应。"""

    def __init__(self, *payloads: dict) -> None:
        self.payloads = list(payloads)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = self.payloads.pop(0) if self.payloads else {}
        return httpx.Response(200, json=body)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    """不读本机配置；把「产品配置的 i8 地址」固定成可比较的值。"""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setattr(app_settings, "_VALUES_LOADER", lambda: {"i8_base_url": BASE})
    monkeypatch.setattr(app_settings, "_CACHE", {"i8_base_url": BASE})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _LoginSpy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        raise AssertionError("严格模式不许登录")


class _CacheSpy:
    """盯住产品的 Cookie 缓存：严格模式一次都不许碰。"""

    def __init__(self, monkeypatch) -> None:
        self.touched: list[str] = []
        for name in ("load", "save", "clear"):
            monkeypatch.setattr(cookie_store, name, self._spy(name))

    def _spy(self, name: str):  # noqa: ANN202
        def _inner(*args, **kwargs):  # noqa: ANN002, ANN003
            self.touched.append(name)
            return None

        return _inner


@pytest.fixture
def guards(monkeypatch):
    login = _LoginSpy()
    monkeypatch.setattr(clients, "http_login", login)
    return login, _CacheSpy(monkeypatch)


def _strict(session: ReusedBrowserSession) -> I8BrowserSessionClient:
    return I8BrowserSessionClient(session)


def test_有效会话可用既有解析链完成一次单号精确查(guards):
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url=BASE, transport=rec.transport(), declared_target="本人 · 四公司"))

    row = strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert row == _map_record(REC)
    assert row is not None
    assert row["bill_no"] == "FKTZS2026090001"
    assert row["bill_type"] == BILL_TYPE_MATERIAL
    # 一次单号精确查 = 一次请求；表单沿用既有常量、组织范围未被改写
    assert len(rec.requests) == 1
    form = rec.requests[0].content.decode()
    assert "FKTZS2026090001" in form
    assert "limit=5" in form
    assert "phidOrgList=3700000000000014" in form
    # 全程没登录、没碰产品缓存
    assert login.calls == 0
    assert cache.touched == []


def test_没有会话材料时一条请求都不发(guards):
    login, cache = guards
    with pytest.raises(StrictSessionUnavailable):
        _strict(ReusedBrowserSession(base_url=BASE))
    assert login.calls == 0
    assert cache.touched == []


def test_会话地址与配置不一致时停止且不发请求(guards):
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(
        ReusedBrowserSession(base_url="https://other-i8.example.test", transport=rec.transport())
    )

    with pytest.raises(StrictTargetMismatch):
        strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert rec.requests == []          # 未发出任何请求
    assert login.calls == 0
    assert cache.touched == []


def test_会话失效时立即停止不重登不清缓存(guards):
    login, cache = guards
    expired = {"Code": "200", "Success": False, "Msg": "No SessionInfo found"}
    rec = _Recorder(expired, {"Success": True, "Record": [REC]})   # 第二份响应不该被用到
    client = _strict(ReusedBrowserSession(base_url=BASE, transport=rec.transport()))

    with pytest.raises(StrictSessionEnded):
        strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert len(rec.requests) == 1      # 只发了一次：没有"重发"
    assert login.calls == 0            # 没有重登（更没强踢）
    assert cache.touched == []         # 没有清缓存、也没有回写
    assert client.facts()["requests_attempted"] == 1
    assert client.facts()["login_blocked"] == 1


def test_会话地址不成形时也停止且不发请求(guards):
    """站点写成 `主机:端口` 而缺协议 ⇒ 解析不出 ⇒ 判不一致而停止（保守方向）。"""
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url="i8.example.test:8443", transport=rec.transport()))

    with pytest.raises(StrictTargetMismatch):
        strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert rec.requests == []
    assert login.calls == 0
    assert cache.touched == []


def test_未给单号时不发请求(guards):
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url=BASE, transport=rec.transport()))

    with pytest.raises(StrictSessionUnavailable):
        strict_payment_notice_by_bill_no(client, "   ")

    assert rec.requests == []
    assert login.calls == 0


def test_会话材料不进证据也不进日志(guards):
    cookie_value = "s3cr3t-session-token"
    session = ReusedBrowserSession(base_url=BASE, cookie_header=f"ASP.NET_SessionId={cookie_value}")
    client = _strict(session)

    facts = client.facts()
    assert facts["cookie_present"] is True
    assert facts["product_session_cache_used"] is False
    assert facts["declared_target_machine_checked"] is False
    assert cookie_value not in json.dumps(facts, ensure_ascii=False)
    assert cookie_value not in repr(session)
    assert cookie_value not in repr(client)


def test_站外绝对地址与协议相对地址都停止且不发请求(guards):
    """请求目的地不受"初始化时比过一次 base_url"的保护 —— 每条请求都要自己核一遍。"""
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url=BASE, transport=rec.transport()))

    for path in ("https://evil.example.test/FC/FM/PaymentBill/getList", "//evil.example.test/x"):
        with pytest.raises(StrictTargetMismatch):
            client.post_json(path, data={})
    assert rec.requests == []          # 一条都没发出去
    assert login.calls == 0
    assert cache.touched == []


def test_同主机不同端口视为不同站点(guards):
    login, cache = guards
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url=BASE, transport=rec.transport()))

    with pytest.raises(StrictTargetMismatch):
        client.post_json(f"{BASE}:8443/FC/FM/PaymentBill/getList", data={})

    assert rec.requests == []
    assert login.calls == 0


def test_写成默认端口仍然算同一个站点(guards):
    """`https://host:443` 与 `https://host` 是同一个站点 —— 不能因为写法不同就误停。"""
    rec = _Recorder({"Success": True, "Record": [REC]})
    client = _strict(ReusedBrowserSession(base_url=f"{BASE}:443", transport=rec.transport()))

    row = strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert row is not None
    assert len(rec.requests) == 1
    assert client.facts()["session_origin"] == "https://i8.example.test"


def test_重定向即停止且不跟随(guards):
    """i8 把请求转走 ⇒ 停止；会话不会被带去未核实的地址。"""
    login, cache = guards
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://evil.example.test/steal"})

    client = _strict(ReusedBrowserSession(base_url=BASE, transport=httpx.MockTransport(handler)))

    with pytest.raises(StrictRedirectStopped):
        strict_payment_notice_by_bill_no(client, "FKTZS2026090001")

    assert len(seen) == 1                       # 只发了那一次，没有跟随跳转
    assert all(r.url.host == "i8.example.test" for r in seen)   # 会话没被带去别的站点
    assert client.facts()["redirect_blocked"] == 1
    assert client.facts()["requests_attempted"] == 1
    assert login.calls == 0
    assert cache.touched == []


def test_失败时不记录响应片段也不拼原始报错(guards):
    """失败只抛固定文案：响应原文既不进用户文案，也不进运行日志。"""
    login, cache = guards
    secret_fragment = "内部错误堆栈-不应外泄"
    logged: list[str] = []
    sink_id = loguru_logger.add(lambda message: logged.append(message), level="DEBUG")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"<html>{secret_fragment}</html>")

    client = _strict(ReusedBrowserSession(base_url=BASE, transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(ExternalServiceError) as caught:
            strict_payment_notice_by_bill_no(client, "FKTZS2026090001")
    finally:
        loguru_logger.remove(sink_id)

    # 用户可见文案是既有固定文案，不含响应片段
    assert caught.value.message == I8_TAKE_FAILED
    assert secret_fragment not in caught.value.message
    # 运行日志里也没有响应片段（严格模式不沿用会记 resp.text[:200] 的那两个方法）
    assert secret_fragment not in "".join(logged)
    assert cache.touched == []
    assert login.calls == 0


def test_事实字段只给站点原点不含声明内容与查询参数(guards):
    login, cache = guards
    session = ReusedBrowserSession(
        base_url=f"{BASE}/some/path?token=abc123#frag",
        cookie_header="ASP.NET_SessionId=deadbeef",
        declared_target="本人 梁丽佳 四公司 生产站",
    )
    client = _strict(session)
    facts = client.facts()

    assert facts["session_origin"] == "https://i8.example.test"   # 默认端口不写，其他部分一律去掉
    blob = json.dumps(facts, ensure_ascii=False)
    for leaked in ("abc123", "deadbeef", "梁丽佳", "/some/path", "frag"):
        assert leaked not in blob
    assert facts["declared_target_present"] is True
    assert facts["declared_target_machine_checked"] is False
    assert facts["identity_cross_checked"] is False
    assert login.calls == 0
    assert cache.touched == []


def test_入口成功时只报解析完成并只留具名字段(guards, monkeypatch, capsys):
    """复核点名的措辞与去敏：退出 0 只能读成「解析链跑通」，输出不许带原始行。"""
    login, cache = guards
    leaky = {**REC, "SensitiveColumn": "不该出现在输出里的列"}
    loader = types.ModuleType("_t476_fake_channel")
    loader.build = lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, json={"Success": True, "Record": [leaky]})
    )
    monkeypatch.setitem(sys.modules, "_t476_fake_channel", loader)
    monkeypatch.setattr(sys, "path", [str(_TOOLS_DEV), *sys.path])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"base_url": BASE, "cookie_header": "a=b"})))

    module = importlib.import_module("i8_browser_session_reuse")
    code = module.main(["--execute", "--bill-no", "FKTZS2026090001", "--transport", "_t476_fake_channel:build"])

    out = capsys.readouterr().out
    assert code == 0
    assert "核对通过" not in out                      # 不许把解析完成说成整体核对通过
    assert "只**证明解析链跑通" in out               # 必须写清判据只到这里
    assert "账号 / 组织 / 页面对象" in out          # 明确指出仍需人工交叉核对
    assert leaky["SensitiveColumn"] not in out        # 只留具名核对字段，不打印原始行
    assert REC["BillName"] not in out
    assert login.calls == 0
    assert cache.touched == []


def test_入口停止时只报受控类别不报异常原文(guards, monkeypatch, capsys):
    login, cache = guards
    loader = types.ModuleType("_t476_fake_channel_stop")
    loader.build = lambda: httpx.MockTransport(
        lambda request: httpx.Response(200, json={"Code": "200", "Success": False, "Msg": "No SessionInfo found"})
    )
    monkeypatch.setitem(sys.modules, "_t476_fake_channel_stop", loader)
    monkeypatch.setattr(sys, "path", [str(_TOOLS_DEV), *sys.path])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"base_url": BASE, "cookie_header": "a=b"})))

    module = importlib.import_module("i8_browser_session_reuse")
    code = module.main(["--execute", "--bill-no", "FKTZS2026090001", "--transport", "_t476_fake_channel_stop:build"])

    out = capsys.readouterr().out
    assert code == 2
    assert "已按边界停止：会话在 i8 侧已失效（未重登、未强踢）。" in out
    assert "No SessionInfo" not in out                # 不打印原始响应片段
    assert "StrictSessionEnded" not in out            # 不打印异常类名
    assert login.calls == 0
    assert cache.touched == []


def test_产品原有缓存与重登策略未被这层改动(guards):
    """`I8Client` 仍是产品原类；严格模式只在另一个类里换会话来源（不改原类行为）。"""
    login, cache = guards
    plain = clients.I8Client()
    assert type(plain) is clients.I8Client          # 产品客户端仍是它自己

    # 严格模式复用同一套请求/判定链（同一父类），但一次读写都没落到产品的会话缓存上
    assert issubclass(I8BrowserSessionClient, clients.I8Client)
    client = _strict(
        ReusedBrowserSession(base_url=BASE, transport=_Recorder({"Success": True, "Record": [REC]}).transport())
    )
    client.post_json("/FC/FM/PaymentBill/getList", data={})
    assert cache.touched == []                       # 没读、没写、没清产品 Cookie 缓存
    assert login.calls == 0                          # 没登录（更没强踢）
