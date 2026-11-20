"""Explicit i8 session selection and operation-scoped HTTP kick confirmation."""

from __future__ import annotations

import json
import secrets
import time
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from app.core.config import get_settings, i8_base_of
from app.core.errors import MustReportError, NotConfiguredError
from app.core.identity import current_i8_credentials
from app.mod02_i8.browser_relay import MODE_BROWSER, relay_scope, resolve_mode
from app.mod02_i8.browser_session import _origin_of
from app.mod02_i8.client import HttpSessionPolicy, I8OnlineConflictError, http_session_policy

KICK_TOKEN_TTL = 120
_TokenBinding = tuple[str, str, str, str, str]

# The workbench runs one worker, like the browser broker. Restarting invalidates confirmations.
_tokens: dict[str, tuple[_TokenBinding, float]] = {}
_token_lock = Lock()


def _issue_token(binding: _TokenBinding) -> str:
    token = secrets.token_urlsafe(32)
    with _token_lock:
        now = time.monotonic()
        for expired in [key for key, (_, end) in _tokens.items() if end <= now]:
            del _tokens[expired]
        _tokens[token] = (binding, now + KICK_TOKEN_TTL)
    return token


def _consume_token(token: str, binding: _TokenBinding) -> None:
    with _token_lock:
        stored = _tokens.get(token)
        if stored and stored[0] == binding and stored[1] > time.monotonic():
            del _tokens[token]
            return
    raise MustReportError("本次 i8 下线确认已失效，请重新发起原操作。")


def revoke_kick_token(token: str, *, owner: str) -> None:
    """Discard a pending confirmation owned by the authenticated account."""
    with _token_lock:
        stored = _tokens.get(token)
        if stored and stored[0][0] == owner:
            del _tokens[token]


@contextmanager
def unified_i8_session(
    payload: object, *, owner: str, operation: str, scope: dict,
) -> Iterator[None]:
    """Run the operation using clients from `open_i8_client` and server-owned scope values.

    HTTP binds the actual destination and credentials for the entire operation.
    An accepted token permits one kick-capable login attempt across its clients.
    """
    def get(key: str) -> str:
        return payload.get(key, "") if isinstance(payload, dict) else getattr(payload, key, "")

    mode = resolve_mode(get("session_mode"))
    token = get("kick_token")
    if mode == MODE_BROWSER:
        if token:
            raise MustReportError("请重新发起操作。浏览器会话无需确认其他会话下线。")
        with relay_scope(mode, get("device_id"), owner=owner):
            yield
        return

    if not owner:
        raise MustReportError("请登录工作台后重新发起 i8 操作。")
    base_url = i8_base_of(get_settings())
    origin = _origin_of(base_url)
    if not origin:
        raise NotConfiguredError("i8 服务地址无效，请核对工作台设置。")
    user, password = current_i8_credentials()
    if not user.strip():
        raise MustReportError("当前账号未绑定 i8，请先在设置中核对绑定。")
    canonical_scope = json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    binding = (owner, origin, user.strip(), operation, canonical_scope)
    if token:
        _consume_token(token, binding)

    can_kick = bool(token)
    allowance_lock = Lock()

    def take_kick_permission() -> bool:
        nonlocal can_kick
        with allowance_lock:
            allowed, can_kick = can_kick, False
            return allowed

    context_token = http_session_policy.set(HttpSessionPolicy(base_url, (user, password), take_kick_permission))
    try:
        with relay_scope(mode):
            yield
    except I8OnlineConflictError as exc:
        if token:
            raise
        raise I8OnlineConflictError(
            "该 i8 账号已有在线会话。请确认是否让现有会话下线并继续本次操作。",
            detail={"kick_token": _issue_token(binding)},
        ) from exc
    finally:
        with allowance_lock:
            can_kick = False
        http_session_policy.reset(context_token)
