"""IPP 直投（出纸）。

依据（《说明书》§4.6 / 技术栈 §2.4）：付款通知书 PDF 经 **IPP 直投**打印机，不依赖打印驱动与桌面会话。
- 001-08：**出纸失败须显式报出原因**，禁止把整批静默丢弃。

实现：最小 IPP 1.1 `Print-Job`（operation 0x0002）二进制包，经 HTTP POST 投到打印机 IPP URI。
⚠️ 打印机地址 / URI 形态属于**本机部署事实**（默认 `192.168.5.248`，可改），从 `.env` 读，不写死。
⚠️ 真实投递需打印机在网可达；切片 1 把"失败显式报错"做成硬约束，真机验证留待本机联调。
"""

from __future__ import annotations

import struct

import httpx

from app.core.config import effective_of, get_settings
from app.core.errors import MustReportError, NotConfiguredError


def _attr(tag: int, name: str, value: bytes) -> bytes:
    name_b = name.encode("utf-8")
    return struct.pack(">B", tag) + struct.pack(">H", len(name_b)) + name_b + struct.pack(">H", len(value)) + value


def _build_print_job(printer_uri: str, pdf: bytes) -> bytes:
    """IPP 1.1 `Print-Job`（0x0002）报文。

    ⚠️⭐ **值标签（value tag）必须与属性的语义类型一致** —— 这是本模块唯一踩过的坑
    （2026-09-16 真机：4 张全回 `0x0400 client-error-bad-request`，响应仅 115 字节、
    `status-message` 只说 `client-error-bad-request`，**不告诉你是哪个属性错了**）：
    **`document-format` 的类型是 `mimeMediaType` ⇒ 标签必须是 `0x49`**。
    曾误用 `0x44`（那是 `keyword`）⇒ 被这台 **RICOH IM 3000 PS3** 直接判为非法报文。
    ℹ️ 排障时曾用"**整个删掉 `document-format`**"绕过（那也能出纸），但那是**把报文改成非标准形态**；
    正解是**把标签改对**（`0x49`）。

    常用值标签（RFC 8010 §3.5，**别记混**）：
    `0x42` nameWithoutLanguage · `0x44` keyword · `0x45` uri · `0x47` charset ·
    `0x48` naturalLanguage · **`0x49` mimeMediaType**。
    ⚠️ `printer-uri` 用 `0x45`；`attributes-charset` / `attributes-natural-language` 用 `0x47` / `0x48`。
    """
    out = bytearray()
    out += bytes([0x01, 0x01])          # IPP version 1.1
    out += struct.pack(">H", 0x0002)    # Print-Job
    out += struct.pack(">I", 1)         # request-id
    out += bytes([0x01])                # operation-attributes group start
    out += _attr(0x47, "attributes-charset", b"utf-8")
    out += _attr(0x48, "attributes-natural-language", b"en")
    out += _attr(0x45, "printer-uri", printer_uri.encode("utf-8"))
    out += _attr(0x42, "requesting-user-name", b"mtrl")
    out += _attr(0x49, "document-format", b"application/pdf")   # ⭐ 0x49 = mimeMediaType（不是 0x44）
    out += bytes([0x03])                # end-of-attributes
    out += pdf
    return bytes(out)


def _to_http_uri(ipp_uri: str) -> str:
    """`ipp://host/...` → `http://host:631/...`（IPP 走 HTTP 传输）。"""
    if ipp_uri.startswith("ipp://"):
        return "http://" + ipp_uri[len("ipp://"):]
    if ipp_uri.startswith("ipps://"):
        return "https://" + ipp_uri[len("ipps://"):]
    return ipp_uri


def send_pdf(pdf: bytes, printer_uri: str | None = None) -> None:
    """把 PDF 经 IPP 投到打印机。**任何失败都显式报错（001-08），不静默丢弃。**"""
    uri = printer_uri or effective_of("printer_ipp_url", get_settings().printer_ipp_url)
    if not uri:
        raise NotConfiguredError("PRINTER_IPP_URL 未配置（见 .env；用户确认默认 192.168.5.248）")

    body = _build_print_job(uri, pdf)
    http_uri = _to_http_uri(uri)
    try:
        resp = httpx.post(
            http_uri,
            content=body,
            headers={"Content-Type": "application/ipp"},
            timeout=httpx.Timeout(20.0, connect=10.0),
        )
    except httpx.HTTPError as exc:
        raise MustReportError(f"出纸失败：无法连接打印机（{uri}）—— {type(exc).__name__}: {exc}")

    data = resp.content
    if len(data) < 4:
        raise MustReportError(f"出纸失败：打印机响应异常（长度 {len(data)}，非 IPP 响应）")
    status = struct.unpack(">H", data[2:4])[0]
    if status != 0x0000:  # successful-ok
        # ⚠️ 必须把打印机自报的 `status-message` **带出来**（001-08「显式报出原因」）——
        #    只给一个十六进制码，现场根本无从下手（2026-09-16 实测踩过：`0x0400` 背后是
        #    "带了 document-format 就被拒"，而这条线索**只**在那段文本里）。
        detail = _status_message(data)
        raise MustReportError(
            f"出纸失败：打印机返回 IPP 状态码 0x{status:04X}"
            f"（{_STATUS_NAME.get(status, '未知')}；HTTP {resp.status_code}）"
            + (f"—— 打印机说明：「{detail}」" if detail else "")
            + "。单据未投递，请检查打印机状态/地址。"
        )


_STATUS_NAME = {
    0x0400: "client-error-bad-request（报文被拒）",
    0x0401: "client-error-forbidden",
    0x0402: "client-error-not-authenticated",
    0x0403: "client-error-not-authorized",
    0x0404: "client-error-not-possible",
    0x0405: "client-error-timeout",
    0x0406: "client-error-not-found",
    0x0407: "client-error-gone",
    0x040A: "client-error-document-format-not-supported",
    0x0500: "server-error-internal-error",
    0x0501: "server-error-operation-not-supported",
    0x0503: "server-error-service-unavailable",
}


def _status_message(data: bytes) -> str:
    """从 IPP 响应里取出 `status-message` 文本（取不到 ⇒ 空串，**不抛**）。"""
    needle = b"status-message"
    i = data.find(needle)
    if i < 0:
        return ""
    p = i + len(needle)
    if p + 2 > len(data):
        return ""
    size = struct.unpack(">H", data[p:p + 2])[0]
    p += 2
    return data[p:p + size].decode("utf-8", "replace").strip()
