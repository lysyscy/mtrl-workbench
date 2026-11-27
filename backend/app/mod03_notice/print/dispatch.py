"""Validate the selected A4 printer once and submit each PDF once."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.config import get_settings
from app.core.errors import MustReportError, log_exc
from app.mod03_notice.print.ipp import IppOutcome, send_pdf, validate_a4
from app.mod03_notice.settings_store import configured_print_mode, require_ipp


@dataclass(frozen=True)
class DispatchAttempt(IppOutcome):
    channel: str = ""


@dataclass(frozen=True)
class DispatchOutcome:
    attempts: tuple[DispatchAttempt, ...]

    @property
    def last(self) -> DispatchAttempt:
        return self.attempts[-1]

    def receipt_fields(self) -> dict:
        return {
            "delivery_status": self.last.status,
            "channel": self.last.channel,
            "job_id": self.last.job_id,
            "job_state": self.last.job_state,
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }


class A4BlockedError(MustReportError):
    code = "a4_blocked"
    http_status = 409

    def __init__(self, channel: str, reason: str):
        attempt = DispatchAttempt("failed", reason, channel=channel)
        super().__init__(reason, detail={"attempts": [asdict(attempt)]})


@dataclass(frozen=True)
class DispatchPlan:
    printer_uri: str

    def send(self, pdf: bytes) -> DispatchOutcome:
        try:
            reply = send_pdf(pdf, printer_uri=self.printer_uri)
        except Exception as exc:  # noqa: BLE001
            # An interrupted submission may already have created a device job.
            log_exc("投递打印机后未取得有效回执", exc)
            reply = IppOutcome("unknown", "请先核对打印机作业和出纸情况，勿重复打印。")
        attempt = DispatchAttempt(reply.status, reply.reason, reply.job_id, reply.job_state, "ipp")
        return DispatchOutcome((attempt,))


def lock_a4_channel(*, mode: str | None = None, printer_uri: str | None = None) -> DispatchPlan:
    settings = get_settings()
    channel = configured_print_mode(settings.print_mode, mode)
    uri = (settings.printer_ipp_url if printer_uri is None else printer_uri).strip()
    try:
        require_ipp(channel)
        validate_a4(uri)
    except MustReportError as exc:
        raise A4BlockedError(channel, exc.message) from exc
    return DispatchPlan(uri)
