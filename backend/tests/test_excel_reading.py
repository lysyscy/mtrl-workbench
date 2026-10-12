"""报告D：从两条读表/预览入口验证共享读取，隔离夹具不冒充真实样表。"""

from contextlib import contextmanager
from datetime import datetime, time
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import preview_store
from app.core.db import get_engine
from app.core.errors import MustReportError
from app.import_kit import api, readers
from app.import_kit.profile_store import ProfileStore
from app.mod11_jc import excel_parse as jc, imp_spec, import_service
from app.mod11_jc.models import JcContract, JcInvoice
from tests.acc_plugin import acc


def book_bytes(rows, merges=(), *, title="台账", empty_first=False):
    """只构造隔离xlsx，合并范围由用例声明。"""
    wb = Workbook()
    ws = wb.active
    if empty_first:
        ws.title = "空表"
        ws = wb.create_sheet()
    ws.title = title
    for row in rows:
        ws.append(row)
    for merge in merges:
        ws.merge_cells(merge)
    buf = BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


@acc()
def test_xlsx_values_and_shape_keep_each_callers_policy():
    data = book_bytes([[0, False, datetime(2026, 9, 15, 8, 30), time(8, 30), 45444, None]])
    generic, _ = readers.read_grid(data)
    legacy = jc.read_grid(data, "台账.xlsx", "台账")
    assert generic == [[0, False, "2026-09-15", "08:30:00", 45444, None]]
    assert legacy == [["0", "False", "2026-09-15 08:30:00", "08:30:00", "45444"]]
    assert jc.to_money("1.005") == Decimal("1.00")
    assert api.parse_amount("1.005") == Decimal("1.01")
    assert jc.to_date("20260915") == "2026-09-15"
    assert api.date_text("20260915") == "20260915"


@acc()
def test_merge_range_is_real_and_each_caller_keeps_its_extent():
    rows = [["供应商", "", "", "合法空列"], ["合同总价", "发票金额", "", ""]]
    rows += [[None] * 4 for _ in range(12)]
    rows += [["甲", 100, "", ""], ["乙", None, "", ""]]
    data = book_bytes(rows, ("A1:B1", "B15:B16"))
    generic, _ = readers.read_grid(data, fill_merged_rows=12)
    legacy = jc.read_grid(data, "台账.xlsx", "台账")
    assert generic[0] == ["供应商", "供应商", None, "合法空列"]
    assert legacy[0] == ["供应商", "供应商", "", "合法空列"]
    assert generic[15][1] is None, "通用数据区不得被整表展开"
    assert legacy[15][1] == "100", "旧集采整表展开不得借重构改变"


@acc()
def test_xls_grid_keeps_coordinates_dates_bool_and_release(monkeypatch):
    """引擎隔离替身（非真实xls），覆盖真实样表没有的日期/布尔/合并块。"""
    import xlrd

    matrix = [[xlrd.sheet.Cell(xlrd.XL_CELL_TEXT, "供应商"), xlrd.sheet.Cell(xlrd.XL_CELL_EMPTY, "")],
              [xlrd.sheet.Cell(xlrd.XL_CELL_DATE, 45444.5), xlrd.sheet.Cell(xlrd.XL_CELL_BOOLEAN, 0)],
              [xlrd.sheet.Cell(xlrd.XL_CELL_NUMBER, 0.0), xlrd.sheet.Cell(xlrd.XL_CELL_NUMBER, 12.5)]]
    sheet = SimpleNamespace(name="xls台账", nrows=3, ncols=2, merged_cells=[(0, 1, 0, 2)],
                            cell=lambda r, c: matrix[r][c])
    closed = []
    fake = SimpleNamespace(nsheets=1, datemode=0, sheet_by_index=lambda i: sheet,
                           sheet_by_name=lambda n: sheet, release_resources=lambda: closed.append(True))
    monkeypatch.setattr(xlrd, "open_workbook", lambda **kwargs: fake)
    data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    generic, _ = readers.read_grid(data, fill_merged_rows=1)
    legacy = jc.read_grid(data, "台账.xls", "xls台账")
    assert generic == [["供应商", "供应商"], ["2024-06-01 12:00:00", "0"], ["0", "12.5"]]
    assert legacy == [["供应商", "供应商"], ["2024-06-01", ""], ["0", "12.5"]]
    assert len(closed) == 2


@acc()
def test_sheet_format_and_failure_contracts_stay_distinct():
    data = book_bytes([], title="空表")
    assert jc.sheet_names(data, "台账.xlsx") == readers.list_sheets(data) == ["空表"]
    assert jc.read_grid(data, "台账.xlsx", "空表") == []
    with pytest.raises(MustReportError, match="空的"):
        readers.read_grid(data)
    with pytest.raises(KeyError):
        jc.read_grid(data, "台账.xlsx", "不存在")
    with pytest.raises(KeyError):
        jc.read_grid(data, "台账.xlsx", "")
    normal = book_bytes([["项目", "金额"], ["甲", 0]])
    assert readers.read_grid(normal, sheet="")[0][1] == ["甲", 0]
    with pytest.raises(MustReportError, match="没有叫"):
        readers.read_grid(data, sheet="不存在")
    with pytest.raises(ValueError, match="不认识"):
        jc.sheet_names(data, "无后缀")
    assert readers.list_sheets(data) == ["空表"], "通用面按内容识别"
    with pytest.raises(MustReportError, match="既不是"):
        readers.read_grid(b"invalid")


@acc()
def test_legacy_preview_retains_incomplete_header_and_mapping_precedence(tmp_path):
    data = book_bytes([
        ["某项目集中采购台账"],
        ["序号", "合同日期", "材料名称", "供应商", "", "贸易公司", ""],
        ["", "", "", "合同总价", "发票金额", "合同总价", "发票金额"],
        [1, "20260915", "材料", "100", "10", "200", "20"],
        ["", "合计", "", "100", "10", "200", "20"],
    ], empty_first=True)
    result = import_service.preview(data, "台账.xlsx", store=ProfileStore(tmp_path / "p.json"))
    assert not next(s for s in result["sheets"] if s["name"] == "空表")["guess"]
    sheet = next(s for s in result["sheets"] if s["name"] == "台账")
    assert sheet["header"] == {"row1": 2, "row2": 3}
    assert sheet["labels"][3:7] == ["供应商合同总价", "供应商发票金额", "贸易公司合同总价", "贸易公司发票金额"]
    assert sheet["sample"][0]["inv_sum"] == Decimal("10.00")
    assert sheet["counts"] == {"data": 1, "skipped": 1}
    mapped = jc.map_columns(sheet["labels"], mapping={"4": "remark", "3": ""})
    assert mapped["fields"].get("remark") == 4 and "contract_amt" not in mapped["fields"]
    dupe = jc.map_columns(["合同金额", "合同总价"])
    assert dupe["fields"]["contract_amt"] == 0 and dupe["dupes"][0]["kept"] == 0


@acc()
def test_real_router_preview_does_not_write_and_confirm_preserves_i8(tmp_path, monkeypatch):
    """实际通用路由+集采钩子，隔离测试库事务最终回滚。"""
    from app.mod01_projects import repository as projects

    data = book_bytes([
        ["集中采购台账"],
        ["序号", "合同日期", "材料名称", "供应商", "", "贸易公司", "", "详细付款方式"],
        ["", "", "", "合同总价", "发票金额", "合同总价", "发票金额", ""],
        [1, "20260915", "Excel材料", "100", "10", "", "", "电汇"],
    ], ("D2:E2", "F2:G2"), empty_first=True)
    monkeypatch.setattr(preview_store, "PREVIEW_DIR", tmp_path / "preview")
    monkeypatch.setattr(api, "current_operator", lambda: "隔离核验")
    app = FastAPI()
    app.include_router(api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
        store=ProfileStore(tmp_path / "profile.json")))
    client = TestClient(app)
    with get_engine().connect() as conn:
        transaction = conn.begin()
        with Session(bind=conn) as session:
            @contextmanager
            def scope():
                yield session
                session.flush()
            monkeypatch.setattr(api, "session_scope", scope)
            project = projects.create_project(session, project_type="正常", name_full="隔离核验D",
                                               warehouse_name="__自检仓_D305__", phid="")
            contract = JcContract(project_id=project.id, contract_amt=Decimal("100"),
                                  supplier="i8供应商", contract_date="2026-01-01", material_name="i8材料")
            session.add(contract)
            session.flush()
            base = "/api/imp/m11_jc"
            parsed = client.post(base + "/parse", files={"file": ("台账.xlsx", data)}).json()
            assert parsed["ok"] and parsed["sheet"] == "台账" and parsed["header_rows"] == [2, 3]
            mapping = {c["src"]: c["field"] for c in parsed["cols"] if c["field"]}
            body = {"token": parsed["token"], "mapping": mapping,
                    "options": {"project_key": project.warehouse_name, "batch": "JC-ISOLATED-D305"}}
            pre = client.post(base + "/preview", json=body).json()
            assert pre["ok"] and pre["writable"] == 1
            assert contract.material_name == "i8材料"
            assert list(session.scalars(select(JcInvoice).where(JcInvoice.contract_id == contract.id))) == []
            confirmed = client.post(base + "/commit", json=body).json()
            assert confirmed["ok"] and confirmed["report"]["updated"] == 1
            assert contract.material_name == "Excel材料" and contract.method == "电汇"
            assert contract.supplier == "i8供应商" and contract.contract_date == "2026-01-01"
            assert contract.contract_amt == Decimal("100")
            assert len(list(session.scalars(select(JcInvoice).where(JcInvoice.contract_id == contract.id)))) == 1
        transaction.rollback()
