"""Best-effort disk cache for HTTP cookies scoped to their i8 account and site."""

from __future__ import annotations

import json
import os
import time
from hashlib import sha256
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings, i8_base_of
from app.core.logging import get_logger
from app.mod02_i8.origin import _origin_of

logger = get_logger()

CACHE_DIR: Path = PROJECT_ROOT / "var" / "state" / "i8_cookie"
DEFAULT_ACCOUNT = "default"


def _account(user: str | None) -> str:
    return (user or get_settings().i8_user or "").strip() or DEFAULT_ACCOUNT


def _cache_origin(origin: str | None) -> str:
    return _origin_of(i8_base_of(get_settings()) if origin is None else origin)


def cookie_path(user: str | None = None, origin: str | None = None) -> Path:
    """Use a stable key without filename collisions between accounts or sites."""
    identity = json.dumps([_account(user), _cache_origin(origin)])
    return CACHE_DIR / f"{sha256(identity.encode('utf-8')).hexdigest()}.json"


def load_meta(user: str | None = None, origin: str | None = None) -> tuple[str | None, str, str]:
    """Read a credential and its metadata only if the site is known and matches."""
    origin = _cache_origin(origin)
    if not origin:
        return None, "", ""
    path = cookie_path(user, origin)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "", ""
    if isinstance(data, dict) and data.get("origin") == origin and data.get("cookie"):
        return str(data["cookie"]), str(data.get("fetched_at") or ""), str(data.get("source") or "")
    return None, "", ""


def load(user: str | None = None, origin: str | None = None) -> str | None:
    cookie, _, _ = load_meta(user, origin)
    return cookie


def save(cookie: str, *, source: str = "http_login", user: str | None = None,
         origin: str | None = None) -> Path | None:
    cookie = str(cookie or "").strip()
    origin = _cache_origin(origin)
    if not cookie or not origin:
        return None
    path = cookie_path(user, origin)
    payload = {
        "cookie": cookie,
        "origin": origin,
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


def clear(user: str | None = None, origin: str | None = None) -> bool:
    origin = _cache_origin(origin)
    if not origin:
        return False
    try:
        cookie_path(user, origin).unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("i8 cookie 缓存删除失败：{}", exc)
        return False


def _restrict(path: Path) -> None:
    """Restrict the file to its owner where chmod supports it."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
