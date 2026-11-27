"""Read and update the notice printer address and channel in the shared settings file."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import ENV_FILE, get_settings
from app.core.errors import MustReportError

# ipp://host[:port][/path] · ipps://… · http(s)://…（IPP over HTTP 传输形态）
_URI_RE = re.compile(r"^(?:ipp|ipps|https?)://[^\s/]+(?:/\S*)?$", re.IGNORECASE)

_KEY = "PRINTER_IPP_URL"
_MODE_KEY = "PRINT_MODE"


def configured_print_mode(saved: str, override: str | None = None) -> str:
    """Only an explicit override can replace a saved device choice."""
    requested = (override or "").strip().lower()
    value = saved.strip().lower() if requested in ("", "auto") else requested
    return "ipp" if value in ("", "auto") else value


def require_ipp(channel: str) -> None:
    if channel != "ipp":
        label = {"driver": "系统驱动", "raw": "RAW 9100"}.get(channel, channel)
        raise MustReportError(f"出纸通道「{label}」无法用于 A4 打印。请明确改用 IPP，或导出 PDF。")


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


def apply_printer_setting(uri: str, *, mode: str | None = None, env_path: Path | None = None) -> dict:
    """Validate both settings before changing the file; preserve unrelated entries."""
    value = validate_printer_uri(uri)
    channel = configured_print_mode(get_settings().print_mode, mode)
    require_ipp(channel)
    path = env_path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    want = {_KEY: value, _MODE_KEY: channel}
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in want:
            out.append(f"{key}={want[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in want.items():              # 文件里没有的键 ⇒ 补在末尾
        if key not in seen:
            out.append(f"{key}={val}")

    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    get_settings.cache_clear()  # 即时生效（001-02）
    return {"printer_ipp_url": value, "print_mode": channel}
