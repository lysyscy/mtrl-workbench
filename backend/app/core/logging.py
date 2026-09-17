"""日志（落盘 UTF-8）。

依据：技术栈 §3.1「日志」行 · 工程坑 1.5-20（脱敏口径）/ 1.5-21（权限与保留期）。

- 脱敏**仅**凭据类字段（password / token / cookie / secret / authorization…）→ `***`
- ⚠️ **业务数据（金额 / 供应商 / 项目名）一律保留** —— 二者不冲突
- 保留 ≤ 30 天；目录权限由部署期收紧（仅运行账户可读写）
"""

from __future__ import annotations

import re
import sys

from loguru import logger

from app.core.config import get_settings

_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "cookie",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "access_key",
)

_REDACT_RE = re.compile(
    r"(?i)\b(" + "|".join(_SENSITIVE_KEYS) + r")\b(\s*[=:]\s*)([^\s,;&'\"]+)"
)
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]+")


def redact(text: str) -> str:
    """把凭据类字段的值替换为 `***`（业务数据不动）。"""
    text = _REDACT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return _BEARER_RE.sub(lambda m: f"{m.group(1)} ***", text)


def _patcher(record: dict) -> None:
    record["message"] = redact(record["message"])


_configured = False


def setup_logging() -> None:
    """装配日志（幂等）：控制台 + 落盘文件。"""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_dir = settings.logs_path
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.configure(patcher=_patcher)

    # 控制台（stderr）
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | <level>{message}</level>"
        ),
        enqueue=False,
    )

    # 落盘（UTF-8）
    logger.add(
        str(log_dir / "app_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        encoding="utf-8",
        rotation="00:00",
        retention=f"{settings.log_retention_days} days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} | {message}",
        enqueue=True,  # 多进程/多线程安全
        backtrace=True,
        diagnose=False,  # 不在栈里 dump 变量，避免把凭据写进日志
    )

    _configured = True
    logger.info("日志已装配：dir={} retention={}d", log_dir, settings.log_retention_days)


def get_logger():
    return logger
