"""打印机地址设置持久化（`ACC-PAY-SETUP-001`）。

依据（§4.6 + 用户 2026-09-15 裁定）：
- 001-01：系统内提供**可发现入口**修改打印机地址（入口在 `router.py`；本模块负责"改得对"）。
- 001-02：**保存后即时生效** —— 写 `.env` 后清 `get_settings` 缓存，下一次取配置即新值。
- 001-03：**持久化** —— 写回工程根 `.env`，服务重启后仍生效。
- 001-04：地址为空 / 格式非法 ⇒ **显式报错**，不得静默沿用旧值。
- 001-05：**只改打印机地址** —— 逐行改写，其余配置一字不动。

⚠️ 不引入新模块（用户裁定"零新模块"）：只写 `.env` 一行 + `cache_clear()`。
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import ENV_FILE, get_settings
from app.core.errors import MustReportError

# ipp://host[:port][/path] · ipps://… · http(s)://…（IPP over HTTP 传输形态）
_URI_RE = re.compile(r"^(?:ipp|ipps|https?)://[^\s/]+(?:/\S*)?$", re.IGNORECASE)

_KEY = "PRINTER_IPP_URL"


def validate_printer_uri(uri: str) -> str:
    """校验打印机地址（001-04）。返回规整后的值；非法即抛 `MustReportError`。"""
    value = (uri or "").strip()
    if not value:
        raise MustReportError("打印机地址不能为空 —— 请填写形如 ipp://192.168.5.248 的地址")
    if not _URI_RE.match(value):
        raise MustReportError(
            f"打印机地址格式非法：「{value}」"
            "（应形如 ipp://192.168.5.248 或 ipp://192.168.5.248:631/printers/xxx）"
        )
    return value


def apply_printer_setting(uri: str, *, env_path: Path | None = None) -> str:
    """把打印机地址写回 `.env` 并即时生效（001-02 / 001-03 / 001-05）。

    - 仅改写 `PRINTER_IPP_URL` 一行（001-05）；文件其余内容原样保留。
    - 写完 `get_settings.cache_clear()` ⇒ 下一次取配置即新值（001-02），无需重启。
    """
    value = validate_printer_uri(uri)  # 先校验：非法则不落盘、不静默（001-04）
    path = env_path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{_KEY}="):
            out.append(f"{_KEY}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{_KEY}={value}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    get_settings.cache_clear()  # 即时生效（001-02）
    return value
