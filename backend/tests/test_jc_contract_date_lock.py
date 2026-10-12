"""审核日期保护的隔离存储回归；只使用内存 SQLite，不接真实业务库。"""

from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project
from app.mod11_jc import repository as R
from app.mod11_jc.models import JcContract, TAG_OUT
from tests.acc_plugin import acc


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Project.__table__.create(engine)
    JcContract.__table__.create(engine)
    with Session(engine) as s:
        yield s
        s.rollback()
    engine.dispose()


def fetched(no, date):
    return {"contract_no": no, "sign_date": date, "supplier_name": "新供应商",
            "bill_name": "新单据名", "party_name": "新甲方", "contract_amt": "123.45",
            "material_name": "新材料"}


@pytest.mark.parametrize("source_date", ["2026-10-12", "", None, "202050225"])
@pytest.mark.parametrize("locked", [True, False])
@acc()
def test_protected_date_and_other_sync_fields(session, source_date, locked):
    row = JcContract(contract_no="REVIEWED", project_id=1, contract_date="2025-02-25",
                     contract_date_locked=locked, supplier="旧供应商", material_name="人工材料",
                     tag=TAG_OUT, remark="人工备注", contract_amt=Decimal("10"))
    session.add(row)
    session.flush()
    result = R.upsert_fetched_contracts(session, project_id=2, rows=[fetched("REVIEWED", source_date)])
    session.expire_all()
    row = session.get(JcContract, row.id)
    assert result == {"inserted": 0, "refreshed": 1, "skipped": 0}
    assert row.contract_date == ("2025-02-25" if locked else source_date or "")
    assert row.contract_date_locked is locked
    assert (row.supplier, row.bill_name, row.party_name, row.contract_amt) == (
        "新供应商", "新单据名", "新甲方", Decimal("123.45"))
    assert (row.material_name, row.tag, row.remark, row.project_id) == ("人工材料", TAG_OUT, "人工备注", 1)


@acc()
def test_new_contract_is_unprotected_and_missing_number_skips(session):
    result = R.upsert_fetched_contracts(session, project_id=1, rows=[fetched("NEW", "2026-10-12"), fetched("", "")])
    row = session.execute(select(JcContract)).scalar_one()
    assert result == {"inserted": 1, "refreshed": 0, "skipped": 1}
    assert row.contract_date == "2026-10-12"
    assert row.contract_date_locked is False
    R.upsert_fetched_contracts(session, project_id=1, rows=[fetched("NEW", "")])
    assert row.contract_date == ""


@acc()
def test_cached_unprotected_row_reloads_new_protection(session):
    row = JcContract(contract_no="CACHED", project_id=1, contract_date="2025-11-14")
    session.add(row)
    session.flush()
    session.connection().execute(text(
        "update jc_contract set contract_date='2025-02-25',contract_date_locked=true where id=:id"), {"id": row.id})
    assert row.contract_date_locked is False  # 此Session尚缓存旧状态。
    R.upsert_fetched_contracts(session, project_id=1, rows=[fetched("CACHED", "2025-11-14")])
    assert row.contract_date == "2025-02-25" and row.contract_date_locked is True


@acc()
def test_migration_defaults_and_downgrade_keep_dates():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    path = Path(__file__).resolve().parents[1] / "alembic/versions/c313261012_contract_date_lock.py"
    spec = importlib.util.spec_from_file_location("date_lock_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as c:
        c.execute(text("create table jc_contract (id integer primary key, contract_date varchar(10))"))
        c.execute(text("insert into jc_contract values (1, '2025-11-14')"))
        with Operations.context(MigrationContext.configure(c)):
            migration.upgrade()
            c.execute(text("insert into jc_contract (id,contract_date) values (2, '')"))
            assert c.execute(text("select contract_date,contract_date_locked from jc_contract order by id")).all() == [
                ("2025-11-14", 0), ("", 0)]
            migration.downgrade()
        assert c.execute(text("select * from jc_contract order by id")).all() == [(1, "2025-11-14"), (2, "")]
    engine.dispose()
