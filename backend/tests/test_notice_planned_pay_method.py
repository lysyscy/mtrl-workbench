"""通知书拟付款方式：读回、付款默认、重抓保护及存量迁移；仅内存库/离线桩。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.mod03_notice.merge import PROTECTED, plan_merge
from app.mod05_flow.models import PaymentFlow
from tests.m03_action_helpers import _client, _notice


def test_通知书拟付款方式完整读回且重抓不覆盖():
    client, _ = _client([_notice(1, planned_pay_method="供应链")])
    item = client.get("/api/m03/notice-list?period=").json()["items"][0]
    assert item["planned_pay_method"] == "供应链"
    assert "planned_pay_method" in PROTECTED
    plan = plan_merge({"planned_pay_method": "供应链"},
                      {"planned_pay_method": "现汇"}, [], notice_id=1)
    assert "planned_pay_method" not in plan.values


@pytest.mark.parametrize("draft,expected", [("", "供应链"), ("承兑", "承兑")])
def test_付款默认通知书拟方式且本次手改优先(draft, expected):
    client, fake = _client([_notice(1, planned_pay_method="供应链")])
    result = client.post("/api/m03/actions/batch-pay", json={
        "ids": [1], "drafts": {"1": {"amount": "10", "pay_method": draft}},
        "pay_date": "2026-10-15", "request_id": "planned-method-test",
    }).json()
    assert result["ok"] is True
    flows = [f for f in fake.added if isinstance(f, PaymentFlow)]
    assert len(flows) == 1 and flows[0].pay_method == expected


def test_拟方式其他仍须实际付款备注且整批拒绝():
    client, fake = _client([_notice(1, planned_pay_method="现汇"),
                            _notice(2, planned_pay_method="其他")])
    payload = {"ids": [1, 2], "drafts": {"1": {"amount": "10"}, "2": {"amount": "20"}},
               "pay_date": "2026-10-15", "request_id": "planned-other-test"}
    result = client.post("/api/m03/actions/batch-pay", json=payload).json()
    assert result["ok"] is False and "必须填备注" in result["message"]
    assert not [f for f in fake.added if isinstance(f, PaymentFlow)]
    result = client.post("/api/m03/actions/batch-pay", json={**payload, "remark": "其他方式已核对"}).json()
    assert result["ok"] is True
    assert {f.pay_method for f in fake.added if isinstance(f, PaymentFlow)} == {"现汇", "其他"}


def test_存量迁移默认空且保留既有金额():
    path = Path(__file__).parents[1] / "alembic/versions/c350261015_notice_planned_pay_method.py"
    spec = importlib.util.spec_from_file_location("planned_method_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE payment_notice (id INTEGER PRIMARY KEY, amount_approved NUMERIC)")
        conn.exec_driver_sql("INSERT INTO payment_notice VALUES (1, 123.45)")
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        assert conn.exec_driver_sql("SELECT amount_approved, planned_pay_method FROM payment_notice").one() == (123.45, "")
        conn.exec_driver_sql("INSERT INTO payment_notice (id) VALUES (2)")
        assert conn.exec_driver_sql("SELECT planned_pay_method FROM payment_notice WHERE id=2").scalar_one() == ""
        column = next(c for c in sa.inspect(conn).get_columns("payment_notice") if c["name"] == "planned_pay_method")
        assert column["nullable"] is False and column["type"].length == 32
        migration.downgrade()
        assert conn.exec_driver_sql("SELECT amount_approved FROM payment_notice WHERE id=1").scalar_one() == 123.45
    engine.dispose()
