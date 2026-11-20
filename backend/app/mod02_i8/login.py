"""i8 纯 HTTP 登录：SM2 加密 + `SupLogin` +（**按需**）`KillOnlineUser`。

依据：
- 《材料科业务全流程说明书》**§3.1.2**（已实现纯 HTTP 登录、不依赖浏览器；Cookie 过期自动重登）
- 《技术栈选型分析》**§3.1**（i8 接入 = httpx）
- **用户裁定 D9**：登录含**强踢** ⇒ **抓取一律人工触发**、**失败不得自动重试登录**

⚠️ **强踢会挤掉该账号的其他在线会话** ⇒ 本模块把强踢做成**必须显式授权**：
   `allow_kick=False`（默认）时，探测到在线冲突就**直接返回失败**，绝不静默踢人。
⚠️ 本模块**不含任何重试循环** —— 反复重登 = 反复顶号（D9 明确禁止）。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

import httpx

from app.core.config import get_settings, i8_base_of
from app.core.errors import ExternalServiceError, NotConfiguredError
from app.core.logging import get_logger

logger = get_logger()


def sm2_encrypt(plain: str) -> str:
    from app.mod02_i8.sm2_crypto import sm2_encrypt as encrypt
    return encrypt(plain)

LOGIN_PATH = "/SUP/Login/SupLogin"
KICK_PATH = "/SUP/Login/KillOnlineUser"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


AUTH_FAILED = "i8 登录未成功，请核对「设置」页的 i8 凭据与网络后重试。"


class I8AuthFailedError(ExternalServiceError):
    code = "i8_auth_failed"


@dataclass
class LoginResult:
    ok: bool
    cookie: str = ""
    kicked_online: bool = False  # 本次是否执行了强踢（= 挤掉了别人的在线会话）
    conflict: bool = False  # 是否探测到该账号已有在线会话
    detail: str = ""


def _build_plain(user: str, password: str, sid: str, is_online_check: str | None = None) -> str:
    payload: dict[str, object] = {
        "orgCode": "",
        "isWeb": 1,
        "userId": user,
        "userPwd": password or "",
        "dataBase": "0001",
        "account": "0001",
        "CustomerCode": "0001",
        "language": "zh-Cn",
        "tm": str(int(time.time() * 1000)),
        "sid": sid,
    }
    if is_online_check is not None:
        payload["isOnlineCheck"] = is_online_check
    return json.dumps(payload, separators=(",", ":"))


def _online_conflict(text: str) -> dict | None:
    """第 1 次 `SupLogin` 的响应里是否含"在线冲突"信息（**含 sessionID 才能踢**）。"""
    try:
        resp = json.loads(text)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(resp, dict) or resp.get("success") or not resp.get("msg"):
        return None
    try:
        inner = json.loads(resp["msg"])
    except Exception:  # noqa: BLE001
        return None
    return inner if isinstance(inner, dict) and inner.get("sessionID") else None


def http_login(
    *,
    user: str | None = None,
    password: str | None = None,
    allow_kick: bool = False,
    base_url: str | None = None,
    follow_redirects: bool | None = None,
) -> LoginResult:
    """登录 i8，返回 `LoginResult`（**成功时** `cookie` 可用）。

    `allow_kick=True` 才允许强踢；工作台直连只在消费本次操作的下线确认后才允许。
    ⚠️ **不重试**：失败直接返回，由人工决定要不要再来一次。
    """
    settings = get_settings()
    base = i8_base_of(settings) if base_url is None else base_url
    if not base:
        raise NotConfiguredError("I8_BASE_URL 未配置（见 .env.example）")
    user = (user or settings.i8_user or "").strip()
    if not user:
        raise NotConfiguredError("I8_USER 未配置（见 .env.example）")
    password = settings.i8_password if password is None else password
    return login_at(
        base, user, password, encrypt=sm2_encrypt, allow_kick=allow_kick,
        follow_redirects=(base_url is None if follow_redirects is None else follow_redirects),
    )


def login_at(base, user, password, *, encrypt, allow_kick=False, follow_redirects=True):
    """用调用方选定的站点和凭据登录，供工作台和单机程序共用。"""
    sid = uuid.uuid4().hex
    session = httpx.Client(
        base_url=base, timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=follow_redirects
    )
    try:
        # ① 探测（若在线冲突，响应里带 sessionID / ipAddress）
        r1 = session.post(LOGIN_PATH, data={"body": encrypt(_build_plain(user, password, sid))})
        conflict = _online_conflict(r1.text)

        kicked = False
        if conflict:
            if not allow_kick:
                return LoginResult(
                    ok=False,
                    conflict=True,
                    detail=(
                        "该账号已有在线会话；本次**未执行强踢**"
                        "（需调用方显式授权 allow_kick=True）"
                    ),
                )
            # ② 强踢
            session.post(
                KICK_PATH,
                data={
                    "ipAddress": conflict.get("ipAddress") or "",
                    "sessionID": conflict["sessionID"],
                    "userId": conflict.get("userId") or "",
                    "account": conflict.get("uCode") or "0001",
                },
            )
            kicked = True
            logger.warning("i8 登录：已执行 KillOnlineUser 强踢（user={}）", user)

        # ③ 正式登录（isOnlineCheck=1）
        r2 = session.post(
            LOGIN_PATH, data={"body": encrypt(_build_plain(user, password, sid, "1"))}
        )
        cookie = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
        if not r2.is_success or "accesstoken" not in r2.text or not cookie:
            logger.warning("i8 登录失败（HTTP {}）：{}", r2.status_code, r2.text[:200])
            return LoginResult(ok=False, conflict=bool(conflict), kicked_online=kicked, detail=AUTH_FAILED)
        return LoginResult(
            ok=True,
            cookie=cookie,
            conflict=bool(conflict),
            kicked_online=kicked,
            detail="登录成功" + ("（已强踢该账号的其他在线会话）" if kicked else "（无在线冲突）"),
        )
    except httpx.HTTPError as exc:
        # ⚠️ 只报错、不重试（D9）
        logger.warning("i8 登录请求失败：{}", exc)
        return LoginResult(ok=False, detail=AUTH_FAILED)
    finally:
        session.close()
