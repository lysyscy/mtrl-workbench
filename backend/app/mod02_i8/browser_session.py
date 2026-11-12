"""i8「仅复用已有会话」的严格模式（验证用适配 · 不落盘 · 不登录 · 不强踢）。

**与产品常态客户端 `I8Client` 分开，互不影响**（后者的缓存 / 重登策略一字未改）：

- 会话来源：只接受**外部注入**的宿主浏览器已有会话（Cookie 头 与/或 传输适配）。
  ⛔ 不读磁盘 Cookie 缓存、⛔ 不写任何会话材料、⛔ 不假定 Cookie 一定可导出。
- 会话失效：响应被判会话失效 ⇒ **立即停止**（⛔ 不重登、⛔ 不清缓存、⛔ 不重试循环）。
- 目标校验：**每一条**真正要发出去的请求，其目的地（协议 / 主机 / 端口）都必须等于产品配置的
  i8 站点；不等 ⇒ 一条请求都不发就停止。⛔ 不跟随任何重定向（跳转即停止，会话不会被带去未核实的地址）。
- 身份与组织：请求表单沿用既有常量（组织过滤常量不由本模块改写），但这**不能证明**会话属于谁；
  操作者声明的账号 / 组织只作为"有无声明"记录，**不冒充机器核对结果**（`facts()` 里明写未机器核对）。
- 诊断脱敏：编码响应在失败时只抛固定的用户文案，**不记录响应片段、不记录原始报错**；
  站点只输出协议 / 主机 / 端口（去掉用户信息与查询串），会话材料一律不出现。

本模块只补「会话从哪来、什么时候必须停」这一层；取数、校验、解析全部沿用既有实现。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from app.core.config import I8_PATH_PAYMENT_NOTICE, get_settings, i8_base_of, i8_endpoint_of
from app.core.errors import AppError, DataConflictError, ExternalServiceError, NotConfiguredError
from app.mod02_i8.client import I8_TAKE_FAILED, I8Client
from app.mod02_i8.notice_source import (
    EMPTY_RETRY,
    EMPTY_RETRY_SLEEP,
    LIST_FORM,
    _extract_records,
    _map_record,
)

__all__ = [
    "I8BrowserSessionClient",
    "ReusedBrowserSession",
    "StrictRedirectStopped",
    "StrictSessionEnded",
    "StrictSessionStopped",
    "StrictSessionUnavailable",
    "StrictTargetMismatch",
    "strict_payment_notice_by_bill_no",
]

#: 停止理由（用户可见文案：只讲"发生了什么 / 下一步"，不带技术细节）。
_STOP_NO_SESSION = "没有可复用的浏览器会话，本次未发出任何 i8 请求。请先在该浏览器里用本人账号登录 i8 并停在业务页，然后再试。"
_STOP_BAD_TARGET = "这个会话所在的 i8 站点与当前配置不一致，本次未发出任何请求。请确认打开的是本单位的 i8 地址，然后再试。"
_STOP_FOREIGN_TARGET = "这次请求要去的地址不属于当前配置的 i8 站点，本次未发出该请求。请确认会话与配置指向同一个 i8 地址，然后再试。"
_STOP_REDIRECT = "这次请求被 i8 转去了另一个地址，本次已停止 —— 没有跟随跳转，会话没有被带去未核实的地址。请确认该浏览器里的 i8 会话仍然有效，然后再试。"
_STOP_SESSION_ENDED = "浏览器里的 i8 会话已经不认了，本次已停止（没有重新登录、也没有顶掉任何在线会话）。请在该浏览器里重新登录 i8，然后再试。"
_STOP_NO_BILL = "没给要查的单号，本次未发出任何 i8 请求。"

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class StrictSessionStopped(AppError):
    """浏览器通道要求整次动作停止；业务容错不得将其降级为空结果。"""


class StrictSessionUnavailable(StrictSessionStopped):
    """没拿到可复用的浏览器会话 —— 未发任何请求就停止。"""

    code = "i8_strict_session_unavailable"
    http_status = 400


class StrictTargetMismatch(DataConflictError, StrictSessionStopped):
    """会话所在站点（或本次请求目的地）与产品配置的 i8 服务地址不一致 —— 停止。"""

    code = "i8_strict_target_mismatch"


class StrictRedirectStopped(StrictTargetMismatch):
    """i8 要把这次请求转走 —— 立即停止，不跟随跳转。"""

    code = "i8_strict_redirect_stopped"


class StrictSessionEnded(ExternalServiceError, StrictSessionStopped):
    """会话在 i8 侧已失效 —— 立即停止，不重登、不强踢。"""

    code = "i8_strict_session_ended"


@dataclass(frozen=True)
class ReusedBrowserSession:
    """一份**当次临时使用**的浏览器会话材料（用完即弃，不落盘、不入日志）。

    - `base_url`：会话所在 i8 站点（必须与产品配置的 i8 服务地址一致）。
    - `cookie_header`：宿主浏览器里那份会话的 Cookie 头；**打印/记录时一律不出现**
      （`repr=False`）。拿不到可导出的 Cookie 时留空，改用 `transport`。
    - `transport`：可注入的传输适配（例如转发到宿主浏览器的通道）—— 用于
      「Cookie 拿不出来但请求能带着会话发出去」的情形。本模块**不自带**浏览器通道实现。
    - `declared_target`：操作者声明的账号 / 组织 / 服务器，**只记"有没有声明"，不记内容**。
    """

    base_url: str
    cookie_header: str = field(default="", repr=False)
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    declared_target: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            raise StrictSessionUnavailable(_STOP_BAD_TARGET)
        object.__setattr__(self, "base_url", base)
        if not (self.cookie_header or "").strip() and self.transport is None:
            raise StrictSessionUnavailable(_STOP_NO_SESSION)


def _parse_url(value: str) -> httpx.URL | None:
    """解析成 `httpx.URL`；解析不出来（缺协议 / 缺主机）时返回 None。"""
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = httpx.URL(text)
    except Exception:  # noqa: BLE001
        return None
    if not parsed.scheme or not parsed.host:
        return None
    return parsed


def _origin_of(value: str) -> str:
    """去敏的站点标识：只留 `协议://主机[:端口]`（去掉用户信息、路径、查询串与片段）。

    解析不出来时返回空串 ⇒ 调用方据此判定"目标未通过核验"而停止（保守方向）。
    默认端口（https:443 / http:80）由 httpx 归一成 None ⇒ 不写端口，与其他来源可直接比。
    """
    parsed = _parse_url(value)
    if parsed is None:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.host.lower()
    try:
        port = parsed.port
    except ValueError:  # 端口写得不像端口 ⇒ 当作"核验不过"
        return ""
    return f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"


class I8BrowserSessionClient(I8Client):
    """严格复用一份已有浏览器会话的 i8 客户端（只读验证用）。

    复用 `I8Client` 的请求 / 判定 / 解析链（`request` / `_is_session_invalid` /
    `serialize_fetch` 全部沿用），只替换这几处：
    会话从哪来（注入）、没有 Cookie 缓存这一层、失效时**不重登**而是停止、
    每条请求先核目的地、不跟随重定向、失败时不留响应片段。
    """

    def __init__(self, session: ReusedBrowserSession) -> None:
        super().__init__(allow_kick=False)  # ⚠️ 占位：本类永不登录，allow_kick 无实际作用
        self._reused = session
        self._attempts = 0
        self._login_blocked = 0
        self._redirect_blocked = 0

    # —— 会话与目标 ————————————————————————————————————————————————

    def _expected_origin(self) -> str:
        expected = i8_base_of(get_settings())
        if not expected:
            raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")
        return _origin_of(expected)

    def _ensure_session(self) -> httpx.Client:
        if self._session is None:
            expected_origin = self._expected_origin()
            if _origin_of(self._reused.base_url) != expected_origin:
                raise StrictTargetMismatch(_STOP_BAD_TARGET)
            self._session = httpx.Client(
                base_url=self._reused.base_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "X-Requested-With": "XMLHttpRequest",
                },
                # ⛔ 不跟随重定向：跳转即停止，会话不会被带去未核实的地址。
                follow_redirects=False,
                transport=self._reused.transport,
            )
        return self._session

    def _ensure_cookie(self) -> None:
        """只取注入的那份 Cookie 头；⛔ 不读磁盘缓存、⛔ 不登录。"""
        self._cookie = (self._reused.cookie_header or "").strip() or None

    def _login(self) -> None:
        """严格模式永不登录（更不强踢）—— 走到这里说明必须停止。"""
        self._login_blocked += 1
        raise StrictSessionEnded(_STOP_SESSION_ENDED)

    def _resolve_target(self, path: str) -> str:
        """算出这条请求真正的目的地（绝对地址原样用；相对地址按会话站点拼）。"""
        text = str(path)
        parsed = _parse_url(text)
        if parsed is not None:
            return text
        return str(self._session.base_url.join(text))

    def _assert_allowed(self, target: str) -> None:
        """目的地不是配置的 i8 站点 ⇒ 一条请求都不发就停止。"""
        if _origin_of(target) != self._expected_origin():
            raise StrictTargetMismatch(_STOP_FOREIGN_TARGET)

    # —— 请求 / 解析 ————————————————————————————————————————————————

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        # 先过站点校验（不一致就此停止，**一条请求都不发**）；通过后才记一次"真的发出去了"。
        self._ensure_session()
        self._assert_allowed(self._resolve_target(path))
        self._attempts += 1
        resp = super().request(method, path, **kwargs)
        if resp.status_code in _REDIRECT_STATUSES or resp.is_redirect:
            self._redirect_blocked += 1
            raise StrictRedirectStopped(_STOP_REDIRECT)
        return resp

    def get_json(self, path: str, **kwargs: object) -> object:
        return self._json_or_stop(self.request("GET", path, **kwargs))

    def post_json(self, path: str, **kwargs: object) -> object:
        return self._json_or_stop(self.request("POST", path, **kwargs))

    @staticmethod
    def _json_or_stop(resp: httpx.Response) -> object:
        """与产品同口径地判失败，但**只抛固定文案**：不记录响应片段、不记录原始报错。"""
        if resp.status_code >= 400:
            raise ExternalServiceError(I8_TAKE_FAILED)
        try:
            return resp.json()
        except ValueError as exc:
            raise ExternalServiceError(I8_TAKE_FAILED) from exc

    # —— 可记录事实（去敏） ——————————————————————————————————————————

    def facts(self) -> dict[str, object]:
        """本次复用的可记录事实（去敏：不含 Cookie 内容、不含声明文字、不含原始响应）。"""
        return {
            "session_origin": _origin_of(self._reused.base_url),
            "cookie_present": bool((self._reused.cookie_header or "").strip()),
            "transport_injected": self._reused.transport is not None,
            "declared_target_present": bool((self._reused.declared_target or "").strip()),
            "declared_target_machine_checked": False,
            "identity_cross_checked": False,
            "product_session_cache_used": False,
            "login_blocked": self._login_blocked,
            "redirect_blocked": self._redirect_blocked,
            "requests_attempted": self._attempts,
        }


def strict_payment_notice_by_bill_no(client: I8Client, bill_no: str) -> dict | None:
    """按单号**精确**查一张付款通知书（沿用既有表单、空结果复核与字段解析）。

    只读一次最小代表：单号精确查（`limit=5`），不做月份全量列表。
    """
    target = (bill_no or "").strip()
    if not target:
        raise StrictSessionUnavailable(_STOP_NO_BILL)
    query = json.dumps(
        {"queryFilter": json.dumps({f"BillNo*string*eq*1": target}, ensure_ascii=False)},
        ensure_ascii=False,
    )
    form = {**LIST_FORM, "queryfilter": query, "limit": "5"}
    settings = get_settings()
    for attempt in range(EMPTY_RETRY + 1):
        payload = client.post_json(i8_endpoint_of(settings, I8_PATH_PAYMENT_NOTICE), data=form)
        records = _extract_records(payload)
        if records:
            return _map_record(records[0])
        if attempt < EMPTY_RETRY:
            time.sleep(EMPTY_RETRY_SLEEP)
    return None
