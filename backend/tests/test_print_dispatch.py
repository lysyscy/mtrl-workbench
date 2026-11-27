"""An A4 batch validates its destination once and sends each PDF once."""

from types import SimpleNamespace

import pytest

from app.mod03_notice.print import dispatch as D
from app.mod03_notice.print.ipp import IppOutcome


@pytest.mark.parametrize("status", ["accepted", "failed", "unknown", "interrupted"])
def test_auto_uses_only_verified_ipp_regardless_of_delivery_result(monkeypatch, status):
    calls = []
    monkeypatch.setattr(D, "get_settings", lambda: SimpleNamespace(print_mode="auto", printer_ipp_url="ipp://first"))
    monkeypatch.setattr(D, "validate_a4", lambda uri: calls.append(("validate", uri)))

    def send(pdf, printer_uri):
        calls.append((pdf, printer_uri))
        if status == "interrupted":
            raise OSError("lost reply")
        return IppOutcome(status, "IPP reason")

    monkeypatch.setattr(D, "send_pdf", send)
    result = D.lock_a4_channel().send(b"%PDF-test")
    assert calls == [("validate", "ipp://first"), (b"%PDF-test", "ipp://first")]
    assert len(result.attempts) == 1
    assert (result.last.channel, result.last.status) == ("ipp", "unknown" if status == "interrupted" else status)


def test_settings_are_snapshotted_once_per_batch(monkeypatch):
    values = SimpleNamespace(print_mode="ipp", printer_ipp_url="ipp://first")
    checked, calls = [], []
    monkeypatch.setattr(D, "get_settings", lambda: values)
    monkeypatch.setattr(D, "validate_a4", checked.append)

    def send(pdf, printer_uri):
        calls.append(printer_uri)
        return IppOutcome("accepted", "", job_id=len(calls))

    monkeypatch.setattr(D, "send_pdf", send)
    original = D.lock_a4_channel()
    values.printer_ipp_url = "ipp://new"
    new = D.lock_a4_channel()
    assert original.send(b"%PDF-first").last.job_id == 1
    assert new.send(b"%PDF-next").last.job_id == 2
    assert original.send(b"%PDF-last").last.job_id == 3
    assert checked == ["ipp://first", "ipp://new"]
    assert calls == ["ipp://first", "ipp://new", "ipp://first"]
