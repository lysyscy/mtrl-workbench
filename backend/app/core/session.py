"""登录会话 —— **自签 cookie**（`hmac` ＋ `sha256`，stdlib）。

依据：《说明书》§1.5.1（「**登出** = 用户管理页提供登出入口；退出后**回到登录页**，
**业务数据不受影响**」）· `MOD-15`。

⚠️⚠️ **为什么自己签、不引中间件**：
   Starlette 有 `SessionMiddleware`，但它依赖 `itsdangerous`，而本工程的
   `requirements.txt` **没有**它 ⇒ 引中间件 = **加一个依赖**。
   ⭐ 本仓在别处（`sm2_crypto`）也有"够用就自己写"的先例 ⇒ 这里用 stdlib 的
   `hmac` ＋ `hashlib` ＋ `secrets` 自签，**零新依赖**、行为完全看得见。

⚠️⚠️ **密钥绝不硬编码** —— `core/config.py` 开篇就是这条底线
   （「凭据只来自环境变量 / `.env`（工程底线·安全：**绝对禁止硬编码**）」）。
   ⇒ `SESSION_SECRET` 从 `.env` 读；**为空时**自动生成一个随机密钥并**写回 `.env`**（只做一次）。
   ⭐ 为什么是"写回 `.env`"而不是"每次启动随机生成"：后者一重启所有人的登录态就失效，
      而本系统是**每天要用的工具** ⇒ 那种"随机"只会让人想把它关掉（比配一次更糟）。

⚠️ 会话**载荷**只有 `账号名 + 过期时间`，用 `|` 连接后签名 ⇒ 形态 `账号.过期戳.签名`。
   ⛔ **不放角色**：角色可能会变（转让管理员）⇒ 放进 cookie 就有一份**过期的真相**；
      要用角色时**每次查库**（本系统 2 个账号，查一次的成本可以忽略）。
"""

from __future__ import annotations

import base64
import contextvars
import datetime as _dt
import hashlib
import hmac
import pathlib
import secrets

from app.core.logging import get_logger

logger = get_logger()

COOKIE_NAME = "mw_session"
#: 会话有效期（小时）。⚠️ **口径没写这个数**（§1.5.1 只说"退出后回到登录页"）⇒
#: 取一个"工作日够用、过夜失效"的值，并**登记为待裁定**（⛔ 不假装它来自口径）。
SESSION_HOURS = 12

_SECRET_FILE_KEY = "SESSION_SECRET"

#: 当前请求的操作人（由 `middleware` 从 cookie 解出后写入）——
#: ⚠️ 用 `ContextVar` 而**不是全局变量**：`uvicorn` 是并发的，全局变量会**串号**
#: （A 的请求读到 B 的名字 ⇒ 留痕写错人，而且**不报错**）。
_current_name: contextvars.ContextVar[str] = contextvars.ContextVar("mw_current_name", default="")


# ------------------------------------------------------------------ 密钥


def _env_path() -> pathlib.Path:
    from app.core.config import ENV_FILE

    return ENV_FILE


def _read_secret_from_env_file() -> str:
    p = _env_path()
    if not p.exists():
        return ""
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith(f"{_SECRET_FILE_KEY}="):
            return ln.split("=", 1)[1].strip()
    return ""


def _append_secret_to_env_file(value: str) -> None:
    """把新生成的密钥**追加**写进 `.env`（⛔ 不覆盖别的行、⛔ 不重排文件）。"""
    p = _env_path()
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if old and not old.endswith("\n"):
        old += "\n"
    p.write_text(old + f"\n# 登录会话签名密钥（首次启动自动生成 · 换掉它 = 所有人需要重新登录）\n"
                      f"{_SECRET_FILE_KEY}={value}\n", encoding="utf-8")


def secret() -> bytes:
    """会话签名密钥（**唯一出口**）。为空 ⇒ 生成一个、写回 `.env`、并用它。"""
    from app.core.config import get_settings

    got = (get_settings().session_secret or "").strip() or _read_secret_from_env_file()
    if got:
        return got.encode("utf-8")
    made = secrets.token_urlsafe(48)
    try:
        _append_secret_to_env_file(made)
        logger.warning("已生成 `SESSION_SECRET` 并写入 .env（首次启动）—— 换掉它会让所有人需重新登录")
    except OSError as e:                                       # noqa: BLE001
        # ⚠️ 写不进去也不能崩：本次进程内**临时**用一个随机密钥（重启后失效 ⇒ 需重新登录）
        logger.warning("写 .env 失败（{}）⇒ 本次进程使用临时密钥（重启后需重新登录）", e)
    return made.encode("utf-8")


# ------------------------------------------------------------------ 签名 / 验签


def _sign(payload: str) -> str:
    mac = hmac.new(secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def make(account: str, *, now: _dt.datetime | None = None) -> str:
    """造一张会话票：`base64(账号).过期时间戳.签名`。

    ⚠️ 账号名**先 base64** 再拼 —— 否则账号名里若含 `.`（§1.5.1 明说**不限字符**）
       会把 `split(".")` 切错位置 ⇒ **验签永远失败**（那种 bug 只在"账号名带点"时出现，
       而"不限制字符"意味着它**迟早会出现**）。
    """
    now = now or _dt.datetime.now()
    exp = int((now + _dt.timedelta(hours=SESSION_HOURS)).timestamp())
    acc = base64.urlsafe_b64encode(account.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{acc}.{exp}"
    return f"{payload}.{_sign(payload)}"


def read(value: str | None, *, now: _dt.datetime | None = None) -> str | None:
    """验签 ＋ 查过期 ⇒ 账号名；任何不对都返回 `None`（⛔ 不抛 —— 调用方只需判"有没有登录"）。

    ⚠️ 验签用 `hmac.compare_digest`（**定长比较**）—— ⛔ 别用 `==`：
       后者会在第一个不同的字节就返回，理论上可从耗时推出签名（那是本仓少见的"顺手做对"）。
    """
    if not value:
        return None
    parts = (value or "").split(".")
    if len(parts) != 3:
        return None
    acc_b64, exp_s, sig = parts
    if not hmac.compare_digest(_sign(f"{acc_b64}.{exp_s}"), sig):
        return None
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if (now or _dt.datetime.now()).timestamp() > exp:
        return None
    pad = "=" * (-len(acc_b64) % 4)
    try:
        return base64.urlsafe_b64decode(acc_b64 + pad).decode("utf-8")
    except Exception:                                          # noqa: BLE001
        return None


# ------------------------------------------------------------------ 当前操作人（请求级）


def set_current_name(name: str) -> None:
    """由**中间件**调用：把本请求的登录用户名放进上下文。"""
    _current_name.set(name or "")


def current_name() -> str:
    """本请求的登录用户名（**未登录 = 空串**）。"""
    return _current_name.get() or ""


__all__ = [
    "COOKIE_NAME", "SESSION_HOURS", "current_name", "make", "read",
    "secret", "set_current_name",
]
