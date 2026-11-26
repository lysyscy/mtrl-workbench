"""三账从 HTTP 写入到 Excel 交付的隔离回归。"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import json
import hashlib
import os
import runpy
from unittest.mock import Mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
import pytest
from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod16_equipment import rental
from app.mod16_equipment.importer import import_equipment_baseline, parse_rental, transfer_date_note
from app.mod16_equipment.models import (
    EquipmentItem, EquipmentScrap, EquipmentTransfer, InventoryItem, Location, RentalLine, RentalMonth,
)

from app.core import session
from app.main import create_app
from app.mod16_equipment.api import i8_adapter
from app.mod16_equipment.sync import I8CustomFormEquipmentAdapter

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


def archive_project(db, disp, **fields):
    project = Project(**({"disp": disp, "warehouse_name": f"测试仓-{disp}", "phid": f"i8-{disp}"} | fields))
    db.add(project)
    db.flush()
    return project.id


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
    inventory = request(c, "GET", "/inventory?category=turnover")
    assert Decimal(inventory["count_amount"]) == Decimal("1.4321")
    assert inventory["items"][0]["linked_equipment_ids"] == inventory["items"][0]["linked_equipment_codes"] == []
    linked = {row["id"]: row for row in request(c, "GET", "/inventory?category=tool")["items"]}
    assert linked[inv["id"]]["linked_equipment_ids"] == [two["equipment"][1]["id"]]
    assert linked[inv["id"]]["linked_equipment_codes"] == [two["codes"][1]]
    new_inv = linked[changed["inventory_item_id"]]
    assert (new_inv["linked_equipment_ids"], new_inv["linked_equipment_codes"]) == ([key], [two["codes"][0]])


def test_creation_uses_purchase_project_for_initial_location(client):
    with session_scope() as db:
        purchase_id = archive_project(db, "购置项目")
        override_id = archive_project(db, "其他项目")
    added = add(client, purchase_project_id=purchase_id, purchase_project_custom="购置片区", quantity=2,
                current_project_id=override_id, current_project_custom="其他片区", current_project="其他项目")
    for item in added["equipment"]:
        assert (item["current_project"], item["current_project_id"], item["current_project_custom"]) == (
            item["purchase_project"], item["purchase_project_id"], item["purchase_project_custom"]) == (
            "购置片区", purchase_id, "购置片区")
    inv, = request(client, "GET", "/inventory")["items"]
    assert inv["linked_equipment_ids"] == [item["id"] for item in added["equipment"]]
    assert inv["linked_equipment_codes"] == added["codes"]
    group, = request(client, "GET", f"/rental?month={MONTH}")["projects"]
    assert group["project_id"] == purchase_id
    assert not request(client, "GET", "/transfers")["items"]


@pytest.mark.parametrize(("category", "scope"), [
    ("equipment", "off_book"), ("equipment", "fixed_asset"),
    ("turnover", "current_asset"), ("turnover", "off_book"), ("turnover", "fixed_asset"),
])
def test_non_i8_scope_never_calls_adapter_or_queues_retry(client, category, scope):
    adapter = RecordingAdapter()
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    created = add(client, item_category=category, asset_scope=scope, in_rental="no")
    item, = created["equipment"]
    assert item["i8_sync_status"] == created["i8_sync"][0]["status"] == "not_applicable"
    edited = request(client, "PATCH", f"/equipment/{item['id']}", {"remark": "已核对"})
    assert edited["i8_sync_status"] == "not_applicable"
    moved = request(client, "POST", "/transfers", dict(
        equipment_ids=[item["id"]], to_project="项目乙", transfer_date="2026-11-20"))
    transfer, = moved["transfers"]
    assert transfer["i8_sync_status"] == moved["i8_sync"][0]["status"] == "not_applicable"
    assert not adapter.events
    assert request(client, "GET", "/i8-sync/issues") == {"equipment": [], "transfers": []}
    request(client, "POST", "/i8-sync/retry", {"equipment_ids": [item["id"]]}, 409)
    request(client, "POST", "/i8-sync/retry", {"transfer_ids": [transfer["id"]]}, 409)


def test_leaving_i8_scope_retires_unresolved_transfers(client):
    item, = add(client, in_rental="no")["equipment"]
    key = item["id"]
    moved = request(client, "POST", "/transfers", dict(
        equipment_ids=[key], to_project="项目乙", transfer_date="2026-11-20"))
    assert moved["i8_sync"][0]["status"] == "pending"
    off_book = request(client, "PATCH", f"/equipment/{key}", {"asset_scope": "off_book"})
    assert off_book["i8_sync_status"] == "not_applicable"
    assert request(client, "GET", "/i8-sync/issues") == {"equipment": [], "transfers": []}
    current = request(client, "PATCH", f"/equipment/{key}", {"asset_scope": "current_asset"})
    assert current["i8_sync_status"] == "pending"
    assert request(client, "GET", "/i8-sync/issues")["transfers"] == []


def test_project_options_excludes_shells_and_orders_by_status_ord_and_id(client):
    with session_scope() as db:
        archived = archive_project(db, "归档", status="archived", ord=-1)
        later = archive_project(db, "在建乙", ord=10)
        first = archive_project(db, "在建甲", ord=2)
        tie = archive_project(db, "在建丙", ord=2)
        shell = archive_project(db, "小微壳", project_type="shell", warehouse_name=None)
    options = request(client, "GET", "/project-options")["items"]
    new = [row for row in options if row["id"] in {archived, later, first, tie, shell}]
    assert [row["id"] for row in new] == [first, tie, later, archived]
    assert new[0] == dict(id=first, disp="在建甲", status="active", phid="i8-在建甲", warehouse_name="测试仓-在建甲",
                          name_full="", project_type="normal", ord=2)
    add_data = BASE | {"purchase_project_id": shell}
    request(client, "POST", "/equipment", add_data, 409)


def test_project_display_and_rental_identity_across_transfer_and_scrap(client):
    with session_scope() as db:
        project_id = archive_project(db, "乌兰察布项目")
        purchase_id = archive_project(db, "南平项目")
    result = add(client, purchase_project=None, purchase_project_id=project_id,
                 purchase_project_custom="  鄂旗项目  ", quantity=2)
    first, second = result["equipment"]
    first_line, second_line = result["rental_line_ids"]
    unlinked = add(client, purchase_project=None, purchase_project_custom="宜阳仓库")["equipment"][0]
    assert (first["purchase_project"], first["purchase_project_disp"], first["purchase_project_custom"]) == (
        "鄂旗项目", "乌兰察布项目", "鄂旗项目")
    assert (first["current_project"], first["current_project_disp"], first["current_project_custom"]) == (
        "鄂旗项目", "乌兰察布项目", "鄂旗项目")
    assert (unlinked["current_project"], unlinked["current_project_id"], unlinked["current_project_disp"],
            unlinked["current_project_custom"]) == ("宜阳仓库", None, None, "宜阳仓库")
    with session_scope() as db:
        db.get(Project, project_id).disp = "乌兰察布储能新名"
        db.get(Project, purchase_id).disp = "南平新名"
    item = request(client, "GET", "/equipment?project=鄂旗项目")["items"][0]
    assert item["purchase_project"] == "鄂旗项目" and item["current_project_disp"] == "乌兰察布储能新名"
    assert (item["inventory_name"], item["inventory_book_qty"], item["inventory_count_qty"]) == ("试验焊机", "2.0000", "2.0000")
    edited = request(client, "PATCH", f"/equipment/{first['id']}", {"purchase_project": "鄂旗项目", "remark": "核对"})
    assert edited["purchase_project_id"] == project_id and edited["purchase_project_custom"] == "鄂旗项目"
    groups = {g["project_name"]: g for g in request(client, "GET", f"/rental?month={MONTH}")["projects"]}
    linked = groups["乌兰察布储能新名"]
    assert linked["project_id"] == project_id
    assert [(l["id"], l["project_custom"]) for l in linked["lines"]] == [(first_line, "鄂旗项目"), (second_line, "鄂旗项目")]
    assert groups["宜阳仓库"]["project_id"] is None
    request(client, "PUT", "/rental/reorder", dict(month=MONTH, project_name="乌兰察布储能新名",
            project_id=project_id, ordered_line_ids=[second_line, first_line]))
    for line in (first_line, second_line):
        resolve(client, line, "this_month")
    transfer, = request(client, "POST", "/transfers", dict(equipment_ids=[first["id"]],
        expected_from_projects={first["id"]: "鄂旗项目"}, to_project_id=purchase_id,
        transfer_date="2026-11-25"))["transfers"]
    assert (transfer["from_project"], transfer["from_project_id"], transfer["from_project_disp"]) == (
        "鄂旗项目", project_id, "乌兰察布储能新名")
    assert (transfer["to_project"], transfer["to_project_id"]) == ("南平新名", purchase_id)
    assert resolve(client, first_line, "from_project")["project_id"] == project_id
    later, = request(client, "GET", "/rental?month=2026-12&project=南平新名")["projects"]
    assert later["lines"][0]["equipment_id"] == first["id"] and later["project_id"] == purchase_id
    scrap, = request(client, "POST", "/scraps", dict(equipment_id=second["id"], scrap_date="2026-11-28"))["scraps"]
    assert (scrap["original_project"], scrap["original_project_id"], scrap["original_project_disp"],
            scrap["original_project_custom"]) == ("鄂旗项目", project_id, "乌兰察布储能新名", "鄂旗项目")
    with session_scope() as db:
        db.delete(db.get(Project, project_id))
    detail = request(client, "GET", f"/equipment/{second['id']}")
    assert detail["equipment"]["current_project_id"] is None and detail["equipment"]["current_project"] == "鄂旗项目"
    assert detail["scrap"]["original_project_id"] is None and detail["scrap"]["original_project_disp"] is None


def test_location_dictionary_rename_and_default_archive_project(client):
    with session_scope() as db:
        project_id = archive_project(db, "乌兰察布项目")
    location = request(client, "POST", "/locations", dict(name=" 鄂旗项目 ", default_project_id=project_id))
    key = location["id"]
    assert location == dict(id=key, name="鄂旗项目", default_project_id=project_id,
                           default_project_disp="乌兰察布项目", is_active=True, sort_order=0)
    other = request(client, "POST", "/locations", dict(name="临时仓", sort_order=-1))
    assert request(client, "GET", "/locations")["items"] == [other, location]
    request(client, "POST", "/locations", {"name": "鄂旗项目"}, 409)
    request(client, "POST", "/locations", {"name": "   "}, 422)
    request(client, "PATCH", f"/locations/{key}", {"default_project_id": project_id + 1}, 409)
    request(client, "PATCH", f"/locations/{key}", {"name": "临时仓"}, 409)

    created = add(client, purchase_project_id=project_id, purchase_project_custom="鄂旗项目")
    item_id = created["equipment"][0]["id"]
    line, = created["rental_line_ids"]
    transfer_to(client, item_id, "外地仓", day=12)
    transfer_to(client, item_id, None, day=15, to_project_id=project_id, to_project_custom="鄂旗项目")
    request(client, "POST", "/scraps", dict(equipment_id=item_id, scrap_date="2026-11-20"))
    renamed = request(client, "PATCH", f"/locations/{key}", dict(name="鄂旗工区", is_active=False))
    assert renamed == location | dict(name="鄂旗工区", is_active=False)
    assert request(client, "GET", "/locations")["items"] == [other]
    assert request(client, "GET", "/locations?include_inactive=true")["items"] == [other, renamed]
    detail = request(client, "GET", f"/equipment/{item_id}?month={MONTH}")
    equipment, transfers = detail["equipment"], detail["transfers"]
    for row, prefix in [(equipment, "purchase_project"), (equipment, "current_project"),
                        (next(t for t in transfers if t["from_project_id"]), "from_project"),
                        (next(t for t in transfers if t["to_project_id"]), "to_project"),
                        (detail["scrap"], "original_project")]:
        assert (row[prefix], row[f"{prefix}_custom"], row[f"{prefix}_id"]) == ("鄂旗工区", "鄂旗工区", project_id)
    rent_line, = detail["rental_lines"]
    assert (rent_line["id"], rent_line["project_name"], rent_line["project_custom"]) == (line, "乌兰察布项目", "鄂旗工区")
    pending = json.loads(rent_line["pending_meta_json"])["queue"]
    assert pending[0]["details"]["from_project"] == pending[1]["details"]["to_project"] == "鄂旗工区"
    with session_scope() as db:
        assert db.get(RentalLine, line).project_name == "鄂旗工区"
        db.delete(db.get(Project, project_id))
    cleared = request(client, "PATCH", f"/locations/{key}", {"is_active": True})
    assert cleared["default_project_id"] is None and cleared["default_project_disp"] is None


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
    assert request(c, "GET", "/inventory")["items"][0]["book_qty"] == "1.0000"
    inventory = workbook(c, "inventory")
    cached = workbook(c, "inventory", data_only=True)["封皮"]
    assert [Decimal(str(cached[cell].value)) for cell in ("E6", "I6", "H7", "H8")] == [
        Decimal("100.1234"), Decimal("100.1234"), Decimal("100.1234"), Decimal("0"),
    ]
    assert inventory.sheetnames == ["封皮", "流动资产盘点表", "周转材料"]
    ws = inventory.worksheets[1]
    assert ws["F5"].value == 1 and "F5*E5" in ws["G5"].value
    cover = inventory["封皮"]
    assert {str(area) for area in cover.merged_cells.ranges} == {
        "C3:K3", "C4:K4", "C5:K5", "B6:D6", "E6:H6", "I6:J6",
        "C7:G7", "C8:G8", "C9:K9", "C10:K10", "A13:K14",
    }
    assert not cover.print_area and not cover.print_title_rows and not cover.HeaderFooter
    assert (cover.page_setup.paperSize, cover.page_setup.orientation) == (9, "landscape")
    assert cover.print_options.horizontalCentered is cover.print_options.verticalCentered is None
    assert cover.sheet_properties.pageSetUpPr.fitToPage is None
    assert cover.page_setup.fitToWidth is cover.page_setup.fitToHeight is cover.page_setup.scale is None
    margins = cover.page_margins
    assert (margins.left, margins.right, margins.top, margins.bottom, margins.header, margins.footer) == (
        .75, .75, 1, 1, .5, .5)
    view = cover.sheet_view
    assert view.tabSelected and view.zoomScale == view.zoomScaleNormal == 145
    assert view.selection[0].activeCell == view.selection[0].sqref == "M8"
    assert (cover.sheet_format.defaultColWidth, cover.sheet_format.defaultRowHeight) == (9, 14.25)
    assert [(col.min, col.max, col.width) for col in cover.column_dimensions.values()] == [
        (1, 3, 9), (4, 4, 12.6416666666667), (5, 6, 9), (7, 7, 9.35833333333333),
        (8, 8, 18.75), (9, 9, 9), (10, 10, 7.425), (11, 16384, 9),
    ]
    assert {row: dim.height for row, dim in cover.row_dimensions.items() if dim.height is not None} == {
        3: 62.15, 4: 36, 5: 36, 6: 36, 7: 36, 8: 27, 9: 27, 10: 27,
    }
    for address, value, size, bold, align in (
        ("C3", "河南省安装集团有限责任公司", 24, True, "center"),
        ("C4", "第四工程公司", 20, False, "center"),
        ("C5", "2026年年中流动资产盘点表", 20, False, "center"),
        ("B6", "流动资产金额总计（原值）：", 14, False, "center"),
        ("E6", "=I6", 14, False, "center"),
        ("I6", "=H7+H8", 14, False, "center"),
        ("K6", "元", 14, False, None),
        ("C7", "其     中：大型工机具：", 14, False, "right"),
        ("H7", "='流动资产盘点表'!I6", 14, False, "center"),
        ("I7", "元", 14, False, None),
        ("C8", "周转材料：", 14, False, "right"),
        ("H8", "='周转材料'!I5", 14, False, "center"),
        ("I8", "元", 14, False, None),
        ("A13", "单位主管：             财务主管：               资产主管：              制表人：   ",
         16, False, None),
    ):
        cell = cover[address]
        assert (cell.value, cell.font.name, cell.font.charset, cell.font.sz, cell.font.bold) == (
            value, "宋体", 134, size, bold)
        assert (cell.alignment.horizontal, cell.alignment.vertical) == (align, "center")
        assert not cell.alignment.wrap_text and not cell.alignment.shrink_to_fit
        assert not cell.fill.patternType
        assert all(side is None or side.style is None for side in (
            cell.border.left, cell.border.right, cell.border.top, cell.border.bottom))
    assert cover["E6"].number_format == "[DBNum2][$RMB]General;[Red][DBNum2][$RMB]General"
    assert cover["I6"].number_format == r'"￥"#,##0.00;[Red]"￥"\-#,##0.00'
    assert cover["H7"].number_format == cover["H8"].number_format == r'"￥"#,##0.00_);[Red]\("￥"#,##0.00\)'
    for sheet, last, category in ((ws, 6, "在用工具"), (inventory["周转材料"], 5, "周转材料")):
        assert (sheet.page_setup.paperSize, sheet.page_setup.orientation, sheet.page_setup.scale) == (9, "landscape", None)
        assert not sheet.sheet_properties.pageSetUpPr.fitToPage
        margins = sheet.page_margins
        assert (margins.left, margins.right, margins.top, margins.bottom, margins.header, margins.footer) == (
            .551, .591, .315, .748, .315, .315)
        assert sheet.max_column == 12 and sheet.print_area == f"'{sheet.title}'!$A$1:$L${last}"
        assert sheet.print_title_rows == "$1:$4"
        assert [sheet.row_dimensions[n].height for n in range(1, 5)] == [33, 20, 28.5, 42.75]
        cell = sheet["A2"]
        assert (cell.value, cell.font.name, cell.font.sz) == (f"类别：{category}", "宋体", 12)
        assert (cell.alignment.horizontal, cell.alignment.vertical) == ("left", "center")
        assert {"A1:L1", "A3:A4", "F3:G3", "H3:I3"} <= {str(cell) for cell in sheet.merged_cells.ranges}
        assert (sheet["A1"].font.name, sheet["A1"].font.sz, sheet["A3"].border.bottom.style) == ("宋体", 18, "thin")
        assert sheet[f"B{last}"].font.bold and sheet[f"L{last}"].border.right.style == "thin"
        assert [sheet.column_dimensions[col].width for col in "ABCDEFGHIJKL"] == pytest.approx([
            4.64166666666667, 19.6416666666667, 14.6416666666667, 6.70833333333333, 11.6416666666667,
            7.85833333333333, 14.1416666666667, 7.64166666666667, 14.5, 6.64166666666667,
            5.64166666666667, 22.7083333333333])
    assert "SUM(G5:G5)" in ws["G6"].value
    resolve(c, lines[0], "charge_this_month")
    request(c, "POST", "/scraps", dict(equipment_ids=[keys[1]], scrap_date="2026-11-29"))
    resolve(c, lines[1], "stop_this_month")
    assert not request(c, "GET", "/inventory")["items"]
    assert not request(c, "GET", "/equipment")["items"]
    assert workbook(c, "inventory").worksheets[1]["B5"].value == "合计："
    assert len(request(c, "GET", "/scraps?project=项目乙&keyword=焊机")["items"]) == 2
    transfers = request(c, "GET", "/transfers?project=项目甲&sync_status=pending")["items"]
    assert all(t["rental_attribution"] == "from_project" for t in transfers)
    distribution = workbook(c, "distribution")
    assert distribution.sheetnames == ["工机具基础信息", "调拨记录", "报废记录", "周转材料", "周转材料调拨记录", "周转材料报废记录"]
    for sheet in distribution.worksheets:
        main = sheet.title in ("工机具基础信息", "周转材料")
        header = sheet["A2" if main else "A1"]
        assert (sheet.page_setup.paperSize, sheet.page_setup.orientation) == (9, "portrait")
        assert sheet.freeze_panes == ("A3" if main else "A2")
        assert (header.font.name, header.font.bold, header.fill.patternType, header.border.left.style) == (
            "宋体", True, "solid", "thin")
        assert sheet.column_dimensions["A"].width == pytest.approx(23.675)
        if main:
            assert "A1:K1" in sheet.merged_cells and sheet["A1"].font.sz == 22
    assert distribution.worksheets[0]["H3"].number_format == "General"
    assert distribution.worksheets[0]["A3"].value == added["codes"][0]
    assert "COUNTIF" in distribution.worksheets[0]["I3"].value
    assert distribution["调拨记录"]["I2"].value == "项目乙" and distribution["报废记录"]["J2"].value == "损坏"
    cached = workbook(c, "distribution", data_only=True)
    assert cached["工机具基础信息"]["I3"].value == "报废" and cached["调拨记录"]["B2"].value == "试验焊机"
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
    assert "G4:G7" in ws["G8"].value and "A1:I1" in ws.merged_cells
    assert Decimal(str(workbook(c, "rental?month=2026-11", data_only=True).active["G8"].value)) == Decimal("16.2468")
    assert "$A$1:$I$9" in ws.print_area and "单位：零项目" in [cell.value for cell in ws["A"]]
    following = request(c, "GET", "/rental?month=2026-12")
    assert Decimal(following["grand_total"]) == Decimal("21.2530")
    groups = {g["project_name"]: g["lines"] for g in following["projects"]}
    assert [r["billing_status"] for r in groups["项目甲"]] == ["normal", "normal"]
    assert groups["项目甲"][0]["custom_unit_price"] == "8.1234"
    assert groups["零项目"][0]["distribution_note"] == "保留" and groups["零项目"][0]["amount"] is None
    assert request(c, "GET", "/rental?month=2026-12&project=项目甲")["projects"][0]["lines"] == groups["项目甲"]


def test_project_reorder_swaps_groups_and_carries_to_export(client):
    with session_scope() as db:
        project_id = archive_project(db, "项目甲")
    official = add(client, name="档案项目设备", purchase_project_id=project_id, quantity=2)["rental_line_ids"]
    added = add(client, name="自定义位置设备", purchase_project="项目甲", quantity=2)
    custom = added["rental_line_ids"]
    for line in official + custom:
        resolve(client, line, "this_month")
    order = dict(month=MONTH, projects=[dict(project_id=None, project_name="项目甲"),
                                        dict(project_id=project_id, project_name="项目甲")])
    request(client, "PUT", "/rental/reorder-projects", order | {"projects": order["projects"][:1]}, 409)
    request(client, "PUT", "/rental/reorder-projects", order | {"projects": order["projects"][:1] * 2}, 409)
    assert request(client, "PUT", "/rental/reorder-projects", order) == order
    transfer_to(client, added["equipment"][0]["id"], None, to_project_id=project_id)
    resolve(client, custom[0], "from_project")
    for month, ranks in ((MONTH, [[0, 0], [1, 1]]), ("2026-12", [[0], [1, 1, 1]])):
        groups = request(client, "GET", f"/rental?month={month}")["projects"]
        assert [group["project_id"] for group in groups] == [None, project_id]
        assert [[line["project_sort_order"] for line in group["lines"]] for group in groups] == ranks
        sheet = workbook(client, f"rental?month={month}").active
        assert sheet["A2"].value == sheet["A12"].value == "单位：项目甲"
        assert sheet["B4"].value == "自定义位置设备" and sheet["B14"].value == "档案项目设备"


def test_rental_print_blocks_and_dynamic_row_heights(client):
    counts = (2, 4, 15, 20, 25, 29, 0, 40, 3)
    with session_scope() as db:
        db.add(RentalMonth(month=MONTH))
        db.flush()
        for group, count in enumerate(counts):
            for index in range(max(count, 1)):
                db.add(RentalLine(month=MONTH, project_name=f"项目{count}", name="样机", quantity=1,
                                  unit_price=3 if count else 0, amount=3 if count else 0,
                                  project_sort_order=group, row_sort_order=index))
    book = workbook(client, f"rental?month={MONTH}")
    ws = book.active
    cached = workbook(client, f"rental?month={MONTH}", data_only=True)
    assert ws.max_column == 9
    assert [ws.column_dimensions[get_column_letter(n)].width for n in range(1, 10)] == [
        4.375, 13.875, 10.25, 5.5, 5.375, 10.125, 11.25, 11, 13]
    assert (ws.page_setup.paperSize, ws.page_setup.orientation) == (9, "portrait")
    assert (ws.page_setup.fitToWidth, ws.page_setup.fitToHeight, ws.sheet_properties.pageSetUpPr.fitToPage) == (1, 0, True)
    assert ws.print_options.horizontalCentered is True and ws.print_options.verticalCentered is False
    assert (ws.page_margins.left, ws.page_margins.right, ws.page_margins.top, ws.page_margins.bottom) == (.5, .5, .6, .6)
    assert (ws["A1"].font.name, ws["A1"].font.sz, ws["A1"].font.bold) == ("宋体", 16, True)
    assert (ws["A2"].font.sz, ws["E2"].font.sz, ws["G2"].font.sz) == (12, 12, 12)
    assert ws["A2"].alignment.shrink_to_fit and ws["E2"].alignment.shrink_to_fit
    assert {"A1:I1", "A2:D2", "E2:F2", "G2:I2"} <= {str(cell) for cell in ws.merged_cells.ranges}
    assert ws["F3"].font.bold and ws["F3"].alignment.wrap_text and ws["F3"].border.right.style == "thin"
    assert ws["F4"].alignment.horizontal == "right" and ws["F4"].number_format == "General"
    assert ws["B6"].value is None and ws["B6"].border.bottom.style == "thin"
    first, footers = 1, []
    for count, row_height in ((2, 36), (4, 30), (15, 29), (20, 25), (25, 20), (29, 510 / 29)):
        data = first + 3
        total_row = data + max(count, 4)
        footer = total_row + 1
        assert ws[f"A{first + 1}"].value == f"单位：项目{count}"
        assert ws[f"B{data}"].font.sz == (12 if count <= 28 else 10.5)
        assert [ws.row_dimensions[n].height for n in (first, first + 1, first + 2, data, total_row, footer)] == (
            pytest.approx([21, 21, 34.5, row_height, 30, 43]))
        assert ws[f"G{footer}"].value == "制表人："
        assert ws[f"G{total_row}"].font.bold
        assert f"SUM(G{data}:G{total_row - 1})" in ws[f"G{total_row}"].value
        assert cached.active[f"G{total_row}"].value == 3 * count
        assert f"$A${first}:$I${footer}" in ws.print_area
        footers.append(footer)
        first = footer + 2
    assert [brk.id for brk in ws.row_breaks.brk] == footers
    assert ws[f"A{first + 1}"].value == "单位：项目0" and f"$A${first}:" not in ws.print_area
    overflow = book["租赁长表 1"]
    assert overflow.page_setup.fitToHeight == 1 and "$A$1:$I$45" in overflow.print_area
    assert overflow.print_options.horizontalCentered is True and overflow.print_options.verticalCentered is False
    assert (overflow["B4"].font.sz, overflow.row_dimensions[4].height) == (10.5, 15.5)
    assert cached[overflow.title]["G44"].value == 120
    assert book["租赁续表 2"]["A2"].value == "单位：项目3"
    assert cached.active[f"G{ws.max_row}"].value == 3 * sum(counts)


def transfer_to(client, key, to, day=24, **kwargs):
    transfer, = request(client, "POST", "/transfers", dict(
        equipment_ids=[key], to_project=to, transfer_date=f"{MONTH}-{day:02d}", **kwargs))["transfers"]
    return transfer["id"]


def test_delete_latest_transfer_restores_draft_attribution_and_project(client):
    with session_scope() as db:
        purchase_id = archive_project(db, "采购项目")
        next_id = archive_project(db, "调入项目")
    added = add(client, purchase_project_id=purchase_id, purchase_project_custom="购置片区")
    key = added["equipment"][0]["id"]
    line, = added["rental_line_ids"]
    resolve(client, line, "this_month")
    older = transfer_to(client, key, None, to_project_id=next_id, to_project_custom="调入片区")
    resolve(client, line, "from_project")
    latest = transfer_to(client, key, "项目丙")
    resolve(client, line, "to_project")
    assert request(client, "GET", "/rental?month=2026-12")["projects"][0]["project_name"] == "项目丙"
    rows = request(client, "GET", "/transfers")["items"]
    assert [(r["id"], r["is_latest_for_equipment"]) for r in rows] == [(older, False), (latest, True)]
    filtered, = request(client, "GET", "/transfers?project=购置片区")["items"]
    assert filtered["id"] == older and filtered["is_latest_for_equipment"] is False
    assert request(client, "DELETE", f"/transfers/{older}", status=409)["message"] == "仅可删除该设备的最新一条调拨记录"

    assert request(client, "DELETE", f"/transfers/{latest}") == dict(
        deleted_transfer_id=latest, equipment_id=key, reverted_project="调入片区",
        reverted_project_id=next_id, reverted_project_custom="调入片区")
    detail = request(client, "GET", f"/equipment/{key}?month={MONTH}")
    assert detail["equipment"]["current_project"] == "调入片区"
    assert detail["transfers"][0]["is_latest_for_equipment"] is True
    rental_line, = detail["rental_lines"]
    assert rental_line["project_id"] == purchase_id
    assert json.loads(rental_line["pending_meta_json"])["next_transfer_id"] == older
    assert request(client, "GET", "/rental?month=2026-12")["projects"][0]["project_id"] == next_id
    distribution = workbook(client, "distribution", data_only=True)
    assert distribution["工机具基础信息"]["J3"].value == "调入片区"
    assert [row[8].value for row in distribution["调拨记录"].iter_rows(min_row=2)] == ["调入片区"]

    assert request(client, "DELETE", f"/transfers/{older}") == dict(
        deleted_transfer_id=older, equipment_id=key, reverted_project="购置片区",
        reverted_project_id=purchase_id, reverted_project_custom="购置片区")
    detail = request(client, "GET", f"/equipment/{key}?month={MONTH}")
    assert detail["equipment"]["current_project_id"] == purchase_id and not detail["transfers"]
    assert detail["rental_lines"][0]["pending_meta_json"] is None
    assert request(client, "GET", "/rental?month=2026-12")["projects"][0]["project_id"] == purchase_id
    request(client, "DELETE", f"/transfers/{latest}", status=404)


def test_delete_transfer_removes_only_its_pending_rental_action(client):
    added = add(client)
    key = added["equipment"][0]["id"]
    line, = added["rental_line_ids"]
    older = transfer_to(client, key, "项目乙", day=23)
    latest = transfer_to(client, key, "项目丙")
    request(client, "DELETE", f"/transfers/{latest}")
    pending = resolve(client, line, "this_month")
    assert pending["pending_action_type"] == "transfer_attribution"
    assert json.loads(pending["pending_meta_json"])["transfer_id"] == older
    request(client, "DELETE", f"/transfers/{older}")
    draft = request(client, "GET", f"/equipment/{key}?month={MONTH}")["rental_lines"][0]
    assert draft["pending_action_type"] == "none" and draft["pending_meta_json"] is None
    assert (draft["project_name"], draft["billing_status"], draft["amount"]) == ("项目甲", "normal", "5.0062")


def test_latest_transfer_orders_undated_history_last(client):
    key = add(client, in_rental="no")["equipment"][0]["id"]
    dated = transfer_to(client, key, "项目乙")
    with session_scope() as db:
        imported = EquipmentTransfer(equipment_id=key, item_category="equipment", from_project="旧项目",
                                     to_project="项目甲", i8_sync_status="not_applicable")
        second = EquipmentTransfer(equipment_id=key, item_category="equipment", from_project="旧项目",
                                   to_project="项目丙", transfer_date=date(2026, 11, 16), i8_sync_status="not_applicable")
        db.add_all([imported, second])
        db.flush()
        undated, earlier = imported.id, second.id
    rows = request(client, "GET", "/transfers")["items"]
    assert [(r["id"], r["is_latest_for_equipment"]) for r in rows] == [
        (dated, True), (undated, False), (earlier, False)]
    assert request(client, "DELETE", f"/transfers/{dated}")["reverted_project"] == "项目甲"


@pytest.mark.parametrize(("guard", "message"), [
    ("synced", "该调拨已同步 i8，暂不支持直接删除，请先核对 i8 单据"),
    ("awaiting_readback", "该调拨的 i8 保存结果待核对，暂不支持直接删除"),
    ("scrapped", "设备已报废，不能删除历史调拨记录"),
])
def test_delete_transfer_conflicts_leave_ledger_intact(client, guard, message):
    added = add(client)
    key = added["equipment"][0]["id"]
    line, = added["rental_line_ids"]
    resolve(client, line, "this_month")
    transfer = transfer_to(client, key, "项目乙")
    resolve(client, line, "to_project")
    if guard == "scrapped":
        request(client, "POST", "/scraps", dict(equipment_id=key, scrap_date=f"{MONTH}-28"))
    else:
        with session_scope() as db:
            row = db.get(EquipmentTransfer, transfer)
            if guard == "synced":
                row.i8_sync_status = guard
            else:
                row.i8_sync_status = "failed"
                row.i8_conflict_json = '{"awaiting_readback": true}'
    before = request(client, "GET", f"/equipment/{key}?month={MONTH}")
    assert request(client, "DELETE", f"/transfers/{transfer}", status=409)["message"] == message
    assert request(client, "GET", f"/equipment/{key}?month={MONTH}") == before


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
    resolve(c, line, "from_project")
    carried = request(c, "GET", "/rental?month=2026-12")["projects"]
    assert len(carried) == 1 and carried[0]["project_name"] == "项目乙"
    assert Decimal(carried[0]["subtotal"]) == Decimal("5.0062")


def test_migration_round_trip_in_isolated_schema(rollback_db):
    filename = Path(__file__).resolve().parents[1] / "alembic/versions/equip261123_equipment_ledger.py"
    revision = runpy.run_path(str(filename))
    baseline = runpy.run_path(str(filename.with_name("equipbase261123_historical_transfers.py")))
    project_links = runpy.run_path(str(filename.with_name("equipproj261124_project_links.py")))
    locations = runpy.run_path(str(filename.with_name("equiploc261125_locations.py")))
    counts = runpy.run_path(str(filename.with_name("equipcount261126_nullable_count.py")))
    schema = rollback_db.exec_driver_sql("select current_schema()").scalar_one()
    assert schema.startswith("backend_verify_")

    def tables():
        return set(inspect(rollback_db).get_table_names(schema=schema))

    initial = tables()
    with Operations.context(MigrationContext.configure(rollback_db)):
        assert "m16_locations" in initial
        counts["downgrade"]()
        locations["downgrade"]()
        assert "m16_locations" not in tables()
        project_links["downgrade"]()
        columns = inspect(rollback_db).get_columns("m16_equipment_items", schema=schema)
        assert "current_project_id" not in {column["name"] for column in columns}
        baseline["downgrade"]()
        revision["downgrade"]()
        assert tables() == {name for name in initial if not name.startswith("m16_")}
        revision["upgrade"]()
        baseline["upgrade"]()
        project_links["upgrade"]()
        locations["upgrade"]()
        counts["upgrade"]()
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


def mark_legacy_confirmed(*months):
    with session_scope() as db:
        for row in db.scalars(select(RentalMonth).where(RentalMonth.month.in_(months))):
            row.status = "confirmed"


def test_rental_remains_editable_in_previously_confirmed_months(client):
    added = add(client)
    equipment_id = added["equipment"][0]["id"]
    line, = added["rental_line_ids"]
    later = "2026-12"
    request(client, "GET", f"/rental?month={later}")
    mark_legacy_confirmed(MONTH, later)
    request(client, "POST", "/rental/confirm", {"month": MONTH}, 404)
    resolve(client, line, "this_month")
    assert Decimal(request(client, "PATCH", f"/rental/lines/{line}", {"quantity": 2})["quantity"]) == 2
    request(client, "PUT", "/rental/reorder", dict(month=MONTH, project_name="项目甲", ordered_line_ids=[line]))
    request(client, "PUT", "/rental/reorder-projects", dict(month=MONTH, projects=[
        dict(project_id=None, project_name="项目甲")]))
    transfer = transfer_to(client, equipment_id, "项目乙")
    resolve(client, line, "to_project")
    assert request(client, "GET", f"/rental?month={later}")["projects"][0]["project_name"] == "项目乙"
    request(client, "DELETE", f"/transfers/{transfer}")
    reopened = request(client, "GET", f"/rental?month={later}")
    assert reopened["status"] == "draft" and reopened["projects"][0]["project_name"] == "项目甲"
    request(client, "PATCH", f"/rental/lines/{line}", {"billing_status": "stopped"})
    assert request(client, "GET", f"/rental?month={later}")["projects"][0]["lines"][0]["billing_status"] == "stopped"


def test_turnover_category_export_and_stop_existing_draft(client):
    line = add(client, item_category="turnover")["rental_line_ids"][0]
    equipment_line = add(client, purchase_project="项目乙")["rental_line_ids"][0]
    with session_scope() as db:
        db.get(RentalLine, line).category_label = "设备"
        db.get(RentalLine, equipment_line).category_label = "周转材料"
    request(client, "PATCH", f"/rental/lines/{line}", {"category_label": "大型工机具"}, 422)
    assert resolve(client, line, "this_month")["category_label"] == "周转材料"
    assert resolve(client, equipment_line, "this_month")["category_label"] == "大型工机具"
    later = "/rental?month=2026-12"
    assert request(client, "GET", later)["projects"][0]["lines"][0]["category_label"] == "周转材料"
    assert workbook(client, later[1:]).active["H4"].value == "周转材料"
    request(client, "PATCH", f"/rental/lines/{line}", {"billing_status": "stopped"})
    stopped = request(client, "GET", later)["projects"][0]["lines"][0]
    assert stopped["billing_status"] == "stopped" and stopped["amount"] is None


def test_remove_rental_flag_stops_from_current_month(client):
    today = date.today().replace(day=1)
    prior = (today - timedelta(days=1)).strftime("%Y-%m")
    months = [today.strftime("%Y-%m"), (today + timedelta(days=32)).strftime("%Y-%m")]
    created = add(client, target_month=prior)
    resolve(client, created["rental_line_ids"][0], "this_month")
    for month in months:
        request(client, "GET", f"/rental?month={month}")
    mark_legacy_confirmed(prior, *months)
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


LIST_PATH = "/sup/customServer/getList"
SAVE_PATH = "/sup/customServer/save"
TEST_CODE = "样机-20261103"


def equipment_row(project="项目甲", project_id="P1"):
    return {"phid": "E1", "u_device_code": TEST_CODE, "bill_name": "样机", "phid_pc": project_id,
            "phid_pc_EXName": project, "u_indata": "2026-11-03 00:00:00", "u_yz": "0.0000",
            "ng_record_ver": 2, "u_msunit": "U1", "u_msunit_EXName": "台",
            "phid_org": "3700000000000014", "u_use_org": "3700000000000014"}


def page(*rows):
    return {"data": list(rows), "total": len(rows)}


def custom_adapter(*responses, project_names=None):
    transport = Mock(spec=["post_json"])
    transport.post_json.side_effect = responses
    adapter = I8CustomFormEquipmentAdapter(
        transport, project_ids={"项目甲": "P1", "项目乙": "P2"},
        project_names=project_names, transfer_operator=("I8-P1", "测试录入人"),
    )
    return adapter, transport.post_json


def save_receipt(phid):
    return {"status": "success", "msg": None, "data": phid, "total": None}


def transfer_bill():
    return {"phid": "B1", "bill_no": "20261124-0001", "phid_pc": "P1",
            "phid_org": "3700000000000014", "app_status": 0, "wf_flag": 0}


def saved_form(calls, business):
    request = calls.call_args_list[1]
    assert request.args == (SAVE_PATH,) and request.kwargs["retry_expired"] is False
    fields = request.kwargs["data"]
    assert set(fields) == {"customBusCode", "data", "billNoStatus", "isContinue"}
    assert fields["customBusCode"] == business and fields["billNoStatus"] == "1"
    assert json.loads(fields["isContinue"]) == {"warn": "0", "validateWarn": "0", "checkProjOrgWarn": "0"}
    return json.loads(fields["data"])


def test_equipment_exact_lookup_reads_all_pages():
    first = [equipment_row() | {"phid": str(i), "u_device_code": f"{TEST_CODE}-{i}"} for i in range(100)]
    adapter, calls = custom_adapter({"total": 101, "data": first}, {"total": 101, "data": [equipment_row()]})
    assert adapter.lookup_by_code(TEST_CODE)["phid"] == "E1"
    common = {"customBusCode": "sbzx", "containerId": "p_form_sbzx_m_list", "limit": "100",
              "clientfilter": "e48f570da0f71818a59e798cfa48fa57bc388a6b8519dc9d0f237f397f1fdf63"
                              "f4b6f41b8fbed0c7a9520cd37c2e728810b59c1f0f0f253c",
              "queryfilter": "5e3410ab22038162"}
    assert [(c.args, c.kwargs) for c in calls.call_args_list] == [
        ((LIST_PATH,), {"data": common | {"page": "0", "start": "0"}}),
        ((LIST_PATH,), {"data": common | {"page": "1", "start": "100"}}),
    ]


@pytest.mark.parametrize("existing", [False, True])
def test_equipment_custom_form_create_or_modify(existing):
    row = equipment_row()
    original = row | {"bill_name": "旧名称", "bill_no": "原单号",
                      "bill_dt": "2026-11-03 13:21:30", "app_dt": None}
    after = page(row | {"ng_record_ver": 3}) if existing else page(row)
    adapter, calls = custom_adapter(page(original) if existing else page(), save_receipt("E1"), after)
    result = adapter.create_equipment({"code": TEST_CODE, "name": "样机", "current_project": "项目甲",
                                       "purchase_date": date(2026, 11, 3), "purchase_price": Decimal("0")})
    assert result.status == "synced"
    expected = {"bill_name": "样机", "u_device_code": TEST_CODE, "phid_pc": "P1",
                "u_spec": None, "u_indata": "2026-11-03 00:00:00", "u_yz": "0",
                "phid_org": "3700000000000014", "u_use_org": "3700000000000014", "u_bz": None}
    if existing:
        expected = original | {"bill_name": "样机", "u_indata": "2026-11-03",
                               "bill_dt": "2026-11-03", "app_dt": ""}
    assert saved_form(calls, "sbzx") == {"p_form_sbzx_m": {
        "form": {"key": "phid", "modifiedRow" if existing else "newRow": expected}}}
    assert calls.call_args_list[-1].args == (LIST_PATH,)


def test_equipment_edit_requires_current_record_version():
    original = equipment_row() | {"bill_name": "旧名称", "ng_record_ver": None}
    adapter, calls = custom_adapter(page(original))
    with pytest.raises(ValueError, match="记录版本"):
        adapter.create_equipment({"code": TEST_CODE, "name": "样机", "current_project": "项目甲"})
    assert [c.args[0] for c in calls.call_args_list] == [LIST_PATH]


@pytest.mark.parametrize("unexpected", [
    {"total": 1, "data": []}, page(equipment_row(), equipment_row() | {"phid": "E2"}),
    page(equipment_row(), equipment_row()), {"Success": False, "total": 0, "data": []},
])
def test_unreliable_lookup_never_creates_equipment(unexpected):
    adapter, calls = custom_adapter(unexpected)
    with pytest.raises(ValueError):
        adapter.create_equipment({"code": TEST_CODE, "name": "样机", "current_project": "项目甲"})
    assert calls.call_count == 1 and calls.call_args.args == (LIST_PATH,)


@pytest.mark.parametrize("project,project_id", [("丙", "P3"), ("项目甲", "P3")])
def test_custom_transfer_conflict_blocks_save(project, project_id):
    adapter, calls = custom_adapter(page(equipment_row(project, project_id)))
    result = adapter.create_transfer(TEST_CODE, "项目甲", "项目乙")
    assert result.status == "conflict"
    assert result.conflict["local"]["from_project"] == "项目甲"
    assert result.conflict["local"]["to_project"] == "项目乙"
    assert result.conflict["snapshot"]["phid_pc"] == project_id
    assert calls.call_count == 1 and calls.call_args.args == (LIST_PATH,)


@pytest.mark.parametrize("bill_rows,after,status", [
    (page(transfer_bill()), page(equipment_row("项目乙全称", "P2")), "synced"),
    (page(transfer_bill()), page(equipment_row("项目甲全称")), "pending"),
    (page(transfer_bill()), page(), "failed"),
    (page(transfer_bill()), page(equipment_row("项目乙全称", "P9")), "failed"),
    (page(), page(equipment_row("项目乙全称", "P2")), "failed"),
])
def test_custom_transfer_save_and_readback(bill_rows, after, status):
    adapter, calls = custom_adapter(
        page(equipment_row("项目甲全称")), save_receipt("B1"), bill_rows, after,
        project_names={"项目甲": "项目甲全称", "项目乙": "项目乙全称"},
    )
    result = adapter.create_transfer(TEST_CODE, "项目甲", "项目乙", transfer_date=date(2026, 11, 23))
    assert result.status == status
    assert [c.args[0] for c in calls.call_args_list] == [LIST_PATH, SAVE_PATH, LIST_PATH, LIST_PATH]
    assert calls.call_args_list[2].kwargs["data"]["containerId"] == "p_form_ldzcdb_m_list"
    payload = saved_form(calls, "ldzcdb")
    assert payload["p_form_ldzcdb_m"] == {"form": {"key": "phid", "newRow": {
        "phid_fill_psn": "I8-P1", "phid_fill_psn_EXName": "测试录入人",
        "phid_schemeid": "3700000000000363", "phid_org": "3700000000000014",
        "phid_org_EXName": "第四工程公司", "phid_pc": "P1", "bill_dt": "2026-11-23",
        "bill_no": None, "bill_name": None, "app_status": None, "wf_flag": None,
    }}}
    detail = payload["p_form_ldzcdb_d"]
    assert detail["isChanged"] is True and detail["table"]["key"] == "phid"
    row = detail["table"]["newRow"][0]["row"]
    assert json.loads(row.pop("imp_info")) == {
        "SchemePhId": "3700000000000363", "SSign": "p_form_sbzx_m", "TSign": "p_form_ldzcdb_d",
        "SOrgPhId": "3700000000000869", "STable": "p_form_sbzx_m", "SPk": "phid",
        "SPkValue": "E1", "SName": "流动资产台账",
    }
    assert detail["table"]["newRow"] == [{"row": {
        "rel_key1": None, "u_sbmc": "E1", "u_sbmc_EXName": "样机", "u_sbbm": TEST_CODE,
        "u_spe": None, "phid_pc": "P1", "phid_pc_EXName": "项目甲全称", "u_inproj": "P2",
        "u_inproj_EXName": "项目乙全称", "u_msuint": "U1", "u_msuint_EXName": "台",
        "key": None, "detail_row_no": 0,
    }}]
    if status == "pending":
        assert result.conflict["bill_phid"] == "B1"
        assert result.conflict["bill_no"] == "20261124-0001"


def test_custom_adapter_injected_at_normal_sync_entry(client):
    adapter, calls = custom_adapter(page(), {"status": "validateWarn"})
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    saved = add(client, in_rental="no")["equipment"][0]
    assert saved["i8_sync_status"] == "failed"
    assert [c.args[0] for c in calls.call_args_list] == [LIST_PATH, SAVE_PATH]


def test_i8_queue_uses_archive_phids_for_creation_and_transfer(client):
    with session_scope() as db:
        origin_id = archive_project(db, "乌兰察布项目", phid="ARCHIVE-1")
        destination_id = archive_project(db, "南平项目", phid="ARCHIVE-2")
    item, = add(client, name="样机", purchase_project=None, purchase_project_id=origin_id,
                purchase_project_custom="鄂旗项目", purchase_price=0, in_rental="no")["equipment"]
    before = equipment_row("i8 乌兰察布全名", "ARCHIVE-1")
    after = equipment_row("i8 南平全名", "ARCHIVE-2")
    adapter, calls = custom_adapter(page(), save_receipt("E1"), page(before), page(before),
                                    save_receipt("B1"), page(transfer_bill() | {"phid_pc": "ARCHIVE-1"}), page(after))
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    transfer, = request(client, "POST", "/transfers", dict(equipment_ids=[item["id"]], to_project_id=destination_id,
        to_project_custom="南平现场", transfer_date="2026-11-25"))["transfers"]
    assert transfer["i8_sync_status"] == "synced" and transfer["to_project"] == "南平现场"
    saves = [json.loads(call.kwargs["data"]["data"]) for call in calls.call_args_list if call.args[0] == SAVE_PATH]
    equipment_save, transfer_save = saves
    assert equipment_save["p_form_sbzx_m"]["form"]["newRow"]["phid_pc"] == "ARCHIVE-1"
    assert transfer_save["p_form_ldzcdb_m"]["form"]["newRow"]["phid_pc"] == "ARCHIVE-1"
    assert transfer_save["p_form_ldzcdb_d"]["table"]["newRow"][0]["row"]["u_inproj"] == "ARCHIVE-2"


def test_transfer_retry_reconciles_unknown_save_without_reposting(client):
    key = add(client, in_rental="no")["equipment"][0]["id"]
    code = request(client, "GET", f"/equipment/{key}")["equipment"]["code"]
    row = equipment_row() | {"u_device_code": code, "bill_name": BASE["name"], "u_yz": BASE["purchase_price"]}
    adapter, calls = custom_adapter(page(row), page(row), TimeoutError(), page(row),
                                    page(row | {"phid_pc": "P2", "phid_pc_EXName": "项目乙"}))
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    transfer = request(client, "POST", "/transfers", dict(equipment_ids=[key], to_project="项目乙",
                                                          transfer_date="2026-11-23"))["transfers"][0]
    assert transfer["i8_sync_status"] == "failed"
    for expected in ["failed", "synced"]:
        result = request(client, "POST", "/i8-sync/retry", {"transfer_ids": [transfer["id"]]})
        assert result["transfers"][0]["status"] == expected
    assert [c.args[0] for c in calls.call_args_list] == [LIST_PATH, LIST_PATH, SAVE_PATH, LIST_PATH, LIST_PATH]


def test_saved_transfer_waits_for_equipment_project_without_reposting(client):
    key = add(client, in_rental="no")["equipment"][0]["id"]
    code = request(client, "GET", f"/equipment/{key}")["equipment"]["code"]
    row = equipment_row() | {
        "u_device_code": code, "bill_name": BASE["name"], "u_yz": BASE["purchase_price"],
        "u_indata": f"{BASE['purchase_date']} 00:00:00", "u_spec": BASE.get("spec"),
    }
    bill = page(transfer_bill())
    moved = page(row | {"phid_pc": "P2", "phid_pc_EXName": "项目乙"})
    adapter, calls = custom_adapter(page(row), page(row), save_receipt("B1"), bill, page(row), bill, moved)
    client.app.dependency_overrides[i8_adapter] = lambda: adapter
    saved = request(client, "POST", "/transfers", dict(equipment_ids=[key], to_project="项目乙",
                                                       transfer_date="2026-11-24"))["transfers"][0]
    assert saved["i8_sync_status"] == "pending"
    assert json.loads(saved["i8_conflict_json"])["bill_no"] == "20261124-0001"
    retried = request(client, "POST", "/i8-sync/retry", {"transfer_ids": [saved["id"]]})
    assert retried["transfers"][0]["status"] == "synced"
    assert [c.args[0] for c in calls.call_args_list] == [
        LIST_PATH, LIST_PATH, SAVE_PATH, LIST_PATH, LIST_PATH, LIST_PATH, LIST_PATH,
    ]


def test_transfer_receipt_commit_failure_does_not_repost(client):
    item, = add(client, name="样机", in_rental="no")["equipment"]
    key = item["id"]
    with session_scope() as db:
        db.get(EquipmentItem, key).i8_sync_status = "synced"
    before = page(equipment_row())
    adapter, calls = custom_adapter(before, save_receipt("B1"), page(transfer_bill()), before, before)
    client.app.dependency_overrides[i8_adapter] = lambda: adapter

    def fail_receipt(db, *_):
        if any(isinstance(row, EquipmentTransfer) and '"bill_phid"' in (row.i8_conflict_json or "")
               for row in db.dirty):
            raise RuntimeError("simulated receipt commit failure")

    event.listen(Session, "before_flush", fail_receipt)
    try:
        with pytest.raises(RuntimeError, match="simulated receipt commit failure"):
            transfer_to(client, key, "项目乙")
    finally:
        event.remove(Session, "before_flush", fail_receipt)
    saved, = request(client, "GET", "/transfers")["items"]
    intent = json.loads(saved["i8_conflict_json"])
    assert intent["awaiting_readback"] and "bill_phid" not in intent
    request(client, "DELETE", f"/transfers/{saved['id']}", status=409)
    retried = request(client, "POST", "/i8-sync/retry", {"transfer_ids": [saved["id"]]})
    assert retried["transfers"][0]["status"] == "failed"
    assert [call.args[0] for call in calls.call_args_list] == [LIST_PATH, SAVE_PATH, LIST_PATH, LIST_PATH, LIST_PATH]


def save_source(path, sheets):
    book = Workbook()
    book.remove(book.active)
    for name, records in sheets.items():
        ws = book.create_sheet(name)
        for row in records:
            ws.append(row)
    book.save(path)
    return path


@pytest.fixture
def baseline_paths(tmp_path):
    item_header = "工机具编号 名称 规格型号 单位 信息化用购买日期 购买日期 购买项目 购买价格 当前状态 当前所在项目 备注 在账 - 列租赁表 列资产账 租赁底稿行 盘点来源行 来源 接续所在项目 数量 核对说明".split()
    transfer = "工机具编号 名称 规格型号 单位 购买日期 购买项目 购买价格 调出项目 调入项目 调拨日期 备注".split()
    scrap = transfer[:7] + ["所在项目", "报废日期", "报废原因", "备注"]
    item = ["甲-01", "样机", None, "台", date(2025, 1, 2), 202501, "晋江污泥处理项目", 2, "在用", "鄂旗项目",
            None, "是", None, "是", "是", "4", "5", "分布原第 3 行", None, 3]
    tricycle = ["电动三轮车", None, "辆", date(2023, 5, 1), 202305, "焦作佰利项目", 5300,
                "在用", "焦作佰利项目", None, "是", None, "否", "是", None, "6、7", None, None, 1]
    distribution = save_source(tmp_path / "d.xlsx", {
        "工机具基础信息": [[], item_header, item, ["乙-01", "样机乙", *item[2:11], "固定资产", None, "是", "否",
                                           None, None, None, None, 1],
                           ["电动三轮车-202305-1", *tricycle], ["电动三轮车-202305-2", *tricycle]],
        "调拨记录": [transfer, ["甲-01", *[None]*6, "酒钢项目", "乌兰察布储能项目", "20260811张永军", "原备注"]],
        "报废记录": [scrap, ["乙-01", *[None]*5, 2, "福建南平项目", 20261101, "损坏"]],
        "周转材料": [[], item_header, ["转-01", "样阀", *item[2:14], "否", None, None, None, None, 1]],
        "周转材料调拨记录": [transfer], "周转材料报废记录": [scrap]})
    header = [None]*4 + ["单价", "帐面数", None, "盘点数", None, None, None, "盈亏原因"]
    inventory = save_source(tmp_path / "i.xlsx", {"2025年年终盘点流动资产": [[], [], header, [],
        [1, "样机", None, "台", 2, 3, 6.01, 3, 6], [2, "电动三轮车", None, "辆", 5300, 1, 5300, 1, 5300],
        [3, "电动三轮车", None, "辆", 5300, 1, 5300, 1, 5300]], "周转材料": [[], [], header]})
    rental_header = "项目 设备名称 规格型号 单位 数量 租赁单价（元） 本月收费 金额（元） 变化／待核 类别 原值（元） 自定义单价（元） 底稿行 上期金额 早期草稿金额 对应设备编号".split()
    rental = save_source(tmp_path / "r.xlsx", {"本月租赁": [[], [], [], [], rental_header,
        ["晋江污泥处理项目", "样机", None, "台", 3, 5, "计费", 15.01, None, "设备", None, 5, 4, None, None, "甲-01"],
        ["宜阳仓库", "样机", None, "台", 1, 0, "金额留空", None, None, None, 0, None, 5, None, None, "甲-01、乙-01"]]})
    return dict(distribution_path=distribution, inventory_path=inventory, rental_path=rental)


def test_baseline_apply_and_excel_readback(client, baseline_paths):
    preview = import_equipment_baseline(None, **baseline_paths, dry_run=True)
    assert preview == dict(equipment_count=4, turnover_count=1, transfer_count=1, scrap_count=1,
        inventory_tool_count=3, inventory_tool_book_total=Decimal("10606.01"), inventory_turnover_count=0,
        rental_line_count=2, rental_grand_total=Decimal("15.01"), linked_inventory_count=3, linked_rental_count=1)
    assert request(client, "GET", f"/rental?month={MONTH}")["projects"] == []
    assert request(client, "GET", "/rental?month=2026-12")["projects"] == []
    original_location = request(client, "POST", "/locations", dict(name="酒钢项目", is_active=False, sort_order=5))
    with session_scope() as db:
        jinjiang = archive_project(db, "晋江污泥项目")
        wulanchabu = archive_project(db, "乌兰察布项目")
        nanping = archive_project(db, "南平项目")
        archive_project(db, "焦作佰利项目")
        assert import_equipment_baseline(db, **baseline_paths) == preview
    with session_scope() as db:
        with pytest.raises(ValueError, match="台账非空"):
            import_equipment_baseline(db, **baseline_paths)
        item = db.scalar(select(EquipmentItem).where(EquipmentItem.code == "甲-01"))
        assert db.get(InventoryItem, item.inventory_item_id).source_row == "5"
        assert item.quantity == 3 and item.source_info == "分布原第 3 行"
        assert (item.purchase_project_id, item.purchase_project_custom) == (jinjiang, None)
        assert (item.current_project_id, item.current_project_custom) == (wulanchabu, "鄂旗项目")
        scrap = db.scalar(select(EquipmentScrap))
        assert (scrap.reason, scrap.original_project_id, scrap.original_project_custom) == ("损坏", nanping, None)
        transfer = db.scalar(select(EquipmentTransfer))
        assert (transfer.transfer_date, transfer.remark) == (date(2026, 8, 11), "张永军；原备注")
        assert (transfer.from_project_id, transfer.from_project_custom) == (None, "酒钢项目")
        assert (transfer.to_project_id, transfer.to_project_custom) == (wulanchabu, None)
        a, b = db.scalars(select(RentalLine).order_by(RentalLine.project_sort_order)).all()
        assert a.equipment_id == item.id and a.custom_unit_price == 5
        assert (a.project_id, a.project_custom) == (jinjiang, None)
        assert b.equipment_id is None and b.billing_status == "blank" and b.amount is None
        assert (b.project_id, b.project_custom) == (None, "宜阳仓库")
        assert a.category_label == b.category_label == "大型工机具"
        unlinked = b.id
        assert [db.get(InventoryItem, db.scalar(select(EquipmentItem.inventory_item_id).where(
            EquipmentItem.code == f"电动三轮车-202305-{i}"))).source_row for i in (1, 2)] == ["6", "7"]
    locations = {r["name"]: r for r in request(client, "GET", "/locations?include_inactive=true")["items"]}
    assert locations["鄂旗项目"]["default_project_id"] == wulanchabu
    assert locations["宜阳仓库"]["default_project_id"] is None
    assert locations["酒钢项目"] == original_location
    assert request(client, "GET", "/i8-sync/issues") == {"equipment": [], "transfers": []}
    with session_scope() as db:
        turnover_id = db.scalar(select(EquipmentItem.id).where(EquipmentItem.item_category == "turnover"))
    edited = request(client, "PATCH", f"/equipment/{turnover_id}", {"remark": "核对"})
    assert edited["inventory_item_id"] is None
    exported = workbook(client, "distribution", data_only=True)
    assert [exported["周转材料"][cell].value for cell in ("L3", "O3")] == ["是", "否"]
    dist = exported["工机具基础信息"]
    assert (dist["E3"].value.date(), dist["F3"].value, dist["T3"].value) == (date(2025, 1, 2), "202501", 3)
    transfer_sheet = exported["调拨记录"]
    assert (transfer_sheet["J2"].value.date(), transfer_sheet["K2"].value) == (date(2026, 8, 11), "张永军；原备注")
    inv = workbook(client, "inventory")["流动资产盘点表"]
    assert inv["G5"].value == 6.01 and "H5*E5" in inv["I5"].value
    rent = workbook(client, f"rental?month={MONTH}").active
    assert rent["G4"].value == 15.01 and rent["G14"].value is None
    later = "/rental?month=2026-12"
    request(client, "GET", later)
    request(client, "PATCH", f"/rental/lines/{unlinked}", {"billing_status": "stopped"})
    lines = {group["project_name"]: group["lines"][0] for group in request(client, "GET", later)["projects"]}
    assert lines["宜阳仓库"]["billing_status"] == "stopped"
    assert lines["晋江污泥项目"]["billing_status"] == "normal"


@pytest.mark.parametrize("original_count", [None, "0", "0.5", "1.5"])
def test_spec_split_preserves_shared_inventory_count(client, original_count):
    created = add(client, quantity=2, purchase_price="10", in_rental="no")
    key = created["equipment"][0]["id"]
    inv_id = created["inventory_item"]["id"]
    request(client, "PATCH", f"/inventory/{inv_id}", {"count_qty": original_count})
    request(client, "PATCH", f"/equipment/{key}", {"spec": "另一规格"})
    old, new = request(client, "GET", "/inventory")["items"]
    assert old["id"] == inv_id and new["linked_equipment_ids"] == [key]
    count = Decimal(original_count) if original_count is not None else None
    split_count = min(count, 1) if count is not None else None
    for row, expected in ((old, count - split_count if count is not None else None), (new, split_count)):
        assert Decimal(row["book_qty"]) == 1 and Decimal(row["book_amount"]) == 10
        if expected is None:
            assert all(row[field] is None for field in ("count_qty", "count_amount", "diff_qty", "diff_amount"))
        else:
            assert [Decimal(row[field]) for field in ("count_qty", "count_amount", "diff_qty", "diff_amount")] == [
                expected, expected * 10, expected - 1, (expected - 1) * 10,
            ]


def test_purchase_project_correction_follows_unmoved_equipment_and_rental(client):
    month = date.today().strftime("%Y-%m")
    next_month = (date.today().replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
    with session_scope() as db:
        project_id = archive_project(db, "更正后项目")
    created = add(client, target_month=month)
    key = created["equipment"][0]["id"]
    resolve(client, created["rental_line_ids"][0], "this_month")
    request(client, "GET", f"/rental?month={next_month}")
    edited = request(client, "PATCH", f"/equipment/{key}",
                     {"purchase_project_id": project_id, "purchase_project_custom": "现场"})
    assert (edited["current_project_id"], edited["current_project_custom"], edited["i8_sync_status"]) == (
        project_id, "现场", "pending",
    )
    for period in (month, next_month):
        group, = request(client, "GET", f"/rental?month={period}")["projects"]
        assert group["project_id"] == project_id and group["lines"][0]["project_custom"] == "现场"


@pytest.mark.parametrize("unknown_purchase", [True, False])
def test_undo_first_transfer_restores_recorded_origin(client, unknown_purchase):
    with session_scope() as db:
        original = archive_project(db, "原项目")
        replacement = archive_project(db, "更正项目")
    item, = add(client, item_category="turnover", in_rental="no", purchase_project_id=original)["equipment"]
    key = item["id"]
    if unknown_purchase:
        with session_scope() as db:
            row = db.get(EquipmentItem, key)
            row.purchase_project, row.purchase_project_id = "", None
            row.current_project = row.current_project_custom = "待核"
            row.current_project_id = None
        assert request(client, "PATCH", f"/equipment/{key}", {"remark": "已复核"})["purchase_project"] == ""
    transfer = transfer_to(client, key, "另一个项目")
    if not unknown_purchase:
        edited = request(client, "PATCH", f"/equipment/{key}", {"purchase_project_id": replacement})
        assert edited["current_project"] == "另一个项目"
    reverted = request(client, "DELETE", f"/transfers/{transfer}")
    assert (reverted["reverted_project_id"], reverted["reverted_project_custom"]) == (
        (None, "待核") if unknown_purchase else (original, None)
    )


def test_rental_edits_propagate_per_field_and_scrap_keeps_future_rows(client):
    created = add(client, custom_unit_price="5")
    key = created["equipment"][0]["id"]
    first = created["rental_line_ids"][0]
    resolve(client, first, "this_month")

    def row(month):
        return request(client, "GET", f"/rental?month={month}")["projects"][0]["lines"][0]

    second, third = row("2026-12"), row("2027-01")
    # Even an explicit price equal to the inherited price starts its own continuation.
    request(client, "PATCH", f"/rental/lines/{second['id']}", {"custom_unit_price": "5"})
    request(client, "PATCH", f"/rental/lines/{first}", {"quantity": "3", "custom_unit_price": "7"})
    for month in ("2026-12", "2027-01"):
        current = row(month)
        assert [Decimal(current[field]) for field in ("quantity", "unit_price", "amount")] == [3, 5, 15]

    request(client, "POST", "/scraps", dict(equipment_id=key, scrap_date=f"{MONTH}-28"))
    resolve(client, first, "charge_this_month")
    for earlier in (second, third):
        current = row(earlier["month"])
        assert (current["id"], current["custom_unit_price"], current["billing_status"], current["amount"]) == (
            earlier["id"], "5.0000", "stopped", None,
        )


def test_rental_pending_transition_and_existing_active_line(client):
    month = date.today().strftime("%Y-%m")
    next_month = (date.today().replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
    created = add(client, target_month=month)
    key = created["equipment"][0]["id"]
    first, = created["rental_line_ids"]
    resolve(client, first, "this_month")
    request(client, "GET", f"/rental?month={next_month}")
    path = f"/equipment/{key}"

    def states():
        with session_scope() as db:
            return [(line.billing_status, line.pending_action_type, line.amount)
                    for line in rental.equipment_lines(db, key, month, include_current=True)]

    # Reproduce pending equipment with active rows left by the previous implementation.
    with session_scope() as db:
        db.get(EquipmentItem, key).in_rental = "pending"
    request(client, "PATCH", path, {"in_rental": "yes"})
    assert [(status, action) for status, action, _ in states()] == [("normal", "none")] * 2
    request(client, "PATCH", path, {"in_rental": "pending"})
    assert states() == [("stopped", "none", None)] * 2
    with session_scope() as db:
        line = db.get(RentalLine, first)
        line.billing_status = "normal"
        rental.recalculate(line)
    request(client, "PATCH", path, {"in_rental": "no"})
    assert states() == [("stopped", "none", None)] * 2
    request(client, "PATCH", path, {"in_rental": "yes"})
    assert [(status, action) for status, action, _ in states()] == [
        ("skip_month", "new_purchase_start"), ("normal", "none"),
    ]


def test_rental_materialized_month_receives_unoverridden_price(client):
    created = add(client)
    first, = created["rental_line_ids"]
    resolve(client, first, "this_month")
    month = "/rental?month=2026-12"
    request(client, "GET", month)
    request(client, "PATCH", f"/rental/lines/{first}", {"custom_unit_price": "8"})
    later = request(client, "GET", month)["projects"][0]["lines"][0]
    assert Decimal(later["unit_price"]) == Decimal(later["amount"]) == 8


@pytest.mark.parametrize("known_turnover", [False, True])
def test_inventory_cover_keeps_unknown_grand_total_blank(client, known_turnover):
    request(client, "POST", "/inventory", dict(category="tool", name="待盘点", book_qty="1", count_qty=None,
                                                unit_price="9"))
    if known_turnover:
        request(client, "POST", "/inventory", dict(category="turnover", name="已盘点", book_qty="1", count_qty="1",
                                                    unit_price="8"))
    cached = workbook(client, "inventory", data_only=True)["封皮"]
    assert [cached[cell].value for cell in ("H7", "H8", "I6", "E6")] == [
        None, 8 if known_turnover else 0, None, None,
    ]
    assert "COUNT('流动资产盘点表'!I5:I5)=1" in workbook(client, "inventory")["封皮"]["I6"].value


def test_equipment_writes_follow_global_history_barrier(client):
    preview = client.post(ROOT + "/equipment/preview", json={k: BASE[k] for k in ("name", "purchase_date")})
    assert preview.status_code == 200 and "X-Operation-History" not in preview.headers
    created = client.post(ROOT + "/equipment", json=BASE)
    assert created.status_code == 200 and created.headers["X-Operation-History"] == "unsupported"


@pytest.mark.parametrize(("source", "parsed", "note"), [
    ("20251029统计", date(2025, 10, 29), "统计"),
    ("20260811张永军", date(2026, 8, 11), "张永军"),
    ("2025.10.29 备注", date(2025, 10, 29), "备注"),
    ("2025-10-29", date(2025, 10, 29), None),
    ("2026年初", None, "2026年初"),
])
def test_transfer_date_note(source, parsed, note):
    assert transfer_date_note(source, None) == (parsed, note)


def test_legacy_rental_sheet(tmp_path):
    path = save_source(tmp_path / "legacy.xlsx", {"分公司9月份 (2)": [
        ["租赁费明细（费用划转）", *[None]*10, "原值"], ["单位：测试项目"], ["序号", "名称"],
        [1, "样机", None, "台", 1, 17, None, "设备", "原分布", None, None, 20],
        [2], [None, "合计："]]})
    line, = parse_rental(path)
    assert (line["project_name"], line["source_row"], line["custom_unit_price"]) == ("测试项目", "4", 17)
    assert line["billing_status"] == "blank" and line["amount"] is None
    assert line["category_label"] == "大型工机具"


def test_optional_tail501_baseline(rollback_db):
    if not os.getenv("M16_BASELINE_PATHS"):
        pytest.skip("按需提供三本接续原件的路径")
    assert rollback_db.exec_driver_sql("SELECT current_schema()").scalar_one().startswith("backend_verify_")
    paths = {key: Path(value) for key, value in json.loads(os.environ["M16_BASELINE_PATHS"]).items()}
    def hashes():
        return [hashlib.sha256(p.read_bytes()).digest() for p in paths.values()]
    original = hashes()
    try:
        preview = import_equipment_baseline(None, **paths, dry_run=True)
        with session_scope() as db:
            for name in ("乌兰察布项目", "晋江污泥项目", "南平项目", "焦作佰利项目", "沭阳热电厂", "泗阳#4",
                         "灵宝二期", "龙源纸业项目", "大唐雷州", "新疆慧能项目", "内蒙宜化项目", "安徽国风项目",
                         "广东茂名项目", "宜昌项目"):
                archive_project(db, name)
            assert import_equipment_baseline(db, **paths) == preview
        with session_scope() as db:
            def count(model, *filters):
                return db.scalar(select(func.count()).select_from(model).where(*filters))
            tool = InventoryItem.category == "tool"
            observed = dict(equipment_count=count(EquipmentItem, EquipmentItem.item_category == "equipment"),
                turnover_count=count(EquipmentItem, EquipmentItem.item_category == "turnover"),
                transfer_count=count(EquipmentTransfer), scrap_count=count(EquipmentScrap), inventory_tool_count=count(InventoryItem, tool),
                inventory_turnover_count=count(InventoryItem, InventoryItem.category == "turnover"),
                inventory_tool_book_total=db.scalar(select(func.sum(InventoryItem.book_amount)).where(tool)),
                rental_line_count=count(RentalLine), rental_grand_total=db.scalar(select(func.sum(RentalLine.amount))),
                linked_inventory_count=count(EquipmentItem, EquipmentItem.inventory_item_id.is_not(None)),
                linked_rental_count=count(RentalLine, RentalLine.equipment_id.is_not(None)))
            assert observed == preview == dict(equipment_count=421, turnover_count=6, transfer_count=295, scrap_count=0,
                inventory_tool_count=146, inventory_turnover_count=6, inventory_tool_book_total=Decimal("758371.4324"),
                rental_line_count=128, rental_grand_total=Decimal("19781.0367"), linked_inventory_count=306, linked_rental_count=88)
            assert count(InventoryItem, ~select(EquipmentItem.id).where(
                EquipmentItem.inventory_item_id == InventoryItem.id, EquipmentItem.status != "scrapped",
                EquipmentItem.asset_scope == "current_asset").exists()) == 0
            assert count(EquipmentItem, EquipmentItem.item_category == "equipment", EquipmentItem.quantity != 1) == 0
            welders = db.scalars(select(EquipmentItem).where(
                EquipmentItem.code.startswith("逆变焊机-20230711-")).order_by(EquipmentItem.code)).all()
            assert [row.code for row in welders] == [f"逆变焊机-20230711-{unit:02d}" for unit in range(1, 16)]
            nanping = db.scalar(select(Project.id).where(Project.disp == "南平项目"))
            assert {(r.name, r.unit, r.purchase_price, r.purchase_date, r.purchase_project, r.current_project,
                     r.current_project_id, r.asset_scope, r.in_rental, r.remark) for r in welders} == {
                ("逆变焊机", "台", Decimal("1132.7430"), date(2023, 7, 11), "南靖项目", "南平项目",
                 nanping, "current_asset", "yes", "实物为4台二保焊机")}
            inventory_ids = {row.inventory_item_id for row in welders}
            assert len(inventory_ids) == 1 and db.get(InventoryItem, welders[0].inventory_item_id).source_row == "75"
            for index, row in enumerate(welders):
                history = db.scalars(select(EquipmentTransfer).where(
                    EquipmentTransfer.equipment_id == row.id).order_by(EquipmentTransfer.id)).all()
                assert [(t.transfer_date, t.from_project, t.to_project, t.remark) for t in history] == (
                    [(date(2025, 10, 29), "南靖项目", "大连项目", "统计"),
                     (date(2025, 10, 29), "大连项目", "晋江污泥项目", "统计"),
                     (date(2026, 4, 5), "晋江污泥项目", "福建南平项目", None)] if index < 4 else [])
            cable = db.scalars(select(EquipmentItem).where(EquipmentItem.name == "电缆")).all()
            assert {(r.spec, r.unit, r.quantity, r.current_project, r.in_rental, r.i8_sync_status) for r in cable} == {
                ("YH35", "m", 5788, "待核", "no", "not_applicable"),
                ("YH50", "m", 1145, "待核", "no", "not_applicable")}
            turnover = db.execute(select(InventoryItem, EquipmentItem)
                .join(EquipmentItem, EquipmentItem.inventory_item_id == InventoryItem.id)
                .where(InventoryItem.category == "turnover")).all()
            assert len(turnover) == 6
            assert all((i.name, i.unit, i.book_qty, i.unit_price) == (e.name, e.unit, e.quantity, e.purchase_price)
                       for i, e in turnover)
            valves = db.scalars(select(RentalLine).where(RentalLine.source_row.in_(("180", "209")))).all()
            assert len(valves) == 2 and all(r.name == "电动闸阀" and r.category_label == "周转材料"
                and db.get(EquipmentItem, r.equipment_id).purchase_price == r.original_value for r in valves)
            assert all(row.category_label in ("周转材料", "大型工机具") for row in db.scalars(select(RentalLine)))
            locations = {row.name: row.default_project_id for row in db.scalars(select(Location))}
            assert {"宜阳仓库", "酒钢项目", "宁夏项目", "开平项目", "廉江项目", "南靖项目", "合肥项目", "鄂旗项目"} <= locations.keys()
            assert locations["鄂旗项目"] == db.scalar(select(Project.id).where(Project.disp == "乌兰察布项目"))
            assert count(EquipmentItem, EquipmentItem.asset_scope == "fixed_asset") == 7
            assert count(RentalMonth, RentalMonth.month == MONTH) == 1
            assert count(RentalLine, RentalLine.billing_status == "blank", RentalLine.amount.is_(None)) == 97
            assert count(RentalLine, RentalLine.custom_unit_price.is_not(None)) == 17
            assert rental.view(db, MONTH)["grand_total"] == Decimal("19781.0367")
    finally:
        assert hashes() == original
