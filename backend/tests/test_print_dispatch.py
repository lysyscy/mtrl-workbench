"""A4 channel selection and ordered print attempt receipts."""

from types import SimpleNamespace

import pytest

from app.core.errors import MustReportError
from app.mod03_notice.print import dispatch as D
from app.mod03_notice.print.ipp import IppOutcome

PDF = b"%PDF-1.4 test"


@pytest.mark.parametrize("status", ["accepted", "failed", "unknown"])
def test_auto_uses_only_verified_ipp_regardless_of_delivery_result(monkeypatch, status):
    calls = []

    def validate(uri):
        calls.append(("validate", uri))

    def send(pdf, printer_uri):
        calls.append(("ipp", printer_uri))
        assert pdf == PDF
        return IppOutcome(status, "IPP reason")

    def forbidden(*args):
        pytest.fail("Channel cannot guarantee A4")

    monkeypatch.setattr(D, "validate_a4", validate)
    monkeypatch.setattr(D, "send_pdf", send)
    monkeypatch.setattr(D, "send_driver", forbidden)
    monkeypatch.setattr(D, "send_raw", forbidden)
    plan = D.lock_a4_channel(mode="auto", printer_uri="ipp://printer")
    outcome = plan.send(PDF)
    assert calls == [("validate", "ipp://printer"), ("ipp", "ipp://printer")]
    assert [(item.channel, item.status, item.reason) for item in outcome.attempts] == [
        ("ipp", status, "IPP reason"),
    ]


@pytest.mark.parametrize("status", ["accepted", "failed", "unknown"])
def test_eligible_fallback_keeps_first_reason_and_stops_after_possible_delivery(status):
    called = []

    def submit(channel, outcome):
        def run(pdf):
            assert pdf == PDF
            called.append(channel)
            return outcome
        return run

    # Hypothetical senders which have all passed the capability gate.
    plan = D.DispatchPlan("auto", "ipp://printer", "", (
        ("first", submit("first", IppOutcome("failed", "first rejection"))),
        ("second", submit("second", IppOutcome(status, "second reason"))),
        ("third", submit("third", IppOutcome("failed", "third rejection"))),
    ))
    result = plan.send(PDF)
    expected = ["first", "second", "third"] if status == "failed" else ["first", "second"]
    assert called == expected
    assert [item.channel for item in result.attempts] == expected
    assert [item.reason for item in result.attempts][:2] == ["first rejection", "second reason"]


def test_settings_are_snapshotted_once_per_batch(monkeypatch):
    calls = []
    checked = []
    values = SimpleNamespace(print_mode="auto", printer_ipp_url="ipp://first", printer_name="First")
    monkeypatch.setattr(D, "get_settings", lambda: values)
    monkeypatch.setattr(D, "validate_a4", checked.append)

    def send(pdf, printer_uri):
        calls.append(printer_uri)
        return IppOutcome("accepted", "", job_id=len(calls))

    monkeypatch.setattr(D, "send_pdf", send)
    original = D.lock_a4_channel()
    values.printer_ipp_url = "ipp://new"
    values.printer_name = "New"
    new = D.lock_a4_channel(mode="ipp")
    assert (original.mode, original.printer_uri, original.printer_name) == ("auto", "ipp://first", "First")
    assert (new.mode, new.printer_uri, new.printer_name) == ("ipp", "ipp://new", "New")
    assert original.send(PDF).last.job_id == 1
    assert new.send(PDF).last.job_id == 2
    assert original.send(PDF).last.job_id == 3
    assert checked == ["ipp://first", "ipp://new"]
    assert calls == ["ipp://first", "ipp://new", "ipp://first"]


def test_raw_端口固定9100_地址里的端口不照抄():
    """⚠️ 地址里的端口（`ipp://host:631/…`）是 **IPP** 用的 —— 照抄到 RAW 等于投错门。"""
    assert D.raw_target("ipp://192.168.5.248") == ("192.168.5.248", 9100)
    assert D.raw_target("ipp://192.168.5.248:631/printers/x") == ("192.168.5.248", 9100)
    assert D.raw_target("  ipp://10.0.0.9  ") == ("10.0.0.9", 9100)
    with pytest.raises(MustReportError) as e:
        D.raw_target("192.168.5.248")
    assert "看不懂" in str(e.value), f"地址取不出 IP 要显式报错：{e.value}"
