"""MOD-02 横切：i8 持久 HTTP 客户端（会话保持 + 401 单次自动重登 + 同表串行锁）。

依据（全部来自《说明书》§3.1.2 / §3.1.3 / §3.6 与用户裁定 D9）：
- 纯 HTTP 登录态（Cookie 会话），不依赖浏览器。
- ⭐ **Cookie 磁盘缓存复用**（`cookie_store`）：**首次请求优先用缓存、命中就根本不登录** ——
  免「每次导出都撞单会话登录」。取数 / 落盘口径见 `app/mod02_i8/cookie_store.py`。
- **会话失效（HTTP 401 / 响应体 Code==401）⇒ 在本次人工操作中重登一次再重试**（§3.1.2 既定口径）。
- ⚠️ **失败 / 接口报错时绝不自动重试登录**（反复重登 = 反复顶号，D9 明确禁止）。
- ⚠️ **同一张表的抓取必须串行化**（进程内互斥），防两人同时点同一张表 ⇒ 双份顶号 + 重复写入。
- ⚠️ 登录含 **强踢**（KillOnlineUser）：登录走 `http_login(allow_kick=...)`，由调用方显式授权；
  **缓存命中的路径根本不登录 ⇒ 不涉及强踢，与 `allow_kick` 的授权语义不冲突**。

⚠️ 本模块**不含任何业务取值**；业务字段一律回《说明书》/ i8 响应。
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.core.config import get_settings, i8_base_of
from app.core.errors import ExternalServiceError, MustReportError, NotConfiguredError
from app.core.identity import current_i8_credentials
from app.core.logging import get_logger
from app.mod02_i8 import cookie_store
from app.mod02_i8.login import AUTH_FAILED, I8AuthFailedError, http_login
from app.mod02_i8.origin import _origin_of

logger = get_logger()

# 同表抓取串行锁登记表（D9：同一张表抓取互斥）
_TABLE_LOCKS: dict[str, threading.Lock] = {}

#: ⚠️ 给**用户**看的那句话（守则 §3.1 细节不上屏 / §3.7 人话 ＋ 下一步）——
#:   具体是**哪个地址、什么状态码、返回了什么**，一律只进**运行日志**（`logger.warning`）。
#:   ⭐ 2026-10-01 `TAIL-211` 收尾：原先这里把 `path` / `HTTP {状态码}` / **响应原文前 200 字**拼进异常 ⇒ 直接上屏。
I8_TAKE_FAILED = "i8 那边的这次取数没成功 —— 请稍后重试；一直不行请联系维护人"
_TABLE_LOCKS_GUARD = threading.Lock()


def _table_lock(table: str) -> threading.Lock:
    with _TABLE_LOCKS_GUARD:
        return _TABLE_LOCKS.setdefault(table, threading.Lock())


@contextmanager
def serialize_fetch(table: str):
    """同一张表的抓取串行化（进程内互斥）。`table` 形如 'payment_notice' / 'print_design'。"""
    lock = _table_lock(table)
    acquired = lock.acquire(timeout=600)
    if not acquired:
        raise ExternalServiceError(f"同表抓取互斥等待超时（{table}）")
    try:
        yield
    finally:
        lock.release()


class I8OnlineConflictError(ExternalServiceError):
    code = "i8_online_conflict"
    http_status = 409


@dataclass(frozen=True)
class HttpSessionPolicy:
    base_url: str
    credentials: tuple[str, str] = field(repr=False)
    take_kick_permission: Callable[[], bool]


http_session_policy: ContextVar[HttpSessionPolicy | None] = ContextVar("i8_http_session_policy", default=None)


class I8Client:
    """持会话的 i8 客户端。

    - 首次请求前取 Cookie：**优先读磁盘缓存**（命中 ⇒ 不登录）；无缓存才惰性登录。
    - 登录成功 ⇒ 把 Cookie 落盘缓存（下次直接复用，不登录、不顶号）。
    - 遇 401（会话失效）重登一次后重试；**仅一次**，重登仍失败 ⇒ 直接抛（不重试循环）。
    - 网络异常 ⇒ 直接抛（不重试）。
    """

    def __init__(self, *, allow_kick: bool = False, policy: HttpSessionPolicy | None = None) -> None:
        self._allow_kick = allow_kick
        self._policy = policy
        self._base = policy.base_url if policy else None
        self._cookie: str | None = None
        self._session: httpx.Client | None = None
        self._lock = threading.Lock()
        # ⭐ i8 凭据**惰性取**（`_creds()`）—— ⛔ 不在 `__init__` 里取：
        #   9 个生产构造点因此**一行都不用改**，而"用哪份凭据"这件事只有一个出口。
        self._i8_creds: tuple[str, str] | None = policy.credentials if policy else None

    def _creds(self) -> tuple[str, str]:
        """本次操作用哪个 i8 账号 ＋ 密码 —— ⭐ **当前登录用户绑定的那一份**（§7.8「每人一份」）。

        ⚠️ 未登录 / 查无此人 ⇒ `current_i8_credentials()` 回落 `.env`（过渡期口径）；
           ⭐ **有身份却没绑 i8 ⇒ 它直接抛 `MustReportError`**（`TAIL-202` · 2026-09-30：
           拿共享账号去登录会顶掉同事的在线会话、执行记录也记错人）—— 这里**不吞**那个异常。
        ⚠️ **一个客户端实例只解析一次**：`_ensure_cookie` 与 `_login` 必须用**同一份**凭据，
           否则 401 重登时可能换了个账号去登（那就是"两个人在同一批数据上互相顶号"）。
        ⚠️ 它同时决定 **cookie 缓存文件**（`cookie_store` 按账号分文件）⇒
           **两个账号各缓存各的**：A 的会话不会被 B 用掉，也不会互相顶号。
        """
        if self._i8_creds is None:
            self._i8_creds = current_i8_credentials()
        return self._i8_creds

    # --- 内部 ---
    def _base_url(self) -> str:
        if self._base is None:
            self._base = i8_base_of(get_settings())
        if not _origin_of(self._base):
            raise NotConfiguredError("i8 服务地址无效，请核对工作台设置。")
        return self._base

    def _ensure_session(self) -> httpx.Client:
        if self._session is None:
            self._session = httpx.Client(
                base_url=self._base_url(),
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "X-Requested-With": "XMLHttpRequest",
                },
                follow_redirects=self._policy is None,
            )
        return self._session

    def _ensure_cookie(self) -> None:
        """首次请求前取 cookie：⭐ **优先用磁盘缓存**（命中 ⇒ **不登录**）；无缓存才登录。

        ⚠️ 缓存命中时**根本不登录** ⇒ 自然不涉及强踢 —— 这是对的，与 `allow_kick` 的
           「须显式授权才踢人」授权语义**不冲突、也不绕过**（强踢只可能发生在真正登录那一步）。
        """
        cached = cookie_store.load(self._creds()[0], _origin_of(self._base_url()))
        if cached:
            logger.info("i8 会话：命中磁盘缓存（不登录）")
            self._cookie = cached
            return
        self._login()

    def _login(self) -> None:
        user, password = self._creds()
        allow_kick = self._policy.take_kick_permission() if self._policy else self._allow_kick
        base_url = self._base_url()
        result = http_login(
            user=user, password=password, allow_kick=allow_kick,
            base_url=base_url, follow_redirects=self._policy is None,
        )
        if not result.ok:
            if result.conflict and not allow_kick:
                raise I8OnlineConflictError("该 i8 账号已有在线会话，本次未强踢。请先退出其他会话，或重新确认并允许强踢。")
            raise I8AuthFailedError(AUTH_FAILED)
        self._cookie = result.cookie
        cookie_store.save(result.cookie, source="http_login", user=user, origin=_origin_of(base_url))

    def _apply_cookie(self) -> None:
        if self._session is not None and self._cookie:
            self._session.headers["Cookie"] = self._cookie

    @staticmethod
    def _is_session_invalid(resp: httpx.Response) -> bool:
        """会话是否失效。

        ⚠️⚠️ **2026-09-19 实测修正（两处，都是"静默出错"级）**：
        ① i8 在某些接口上**不用 401** 表达会话失效 —— 它回
           **HTTP 200 ＋ `{"Code": 0 或 200, "Success": false, "Msg": "No SessionInfo found"}`**
           （错误藏在 body 里）。只判 401 ⇒ **cookie 失效时"成功"返回空数据**：
           不报错、不重登、不提示，表现就是「抓取成功但 0 条」。
           ⚠️ 叠加 `cookie_store` 缓存后更危险：缓存命中 ⇒ **根本不登录**
           ⇒ 一个**已失效的 cookie 会被反复使用**（2026-09-19 实际踩到两次）。
        ② `Code` 是**字符串**（`'200'` / `'0'`），原来的 `body.get("Code") == 401`
           拿 int 去比 ⇒ **恒为假** ⇒ 那条判断**从来没生效过**。
        """
        if resp.status_code == 401:
            return True
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(body, dict):
            return False
        if str(body.get("Code")) == "401":
            return True
        return "no sessioninfo" in str(body.get("Msg") or body.get("msg") or "").lower()

    # --- 公共请求 ---
    def request(self, method: str, path: str, *, retry_expired: bool = True, **kwargs: Any) -> httpx.Response:
        """发请求，默认允许会话失效后重登一次。"""
        with self._lock:
            session = self._ensure_session()
            if httpx.URL(path).is_absolute_url and _origin_of(path) != _origin_of(str(session.base_url)):
                raise MustReportError("i8 站点已变化，请重新发起本次操作。")
            if self._cookie is None:
                self._ensure_cookie()
            self._apply_cookie()

            resp = session.request(method, path, **kwargs)
            if retry_expired and self._is_session_invalid(resp):
                # ⚠️ 仅重登一次（D9：不得自动重试登录循环）
                logger.warning("i8 会话失效（401 或 body 报 No SessionInfo），尝试重登一次")
                self._login()                       # 成功后已更新缓存
                self._apply_cookie()
                resp = session.request(method, path, **kwargs)
                if self._is_session_invalid(resp):
                    # 刚写入的 cookie 已知不可用 ⇒ 从缓存抹掉（否则下次进程启动会先拿它白撞一次 401）。
                    # ⚠️ 这不改判定：异常照旧抛，只是顺手清掉一个**已被证伪**的凭证。
                    cookie_store.clear(self._creds()[0], _origin_of(self._base_url()))
                    logger.warning("i8 会话重登后仍无效（401）")
                    raise I8AuthFailedError(AUTH_FAILED)
            return resp

    def get_json(self, path: str, **kwargs: Any) -> Any:
        resp = self.request("GET", path, **kwargs)
        if resp.status_code >= 400:
            logger.warning("i8 取数失败：%s → HTTP %s：%s", path, resp.status_code, resp.text[:200])
            raise ExternalServiceError(I8_TAKE_FAILED)
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            logger.warning("i8 取数返回的不是 JSON：%s → %s", path, resp.text[:200])
            raise ExternalServiceError(I8_TAKE_FAILED) from exc

    def post_json(self, path: str, **kwargs: Any) -> Any:
        resp = self.request("POST", path, **kwargs)
        if resp.status_code >= 400:
            logger.warning("i8 取数失败：%s → HTTP %s：%s", path, resp.status_code, resp.text[:200])
            raise ExternalServiceError(I8_TAKE_FAILED)
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            logger.warning("i8 取数返回的不是 JSON：%s → %s", path, resp.text[:200])
            raise ExternalServiceError(I8_TAKE_FAILED) from exc

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
