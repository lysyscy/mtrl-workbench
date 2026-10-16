"""付款计划非法金额拒写回归；HTTP 与真实测试库共用外层回滚事务。"""
from __future__ import annotations

import io
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import db, preview_store
from app.import_kit import api as imp_api
from app.import_kit.profile_store import ProfileStore
from app.mod01_projects import models as _project_models  # noqa: F401
from app.mod04_plan import imp_spec, repository as repo
from app.mod04_plan.models import PlanRow
from tests.acc_plugin import acc

HEADERS = ["项目", "单据号", "该流程金额", "本月预付款金额"]
BASE = "/api/imp/m04_plan"


@pytest.fixture
def isolated_plan(tmp_path, monkeypatch):
    engine = db.get_engine()
    assert engine.dialect.name == "postgresql"
    assert engine.url.database and engine.url.database.endswith("_test")
    ym = f"{9000 + uuid4().int % 1000}-09"
    with engine.connect() as connection:
        outer = connection.begin()

        @contextmanager
        def scope():
            with Session(bind=connection, expire_on_commit=False,
                         join_transaction_mode="create_savepoint") as session:
                try:
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

        monkeypatch.setattr(db, "session_scope", scope)
        monkeypatch.setattr(imp_api, "session_scope", scope)
        monkeypatch.setattr(imp_api, "current_operator", lambda: "隔离计划导入自检")
        monkeypatch.setattr(preview_store, "PREVIEW_DIR", tmp_path / "previews")
        app = FastAPI()
        app.include_router(imp_api.build_router(
            imp_spec.SPEC, imp_spec.HOOKS, store=ProfileStore(tmp_path / "profile.json")))
        try:
            with scope() as session:
                session.execute(delete(PlanRow).where(PlanRow.year_month == ym))
            with TestClient(app) as client:
                yield client, scope, ym
        finally:
            outer.rollback()


def _body(client, ym, rows, *, map_optional=True):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    data = io.BytesIO()
    wb.save(data)
    parsed = client.post(BASE + "/parse", files={
        "file": ("计划.xlsx", data.getvalue(),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert parsed["ok"] and parsed["header_row"] == 1, parsed
    labels = HEADERS if map_optional else HEADERS[:-1]
    return {"token": parsed["token"], "mapping": {label: label for label in labels},
            "options": {"year_month": ym}}


def _snapshot(scope, ym):
    with scope() as session:
        rows = session.scalars(select(PlanRow).where(PlanRow.year_month == ym)
                               .order_by(PlanRow.id)).all()
        return [{column.name: getattr(row, column.name) for column in PlanRow.__table__.columns}
                for row in rows]


@acc()
@pytest.mark.parametrize("bad_column", ["该流程金额", "本月预付款金额"])
def test_invalid_amount_rejects_whole_month_without_overwriting_or_deleting(isolated_plan, bad_column):
    client, scope, ym = isolated_plan
    project = "__不存在的计划项目_" + uuid4().hex
    with scope() as session:
        repo.merge_month(session, year_month=ym, rows=[
            {"project_input": project, "doc_no": "old-1", "flow_amount": Decimal("123.45"),
             "planned_amount": Decimal("67.89")},
            {"project_input": project, "doc_no": "old-2", "flow_amount": Decimal("987.65"),
             "planned_amount": Decimal("43.21")},
            {"project_input": project, "doc_no": "old-omitted", "flow_amount": Decimal("55"),
             "planned_amount": Decimal("44")},
        ])
        session.add(PlanRow(year_month=ym, project_input=project, doc_no="manual",
                            flow_amount=Decimal("12"), planned_amount=Decimal("3"), is_manual=True))
    before = _snapshot(scope, ym)
    invalid = [project, "old-2", "987.65", "43.21"]
    invalid[HEADERS.index(bad_column)] = "金额填错了"
    body = _body(client, ym, [
        [project, "old-1", "999", "888"], invalid, [project, "new-row", "10", "5"]])
    preview = client.post(BASE + "/preview", json=body).json()
    assert _snapshot(scope, ym) == before, "预览不得写库"
    committed = client.post(BASE + "/commit", json=body).json()
    after = _snapshot(scope, ym)
    assert after == before, (
        "非法金额整批拒写：原金额、手动行与行集合都必须保留；实际="
        + repr([(row["doc_no"], row["flow_amount"], row["planned_amount"]) for row in after]))
    for response in (preview, committed):
        assert response["ok"] is False, response
        assert "第 3 行" in response["message"] and bad_column in response["message"], response


@acc()
@pytest.mark.parametrize("flow,planned,map_optional,expected_flow,expected_planned", [
    ("1,250.50", "250.25", True, "1250.50", "250.25"),
    (0, 0, True, "0", "0"),
    (100, None, True, "100", "0"),
    ("", "", True, "0", "0"),
    (100, "未映射原值", False, "100", "0"),
])
def test_valid_zero_empty_and_unmapped_optional_amounts_keep_existing_rules(
        isolated_plan, flow, planned, map_optional, expected_flow, expected_planned):
    client, scope, ym = isolated_plan
    project = "__不存在的计划项目_" + uuid4().hex
    body = _body(client, ym, [[project, "valid-row", flow, planned]], map_optional=map_optional)
    preview = client.post(BASE + "/preview", json=body).json()
    assert preview["ok"] and preview["total"] == 1, preview
    assert preview["kpis"]["项目未匹配"] == 1
    assert "writable" not in preview and "skipped" not in preview
    assert _snapshot(scope, ym) == []
    committed = client.post(BASE + "/commit", json=body).json()
    assert committed["ok"] and committed["report"]["created"] == 1, committed
    rows = _snapshot(scope, ym)
    assert len(rows) == 1 and rows[0]["project_id"] is None
    assert rows[0]["flow_amount"] == Decimal(expected_flow)
    assert rows[0]["planned_amount"] == Decimal(expected_planned)
    if not map_optional:
        assert rows[0]["raw"]["本月预付款金额"] == "未映射原值"
