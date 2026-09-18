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
from typing import Any

import httpx

from app.core.config import get_settings, i8_base_of
from app.core.errors import ExternalServiceError, NotConfiguredError
from app.core.logging import get_logger
from app.mod02_i8 import cookie_store
from app.mod02_i8.login import http_login

logger = get_logger()

# 同表抓取串行锁登记表（D9：同一张表抓取互斥）
_TABLE_LOCKS: dict[str, threading.Lock] = {}
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


class I8Client:
    """持会话的 i8 客户端。

    - 首次请求前取 Cookie：**优先读磁盘缓存**（命中 ⇒ 不登录）；无缓存才惰性登录。
    - 登录成功 ⇒ 把 Cookie 落盘缓存（下次直接复用，不登录、不顶号）。
    - 遇 401（会话失效）重登一次后重试；**仅一次**，重登仍失败 ⇒ 直接抛（不重试循环）。
    - 网络异常 ⇒ 直接抛（不重试）。
    """

    def __init__(self, *, allow_kick: bool = False) -> None:
        self._allow_kick = allow_kick
        self._cookie: str | None = None
        self._session: httpx.Client | None = None
        self._lock = threading.Lock()

    # --- 内部 ---
    def _ensure_session(self) -> httpx.Client:
        if self._session is None:
            settings = get_settings()
            base = i8_base_of(settings)
            if not base:
                raise NotConfiguredError("I8_BASE_URL 未配置（见 .env.example）")
            self._session = httpx.Client(
                base_url=base,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "X-Requested-With": "XMLHttpRequest",
                },
                follow_redirects=True,
            )
        return self._session

    def _ensure_cookie(self) -> None:
        """首次请求前取 cookie：⭐ **优先用磁盘缓存**（命中 ⇒ **不登录**）；无缓存才登录。

        ⚠️ 缓存命中时**根本不登录** ⇒ 自然不涉及强踢 —— 这是对的，与 `allow_kick` 的
           「须显式授权才踢人」授权语义**不冲突、也不绕过**（强踢只可能发生在真正登录那一步）。
        """
        cached = cookie_store.load()
        if cached:
            logger.info("i8 会话：命中磁盘缓存（不登录）")
            self._cookie = cached
            return
        self._login()

    def _login(self) -> None:
        result = http_login(allow_kick=self._allow_kick)
        if not result.ok:
            raise ExternalServiceError(f"i8 登录失败：{result.detail}")
        self._cookie = result.cookie
        cookie_store.save(result.cookie, source="http_login")     # ⭐ 登录成功 ⇒ 落盘复用

    def _apply_cookie(self) -> None:
        if self._session is not None and self._cookie:
            self._session.headers["Cookie"] = self._cookie

    @staticmethod
    def _is_session_invalid(resp: httpx.Response) -> bool:
        if resp.status_code == 401:
            return True
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            return False
        return isinstance(body, dict) and body.get("Code") == 401

    # --- 公共请求 ---
    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """发请求；401 时重登一次重试；其余一律不重试。"""
        with self._lock:
            session = self._ensure_session()
            if self._cookie is None:
                self._ensure_cookie()
            self._apply_cookie()

            resp = session.request(method, path, **kwargs)
            if self._is_session_invalid(resp):
                # ⚠️ 仅重登一次（D9：不得自动重试登录循环）
                logger.warning("i8 会话失效（401），尝试重登一次")
                self._login()                       # 成功后已更新缓存
                self._apply_cookie()
                resp = session.request(method, path, **kwargs)
                if self._is_session_invalid(resp):
                    # 刚写入的 cookie 已知不可用 ⇒ 从缓存抹掉（否则下次进程启动会先拿它白撞一次 401）。
                    # ⚠️ 这不改判定：异常照旧抛，只是顺手清掉一个**已被证伪**的凭证。
                    cookie_store.clear()
                    raise ExternalServiceError("i8 会话重登后仍无效（401）")
            return resp

    def get_json(self, path: str, **kwargs: Any) -> Any:
        resp = self.request("GET", path, **kwargs)
        if resp.status_code >= 400:
            raise ExternalServiceError(f"i8 接口 {path} 返回 HTTP {resp.status_code}：{resp.text[:200]}")
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(f"i8 接口 {path} 响应非 JSON：{resp.text[:200]}") from exc

    def post_json(self, path: str, **kwargs: Any) -> Any:
        resp = self.request("POST", path, **kwargs)
        if resp.status_code >= 400:
            raise ExternalServiceError(f"i8 接口 {path} 返回 HTTP {resp.status_code}：{resp.text[:200]}")
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(f"i8 接口 {path} 响应非 JSON：{resp.text[:200]}") from exc

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
