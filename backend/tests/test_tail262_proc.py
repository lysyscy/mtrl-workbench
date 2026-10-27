"""TAIL-262: historical reads and public matrix regression seams."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.db import Base
from app.mod01_projects import models as _projects  # noqa: F401
from app.mod06_proc import domain as D, repository as R
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot, ProcMaterialManual


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[_projects.Project.__table__, ProcCutoff.__table__,
                                           ProcHistoryBatch.__table__, ProcHistorySnapshot.__table__, ProcMaterialManual.__table__])
    with Session(engine) as s:
        yield s


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


def test_historical_batches_filter_active_values_without_removing_trace(session):
    session.add_all([ProcHistoryBatch(batch_no=name, warehouse_name='A', status=status)
                     for name, status in [('active', 'active'), ('old', 'replaced'), ('undo', 'rolled_back')]])
    session.add_all([ProcHistorySnapshot(batch_no=name, warehouse_name='A', ym='2025-01', in_0=amount)
                     for name, amount in [('active', '12.34'), ('old', '999'), ('undo', '888')]])
    session.flush()
    active = R.load_history(session)
    assert [(row['ym'], row['in_主辅材']) for row in active] == [('2025-01', Decimal('12.34'))]
    assert len(R.load_history(session, active_only=False)) == 3
    assert {row.status for row in R.load_batches(session)} == {'active', 'replaced', 'rolled_back'}
