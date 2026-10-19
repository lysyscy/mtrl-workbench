"""`MOD-02` 横切：i8 **Cookie 的磁盘缓存**（唯一出口）—— 免「每次导出都撞单会话登录」。

## 为什么要有它
i8 侧是**单会话**：该账号已有在线会话时登录被拒（除非调用方显式 `allow_kick=True` 强踢）。
`I8Client` 的 cookie 原本**只存在实例内存里** ⇒ **每个新 `I8Client()` 实例首次请求都要登录一次**
⇒ **导出**（高频操作）几乎次次撞会话。把 cookie **落盘缓存**后：**有缓存直接用、根本不登录**，
只在「缓存缺失 / 会话失效（401）」时才登录 —— 登录次数少 ⇒ 顶号风险小。

## 三段式（照交付面素材包 `common_export.py`，**只借鉴接口形态**，口径不反推）
- `cookie_path(user)` → `var/state/i8_cookie/<账号>.json`（**按账号分文件**；账号缺省回退 `I8_USER`）
- `load(user)` / `load_meta(user)` → 读 cookie（**兼容旧纯文本格式**，见 `load_meta`）
- `save(cookie, source=…, user=…)` → 写 `{"cookie": …, "fetched_at": …, "source": …}`
- `clear(user)` → 删缓存文件

## ⚠️ 三条纪律
1. **cookie 是凭证** ⇒ 落点 `artifacts/` 由 `.gitignore`（`artifacts/*` ＋ 显式的 `var/state/i8_cookie/`）
   忽略；本模块**不 commit、不打印 cookie**；写盘后尽量收紧权限（`0o600`，Windows 上为尽力而为）。
2. **缓存是优化、不是功能** ⇒ 读 / 写 / 删**失败一律不抛**，只记 `warning`、退回「无缓存」。
   （若让缓存异常打断抓取，等于用"锦上添花"砸了"主流程"。）
3. 本模块**只做文件读写**，**不连 i8、不判"有效 / 失效"** —— 失效判定在 `I8Client` 的 401 分支。

## 主动探测：**不做**（取舍写在这里）
素材包的 `probe_cookie` 会在用缓存前**先打一次轻量请求**（`getList limit=1`）判 cookie 是否有效。
本仓**不搬这一层**，理由：
1. **兜底已有**：`I8Client` 的「401 ⇒ 重登**一次**」已经能发现并恢复失效（重登成功即更新缓存）；
   再叠一层探测，等于每次导出都**多打一次 i8**（多一次上行、多一个失败面），收益只是"把发现时机提前一点"。
2. **口径耦合**：素材包的探测绑在 `PaymentBill/getList` 的 form 细节上，本仓未复刻那条口径 ——
   硬搬会把「接口口径」耦合进缓存层，违背「**只加缓存、不改判定**」。
⇒ 失效发现由 `I8Client` 的 401 分支负责；**本模块只读写文件**。

## 与素材包的**一处刻意不同（并说明理由）**
素材包把 cookie 文件平铺在 `var/cache/信息化cookie_<账号>.json`（前置词把命名空间写在文件名里）；
本仓改为**子目录专属命名空间** `var/state/i8_cookie/<账号>.json`（目录已表明"这是 i8 cookie"，
文件名只留账号 ⇒ 更短、更清楚）。**三段式的接口形态与旧格式兼容行为保持不变**。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings
from app.core.logging import get_logger

logger = get_logger()

#: 缓存落点（**模块级常量** —— 测试用 `monkeypatch.setattr` 换到临时目录，不必碰真实盘）
CACHE_DIR: Path = PROJECT_ROOT / "var" / "state" / "i8_cookie"

#: 账号解析不到时的中性回退名（素材包回退 `LOGIN_USER` 常量；本仓无此常量，用一个中性占位）
DEFAULT_ACCOUNT = "default"


def _account(user: str | None) -> str:
    """解析账号：显式传入优先，否则取 `I8_USER`；都没有 ⇒ `DEFAULT_ACCOUNT`。"""
    u = (user or get_settings().i8_user or "").strip()
    return u or DEFAULT_ACCOUNT


def _safe_name(name: str) -> str:
    """账号 → 安全文件名（只留字母 / 数字 / `_` / `-`；其余替换为 `_`）。

    照素材包 `_cookie_path` 的口径：**别让账号里的怪异字符跑进路径**（防目录穿越）。
    """
    safe = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in name)
    return safe or DEFAULT_ACCOUNT


def cookie_path(user: str | None = None) -> Path:
    """该账号的缓存文件路径 —— **唯一出口**（`load`/`save`/`clear` 都走它，⛔ 别各自拼一份）。"""
    return CACHE_DIR / f"{_safe_name(_account(user))}.json"


def load_meta(user: str | None = None) -> tuple[str | None, str, str]:
    """读缓存 → `(cookie, fetched_at, source)`。

    - **新格式**（JSON `{"cookie": …, "fetched_at": …, "source": …}`）：原样返回三项。
    - **旧纯文本格式**（整个文件就是一行 cookie）：返回 `(cookie, "", "legacy")` —— 向后兼容。
    - 文件不存在 / 空 / 格式不认 ⇒ `(None, "", "")`（**不猜**，当作无缓存）。
    """
    path = cookie_path(user)
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, "", ""
    if not raw:
        return None, "", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "", "legacy"        # 旧纯文本格式，向后兼容
    if isinstance(data, dict) and data.get("cookie"):
        return (
            str(data["cookie"]),
            str(data.get("fetched_at") or ""),
            str(data.get("source") or ""),
        )
    logger.warning("i8 cookie 缓存格式不认（{}）—— 当无缓存", path.name)
    return None, "", ""


def load(user: str | None = None) -> str | None:
    """读缓存 cookie 字符串；无 / 空 / 不认 ⇒ `None`（兼容旧纯文本格式）。"""
    cookie, _, _ = load_meta(user)
    return cookie


def save(cookie: str, *, source: str = "http_login", user: str | None = None) -> Path | None:
    """把 cookie 落盘（JSON：`cookie` / `fetched_at` / `source`）→ 返回写入路径。

    - 空 cookie ⇒ 不写、返回 `None`（⛔ 不写空凭证）。
    - ⚠️ **写失败不抛**（缓存是优化）：只记 `warning` 并返回 `None`。
    """
    c = str(cookie or "").strip()
    if not c:
        return None
    path = cookie_path(user)
    payload = {
        "cookie": c,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _restrict(path)
    except OSError as exc:
        logger.warning("i8 cookie 缓存写入失败（不影响本次抓取）：{}", exc)
        return None
    return path


def clear(user: str | None = None) -> bool:
    """删除该账号的缓存文件；确实删掉了 ⇒ `True`（文件本就不在 / 删不掉 ⇒ `False`，**不抛**）。"""
    path = cookie_path(user)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("i8 cookie 缓存删除失败：{}", exc)
        return False


def _restrict(path: Path) -> None:
    """尽量把缓存文件收紧到「仅属主可读写」（`0o600`）。

    ⚠️ POSIX 上有效；Windows 的 `chmod` 对 ACL 影响有限 ⇒ **尽力而为、失败不抛**
    （真正的访问控制在部署期收紧目录权限）。
    """
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


__all__ = [
    "CACHE_DIR", "DEFAULT_ACCOUNT",
    "cookie_path", "load_meta", "load", "save", "clear",
]
