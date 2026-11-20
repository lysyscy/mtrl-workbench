"""MOD-02 横切：把**浏览器通道**接成 `httpx` transport，并提供"按当前会话模式开客户端"的工厂。

## 数据流（一条请求的完整来回）

```
I8Client.request()  ──httpx──▶  BrowserRelayTransport.handle_request()
                                     │  ① 核目标（只允许当前连接的 i8 站点原点）
                                     │  ② 脱敏请求头（Cookie / Authorization 一律不发出去）
                                     │  ③ broker.enqueue()   ← 后端**挂起**
                                     ▼
                        页面 GET /api/m02/browser/pending（长轮询，走同一套身份门）
                                     ▼
                        扩展在**已登录 i8 标签**里同源 fetch（浏览器自带 Cookie）
                                     ▼
                        页面 POST /api/m02/browser/complete（一次性票）
                                     ▼
                     broker 唤醒 ③ ──▶ 组装 httpx.Response ──▶ 回到 I8Client 的既有解析链
```

⚠️ **解析链一行没改**：`I8Client.get_json/post_json`、`NoticeFetcher`、`_extract_records`、
   `_map_record`、后续业务校验与落库全都照旧。本模块只换"这一段字节怎么走"。

## 与"产品原有 HTTP 模式"的关系

- 显式 `http` ⇒ 工厂使用统一会话策略绑定的账号、站点和本次下线确认。
- 选了 `browser` ⇒ 返回 `I8BrowserSessionClient`：`_login()` 直接抛停止、`_ensure_cookie()` 不碰
  `cookie_store` ⇒ **结构上**不可能登录、强踢、写会话缓存。
- 选了 `browser` 但连接不在 ⇒ **当场抛停止**，⛔ 绝不悄悄退回 HTTP
  （那会变成"以登录成功冒充复用成功"）。
"""

from __future__ import annotations

import base64
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings, i8_base_of
from app.core.errors import ExternalServiceError, MustReportError, NotConfiguredError
from app.core.logging import get_logger
from app.mod02_i8 import browser_broker
from app.mod02_i8.browser_broker import RELAY_WAIT_SECONDS, BrowserBroker, BrowserRelayUnavailable, ConnectionInfo
from app.mod02_i8.browser_session import (
    _REDIRECT_STATUSES,
    _STOP_REDIRECT,
    I8BrowserSessionClient,
    ReusedBrowserSession,
    StrictRedirectStopped,
    StrictSessionEnded,
    StrictSessionUnavailable,
    StrictTargetMismatch,
    _origin_of,
)
from app.mod02_i8.client import I8Client, http_session_policy
from app.mod02_i8.contract_source import DETAIL_PATH as CONTRACT_DETAIL_PATH, LIST_PATH as CONTRACT_LIST_PATH
from app.mod02_i8.sources import WH_PARAMS

logger = get_logger()

#: 会话模式取值（前端 `Segmented` 的两项；默认 `http` = 产品原有行为）。
MODE_HTTP = "http"
MODE_BROWSER = "browser"

#: 请求头**白名单**：只放行取数真正需要的几个，其余一律不发出去。
#: ⚠️ `cookie` / `authorization` / `host` 即使被塞进来也会被下面的 `_BLOCKED` 再挡一次（双保险）。
_ALLOWED_HEADERS = frozenset({"accept", "content-type", "x-requested-with", "accept-language"})
_BLOCKED_HEADERS = frozenset({
    "cookie", "authorization", "proxy-authorization", "host", "content-length",
    "set-cookie", "referer", "origin",
})

_ORG_IN_QUERY = re.compile(r"#curOrg:(\d+)#")

#: ⭐ **只读端点白名单**（方法 + 精确路径），逐条对应本仓**真实存在**的取数调用点。
#: ⚠️ 不看"POST 就当只读"：每条都是人工核对过的「读接口」；登录 / 强踢 / 任何保存端点
#:    （`/SUP/Login/SupLogin`、`/SUP/Login/KillOnlineUser` 等）**永远不在这张表里**。
#: ⚠️ 新增取数口时必须同时加到这里 —— 否则浏览器模式会**当场停**（这是故意的：宁可停，不要偷偷放行）。
#: ⚠️ 扩展侧（`apps/browser-extension/service_worker.js` 的 `READONLY_ENDPOINTS`）是同一张表的副本：
#:    两侧必须逐条一致，改一边就要改另一边（扩展读不到部署配置，只能写死已核过的路径）。
_READONLY_ENDPOINTS: dict[str, frozenset[str]] = {
    "GET": frozenset({
        "/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint",  # notice_source.FLOW_PATH
        "/SUP/RichHelp/GetCommonUseList",                 # config.I8_PATH_COMMON_PROJECT
        "/reportcenter/printManage/getPrintDesign",       # config.I8_PATH_PRINT_DESIGN
    }),
    "POST": frozenset({
        "/FC/FM/PaymentBill/getList",                     # config.I8_PATH_PAYMENT_NOTICE
        "/FC/FM/PaymentBill/getInfo",                     # notice_source.INFO_PATH
        "/FC/FM/PaymentBill/getDetInfo",                  # notice_source.DETAIL_PATH
        "/PMS/PMM/KcBaseSetting/GetWareHouseList",        # config.I8_PATH_WAREHOUSE_LIST
        "/reportcenter/reportExport/export",              # config.I8_PATH_REPORT_EXPORT（二进制报表读取，≠ 实际打印）
        "/PMS/PCM/Contract/ProjBal/GetCntProjBalList",    # payable_source.PATH
        CONTRACT_DETAIL_PATH,
        CONTRACT_LIST_PATH,
        "/sup/customServer/getList",                      # workbench_i8.LIST_PATH（小写 sup，原样）
    }),
}

def _request_read_timeout(request: httpx.Request) -> float | None:
    """取这条请求**自己的** read 超时预算（秒）；没有就返回 `None`。

    依据：`httpx` 构造请求时会把超时写进 `request.extensions["timeout"]`
    （`BaseClient._build_request` / `_set_timeout`，值是 `Timeout.as_dict()` 的
    `{"connect","read","write","pool"}`）。所以 `post_json(..., timeout=LIST_TIMEOUT)`
    的 200s、`DETAIL_TIMEOUT` 的 60s 天然会传到这里，**不需要**另维护一份预算表。

    ⚠️ 这就是"不许拿 broker 的 30s 去截断 200s 合同列表"的落点：
       预算是**逐条请求**的，broker 只是照抄。
    """
    raw = request.extensions.get("timeout") if request.extensions else None
    if not isinstance(raw, dict):
        return None
    value = raw.get("read")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return float(value)


def _normalized_path(url: httpx.URL) -> str:
    """取"可以拿去比对"的路径：任何可疑写法一律返回空串（⇒ 与白名单必然不等 ⇒ 停）。

    ⚠️ 防的是"伪装路径"：`/FC/../x`、`//FC/x`、`/FC/FM/x/`、`%2e%2e` 之类。
       `httpx.URL.path` 会把 `%2e` 解码成 `.`（实测 `/FC/%2e%2e/x` → `/FC/../x`），
       所以下面直接拒绝 `..` 与 `//` 就够了；尾部斜杠也一律拒绝（白名单里没有以 `/` 结尾的）。
    """
    path = url.path or ""
    if not path.startswith("/") or ".." in path or "//" in path:
        return ""
    if len(path) > 1 and path.endswith("/"):
        return ""
    return path


_SIGNATURE_IMAGE_PATH = re.compile(
    r"/(?:[A-Za-z0-9_.~-]+/)*[A-Za-z0-9_.~-]+\.(?:png|jpe?g|gif|bmp|webp)", re.IGNORECASE,
)


def is_signature_image_target(url: str) -> bool:
    """The flow supplies a signed raster-image URL. Inspect its raw path before URL normalization."""
    try:
        raw = urlsplit(url)
        target = httpx.URL(url)
    except (httpx.InvalidURL, TypeError, ValueError):
        return False
    tokens = target.params.get_list("s")
    return (
        not raw.fragment and ".." not in raw.path and not target.userinfo
        and _SIGNATURE_IMAGE_PATH.fullmatch(raw.path) is not None
        and len(tokens) == 1 and bool(tokens[0].strip())
    )


_SIGNATURE_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"), (b"BM", "image/bmp"),
)


def signature_image_mime(blob: bytes) -> str:
    if blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
        return "image/webp"
    return next((mime for magic, mime in _SIGNATURE_IMAGE_MAGIC if blob.startswith(magic)), "")


def require_signature_image(response: httpx.Response) -> None:
    """Reject login pages and non-image responses without exposing signed URLs."""
    status = response.status_code
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if 300 <= status < 400:
        raise StrictRedirectStopped(_STOP_REDIRECT)
    if status in (401, 403) or (200 <= status < 300 and media_type == "text/html"):
        raise StrictSessionEnded("i8 签名图返回登录或会话异常页面，本批已停止。请核对 i8 会话后重试。")
    if not 200 <= status < 300:
        raise ExternalServiceError(f"签名图下载失败（HTTP {status}）。")
    if not signature_image_mime(response.content) or not media_type.startswith("image/") or media_type == "image/":
        if I8Client._is_session_invalid(response) or "no sessioninfo" in response.text.lower():
            raise StrictSessionEnded("i8 会话已失效，本批已停止。请核对 i8 会话后重试。")
        raise ExternalServiceError("i8 签名图响应不是图片。")


def assert_readonly(method: str, url: str) -> None:
    """**后端侧**只读端点校验：不在白名单内 ⇒ 当场停（⛔ 不发出去、不重试、不换通道）。

    这里只比值/路径，**不**假设"POST 就是只读"。
    """
    verb = str(method or "").strip().upper()
    try:
        parsed = httpx.URL(str(url or ""))
    except (httpx.InvalidURL, TypeError, ValueError):
        raise StrictTargetMismatch(
            "这次请求的地址不成形，本次已停止（未发出去、未登录）。"
        ) from None
    if parsed.scheme not in ("http", "https") or not parsed.host:
        raise StrictTargetMismatch(
            "这次请求的地址不成形，本次已停止（未发出去、未登录）。"
        )
    if parsed.userinfo:
        # 带 user:pass 的地址一律不认（会话材料/凭据都不能从这里走）。
        raise StrictTargetMismatch(
            "这次请求的地址里带了账号信息，本次已停止（未发出去、未登录）。"
        )
    if verb == "GET" and is_signature_image_target(url):
        return
    path = _normalized_path(parsed)
    if path not in _READONLY_ENDPOINTS.get(verb, frozenset()):
        raise StrictTargetMismatch(
            "这次请求不在只读取数白名单里，本次已停止（未发出去、未登录、未改任何数据）。"
        )


def expected_org_id() -> str:
    """当前配置下 i8 取数**实际**使用的组织 id。

    ⚠️ **不新写一份常量**：直接从既有取数表单（`sources.WH_PARAMS["orgQuery"]`）里解析 ——
       那是"每条请求都带着的组织范围"。两处一旦分叉，就会变成
       "界面说核过组织、实际请求发了别的组织"。
    """
    match = _ORG_IN_QUERY.search(str(WH_PARAMS.get("orgQuery") or ""))
    return match.group(1) if match else ""


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    """只保留白名单里的请求头（去敏：会话材料永远不出后端）。"""
    out: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in _BLOCKED_HEADERS or lowered not in _ALLOWED_HEADERS:
            continue
        out[key] = value
    return out


def _decode_reply(status: object, raw_headers: object, body_b64: object,
                  declared_length: object = None, relay_failure: str | None = None) -> tuple[int, dict[str, str], bytes]:
    """解浏览器回帖（base64 body + 可选长度声明）。形状不对 ⇒ 受控停止。

    ⛔ 不把原始字符串抛给用户、不把响应片段写日志 —— 失败一律给固定文案。
    """
    # A relay failure is not an HTTP response from i8. Keep it strict before
    # optional material/warehouse readers can turn ordinary errors into blanks.
    if relay_failure is not None:
        if relay_failure == "session-ended":
            raise StrictSessionEnded("i8 会话已失效，本批已停止。请核对 i8 会话后重试。")
        if relay_failure == "timeout":
            raise StrictSessionEnded("浏览器在这条请求的时间预算内没有回音，本次已停止（超时，未重试、未登录）。")
        if relay_failure == "redirect":
            raise StrictRedirectStopped("浏览器返回了无法核对的不透明响应，本次已停止（未跟随跳转、未重试、未登录）。")
        if relay_failure == "target":
            raise StrictTargetMismatch("请求目标与选中的 i8 标签不一致，本次已停止（未重试、未登录）。")
        if relay_failure == "network":
            raise StrictSessionUnavailable("浏览器未能完成本次取数，请核对网络与站点；本次已停止（未重试、未登录）。")
        if relay_failure == "unavailable":
            raise StrictSessionUnavailable("浏览器取数通道暂不可用，本次已停止；连接恢复后请核对结果，再重新发起抓取。")
        raise StrictSessionUnavailable("浏览器取数结果无法核对，本次已停止；请更新页面与扩展后重新连接。")
    if not isinstance(status, int) or isinstance(status, bool) or status < 100 or status > 599:
        raise StrictSessionUnavailable("浏览器回帖的状态码不成形，本次已停止（未重试、未登录）。")
    headers: dict[str, str] = {}
    if isinstance(raw_headers, dict):
        for key, value in raw_headers.items():
            if isinstance(key, str) and isinstance(value, str) and key.lower() not in _BLOCKED_HEADERS:
                headers[key] = value
    if not isinstance(body_b64, str):
        raise StrictSessionUnavailable("浏览器回帖缺少响应体，本次已停止（未重试、未登录）。")
    try:
        body = base64.b64decode(body_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise StrictSessionUnavailable(
            "浏览器回帖的响应体读取失败，本次已停止（未重试、未登录）。"
        ) from None
    if isinstance(declared_length, int) and not isinstance(declared_length, bool) \
            and declared_length >= 0 and declared_length != len(body):
        # 完整性：页面/扩展报的长度与实际字节数不一致 ⇒ 当作**没拿到可信结果**，停。
        raise StrictSessionUnavailable(
            "浏览器回的响应体长度对不上（传输可能被截断），本次已停止（未重试、未登录）。"
        )
    if status in _REDIRECT_STATUSES:
        # ⚠️ 真浏览器上这条分支基本不会走到：`redirect:'manual'` 实测返回的是
        #    不透明响应（`opaqueredirect`、status 0、读不到 Location），扩展会在那边
        #    直接判停并回一条失败消息。这里保留是给"可信通道另有 3xx 回帖"留的兜底，
        #    不要据此声称浏览器模式能识别跳转目标。
        raise StrictRedirectStopped(_STOP_REDIRECT)
    return status, headers, body


class BrowserRelayTransport(httpx.BaseTransport):
    """一条请求 ↔ 一次浏览器往返。`httpx.Client(transport=...)` 注入后，`I8Client` 完全无感。"""

    def __init__(self, *, owner: str, device: str, origin: str,
                 broker: BrowserBroker | None = None, expected_generation: int | None = None) -> None:
        self._owner = owner
        self._device = device
        #: 只允许同一个站点原点（规范化后比较，含端口）。
        self._origin = _origin_of(origin) or origin
        self._broker = broker
        connection = self.broker.connection_of(owner, device) if expected_generation is None else None
        self._generation = connection.generation if connection else expected_generation

    @property
    def broker(self) -> BrowserBroker:
        return self._broker if self._broker is not None else browser_broker.broker()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        target = str(request.url)
        if _origin_of(target) != self._origin:
            # ⛔ 目标校验覆盖**每一条实际请求**（不是只比初始化时那个 base_url）。
            raise StrictTargetMismatch(
                "这次请求要去的地址不属于当前连接的 i8 站点，本次已停止（未发出去、未登录）。"
            )
        # ⛔ **只读端点白名单**：站点对了不代表能发 —— 登录/踢人/保存端点绝不能从这条通道走。
        assert_readonly(request.method, target)
        body = request.read() if request.method not in ("GET", "HEAD") else b""
        if self._generation is None:
            raise BrowserRelayUnavailable("浏览器连接不在，本次操作已停止，请重新确认后发起。")
        pending = self.broker.enqueue(
            self._owner, self._device,
            method=request.method, url=target,
            headers=_safe_headers(request.headers), body=body,
            # ⚠️ 预算逐条透传（合同列表 200s / 详情 60s / 其余 30s）——
            #    ⛔ 别在这里统一成默认值，那就是拿 30s 截断 200s 的请求。
            timeout_seconds=_request_read_timeout(request) or RELAY_WAIT_SECONDS,
            expected_generation=self._generation,
        )
        self.broker.wait(pending)
        status, headers, content = _decode_reply(
            pending.status, pending.reply_headers,
            base64.b64encode(pending.reply_body).decode("ascii"),
            # ⚠️ 长度核对用的是**浏览器自报**的那个数（`reply_declared_length`），
            #    不是本地算出来的长度 —— 否则"截断"永远检不出来。
            pending.reply_declared_length,
            pending.relay_failure,
        )
        response = httpx.Response(status, headers=headers, content=content, request=request)
        if request.method == "GET" and is_signature_image_target(target):
            require_signature_image(response)
        return response


#: 当前请求的作用域包含模式、设备和确认的浏览器连接。
#: ⚠️ 用 `ContextVar` 而不是全局变量：`uvicorn` 并发处理，全局量会串号（同 `core/session.py` 的教训）。
_relay_scope: ContextVar[tuple[str, str, ConnectionInfo | None]] = ContextVar(
    "i8_relay_scope", default=("", "", None),
)


@contextmanager
def relay_scope(mode: str, device_id: str = "", *, owner: str | None = None) -> Iterator[None]:
    """Hold the confirmed browser connection for the duration of an operation."""
    mode = resolve_mode(mode)
    device = str(device_id or "")
    connection = _browser_connection(owner, device) if mode == MODE_BROWSER and owner is not None else None
    token = _relay_scope.set((mode, device, connection))
    try:
        yield
    finally:
        _relay_scope.reset(token)


def current_scope() -> tuple[str, str]:
    mode, device, _ = _relay_scope.get()
    return mode, device


def resolve_mode(value: object) -> str:
    """只接受请求显式选择的会话模式。"""
    if not isinstance(value, str) or value not in (MODE_HTTP, MODE_BROWSER):
        raise MustReportError("取数方式无法识别，请刷新页面后重新选择。")
    return value


def _browser_connection(owner: str, device: str) -> ConnectionInfo:
    configured = _origin_of(i8_base_of(get_settings()))
    if not configured:
        raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")
    if not owner:
        raise BrowserRelayUnavailable("浏览器通道需要登录身份，本次已停止。")

    connection = browser_broker.broker().connection_of(owner, device)
    if connection is None:
        raise BrowserRelayUnavailable(
            "已选择「用浏览器已有会话」，但工作台与浏览器的连接不在（可能未连接、已断开或页面已刷新）。"
            "本次已停止；没有改用登录方式，也没有顶掉任何在线会话。请到「i8 接入」页重新连接后再抓取。"
        )
    if connection.origin != configured:
        # 站点不一致：连接登记时已核过，这里再核一次（设置可能在连接后被改）。
        raise StrictTargetMismatch(
            "浏览器的 i8 站点与工作台当前配置不一致，本次已停止（未发请求、未改任何配置）。"
            "请让工作台的 i8 服务器设置与浏览器里那个站点一致，或改用工作台直连模式。"
        )
    return connection


def open_i8_client(*, owner: str) -> I8Client:
    """为当前会话策略创建客户端。owner 取自服务端认证身份。"""
    mode, device, connection = _relay_scope.get()
    if resolve_mode(mode) == MODE_HTTP:
        policy = http_session_policy.get()
        if policy is None:
            raise MustReportError("工作台直连会话尚未建立，请重新发起 i8 操作。")
        return I8Client(policy=policy)
    current = _browser_connection(owner, device)
    if connection is not None and (
        connection.owner != owner or connection.generation != current.generation
    ):
        raise BrowserRelayUnavailable("浏览器已重新连接，本次操作已停止，请重新确认后发起。")
    connection = connection or current
    reused = ReusedBrowserSession(
        base_url=connection.origin,
        transport=BrowserRelayTransport(
            owner=owner, device=device, origin=connection.origin, expected_generation=connection.generation,
        ),
        declared_target=connection.origin,
    )
    return I8BrowserSessionClient(reused)


__all__ = [
    "BrowserRelayTransport",
    "MODE_BROWSER",
    "MODE_HTTP",
    "current_scope",
    "expected_org_id",
    "open_i8_client",
    "relay_scope",
    "resolve_mode",
]
