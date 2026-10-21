"""真实期初控制月界，无期初与未填日期付款均不能截断历史月。"""
from decimal import Decimal as D

import pytest

from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow import repository, service
from app.mod05_flow.models import OpeningBalance
from app.mod06_proc import repository as proc
from app.report_export import ledger_export
from tests.test_proc_split_cutoffs import session


def project(session, name):
    row = Project(project_type="normal", name_full=name, warehouse_name=name, disp=name)
    session.add(row)
    session.flush()
    return row


def notice(session, p, cat, date, paid, *, excluded=False):
    row = PaymentNotice(ph_id=f"__range_{p.id}_{cat}_{date}_{paid}_{excluded}",
                        bill_no="台账月界回归", doc_date=date, category=cat,
                        ownership_id=p.id, stat_settle=100, stat_paid=paid,
                        excluded=excluded, fields={})
    session.add(row)
    session.flush()
    return row


@pytest.mark.parametrize("cat", ["material", "mechanical"])
@pytest.mark.parametrize("auto", [None, "0", "25.12"])
def test_no_opening_preserves_old_months_and_export(session, cat, auto, tmp_path, monkeypatch):
    p = project(session, "__ledger_range__")
    other = project(session, "__ledger_other__")
    notice(session, other, cat, "2020-01-01", 999)
    notice(session, p, cat, "2024-07-10", 10)
    notice(session, p, cat, "2025-12-10", 20)
    notice(session, p, cat, "", 999, excluded=True)
    if cat == "mechanical":
        proc.save_mech(session, warehouse=p.warehouse_name, ym="2024-06", values={"mech_2": 80, "mech_3": 20})
        proc.save_mech(session, warehouse=p.warehouse_name, ym="2025-12", values={"mech_2": 150})
    if auto is not None:
        notice(session, p, cat, "", auto)
    data = service.build_ledger(session, project_id=p.id)
    side = next(s for s in data["sides"] if s["category"] == cat)
    months = [r for r in side["display_rows"] if r["row_kind"] == "month"]
    assert side["opening_id"] is None
    assert not any(r["row_kind"] == "opening_total" or r["is_opening"] for r in side["rows"])
    assert months[0]["month"] == ("2024-06" if cat == "mechanical" else "2024-07")
    assert months[-1]["month"] == "2025-12"
    assert next(r for r in months if r["month"] == "2024-07")["payment"] == "10.00"
    assert side["opening_default"] == {"cutoff_ym": "2024-05" if cat == "mechanical" else "2024-06", "fallback": False}
    historical = [r for r in side["display_rows"] if r["row_kind"] == "opening_auto"]
    assert len(historical) == (auto is not None)
    if historical:
        assert historical[0]["payment"] == f"{D(auto):.2f}"
        assert historical[0]["month_label"] == "未填单据日期付款"
        assert historical[0]["other_expense"] == "0.00"
    spec = ledger_export.ledger_spec(ledger_export.SHEET_OF_CATEGORY[cat], side, display=p.disp)
    assert spec["tail"][0][1]["C"] == (D(250) if cat == "mechanical" else D(200))
    assert spec["tail"][0][1]["D"] == D(30) + D(auto or 0)
    assert spec["tail"][0][1]["E"] == (D(220) if cat == "mechanical" else D(170)) - D(auto or 0)
    assert "2024-07" in [r[1]["B"] for r in spec["rows"]]
    opposite = next(s for s in data["sides"] if s["category"] != cat)
    assert opposite["rows"] == [] and opposite["display_rows"] == []
    with pytest.raises(MustReportError, match="期初"):
        service.set_opening_payment(session, project_id=p.id, category=cat, payment="50")
    assert repository.list_openings(session, project_id=p.id, category=cat) == []
    if auto == "25.12":
        import openpyxl
        from app.report_export import service as exporter
        monkeypatch.setattr(exporter, "EXPORT_ROOT", tmp_path)
        path = exporter.export_ledger(session, [p.warehouse_name], "2025-12")
        workbook = openpyxl.load_workbook(path, data_only=True)
        try:
            values = list(workbook[ledger_export.SHEET_OF_CATEGORY[cat]].values)
            by_month = {r[1]: r for r in values}
            assert by_month["2024-07"][3] == 10
            assert by_month["未填单据日期付款"][3] == 25.12
            assert "2025-11及之前" not in by_month
            assert D(str(by_month["合计："][3])) == D("55.12")
        finally:
            workbook.close()


@pytest.mark.parametrize("cat", ["material", "mechanical"])
@pytest.mark.parametrize("cutoff", ["2024-08", "2025-11", "2026-02"])
def test_real_opening_keeps_its_cutoff_and_counts_auto_once(session, cat, cutoff):
    p = project(session, "__ledger_cutoff__")
    session.add(OpeningBalance(category=cat, project_id=p.id, cutoff_ym=cutoff,
                               settle_amount=1000, paid_amount=100))
    session.flush()
    notice(session, p, cat, "2024-07-10", 999)
    notice(session, p, cat, "2026-03-10", 20)
    notice(session, p, cat, "", 25)
    side = next(s for s in service.build_ledger(session, project_id=p.id)["sides"] if s["category"] == cat)
    first, *monthly = side["display_rows"]
    assert first["month"] == cutoff and first["month_label"] == cutoff + "及之前"
    assert first["is_opening"] and first["payment"] == "125.00"
    assert all(r["month"] > cutoff for r in monthly)
    assert monthly[-1]["month"] == "2026-03"
    spec = ledger_export.ledger_spec(ledger_export.SHEET_OF_CATEGORY[cat], side, display=p.disp)
    assert spec["tail"][0][1]["D"] == D(145)
    service.set_opening_payment(session, project_id=p.id, category=cat, payment="150")
    opening = repository.list_openings(session, project_id=p.id, category=cat)[0]
    assert opening.cutoff_ym == cutoff and opening.settle_amount == D(1000)
    assert opening.paid_amount == D(125)
