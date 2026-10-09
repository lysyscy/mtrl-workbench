"""TAIL-262: process history import and public matrix regression seams."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.db import Base
from app.mod01_projects import models as _projects  # noqa: F401
from app.mod06_proc import domain as D, imp_spec, repository as R
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot
from tests.acc_plugin import acc


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[_projects.Project.__table__, ProcCutoff.__table__,
                                           ProcHistoryBatch.__table__, ProcHistorySnapshot.__table__])
    with Session(engine) as s:
        yield s


@acc()
def test_cutoff_preview_and_commit_use_same_plan(session):
    records = [{"_row": 4, "核算月": "2025-11", "入库主辅材": "10"},
               {"_row": 5, "核算月": "2025-12", "入库主辅材": "20"},
               {"_row": 6, "核算月": "2026-01", "入库主辅材": ""}]
    opts = {"warehouse": "历史项目", "cutoff_ym": "2025-11", "batch": "cutoff"}
    preview = imp_spec.preview(session, records, {}, opts)
    assert preview["writable"] == 1
    assert any(x["row"] == 5 and "截止" in x["why"] for x in preview["skipped"])
    result = imp_spec.commit(session, records, {}, "自检", opts)
    assert result["rows"] == 1 and result["months"] == ["2025-11"]
    assert [r["ym"] for r in R.load_history(session)] == ["2025-11"]


@acc()
def test_reimport_replaces_all_project_history_and_failure_keeps_old(session):
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-01", "in_主辅材": 10},
                                                   {"ym": "2025-02", "in_主辅材": 20}],
                      batch_no="old", operator="自检")
    R.import_snapshot(session, warehouse="B", rows=[{"ym": "2025-01", "in_主辅材": 99}],
                      batch_no="other", operator="自检")
    session.commit()
    with pytest.raises(Exception):
        R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-03", "in_主辅材": "invalid"}],
                          batch_no="fail", operator="自检")
    session.rollback()
    assert [r["ym"] for r in R.load_history(session) if r["warehouse"] == "A"] == ["2025-01", "2025-02"]
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-03", "in_主辅材": 30}],
                      batch_no="new", operator="自检")
    assert [(r["warehouse"], r["ym"]) for r in R.load_history(session)] == [("B", "2025-01"), ("A", "2025-03")]
    assert len(R.load_history(session, active_only=False)) == 4


@acc()
def test_database_write_failure_restores_old_history_cutoff_without_outer_rollback(session):
    from sqlalchemy.exc import IntegrityError
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-01", "in_主辅材": 10}],
                      batch_no="old", operator="自检", cutoff_ym="2025-01")
    R.import_snapshot(session, warehouse="B", rows=[{"ym": "2025-02", "in_主辅材": 99}],
                      batch_no="other", operator="自检", cutoff_ym="2025-02")
    session.commit()
    with pytest.raises(IntegrityError):
        R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-03", "in_主辅材": 30}],
                          batch_no="old", operator="自检", cutoff_ym="2025-03")
    assert [(r["warehouse"], r["ym"], r["in_主辅材"]) for r in R.load_history(session)] == [
        ("A", "2025-01", Decimal("10.00")), ("B", "2025-02", Decimal("99.00"))]
    assert R.load_cutoff(session, warehouse="A") == "2025-01"
    assert R.load_cutoff(session, warehouse="B") == "2025-02"
    session.commit()


@acc()
def test_validation_failure_in_mixed_file_keeps_all_old_history(session):
    from app.core.errors import MustReportError
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-01", "in_主辅材": 10}],
                      batch_no="old", operator="自检", cutoff_ym="2025-01")
    session.commit()
    with pytest.raises(MustReportError):
        imp_spec.commit(session, [{"_row":4,"核算月":"2025-03","入库主辅材":"30"},
                                  {"_row":5,"核算月":"坏月份","入库主辅材":"40"}], {}, "自检",
                        {"warehouse":"A","cutoff_ym":"2025-03"})
    assert [(r['ym'],r['in_主辅材']) for r in R.load_history(session)] == [('2025-01',Decimal('10.00'))]
    assert R.load_cutoff(session,warehouse='A') == '2025-01'



@acc()
def test_material_i8_same_month_precedence_keeps_history_mechanical():
    inv = [{"warehouse": "A", "ym": "2025-11", "direction": "入库", "material_property": "主材",
            "amount": 10, "adj_amount": 15}]
    history = [{"warehouse": "A", "ym": "2025-11", "in_主辅材": 999, "in_工具": 777, "mech_0": 7},
               {"warehouse": "A", "ym": "2025-10", "in_主辅材": 8, "mech_0": 6}]
    raw = D.build_matrix(inv_rows=inv, history_rows=history, manual_rows=[{"warehouse": "A", "ym": "2025-11", "mech_0": 7}, {"warehouse": "A", "ym": "2025-10", "mech_0": 6}], warehouse="A", adjusted=False, cutoff_ym="2025-11")
    adj = D.build_matrix(inv_rows=inv, history_rows=history, manual_rows=[{"warehouse": "A", "ym": "2025-11", "mech_0": 7}, {"warehouse": "A", "ym": "2025-10", "mech_0": 6}], warehouse="A", adjusted=True, cutoff_ym="2025-11")
    assert raw[1]["in_主辅材"] == Decimal("10.00")
    assert adj[1]["in_主辅材"] == Decimal("15.00")
    assert raw[1]["mech_0"] == adj[1]["mech_0"] == Decimal("7.00")
    assert raw[0]["in_主辅材"] == Decimal("8.00")
    assert raw[1]["in_工具"] == adj[1]["in_工具"] == Decimal("0.00")
    assert D.difference_rows(raw, adj)[1]["in_主辅材"] == Decimal("5.00")
    assert D.column_totals(raw)["in_主辅材"] == Decimal("18.00")
    assert D.column_totals(adj)["in_主辅材"] == Decimal("23.00")
    inv[0]["amount"] = 0
    zero = D.build_matrix(inv_rows=inv, history_rows=history, manual_rows=[{"warehouse": "A", "ym": "2025-11", "mech_0": 7}, {"warehouse": "A", "ym": "2025-10", "mech_0": 6}], warehouse="A", adjusted=False, cutoff_ym="2025-11")
    assert zero[1]["in_主辅材"] == zero[1]["in_工具"] == Decimal("0.00")
