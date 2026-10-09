"""验证双截止筛选、机械逐格互覆/回滚与真实PG事务中的金额及旧数据显示迁移。"""
from decimal import Decimal

from app.mod06_proc import importer as I, domain as D
from tests.acc_plugin import acc
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.db import Base
from app.mod01_projects.models import Project
from app.mod06_proc import repository as R
from app.mod06_proc.models import (ProcMechManual, ProcHistoryBatch, ProcHistorySnapshot,
                                   ProcCutoff, ProcMechImportChange)


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


@acc()
def test_category_cutoffs_filter_before_amount_validation():
    rows, _, bad = I.plan_rows([
        {"_row": 19, "核算月": "2025年12月（一标）", "入库主辅材": "备注", "内租设备": "12"},
        {"_row": 20, "核算月": "2025年12月（三标）", "内租设备": "8"},
    ], material_cutoff_ym="2025-11", mechanical_cutoff_ym="2026-09")
    assert not bad
    assert sum(row.get("mech_1", 0) for row in rows) == Decimal("20.00")
    assert not any("in_主辅材" in row for row in rows)
    from app.mod06_proc import imp_spec
    preview = imp_spec.preview(None, [{"_row": 19, "核算月": "2025年12月（一标）",
        "入库主辅材": "备注", "内租设备": "12"}], {},
        {"material_cutoff_ym": "2025-11", "mechanical_cutoff_ym": "2026-09"})
    detail = preview["blocks"][0]["rows"][0]
    assert "不导入" in detail[2] and "导入" in detail[3]
    assert not preview["skipped"]


@acc()
def test_effective_sources_ignore_import_cutoffs():
    rows = D.build_matrix(inv_rows=[], history_rows=[{"warehouse": "A", "ym": "2025-12", "in_主辅材": 10}],
                          manual_rows=[{"warehouse": "A", "ym": "2025-12", "mech_1": 20}],
                          warehouse="A", adjusted=False, cutoff_ym="2025-11")
    assert rows[0]["in_主辅材"] == Decimal("10.00")
    assert rows[0]["mech_1"] == Decimal("20.00")
    assert D.column_editable("mech_1", ym="2025-01", cutoff_ym="2025-11")


@acc()
def test_import_manual_reimport_and_rollback_preserve_later_edits(session):
    R.save_mech(session, ym="2025-09", warehouse="A", values={"mech_0": 1, "mech_1": 2})
    R.save_mech(session, ym="2026-10", warehouse="A", values={"mech_0": 77})
    def write(batch):
        return R.import_snapshot(session, warehouse="A", rows=[
            {"ym": "2025-09", "mech_0": 3, "mech_1": 4},
            {"ym": "2025-09", "mech_0": 2, "mech_1": 6},
            {"ym": "2026-09", "mech_0": 8}], batch_no=batch, operator="验证",
            material_cutoff_ym="2025-11", mechanical_cutoff_ym="2026-09")
    write("first")
    assert {r["ym"]: r["mech_0"] for r in R.load_mech(session)} == {
        "2025-09": Decimal("5.00"), "2026-09": Decimal("8.00"), "2026-10": Decimal("77.00")}
    R.save_mech(session, ym="2025-09", warehouse="A", values={"mech_0": 9})
    R.rollback_batch(session, batch_no="first")
    values = {r["ym"]: r for r in R.load_mech(session)}
    assert values["2025-09"]["mech_0"] == Decimal("9.00")
    assert values["2025-09"]["mech_1"] == Decimal("2.00")
    write("second")
    write("third")
    R.rollback_batch(session, batch_no="second")
    assert {r["ym"]: r for r in R.load_mech(session)}["2025-09"]["mech_0"] == Decimal("5.00")
    R.rollback_batch(session, batch_no="third")
    assert {r["ym"]: r for r in R.load_mech(session)}["2025-09"]["mech_0"] == Decimal("9.00")
    assert R.rollback_batch(session, batch_no="third") == 0


@acc()
def test_mechanical_only_import_has_no_fake_material_and_zero_clears(session):
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2025-11", "in_主辅材": 123}],
                      batch_no="old", operator="验证")
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2026-09", "mech_2": 44}],
                      batch_no="new", operator="验证", material_cutoff_ym="2025-11",
                      mechanical_cutoff_ym="2026-09")
    history = R.load_history(session)
    assert not any(key in row for key in D.MATERIAL_KEYS for row in history)
    matrix = D.build_matrix(inv_rows=[], history_rows=history, manual_rows=R.load_mech(session),
                            warehouse="A", adjusted=False, cutoff_ym="2025-11")
    assert matrix[0]["material_empty"] is True
    assert all(matrix[0][key] is None for key in D.MATERIAL_KEYS)
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2026-09", "mech_2": 0}],
                      batch_no="zero", operator="验证")
    assert R.load_mech(session)[0]["mech_2"] == Decimal("0.00")
    assert not any(row["ym"] == "2025-11" for row in R.load_history(session))


@acc()
def test_mechanical_import_preserves_red_letter_amount(session):
    from app.mod06_proc import imp_spec
    records = [{"_row": 4, "核算月": "2026-09", "内租设备": "-23.45"}]
    opts = {"warehouse": "A", "material_cutoff_ym": "2025-11", "mechanical_cutoff_ym": "2026-09"}
    assert imp_spec.preview(session, records, {}, opts)["writable"] == 1
    imp_spec.commit(session, records, {}, "验证", opts)
    assert R.load_mech(session)[0]["mech_1"] == Decimal("-23.45")


@acc()
def test_numeric_zero_is_imported_and_category_defaults_are_independent():
    rows, _, bad = I.plan_rows([{"_row": 4, "核算月": "2026-09", "内租设备": 0},
                               {"_row": 5, "核算月": "2025-11", "入库主辅材": 12}])
    assert not bad and len(rows) == 2
    assert rows[0]["mech_1"] == Decimal("0.00")
    assert I.selected_cutoffs(rows) == {"material_cutoff_ym": "2025-11", "mechanical_cutoff_ym": "2026-09"}


@acc()
def test_rollback_removes_only_import_created_month_and_preserves_explicit_manual_zero(session):
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2026-08", "mech_0": 8}],
                      batch_no="only_import", operator="验证")
    R.rollback_batch(session, batch_no="only_import")
    assert R.load_mech(session) == []
    R.import_snapshot(session, warehouse="A", rows=[{"ym": "2026-08", "mech_0": 8}],
                      batch_no="later_manual", operator="验证")
    R.save_mech(session, warehouse="A", ym="2026-08", values={"mech_0": 0})
    R.rollback_batch(session, batch_no="later_manual")
    assert R.load_mech(session)[0]["ym"] == "2026-08"
    assert R.load_mech(session)[0]["mech_0"] == Decimal("0.00")


@acc()
def test_migration_uses_old_effective_history_and_preserves_formal_manual(session):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parents[1] / "alembic/versions/c262263d2609_proc_split_cutoffs.py"
    spec = importlib.util.spec_from_file_location("split_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    R.set_cutoff(session, warehouse="A", cutoff_ym="2025-11")
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
    R.save_mech(session, warehouse="A", ym="2025-11", values={"mech_1": 12})
    R.rollback_batch(session, batch_no="active")
    legacy = {r["ym"]: r for r in R.load_mech(session)}
    assert legacy["2025-11"]["mech_0"] == Decimal("0.00")
    assert legacy["2025-11"]["mech_1"] == Decimal("12.00")
    assert legacy["2025-12"]["mech_0"] == Decimal("88.00")


@acc()
@pytest.mark.parametrize("project,late_months", [("晋江", 10), ("安徽国风", 3), ("福建南平", 6)])
def test_real_workbooks_selected_categories_commit_without_mutating_source(session, project, late_months):
    from pathlib import Path
    from hashlib import sha256
    from app.mod06_proc import imp_spec
    source = Path("D:/工作/材料/材机报表/材机费汇总（过程资料）") / f"材料机械消耗汇总表({project}).xlsx"
    if not source.exists():
        pytest.skip("现场样表不在此机器")
    data = source.read_bytes()
    fingerprint = sha256(data).hexdigest()
    grid, _ = I.read_sheet(data)
    head, leaf, index = I._pick_header(grid)
    labels = {f.key: f.label for f in I.FIELDS}
    records = [{"_row": number + 1, **{labels[key]: row[col] if col < len(row) else ""
                 for key, col in index.items()}}
               for number, row in enumerate(grid) if number > (leaf if leaf is not None else head)]
    opts = {"warehouse": project, "material_cutoff_ym": "2025-11", "mechanical_cutoff_ym": "2026-09"}
    preview = imp_spec.preview(session, records, {}, opts)
    assert preview["writable"] > 0, preview["blocks"]
    imp_spec.commit(session, records, {}, "现场样表隔离验证", opts)
    months = {r["ym"] for r in R.load_mech(session) if r["ym"] >= "2025-12"
              and any(r[k] != 0 for k in D.MECH_KEYS)}
    assert len(months) == late_months
    history = R.load_history(session)
    assert all(r["ym"] <= "2025-11" for r in history if any(k in r for k in D.MATERIAL_KEYS))
    if project != "晋江":
        assert not any(k in r for r in history for k in D.MATERIAL_KEYS)
    else:
        assert {"2025-09", "2025-10"}.issubset({r["ym"] for r in history})
    assert sha256(source.read_bytes()).hexdigest() == fingerprint
