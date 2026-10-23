"""集采合同约定的 API 回归，运行于任务专用 PostgreSQL schema。"""
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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
