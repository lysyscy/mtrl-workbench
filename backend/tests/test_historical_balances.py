"""Cumulative history never adds a second payment or a second mechanical settlement."""
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from app.core.errors import MustReportError
from app.mod05_flow import history, service
from app.mod05_flow.models import OpeningBalance
from app.mod06_proc import repository as proc
from tests.test_ledger_opening_range import project, notice
from tests.test_proc_split_cutoffs import session  # noqa: F401


def data(p, kind="payment", amount="1000", category="material", cutoff="2025-11", **kw):
    return dict(id=None, project_id=p.id, category=category, entry_kind=kind,
                cutoff_ym=cutoff, input_mode="paid", amount=amount, remark="核对", **kw)


def save(s, payload):
    checked = history.preview(s, payload)
    return history.save(s, payload, checked["token"])


def test_multiple_i6_supplements_and_payment_total_count_once(session):
    p = project(session, "__history_material__")
    save(session, data(p, "settlement", "1000"))
    save(session, data(p, "settlement", "500", cutoff="2025-12"))
    notice(session, p, "material", "2025-10-01", 200)
    save(session, data(p, amount="1000"))
    # 100 notice settlement + 1500 i6 supplement - 1000 cumulative paid.
    debt = service.build_debt(session)
    mine = [r for r in service.opening_views(session) if r.project_id == p.id]
    assert sum(r.paid_amount for r in mine) == D(800)
    side = service.build_ledger(session, project_id=p.id)["sides"][0]
    assert sum(D(r["other_expense"]) for r in side["display_rows"]) == D(1600)
    assert sum(D(r["payment"]) for r in side["display_rows"]) == D(1000)
    assert any(r["month"] == "2025-10" and r["row_kind"] == "month" for r in side["display_rows"])
    assert len(debt["openings"]) >= 3
    from app.report_export import ledger_export
    exported = ledger_export.ledger_spec(ledger_export.SHEET_OF_CATEGORY["material"], side, display=p.disp)
    assert exported["tail"][0][1]["C"] == D(1600)
    assert exported["tail"][0][1]["D"] == D(1000)
    assert exported["tail"][0][1]["E"] == D(600)
    item = next(r for r in service.total_debt_rows(session)["items"] if r["project"] == p.disp)
    assert item["material"] == D(600)
    save(session, data(p, amount="1200", cutoff="2025-12"))
    side = service.build_ledger(session, project_id=p.id)["sides"][0]
    assert sum(D(r["payment"]) for r in side["display_rows"]) == D(1200)
    earlier = service.build_ledger(session, project_id=p.id, end_ym="2025-11")["sides"][0]
    assert sum(D(r["payment"]) for r in earlier["display_rows"]) == D(1000)


def test_mechanical_known_debt_resolves_fixed_payment_without_second_settlement(session):
    p = project(session, "__history_mechanical__")
    proc.save_mech(session, warehouse=p.warehouse_name, ym="2025-10", values={"mech_2": 1000, "mech_3": 500})
    notice(session, p, "mechanical", "2025-10-01", 200)
    payload = data(p, amount="0", category="mechanical")
    payload["input_mode"] = "debt"
    checked = history.preview(session, payload)
    assert checked["settlement"] == "1500.00"
    assert checked["paid_total"] == "1500.00"
    assert checked["payment_adjustment"] == "1300.00"
    saved = save(session, payload)
    assert session.get(OpeningBalance, saved["id"]).settle_amount == 0
    side = service.build_ledger(session, project_id=p.id)["sides"][1]
    assert sum(D(r["debt"]) for r in side["display_rows"]) == 0
    proc.save_mech(session, warehouse=p.warehouse_name, ym="2025-10", values={"mech_2": 1200})
    ledger = service.build_ledger(session, project_id=p.id)
    record = next(r for r in ledger["history"] if r["id"] == saved["id"])
    assert record["needs_review"]
    assert session.get(OpeningBalance, saved["id"]).paid_amount == D(1500)
    assert sum(D(r["debt"]) for r in ledger["sides"][1]["display_rows"]) == D(200)
    totals = service.total_debt_rows(session)
    item = next(r for r in totals["items"] if r["project"] == p.disp)
    assert item["mech"] == D(200)
    raw = service.build_debt(session, jc_debt=0)
    live = service.build_debt_live(session, jc_debt=0)
    mechanical = lambda d: D(next(r["amount"] for r in d["by_category"] if r["category"] == "mechanical"))
    assert mechanical(live) - mechanical(raw) == D(1700)


def test_later_payment_changes_are_visible_and_reconciliation_is_explicit(session):
    p = project(session, "__history_review__")
    n = notice(session, p, "material", "2025-10-01", 100)
    saved = save(session, data(p, amount="1000"))
    n.stat_paid = D(200)
    session.flush()
    ledger = service.build_ledger(session, project_id=p.id)
    assert ledger["history"][0]["needs_review"]
    assert sum(D(r["payment"]) for r in ledger["sides"][0]["display_rows"]) == D(1100)
    # Confirming that the new 100 was already in history reduces the supplement.
    payload = data(p, amount="1000")
    payload["id"] = saved["id"]
    save(session, payload)
    ledger = service.build_ledger(session, project_id=p.id)
    assert not ledger["history"][0]["needs_review"]
    assert sum(D(r["payment"]) for r in ledger["sides"][0]["display_rows"]) == D(1000)


def test_preview_rejects_stale_values_invalid_types_and_duplicate_cutoff(session):
    p = project(session, "__history_validate__")
    payload = data(p)
    checked = history.preview(session, payload)
    notice(session, p, "material", "2025-11-01", 100)
    with pytest.raises(MustReportError, match="已变化"):
        history.save(session, payload, checked["token"])
    assert not [r for r in service.opening_views(session) if r.project_id == p.id]
    save(session, payload)
    with pytest.raises(MustReportError, match="已有累计付款"):
        history.preview(session, payload)
    for invalid in (data(p, "settlement", category="mechanical"), data(p, amount="NaN"),
                    data(p, amount="-1"), data(p, cutoff="2025-13")):
        with pytest.raises(MustReportError):
            history.preview(session, invalid)


def test_migration_splits_confirmed_totals_without_changing_net_debt(session):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    conn = session.connection()
    conn.execute(text("""CREATE TEMP TABLE opening_balance (
        id serial primary key, category varchar(16), project_id integer, cutoff_ym varchar(7),
        settle_amount numeric(18,2), paid_amount numeric(18,2), remark varchar(512), created_at timestamp)
        ON COMMIT DROP"""))
    conn.execute(text("""CREATE TEMP TABLE payment_notice (
        ownership_id integer, category varchar(16), excluded boolean, doc_date varchar(32), stat_paid numeric(18,2))
        ON COMMIT DROP"""))
    conn.execute(text("""INSERT INTO opening_balance(category,project_id,cutoff_ym,settle_amount,paid_amount,remark,created_at)
        VALUES ('material',1,'2025-11',1000.12,1000.12,'已付清',now()),
               ('material',10,'2025-11',500.34,500.34,'已付清',now())"""))
    path = Path(__file__).parents[1] / "alembic/versions/c390261021_historical_balances.py"
    spec = importlib.util.spec_from_file_location("history_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(conn)):
        module.upgrade()
    rows = conn.execute(text("SELECT * FROM opening_balance ORDER BY id")).mappings().all()
    assert len(rows) == 4
    assert sum(r["settle_amount"] for r in rows) == D("1500.46")
    assert sum(r["paid_amount"] for r in rows) == D("1500.46")
    assert [r["entry_kind"] for r in rows] == ["settlement", "settlement", "payment", "payment"]
