"""90条修正/恢复的PG事务验证；独立测试库临时schema，整批回滚。"""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.mod01_projects.models import Project
from app.mod11_jc.models import JcContract


@pytest.fixture
def isolated():
    url = get_settings().test_database_url
    assert make_url(url).database == "mtrl_workbench_test"
    path = Path(__file__).resolve().parents[2] / "tools/oneoff/_tail313_contract_dates.py"
    spec = importlib.util.spec_from_file_location("date_transaction", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine(url, echo=False)
    with engine.connect() as c:
        tx = c.begin()
        assert c.execute(text("select current_database()")).scalar_one() == "mtrl_workbench_test"
        schema = "tail313_test_" + uuid4().hex
        c.execute(text(f'create schema "{schema}"'))
        c.execute(text(f'set local search_path="{schema}"'))
        Project.__table__.create(c)
        JcContract.__table__.create(c)
        with Session(bind=c, join_transaction_mode="create_savepoint") as s:
            s.add(Project(id=1, warehouse_name="隔离项目", name_full="隔离项目"))
            s.flush()
            for i in range(10001, 10092):
                s.add(JcContract(id=i, project_id=1, contract_no=f"FAKE-{i}",
                                 contract_date="2025-11-14", contract_amt=10, supplier="原供应商"))
            s.commit()  # 只释放测试会话savepoint；外层事务未提交。
        before = [dict(r) for r in c.execute(text(
            "select c.*,p.warehouse_name project from jc_contract c join project p on p.id=c.project_id "
            "where c.id<10091 order by c.id")).mappings()]
        records = [{"id": r["id"], "contract_no": r["contract_no"], "project_id": 1, "project": "隔离项目",
                    "expected_old_date": "2025-11-14", "expected_updated_at": str(r["updated_at"]),
                    "new_date": "2025-02-25", "restore_date": "2025-11-14", "restore_locked": False} for r in before]
        try:
            yield c, module, before, records
        finally:
            tx.rollback()  # 临时schema与全部假数据一起移除。
    engine.dispose()


def test_90_updates_restore_and_excluded_record(isolated):
    c, module, before, records = isolated
    after = module.write_dates(c, before, records)
    assert len(after) == 90 and all(r["contract_date"] == "2025-02-25" and r["contract_date_locked"] for r in after)
    assert all(r["contract_amt"] == 10 and r["supplier"] == "原供应商" for r in after)
    assert c.execute(text("select contract_date,contract_date_locked from jc_contract where id=10091")).one() == ("2025-11-14", False)
    restored = module.write_dates(c, after, records, restore=True)
    assert all(r["contract_date"] == "2025-11-14" and not r["contract_date_locked"] for r in restored)


def test_identity_mismatch_refuses_entire_batch(isolated):
    c, module, before, records = isolated
    records[-1]["contract_no"] = "WRONG"
    with pytest.raises(AssertionError):
        module.write_dates(c, before, records)
    assert c.execute(text("select count(*) from jc_contract where contract_date_locked")).scalar_one() == 0


def test_mid_batch_rowcount_failure_rolls_back(isolated):
    c, module, before, records = isolated

    class Interrupted:
        count = 0

        def execute(self, statement, params=None):
            if str(statement).startswith("update jc_contract"):
                self.count += 1
                if self.count == 5:
                    class NoRow:
                        rowcount = 0
                    return NoRow()
            return c.execute(statement, params) if params is not None else c.execute(statement)

    with pytest.raises(AssertionError), c.begin_nested():
        module.write_dates(Interrupted(), before, records)
    assert c.execute(text("select count(*) from jc_contract where contract_date_locked")).scalar_one() == 0
