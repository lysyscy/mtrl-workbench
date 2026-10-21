"""直接录入历史行与未填日期付款均不能截断正常月份。"""
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
    historical = [r for r in side["display_rows"] if r["row_kind"] == "undated"]
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


@pytest.mark.parametrize("month",["2024-08","2025-11"])
def test_manual_rows_keep_all_notices_and_undated_payment_once(session,month):
    p=project(session,"__ledger_manual_range__")
    session.add(OpeningBalance(category="material",project_id=p.id,cutoff_ym=month,
                               settle_amount=1000,paid_amount=100,entry_kind="manual"));session.flush()
    notice(session,p,"material","2024-07-10",999)
    notice(session,p,"material","2026-03-10",20)
    notice(session,p,"material","",25)
    side=service.build_ledger(session,project_id=p.id)["sides"][0]
    rows=side["display_rows"]
    manual=next(r for r in rows if r["row_kind"]=="manual")
    assert manual["month"]==month and manual["payment"]=="100.00"
    assert not any(r["is_opening"] for r in rows)
    assert any(r["month"]=="2024-07" and r["payment"]=="999.00" for r in rows)
    spec=ledger_export.ledger_spec("辅材",side,display=p.disp)
    assert spec["tail"][0][1]=={"C":D(1200),"D":D(1144),"E":D(56)}
