"""IPP A4 capability check and Print-Job submission."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.errors import MustReportError, log_exc
from app.mod03_notice.settings_store import validate_printer_uri

_MEDIA_A4 = b"iso_a4_210x297mm"
_PRINT_JOB = 0x0002
_VALIDATE_JOB = 0x0004
_REQUEST_ID = 1
_STATUS_NAME = {
    0x0400: "报文被拒",
    0x0401: "打印机拒绝访问",
    0x0402: "打印机需要身份验证",
    0x0403: "打印机拒绝授权",
    0x0405: "打印机处理超时",
    0x0406: "打印机找不到请求的资源",
    0x040A: "打印机不支持此文档格式",
    0x040B: "打印机不支持请求的属性或属性值",
    0x0500: "打印机内部错误",
    0x0501: "打印机不支持此操作",
    0x0503: "打印服务不可用",
}
DeliveryStatus = Literal["accepted", "failed", "unknown"]


@dataclass(frozen=True)
class IppOutcome:
    status: DeliveryStatus
    reason: str
    job_id: int | None = None
    job_state: int | None = None


def _attr(tag: int, name: str, value: bytes) -> bytes:
    name_bytes = name.encode("ascii")
    return struct.pack(">BH", tag, len(name_bytes)) + name_bytes + struct.pack(">H", len(value)) + value


def _build_request(operation: int, printer_uri: str, pdf: bytes = b"") -> bytes:
    return b"".join((
        struct.pack(">BBHI", 1, 1, operation, _REQUEST_ID),
        b"\x01",  # operation attributes
        _attr(0x47, "attributes-charset", b"utf-8"),
        _attr(0x48, "attributes-natural-language", b"en"),
        _attr(0x45, "printer-uri", printer_uri.encode("utf-8")),
        _attr(0x42, "requesting-user-name", b"mtrl"),
        _attr(0x49, "document-format", b"application/pdf"),  # mimeMediaType
        _attr(0x22, "ipp-attribute-fidelity", b"\x01"),  # Reject unsupported job attributes.
        b"\x02",  # job attributes
        _attr(0x44, "media", _MEDIA_A4),  # keyword
        b"\x03",
        pdf,
    ))


def _to_http_uri(printer_uri: str) -> httpx.URL:
    url = httpx.URL(validate_printer_uri(printer_uri))
    if not url.host or url.userinfo:
        raise MustReportError("请填写有效的打印机地址，地址中不能包含登录凭据。")
    if url.scheme in ("ipp", "ipps"):
        return url.copy_with(scheme={"ipp": "http", "ipps": "https"}[url.scheme], port=url.port or 631)
    return url


@dataclass(frozen=True)
class _Response:
    status: int
    message: str = ""
    job_id: int | None = None
    job_state: int | None = None


def _parse_response(data: bytes) -> _Response:
    if len(data) < 9 or data[0] not in (1, 2):
        raise ValueError("Invalid IPP response header")
    status, request_id = struct.unpack_from(">HI", data, 2)
    if request_id != _REQUEST_ID:
        raise ValueError("Wrong IPP request ID")
    pos = 8
    group = 0
    message = ""
    job: dict[bytes, int] = {}
    while pos < len(data):
        tag = data[pos]
        pos += 1
        if tag == 0x03:
            return _Response(status, message, job.get(b"job-id"), job.get(b"job-state"))
        if tag < 0x10:
            group = tag
            continue
        name_len = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        name = data[pos:pos + name_len]
        pos += name_len
        value_len = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        value = data[pos:pos + value_len]
        pos += value_len
        if group == 0x01 and name == b"status-message":
            message = value.decode("utf-8", "replace").strip()
        if group == 0x02 and name in (b"job-id", b"job-state") and tag in (0x21, 0x23) and len(value) == 4:
            job[name] = int.from_bytes(value, "big", signed=True)
    raise ValueError("Incomplete IPP response")


def _post(url: httpx.URL, body: bytes) -> _Response:
    response = httpx.post(
        url, content=body, headers={"Content-Type": "application/ipp"},
        timeout=httpx.Timeout(20.0, connect=10.0),
    )
    return _parse_response(response.content)


def _reply_reason(reply: _Response) -> str:
    reason = f"打印机返回 IPP 状态码 0x{reply.status:04X}"
    label = _STATUS_NAME.get(reply.status)
    if label:
        reason += f"（{label}）"
    return reason + (f"。打印机说明：{reply.message}" if reply.message else "")


def validate_a4(printer_uri: str) -> None:
    """Validate the same PDF + A4 attributes as Print-Job, without creating a job."""
    try:
        response = _post(_to_http_uri(printer_uri), _build_request(_VALIDATE_JOB, printer_uri))
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, struct.error) as exc:
        log_exc("IPP A4 校验未取得有效响应", exc)
        raise MustReportError("未能确认打印机接受 A4，请核对 IPP 地址、电源与网络。") from exc
    if response.status != 0:
        raise MustReportError(f"打印机未确认接受显式 A4。{_reply_reason(response)}")


def send_pdf(pdf: bytes, printer_uri: str) -> IppOutcome:
    """Submit a job to a target whose A4 capability has already been checked."""
    try:
        url = _to_http_uri(printer_uri)
        body = _build_request(_PRINT_JOB, printer_uri, pdf)
    except (MustReportError, httpx.InvalidURL, ValueError, struct.error) as exc:
        log_exc("IPP 打印地址或请求无效", exc)
        return IppOutcome("failed", "打印地址或请求格式无效，请核对 IPP 设置。")

    try:
        reply = _post(url, body)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
        log_exc("IPP 请求发送前连接失败", exc)
        return IppOutcome("failed", f"出纸失败：无法连接打印机（{printer_uri}），请核对地址、电源与网络。")
    except (httpx.HTTPError, ValueError, struct.error) as exc:
        log_exc("IPP 作业结果待核实", exc)
        return IppOutcome("unknown", "未取得有效的打印机回执，请先核对打印机作业和出纸情况，勿重复打印。")
    if reply.status >> 8:
        return IppOutcome("failed", f"出纸失败：{_reply_reason(reply)}", reply.job_id, reply.job_state)
    reason = "打印机已接收作业。"
    if reply.status:
        reason += f"请核对打印机属性和出纸情况。{_reply_reason(reply)}"
    elif reply.message:
        reason += f"打印机说明：{reply.message}"
    return IppOutcome("accepted", reason, reply.job_id, reply.job_state)
