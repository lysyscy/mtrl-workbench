"""Preserve the difference between acceptance, rejection and missing IPP evidence."""

from types import SimpleNamespace

import httpx
import pytest

from app.core.errors import MustReportError
from app.mod03_notice import service as S
from app.mod03_notice.print import ipp
from app.mod03_notice.print.dispatch import DispatchAttempt, DispatchOutcome
from app.mod03_notice.print_batch_store import batch_response

PDF = b"%PDF-1.4 test"
URI = "ipp://printer.example.test/ipp/print"


def response(status, attributes=b""):
    return httpx.Response(200, content=(
        b"\x01\x01" + status.to_bytes(2, "big") + b"\x00\x00\x00\x01" + attributes + b"\x03"
    ))


@pytest.mark.parametrize("status", [0, 1, 2])
@pytest.mark.parametrize("id_tag", [0x21, 0x23])
def test_acceptance_includes_job_id_and_state_without_claiming_paper_output(monkeypatch, status, id_tag):
    attributes = (
        bytes([0x02, id_tag]) + b"\x00\x06job-id\x00\x04\x00\x00\x00\x42"
        b"\x23\x00\x09job-state\x00\x04\x00\x00\x00\x03"
    )
    monkeypatch.setattr(ipp.httpx, "post", lambda *args, **kwargs: response(status, attributes))
    reply = ipp.send_pdf(PDF, URI)
    assert (reply.status, reply.job_id, reply.job_state) == ("accepted", 66, 3)
    assert "打印机已接收" in reply.reason and "打印完成" not in reply.reason


def test_explicit_ipp_error_preserves_printer_message(monkeypatch):
    attribute = b"\x01\x41\x00\x0estatus-message\x00\x0emedia rejected"
    monkeypatch.setattr(ipp.httpx, "post", lambda *args, **kwargs: response(0x040B, attribute))
    reply = ipp.send_pdf(PDF, URI)
    assert reply.status == "failed" and "0x040B" in reply.reason and "media rejected" in reply.reason


@pytest.mark.parametrize(("exception", "status"), [
    (httpx.ConnectError, "failed"), (httpx.ConnectTimeout, "failed"),
    (httpx.ReadError, "unknown"), (httpx.ReadTimeout, "unknown"),
    (httpx.WriteTimeout, "unknown"), (httpx.RemoteProtocolError, "unknown"),
])
def test_transport_distinguishes_before_send_and_ambiguous_submission(monkeypatch, exception, status):
    def disconnected(*args, **kwargs):
        raise exception("disconnected")

    monkeypatch.setattr(ipp.httpx, "post", disconnected)
    assert ipp.send_pdf(PDF, URI).status == status


@pytest.mark.parametrize("data", [b"<html>", b"\x01\x01\x00\x00\x00\x00\x00\x01"])
def test_invalid_or_interrupted_response_stays_unknown(monkeypatch, data):
    monkeypatch.setattr(ipp.httpx, "post", lambda *args, **kwargs: httpx.Response(200, content=data))
    assert ipp.send_pdf(PDF, URI).status == "unknown"


def test_a4_validation_requires_success_without_substitution(monkeypatch):
    monkeypatch.setattr(ipp.httpx, "post", lambda *args, **kwargs: response(0x0001))
    with pytest.raises(MustReportError, match="未确认接受显式 A4"):
        ipp.validate_a4(URI)


def test_receipt_serialization_keeps_all_attempt_reasons(monkeypatch):
    attempts = (
        DispatchAttempt("failed", "first rejection", channel="first"),
        DispatchAttempt("unknown", "second response interrupted", channel="second"),
    )
    result = _run(monkeypatch, lambda pdf: DispatchOutcome(attempts))
    response = batch_response(result)
    assert response.unknown == 1 and response.failed == response.success == 0
    assert response.unprinted_bill_nos == []
    receipt = response.items[0]
    assert receipt.delivery_status == "unknown" and receipt.channel == "second"
    assert [(attempt.channel, attempt.reason) for attempt in receipt.attempts] == [
        ("first", "first rejection"), ("second", "second response interrupted"),
    ]


def _run(monkeypatch, dispatch):
    """跑一次 `run_batch`（渲染/版式全打桩 ⇒ **不连库、不连 i8、不连打印机**）。"""
    monkeypatch.setattr(S, "render_notice_html", lambda *a, **k: "<html/>")
    notice = SimpleNamespace(id=7, ph_id="ph-7", bill_no="FKTZS-1", bill_type="t")
    return S.run_batch(
        [notice],
        mode=S.MODE_PRINT,
        # ⚠️ 两个取数件要的是**带 `.fetch` 的对象**（生产上分别是 `DesignFetcher` / `NoticeDetailFetcher`）
        design_fetcher=SimpleNamespace(fetch=lambda bt: SimpleNamespace(tpl=None)),
        detail_fetcher=SimpleNamespace(fetch=lambda *a, **k: None),
        signature_store=None,
        render_pdf=lambda html: b"%PDF-1.4 x",      # ⚠️ `render_pdf` 是**入参**（不是模块属性）⇒ 直接给桩
        dispatch_pdf=dispatch,
    )


def test_投递说明进回执且不算失败(monkeypatch):
    """⭐ 投递实现返回一句 ⇒ `ok=True, unverified=True, reason=那句`（**新第三态**）。"""
    r = _run(monkeypatch, lambda pdf: "已投递（未核实）")
    o = r.outcomes[0]
    assert o.ok is True, "『说不清』⛔ 不是失败"
    assert o.unverified is True and o.reason == "已投递（未核实）"
    assert len(r.success) == 1, "它算**成功**（`success` 集合里）"
    response = batch_response(r)
    assert response.items[0].unverified is True, "API不能丢掉未核实标记，避免误导重复投递"


def test_已核实与真失败两态不受影响(monkeypatch):
    """空串 = 已核实（`unverified=False`）；抛异常 = 失败（`ok=False`，⛔ 且不是 unverified）。"""
    o = _run(monkeypatch, lambda pdf: "").outcomes[0]
    assert o.ok is True and o.unverified is False and o.reason == ""

    def _boom(pdf):
        raise MustReportError("出纸失败：打印机返回 IPP 状态码 0x0400")

    o2 = _run(monkeypatch, _boom).outcomes[0]
    assert o2.ok is False and o2.unverified is False, "失败就是失败，⛔ 别混进『未核实』"
    assert "出纸失败" in o2.reason


def test_probe_distinguishes_delivery_states_and_exit_codes(monkeypatch, tmp_path, capsys):
    import sys
    from types import SimpleNamespace

    from tools.probe import print_bills as cli

    monkeypatch.setattr(cli, "OUT_DIR", tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(printer_ipp_url="ipp://fixture"))
    for dependency in ("I8Client", "PdfRenderer", "NoticeDetailFetcher", "SignatureStore"):
        monkeypatch.setattr(cli, dependency, lambda *a, **kw: SimpleNamespace(close=lambda: None))

    def render(_client, bill_no, *args):
        if bill_no == "missing":
            return {"bill_no": bill_no, "ok": False, "reason": "not found"}
        pdf = tmp_path / f"{bill_no}.pdf"
        pdf.write_bytes(bill_no.encode())
        return dict(bill_no=bill_no, ok=True, reason="", bill_type="material", type_raw="material",
                    print_name="sample", print_id=1, detail=1, flow=0, slots=0, filled=0,
                    blank=[], missing=[], unresolved=0, pdf=pdf)

    sent = []
    def send(pdf, uri):
        sent.append((pdf, uri))
        status = {b"reject": "failed", b"timeout": "unknown"}.get(pdf, "accepted")
        return ipp.IppOutcome(status, "fixture receipt")

    monkeypatch.setattr(cli, "one_bill", render)
    monkeypatch.setattr(cli, "send_pdf", send)
    monkeypatch.setattr(sys, "argv", ["print_bills", "missing", "reject", "timeout", "ok"])
    assert cli.main() == 1
    output = capsys.readouterr().out.splitlines()
    assert next(line for line in output if " · 未出 " in line).endswith("['missing', 'reject']")
    unknown = next(line for line in output if line.startswith("结果待核实"))
    assert "['timeout']" in unknown and "勿盲目重打" in unknown
    assert sent == [(bill, "ipp://fixture") for bill in (b"reject", b"timeout", b"ok")]
    sent.clear()
    for bill, expected in (("ok", 0), ("reject", 1), ("timeout", 1)):
        monkeypatch.setattr(sys, "argv", ["print_bills", bill])
        assert cli.main() == expected
    sent.clear()
    monkeypatch.setattr(sys, "argv", ["print_bills", "--expect", "material=2", "ok"])
    assert cli.main() == 2 and sent == []
    monkeypatch.setattr(sys, "argv", ["print_bills", "--no-print", "ok"])
    assert cli.main() == 0 and sent == []
