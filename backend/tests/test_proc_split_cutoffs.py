"""历史数据迁移、兼容截止分组与单格保存的保留回归。"""
from decimal import Decimal

from app.mod06_proc import domain as D
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.db import Base
from app.mod01_projects.models import Project
from app.mod06_proc import repository as R
from app.mod06_proc.models import (ProcMechManual, ProcHistoryBatch, ProcHistorySnapshot,
                                   ProcCutoff, ProcMechImportChange)


def test_single_cell_api_preserves_other_amounts_and_origins(session, monkeypatch):
    from contextlib import contextmanager
    from app.mod06_proc import router
    from app.core.errors import MustReportError

    @contextmanager
    def scope():
        yield session

    monkeypatch.setattr(router, "session_scope", scope)
    row = R.save_mech(session, ym="2025-01", warehouse="A",
                      values={"mech_0": 1200, "mech_1": 765})
    row.source_batches = {"mech_1": "import-1"}
    router.api_mech_save(router.MechSaveRequest(warehouse="A", ym="2025-01",
                                               values={"mech_0": "15000"}))
    assert row.mech_0 == Decimal("15000")
    assert row.mech_1 == Decimal("765")
    assert row.source_batches["mech_1"] == "import-1"
    for invalid in ("-1", "abc"):
        with pytest.raises(MustReportError):
            router.api_mech_save(router.MechSaveRequest(warehouse="A", ym="2025-01",
                                                       values={"mech_0": invalid}))
        assert row.mech_0 == Decimal("15000")
    router.api_mech_save(router.MechSaveRequest(warehouse="A", ym="2025-01",
                                               values={"mech_0": ""}))
    assert row.mech_0 == 0 and row.mech_1 == Decimal("765")


@pytest.fixture
def session():
    from app.core.config import get_settings
    engine = create_engine(get_settings().test_database_url)
    with engine.connect() as connection:
        transaction = connection.begin()
        # 全部清理仅存在未提交事务中；不污染其他真实PG判据的已提交数据。
        for model in (ProcMechImportChange, ProcMechManual, ProcHistorySnapshot, ProcHistoryBatch, ProcCutoff):
            connection.execute(model.__table__.delete())
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


def test_effective_sources_ignore_import_cutoffs():
    rows = D.build_matrix(inv_rows=[], history_rows=[{"warehouse": "A", "ym": "2025-12", "in_主辅材": 10}],
                          manual_rows=[{"warehouse": "A", "ym": "2025-12", "mech_1": 20}],
                          warehouse="A", adjusted=False, cutoff_ym="2025-11")
    assert rows[0]["in_主辅材"] == Decimal("10.00")
    assert rows[0]["mech_1"] == Decimal("20.00")
    assert D.column_editable("mech_1", ym="2025-01", cutoff_ym="2025-11")


def test_migration_uses_old_effective_history_and_preserves_formal_manual(session):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parents[1] / "alembic/versions/c262263d2609_proc_split_cutoffs.py"
    spec = importlib.util.spec_from_file_location("split_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    session.add(ProcCutoff(warehouse_name="A", cutoff_ym="2025-11"))
    session.flush()
    R.save_mech(session, ym="2025-11", warehouse="A", values={"mech_0": 99})
    R.save_mech(session, ym="2025-12", warehouse="A", values={"mech_0": 88})
    session.add(ProcHistoryBatch(batch_no="active", warehouse_name="A", status="active"))
    session.add(ProcHistoryBatch(batch_no="replaced", warehouse_name="A", status="replaced"))
    session.add_all([
        ProcHistorySnapshot(batch_no="active", warehouse_name="A", ym="2025-11", mech_0=10),
        ProcHistorySnapshot(batch_no="active", warehouse_name="A", ym="2025-11", mech_0=20),
        ProcHistorySnapshot(batch_no="replaced", warehouse_name="A", ym="2025-11", mech_0=999),
        ProcHistorySnapshot(batch_no="active", warehouse_name="A", ym="2025-12", mech_0=777)])
    session.flush()
    migration.migrate_displayed_mechanics(session.connection())
    session.expire_all()
    assert {r["ym"]: r["mech_0"] for r in R.load_mech(session)} == {
        "2025-11": Decimal("30.00"), "2025-12": Decimal("88.00")}
    followup_spec = importlib.util.spec_from_file_location("split_rollback_migration",
        path.parent / "c262263e2610_proc_legacy_rollback.py")
    followup = importlib.util.module_from_spec(followup_spec)
    followup_spec.loader.exec_module(followup)
    followup.attach_legacy_rollback(session.connection())
    session.expire_all()
    legacy = {r['ym']: r for r in R.load_mech(session)}
    assert legacy['2025-11']['mech_0'] == Decimal('30.00')
    assert legacy['2025-12']['mech_0'] == Decimal('88.00')
    assert R.mech_row(session, 'A', '2025-11').source_batches['mech_0'] == 'active'
    assert list(session.scalars(select(ProcMechImportChange)))
