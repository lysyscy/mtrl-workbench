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
_MODE_KEY = "PRINT_MODE"
_NAME_KEY = "PRINTER_NAME"

#: ⭐ **出纸通道**（`TAIL-46`-③）—— 口径照用户调好的 `i8一键打印_新版`（2026-09-18）：
#: `auto` = 依次试 IPP → 系统驱动 → RAW 9100（换任何打印机都能打，推荐）；
#: `ipp` = 只走标准 IPP（能确认打印机真的收件；Ricoh 用这条）；
#: `driver` = 走 Windows 打印驱动出纸（**最稳**，需本机装过该打印机驱动 ⇒ 必须给 `printer_name`）；
#: `raw` = 只走 RAW 9100（只对"自己能读 PDF"的打印机有意义，多数小型机会打乱码）。
PRINT_MODES: tuple[str, ...] = ("auto", "ipp", "driver", "raw")

#: 通道 → 中文（**只给人看**）
MODE_LABEL = {"auto": "自动（推荐）", "ipp": "IPP", "driver": "系统驱动", "raw": "RAW 9100"}


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


def validate_print_mode(mode: str, printer_name: str = "") -> str:
    """校验出纸通道（`TAIL-46`-③）。返回规整后的值；非法即抛。

    ⚠️ 选 `driver` **必须**给打印机名 —— 那条通道靠**本机驱动**出纸，不用 IP：
       不给名字就只能落到"系统默认打印机"，那不是用户选的意思（⛔ 不猜）。
    """
    value = (mode or "").strip().lower() or "auto"
    if value not in PRINT_MODES:
        raise MustReportError(
            f"出纸通道「{mode}」不认 —— 只能是 {' / '.join(PRINT_MODES)}"
            f"（{MODE_LABEL['auto']} / {MODE_LABEL['ipp']} / {MODE_LABEL['driver']} / {MODE_LABEL['raw']}）"
        )
    if value == "driver" and not (printer_name or "").strip():
        raise MustReportError(
            "出纸通道选了「系统驱动」⇒ 必须选一个**打印机名**（这条通道靠本机驱动出纸、不用 IP）"
        )
    return value


def apply_printer_setting(
    uri: str,
    *,
    mode: str = "auto",
    printer_name: str = "",
    env_path: Path | None = None,
) -> dict:
    """把打印机设置写回 `.env` 并即时生效（001-02 / 001-03 / 001-05）。

    - ⚠️ 2026-09-18（`TAIL-46`-③）由「**只写地址**」扩成**写三项**（地址 ＋ 出纸通道 ＋ 打印机名）——
       `001-05` 的原意是"**逐行改写、其余配置一字不动**"，这条**照旧成立**（只碰这三个键）。
    - 写完 `get_settings.cache_clear()` ⇒ 下一次取配置即新值（001-02），无需重启。
    - 返回三项的新值（调用方回执里要说给用户听）。
    """
    value = validate_printer_uri(uri)          # 先校验：非法则不落盘、不静默（001-04）
    name = (printer_name or "").strip()
    m = validate_print_mode(mode, name)        # ⚠️ 校验在写之前 ⇒ 任一项非法就**一个字都不写**
    path = env_path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    want = {_KEY: value, _MODE_KEY: m, _NAME_KEY: name}
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
    return {"printer_ipp_url": value, "print_mode": m, "printer_name": name}
