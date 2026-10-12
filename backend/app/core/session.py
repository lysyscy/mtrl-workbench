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

⚠️ 新会话载荷为 `v2.base64(账号).时间戳.签名`，版本也参与签名。
   旧三段票统一拒绝，升级后重新登录一次；不换密钥、不改变账号或密码。
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
#: 浏览器持久cookie保存期限；Chrome将Max-Age/Expires上限限制为400天。
#: 服务器不再按时间过期（用户2026-10-12确认）；浏览器仍可清理cookie。
COOKIE_MAX_AGE_SECONDS = 400 * 24 * 3600


class AccountIdentity(str):
    """新会话的唯一账号；仍为字符串，便于既有调用者展示和比较。"""


_SECRET_FILE_KEY = "SESSION_SECRET"

#: 当前请求的账号身份（由中间件从 cookie 解出后写入；姓名由账号行提供）——
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
    """造一张账号会话票：`v2.base64(账号).签发时间戳.签名`。

    ⚠️ 账号名**先 base64** 再拼 —— 否则账号名里若含 `.`（§1.5.1 明说**不限字符**）
       会把 `split(".")` 切错位置 ⇒ **验签永远失败**（那种 bug 只在"账号名带点"时出现，
       而"不限制字符"意味着它**迟早会出现**）。
    """
    now = now or _dt.datetime.now()
    stamp = int(now.timestamp())
    acc = base64.urlsafe_b64encode(account.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"v2.{acc}.{stamp}"
    return f"{payload}.{_sign(payload)}"


def read(value: str | None, *, now: _dt.datetime | None = None) -> str | None:
    """只接受签名有效的v2账号会话，旧标签票统一拒绝；不按时间自动过期。

    时间字段仍须为整数且参与签名；已有v2票的原过期戳亦保留有效。
    now保留给既有调用者，验签不再依赖时钟。

    ⚠️ 验签用 `hmac.compare_digest`（**定长比较**）—— ⛔ 别用 `==`：
       后者会在第一个不同的字节就返回，理论上可从耗时推出签名（那是本仓少见的"顺手做对"）。
    """
    if not value:
        return None
    parts = (value or "").split(".")
    if len(parts) != 4 or parts[0] != "v2":
        return None
    _, acc_b64, exp_s, sig = parts
    if not hmac.compare_digest(_sign(".".join(parts[:-1])), sig):
        return None
    try:
        int(exp_s)  # 保留原时间字段的整数校验，不再用它判断过期。
    except ValueError:
        return None
    pad = "=" * (-len(acc_b64) % 4)
    try:
        identity = base64.urlsafe_b64decode(acc_b64 + pad).decode("utf-8")
        return AccountIdentity(identity) if identity.strip() else None
    except Exception:                                          # noqa: BLE001
        return None


# ------------------------------------------------------------------ 当前操作人（请求级）


def set_current_name(name: str) -> None:
    """由中间件调用：保留本请求身份的格式类型，显示姓名另由账号行取得。"""
    _current_name.set(name or "")


def current_name() -> str:
    """本请求的账号身份（未登录为空串；名称沿用既有调用者）。"""
    return _current_name.get() or ""


__all__ = [
    "AccountIdentity", "COOKIE_NAME", "COOKIE_MAX_AGE_SECONDS", "current_name", "make", "read",
    "secret", "set_current_name",
]
