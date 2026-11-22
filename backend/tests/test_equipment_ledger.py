"""三账从 HTTP 写入到 Excel 交付的隔离回归。"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import json
import runpy

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from openpyxl import load_workbook
import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.mod16_equipment.models import EquipmentItem, EquipmentTransfer

from app.core import session
from app.main import create_app
from app.mod16_equipment.api import i8_adapter

ROOT = "/api/m16"
MONTH = "2026-11"
BASE = dict(name="试验焊机", purchase_date="2026-11-03", purchase_project="项目甲", purchase_price="100.1234")


@pytest.fixture
def client(rollback_db, monkeypatch):
    monkeypatch.setattr(session, "secret", lambda: b"equipment-ledger-isolated-test")
    app = create_app()
    with TestClient(app) as http:
        http.cookies.set(session.COOKIE_NAME, session.make("equipment-test"))
        yield http


def request(c, method, path, data=None, status=200):
    response = c.request(method, ROOT + path, json=data)
    assert response.status_code == status, response.text
    return response.json()


def add(c, **kw):
    return request(c, "POST", "/equipment", BASE | kw)


def resolve(c, key, choice):
    return request(c, "POST", f"/rental/lines/{key}/resolve", {"choice": choice})


def workbook(c, path, **kw):
    response = c.get(ROOT + "/export/" + path)
    assert response.status_code == 200
    assert ".xlsx" in response.headers["Content-Disposition"]
    return load_workbook(BytesIO(response.content), **kw)


def test_numbering_receipt_precision_filters_and_inventory_edits(client):
    c = client
    preview = {k: BASE[k] for k in ("name", "purchase_date")}
    assert c.get(ROOT + "/equipment/preview", params=preview).json()["codes"] == ["试验焊机-20261103"]
    one = add(c)
    request(c, "POST", "/equipment", BASE | {"expected_codes": one["codes"]}, 409)
    assert one["i8_sync"][0]["message"] == "i8接口暂未接通，已保存本地待同步"
    codes = request(c, "POST", "/equipment/preview", preview | {"quantity": 2})["codes"]
    two = add(c, quantity=2, in_rental="no")
    assert codes == two["codes"] == ["试验焊机-20261103-02", "试验焊机-20261103-03"]
    inv = two["inventory_item"]
    assert Decimal(inv["book_amount"]) == Decimal("200.2468")
    assert all(i["inventory_item_id"] == inv["id"] and Decimal(i["quantity"]) == 1 for i in two["equipment"])
    request(c, "POST", "/equipment", BASE | {"quantity": "1.5"}, 422)
    assert not two["rental_line_ids"]
    other = add(c, item_category="turnover", quantity="1.5", asset_scope="fixed_asset")
    assert len(other["equipment"]) == 1 and other["inventory_item"] is None
    filtered = request(c, "GET", "/equipment?item_category=equipment&asset_scope=current_asset&in_rental=no&sync_issue_only=true&keyword=焊机&project=项目甲")
    assert filtered["summary"] == dict(active_count=2, pending_sync_count=2, conflict_count=0, pending_rental_count=0)
    key = two["equipment"][0]["id"]
    changed = request(c, "PATCH", f"/equipment/{key}", {"name": "试验乙", "purchase_price": None})
    assert changed["inventory_item_id"] != inv["id"]
    detail = request(c, "GET", f"/equipment/{key}?month={MONTH}")
    assert detail["inventory_item"]["book_amount"] is None
    assert detail["equipment"]["code"] == two["codes"][0]
    manual = request(c, "POST", "/inventory", dict(category="turnover", name="电缆", unit_price=None, book_qty=2, count_qty=1))
    assert manual["book_amount"] is None
    patched = request(c, "PATCH", f"/inventory/{manual['id']}", dict(unit_price="1.4321", diff_qty=-1, diff_reason="待核"))
    assert Decimal(patched["diff_amount"]) == Decimal("-1.4321")
    assert Decimal(request(c, "GET", "/inventory?category=turnover")["count_amount"]) == Decimal("1.4321")


def test_transfer_scrap_pending_queue_and_exports(client):
    c = client
    added = add(c, quantity=2)
    keys = [i["id"] for i in added["equipment"]]
    lines = added["rental_line_ids"]
    assert added["codes"] == ["试验焊机-20261103-01", "试验焊机-20261103-02"]
    tr = request(c, "POST", "/transfers", dict(equipment_ids=keys, to_project="项目乙", transfer_date="2026-11-25"))
    assert len(tr["transfers"]) == 2 and tr["rental_line_ids"] == lines
    assert request(c, "GET", "/inventory")["items"][0]["book_qty"] == "2.0000"
    for key, line in zip(keys, lines):
        detail = request(c, "GET", f"/equipment/{key}?month={MONTH}")
        assert detail["equipment"]["current_project"] == "项目乙" and len(detail["transfers"]) == 1
        next_action = resolve(c, line, "this_month")
        assert next_action["pending_action_type"] == "transfer_attribution"
        assert json.loads(next_action["pending_meta_json"])["suggested_side"] == "from_project"
        resolve(c, line, "from_project")
    request(c, "POST", "/scraps", dict(equipment_id=keys[0], scrap_date="2026-11-28", reason="损坏"))
    request(c, "POST", "/rental/confirm", {"month": MONTH}, 409)
    assert request(c, "GET", "/inventory")["items"][0]["book_qty"] == "1.0000"
    inventory = workbook(c, "inventory")
    assert Decimal(str(workbook(c, "inventory", data_only=True)["封皮"]["I6"].value)) == Decimal("100.1234")
    assert inventory.sheetnames == ["封皮", "流动资产盘点表", "周转材料"]
    ws = inventory.worksheets[1]
    assert ws["F5"].value == 1 and "F5*E5" in ws["G5"].value
    assert "I6" in inventory["封皮"]["H7"].value and ws.page_setup.scale == 92
    assert "A1:L1" in ws.merged_cells and ws.print_title_rows == "$1:$4"
    resolve(c, lines[0], "charge_this_month")
    request(c, "POST", "/scraps", dict(equipment_ids=[keys[1]], scrap_date="2026-11-29"))
    resolve(c, lines[1], "stop_this_month")
    assert not request(c, "GET", "/inventory")["items"]
    assert not request(c, "GET", "/equipment")["items"]
    assert workbook(c, "inventory").worksheets[1]["B5"].value == "合计"
    assert len(request(c, "GET", "/scraps?project=项目乙&keyword=焊机")["items"]) == 2
    transfers = request(c, "GET", "/transfers?project=项目甲&sync_status=pending")["items"]
    assert all(t["rental_attribution"] == "from_project" for t in transfers)
    distribution = workbook(c, "distribution")
    assert distribution.sheetnames == ["工机具基础信息", "调拨记录", "报废记录", "周转材料", "周转材料调拨记录", "周转材料报废记录"]
    assert distribution.worksheets[0]["A3"].value == added["codes"][0]
    assert "COUNTIF" in distribution.worksheets[0]["I3"].value
    assert distribution["调拨记录"]["I2"].value == "项目乙" and distribution["报废记录"]["J2"].value == "损坏"
    cached = workbook(c, "distribution", data_only=True)
    assert cached["工机具基础信息"]["I3"].value == "报废" and cached["调拨记录"]["B2"].value == "试验焊机"
    assert request(c, "POST", "/rental/confirm", {"month": MONTH})["status"] == "confirmed"
    request(c, "PATCH", f"/rental/lines/{lines[0]}", {"quantity": 2}, 409)
    assert not request(c, "GET", "/rental?month=2026-12")["projects"]


def test_rental_carry_reorder_custom_price_blank_and_print(client):
    c = client
    a, b = add(c, quantity=2)["rental_line_ids"]
    zero = add(c, purchase_project="零项目", purchase_price=None)["rental_line_ids"][0]
    resolve(c, a, "next_month")
    resolve(c, b, "this_month")
    resolve(c, zero, "this_month")
    request(c, "PATCH", f"/rental/lines/{zero}", dict(billing_status="blank", distribution_note="保留"))
    request(c, "PATCH", f"/rental/lines/{b}", dict(custom_unit_price=0))
    cleared = request(c, "PATCH", f"/rental/lines/{b}", dict(custom_unit_price=None))
    assert Decimal(cleared["amount"]) == Decimal("5.0062")
    request(c, "PATCH", f"/rental/lines/{b}", dict(custom_unit_price="8.1234", quantity=2))
    request(c, "PUT", "/rental/reorder", dict(month=MONTH, project_name="项目甲", ordered_line_ids=[b]), 409)
    request(c, "PUT", "/rental/reorder", dict(month=MONTH, project_name="项目甲", ordered_line_ids=[b, a]))
    current = request(c, "GET", "/rental?month=2026-11")
    assert current["printable_project_count"] == 1 and Decimal(current["grand_total"]) == Decimal("16.2468")
    ws = workbook(c, "rental?month=2026-11").active
    assert ws.max_column == 9 and ws["F3"].value == "租赁单价（元）"
    assert "G4:G5" in ws["G6"].value and "A1:I1" in ws.merged_cells
    assert Decimal(str(workbook(c, "rental?month=2026-11", data_only=True).active["G6"].value)) == Decimal("16.2468")
    assert "$A$1:$I$7" in ws.print_area and "单位：零项目" in [cell.value for cell in ws["A"]]
    following = request(c, "GET", "/rental?month=2026-12")
    assert Decimal(following["grand_total"]) == Decimal("21.2530")
    groups = {g["project_name"]: g["lines"] for g in following["projects"]}
    assert [r["billing_status"] for r in groups["项目甲"]] == ["normal", "normal"]
    assert groups["项目甲"][0]["custom_unit_price"] == "8.1234"
    assert groups["零项目"][0]["distribution_note"] == "保留" and groups["零项目"][0]["amount"] is None
    assert request(c, "GET", "/rental?month=2026-12&project=项目甲")["projects"][0]["lines"] == groups["项目甲"]


def test_adapter_conflict_retry_and_batch_rollback(client):
    c = client

    class Fake:
        project = None
        writes = []
        def snapshot(self, code):
            return {"current_project": self.project} if self.project else None
        def save_equipment(self, data):
            self.writes.append(data["purchase_date"])
            self.project = data["current_project"]
        def transfer(self, code, expected_project, to_project):
            assert self.project == expected_project
            self.writes.append(to_project)
            self.project = to_project

    adapter = Fake()
    c.app.dependency_overrides[i8_adapter] = lambda: adapter
    key = add(c, in_rental="no")["equipment"][0]["id"]
    assert adapter.writes == ["2026-11-03"]
    adapter.project = "其他"
    req = dict(equipment_ids=[key, 999999], to_project="项目乙", transfer_date="2026-11-24")
    request(c, "POST", "/transfers", req, 404)
    assert request(c, "GET", f"/equipment/{key}")["equipment"]["current_project"] == "项目甲"
    result = request(c, "POST", "/transfers", req | {"equipment_ids": [key]})
    tr = result["transfers"][0]
    assert tr["i8_sync_status"] == "conflict" and adapter.writes == ["2026-11-03"]
    assert request(c, "GET", "/equipment?sync_issue_only=true")["summary"]["conflict_count"] == 1
    assert json.loads(tr["i8_conflict_json"])["snapshot"]["current_project"] == "其他"
    assert request(c, "GET", "/i8-sync/issues")["transfers"][0]["id"] == tr["id"]
    adapter.project = "项目甲"
    assert request(c, "POST", "/i8-sync/retry", {"transfer_ids": [tr["id"]]})["transfers"][0]["status"] == "synced"
    assert request(c, "GET", "/i8-sync/issues") == {"equipment": [], "transfers": []}


def test_early_month_view_and_transfer_across_months(client):
    c = client
    assert request(c, "GET", "/rental?month=2026-12")["projects"] == []
    item = add(c)
    key = item["equipment"][0]["id"]
    line = item["rental_line_ids"][0]
    resolve(c, line, "next_month")
    tr = request(c, "POST", "/transfers", dict(equipment_ids=[key], to_project="项目乙", transfer_date="2026-11-24"))
    assert tr["rental_line_ids"] == [line]
    detail = request(c, "GET", f"/equipment/{key}?month=2026-11")
    assert json.loads(detail["rental_lines"][0]["pending_meta_json"])["suggested_side"] == "to_project"
    request(c, "POST", "/rental/confirm", {"month": "2026-12"}, 409)
    resolve(c, line, "from_project")
    carried = request(c, "GET", "/rental?month=2026-12")["projects"]
    assert len(carried) == 1 and carried[0]["project_name"] == "项目乙"
    assert Decimal(carried[0]["subtotal"]) == Decimal("5.0062")


def test_migration_round_trip_in_isolated_schema(rollback_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/equip261123_equipment_ledger.py"
    revision = runpy.run_path(str(filename))
    schema = rollback_db.exec_driver_sql("select current_schema()").scalar_one()
    assert schema.startswith("backend_verify_")

    def tables():
        return set(inspect(rollback_db).get_table_names(schema=schema))

    initial = tables()
    with Operations.context(MigrationContext.configure(rollback_db)):
        revision["downgrade"]()
        assert tables() == {name for name in initial if not name.startswith("m16_")}
        revision["upgrade"]()
    assert tables() == initial

class RecordingAdapter:
    def __init__(self):
        self.projects = {}
        self.events = []

    def snapshot(self, code):
        return {"current_project": self.projects[code]} if code in self.projects else None

    def save_equipment(self, data):
        with session_scope() as db:
            item = db.get(EquipmentItem, data["id"])
            assert item.i8_sync_status == "pending"
        self.projects[data["code"]] = data["current_project"]
        self.events.append(("create", data["current_project"]))

    def transfer(self, code, expected_project, to_project):
        with session_scope() as db:
            pending = db.scalar(select(EquipmentTransfer).join(EquipmentItem).where(
                EquipmentItem.code == code, EquipmentTransfer.to_project == to_project))
            assert pending.i8_sync_status == "pending"
        assert self.projects[code] == expected_project
        self.projects[code] = to_project
        self.events.append(("transfer", expected_project, to_project))


@pytest.mark.parametrize("operation", ["create", "transfer"])
def test_local_commit_failure_never_writes_i8(client, operation):
    adapter = RecordingAdapter()
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    ids = [row["id"] for row in add(client, quantity=2, in_rental="no")["equipment"]]
    adapter.events.clear()

    def reject_commit(db):
        raise RuntimeError("simulated local commit failure")

    event.listen(Session, "before_commit", reject_commit)
    try:
        with pytest.raises(RuntimeError, match="simulated local commit failure"):
            if operation == "create":
                add(client, quantity=2, in_rental="no")
            else:
                request(client, "POST", "/transfers", dict(equipment_ids=ids, transfer_date="2026-11-05", to_project="乙"))
    finally:
        event.remove(Session, "before_commit", reject_commit)
    assert adapter.events == []
    assert [r["id"] for r in request(client, "GET", "/equipment")["items"]] == ids
    assert request(client, "GET", "/transfers")["items"] == []


@pytest.mark.parametrize("retry_by", ["equipment_ids", "transfer_ids"])
def test_offline_creation_replayed_before_transfers(client, retry_by):
    key = add(client, in_rental="no")["equipment"][0]["id"]
    transfer_ids = []
    for target in ["项目乙", "项目丙"]:
        row = request(client, "POST", "/transfers", dict(equipment_ids=[key], transfer_date="2026-11-10",
                                                        to_project=target))["transfers"][0]
        transfer_ids.append(row["id"])
    adapter = RecordingAdapter()
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    result = request(client, "POST", "/i8-sync/retry", {retry_by: [key if retry_by == "equipment_ids" else transfer_ids[-1]]})
    assert adapter.events == [("create", "项目甲"), ("transfer", "项目甲", "项目乙"), ("transfer", "项目乙", "项目丙")]
    assert [r["id"] for r in result["transfers"]] == transfer_ids
    assert request(client, "GET", "/i8-sync/issues") == {"equipment": [], "transfers": []}


def test_transfer_rejects_stale_origin_and_backdated_changes(client):
    key = add(client, in_rental="no")["equipment"][0]["id"]
    data = dict(equipment_ids=[key], expected_from_projects={key: "项目甲"}, to_project="乙", transfer_date="2026-11-11")
    request(client, "POST", "/transfers", data)
    request(client, "POST", "/transfers", data | {"to_project": "丙"}, 409)
    request(client, "POST", "/transfers", data | dict(to_project="丙", expected_from_projects={key: "乙"},
                                                      transfer_date="2026-11-10"), 409)
    detail = request(client, "GET", f"/equipment/{key}")
    assert detail["equipment"]["current_project"] == "乙" and len(detail["transfers"]) == 1


@pytest.mark.parametrize("count,remaining", [(0, 0), (3, 2)])
def test_scrap_handles_inventory_discrepancy(client, count, remaining):
    created = add(client, in_rental="no", purchase_price="10")
    key = created["equipment"][0]["id"]
    request(client, "PATCH", f"/inventory/{created['inventory_item']['id']}", {"count_qty": count})
    request(client, "POST", "/scraps", dict(equipment_id=key, scrap_date="2026-11-23"))
    row = request(client, "GET", f"/equipment/{key}")["inventory_item"]
    assert [Decimal(row[k]) for k in ("book_qty", "count_qty", "diff_qty")] == [0, remaining, remaining]
    assert [Decimal(row[k]) for k in ("book_amount", "count_amount", "diff_amount")] == [0, 10*remaining, 10*remaining]
    assert row["is_active"] == bool(remaining)


def test_stop_propagation_and_confirmed_month_conflict(client):
    line = add(client)["rental_line_ids"][0]
    resolve(client, line, "this_month")
    for month in ["2026-12", "2027-01"]:
        request(client, "GET", f"/rental?month={month}")
    request(client, "POST", "/rental/confirm", {"month": "2027-01"})
    conflict = request(client, "PATCH", f"/rental/lines/{line}", {"billing_status": "stopped"}, 409)
    assert "2027-01" in conflict["message"]
    assert request(client, "GET", "/rental?month=2026-12")["projects"][0]["lines"][0]["billing_status"] == "normal"


def test_turnover_category_export_and_stop_existing_draft(client):
    line = add(client, item_category="turnover")["rental_line_ids"][0]
    assert resolve(client, line, "this_month")["category_label"] == "周转材料"
    later = "/rental?month=2026-12"
    assert request(client, "GET", later)["projects"][0]["lines"][0]["category_label"] == "周转材料"
    assert workbook(client, later[1:]).active["H4"].value == "周转材料"
    request(client, "PATCH", f"/rental/lines/{line}", {"billing_status": "stopped"})
    stopped = request(client, "GET", later)["projects"][0]["lines"][0]
    assert stopped["billing_status"] == "stopped" and stopped["amount"] is None


def test_remove_rental_flag_stops_open_months_only(client):
    today = date.today().replace(day=1)
    prior = (today - timedelta(days=1)).strftime("%Y-%m")
    months = [today.strftime("%Y-%m"), (today + timedelta(days=32)).strftime("%Y-%m")]
    created = add(client, target_month=prior)
    resolve(client, created["rental_line_ids"][0], "this_month")
    request(client, "POST", "/rental/confirm", {"month": prior})
    for month in months:
        request(client, "GET", f"/rental?month={month}")
    request(client, "PATCH", f"/equipment/{created['equipment'][0]['id']}", {"in_rental": "no"})
    for month in months:
        row = request(client, "GET", f"/rental?month={month}")["projects"][0]["lines"][0]
        assert row["billing_status"] == "stopped" and row["amount"] is None
    assert request(client, "GET", f"/rental?month={prior}")["projects"][0]["lines"][0]["billing_status"] == "normal"

def test_adapter_runs_after_session_closes(client):
    active_sessions = set()
    observed = []

    def opened(db, transaction):
        if transaction.parent is None:
            active_sessions.add(db)

    def closed(db, transaction):
        if transaction.parent is None:
            active_sessions.discard(db)

    class Probe(RecordingAdapter):
        def snapshot(self, code):
            observed.append(len(active_sessions))
            return super().snapshot(code)

    adapter = Probe()
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    event.listen(Session, "after_transaction_create", opened)
    event.listen(Session, "after_transaction_end", closed)
    try:
        key = add(client, in_rental="no")["equipment"][0]["id"]
        request(client, "POST", "/transfers", dict(equipment_ids=[key], transfer_date="2026-11-05", to_project="乙"))
    finally:
        event.remove(Session, "after_transaction_create", opened)
        event.remove(Session, "after_transaction_end", closed)
    assert adapter.events == [("create", "项目甲"), ("transfer", "项目甲", "乙")]
    assert observed == [0, 0, 0, 0]
