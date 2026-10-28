"""集采合同约定的 API 回归，运行于任务专用 PostgreSQL schema。"""
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod11_jc import api, repository as R
from app.mod11_jc.models import JcContract


@pytest.fixture
def contract(rollback_db):
    with session_scope() as s:
        p = Project(warehouse_name="账期隔离仓", name_full="账期隔离项目")
        s.add(p)
        s.flush()
        row = R.insert_contract(s, project_id=p.id, contract_amt="123.45", remark="原备注")
        return row.id


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_contract_fields_persist_and_refetch_preserves_human_values(contract, client):
    result = client.post("/api/m11/fields", json={"id": contract, "fields": {
        "payment_term": "60天", "payment_method": "承兑", "remark": "5%质保金一年"}}).json()
    assert result["ok"]
    data = client.get("/api/m11/detail", params={"id": contract}).json()["data"]
    assert (data["payment_term"], data["payment_method"], data["remark"]) == ("60±0天", "承兑", "5%质保金一年")
    with session_scope() as s:
        row = s.get(JcContract, contract)
        row.contract_no = "TERMS-ISOLATED"
        s.flush()
        R.upsert_fetched_contracts(s, project_id=row.project_id, rows=[{
            "contract_no": row.contract_no, "contract_amt": "123.45", "remark": "覆盖测试",
            "payment_term": "999天", "payment_method": "现汇"}])
    rows = client.get("/api/m11/list").json()["rows"]
    row = next(r for r in rows if r["id"] == contract)
    assert (row["payment_term"], row["payment_method"], row["remark"]) == ("60±0天", "承兑", "5%质保金一年")
    assert Decimal(row["contract_amt"]) == Decimal("123.45")


@pytest.mark.parametrize("fields", [
    {"payment_term": "-60天"}, {"payment_term": "90±-10天"},
    {"payment_term": "三个月"}, {"payment_term": "60.5天"},
    {"payment_method": "银行承兑"}, {"payment_term": [60]},
])
def test_invalid_input_keeps_entire_update(contract, client, fields):
    result = client.post("/api/m11/fields", json={"id": contract, "fields": {"remark": "不应写入", **fields}}).json()
    assert not result["ok"]
    assert client.get("/api/m11/detail", params={"id": contract}).json()["data"]["remark"] == "原备注"


def test_add_and_clear_fields(contract, client):
    result = client.post("/api/m11/add", json={"project_key": "账期隔离仓", "payment_term": "90±10", "payment_method": "供应链"}).json()
    assert result["ok"]
    data = client.get("/api/m11/detail", params={"id": result["id"]}).json()["data"]
    assert (data["payment_term"], data["payment_method"]) == ("90±10天", "供应链")
    assert client.post("/api/m11/fields", json={"id": result["id"], "fields": {"payment_term": "", "payment_method": ""}}).json()["ok"]
    data = client.get("/api/m11/detail", params={"id": result["id"]}).json()["data"]
    assert data["payment_term"] == data["payment_method"] == ""


@pytest.mark.parametrize("remark,term,method,left", [
    ("90±7，银承，5%质保金一年", "90±7天", "承兑", "5%质保金一年"),
    ("20±7天内、银行承兑", "20±7天", "承兑", ""),
    ("60天，承兑", "60±0天", "承兑", ""),
    ("发货前95%，5%质保金，银承", "", "承兑", "发货前95%，5%质保金"),
    ("验收后60天，银行承兑", "", "承兑", "验收后60天"),
    ("90±10，60天，现汇", "", "现汇", "90±10，60天"),
    ("60天，现汇或承兑", "60±0天", "", "现汇或承兑"),
    ("三个月，承兑", "", "承兑", "三个月"),
    ("60±7银行承兑", "60±7天", "承兑", ""),
    ("30±7银承", "30±7天", "承兑", ""),
    ("90天银行承兑", "90±0天", "承兑", ""),
    ("30天承兑", "30±0天", "承兑", ""),
    ("60天现汇", "60±0天", "现汇", ""),
    ("60±7银承5%质保金", "60±7天", "承兑", "5%质保金"),
    ("增补45±7承兑5%质保金", "45±7天", "承兑", "增补5%质保金"),
    ("45天银承5%质保金", "45±0天", "承兑", "5%质保金"),
    ("承兑5%质保金", "", "承兑", "5%质保金"),
    (" 60±7 银承 5%质保金一年 ", "60±7天", "承兑", "5%质保金一年"),
    ("60天现汇，30天承兑", "", "", "60天现汇，30天承兑"),
    ("非承兑", "", "", "非承兑"),
    ("每个月20日对账、开具发票，次月底前以银行承兑方式支付货款，直至项目结束", "", "", "每个月20日对账、开具发票，次月底前以银行承兑方式支付货款，直至项目结束"),
    ("增补60万合同", "", "", "增补60万合同"),
])
def test_remark_migration_preserves_other_text_and_is_repeatable(remark, term, method, left):
    from app.mod11_jc.domain import remark_payment_proposal
    expected = {"payment_term": term, "payment_method": method, "remark": left}
    assert remark_payment_proposal(remark=remark) == expected
    assert remark_payment_proposal(**expected) == expected
    manual = remark_payment_proposal(remark=remark, payment_term="30±0天", payment_method="其他")
    assert manual == {"payment_term": "30±0天", "payment_method": "其他", "remark": remark}



def test_preview_apply_is_atomic_and_rejects_stale_rows(contract):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "tools/oneoff/_jc_payment_terms.py"
    spec = importlib.util.spec_from_file_location("terms_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with session_scope() as s:
        row = s.get(JcContract, contract)
        row.remark = "90±7，银承，5%质保金一年"
    with session_scope() as s:
        preview = migration.proposal(migration.snapshot(s.connection()))
        assert migration.apply_preview(s.connection(), preview) == 1
        current = migration.snapshot(s.connection())
        assert current[0]["payment_term"] == "90±7天"
        assert current[0]["payment_method"] == "承兑"
        assert current[0]["remark"] == "5%质保金一年"
        assert migration.proposal(current) == []
        with pytest.raises(ValueError, match="已变化"):
            migration.apply_preview(s.connection(), preview)
    with session_scope() as s:
        row = s.get(JcContract, contract)
        assert row.contract_amt == Decimal("123.45")



def test_schema_migration_defaults_and_downgrade_preserve_business_values():
    import importlib.util
    from pathlib import Path
    from uuid import uuid4
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from app.core.db import get_engine
    path = Path(__file__).resolve().parents[1] / "alembic/versions/c432261023_jc_payment_terms.py"
    spec = importlib.util.spec_from_file_location("terms_schema_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with get_engine().connect() as c:
        outer = c.begin()
        try:
            schema = "terms_ddl_" + uuid4().hex
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
            c.execute(text(f'SET LOCAL search_path="{schema}"'))
            c.execute(text("CREATE TABLE jc_contract (id integer primary key, remark text, contract_amt numeric(18,2), method text)"))
            c.execute(text("INSERT INTO jc_contract VALUES (1,'60天，银承',123.45,'旧长文本')"))
            with Operations.context(MigrationContext.configure(c)):
                migration.upgrade()
                assert c.execute(text("SELECT remark,contract_amt,method,payment_term,payment_method FROM jc_contract")).one() == (
                    '60天，银承', Decimal('123.45'), '旧长文本', '', '')
                migration.downgrade()
            assert c.execute(text("SELECT * FROM jc_contract")).one() == (1, '60天，银承', Decimal('123.45'), '旧长文本')
        finally:
            outer.rollback()



def test_migration_target_binds_actual_table_schema():
    import importlib.util
    from pathlib import Path
    from uuid import uuid4
    from sqlalchemy import text
    from app.core.db import get_engine
    path = Path(__file__).resolve().parents[2] / "tools/oneoff/_jc_payment_terms.py"
    spec = importlib.util.spec_from_file_location("terms_target", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with get_engine().connect() as c:
        outer = c.begin()
        try:
            original = migration.target_fingerprint(c)
            schema = 'terms_identity_' + uuid4().hex
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
            c.execute(text(f'CREATE TABLE "{schema}".jc_contract (id integer)'))
            c.execute(text(f'SET LOCAL search_path="{schema}"'))
            assert migration.target_fingerprint(c) != original
        finally:
            outer.rollback()
