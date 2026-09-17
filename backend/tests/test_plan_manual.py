"""付款计划**手动行**的工程自检（离线 · 不连库）。

用户 2026-09-16 裁定：**① 付款计划要手动行，而且手动行一样要被审查**。

⇒ 本文件守两件事：
1. 手动行**能增能改**、且**不被导入清理**（落在 `merge_month`，`test_plan_import` 也有一条）；
2. ⭐ **手动行与导入行走完全同一条审查链路** —— 同样 6 种判定、同样进两档筛选、同样计 KPI 与合计。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.errors import MustReportError
from app.main import create_app
from app.mod01_projects.models import Project
from app.mod04_plan import repository as repo
from app.mod04_plan.domain import (
    BUCKET_MATCHED,
    BUCKET_UNMATCHED,
    R_AMOUNT_MISMATCH,
    R_DOC_NOT_FOUND,
    R_MATCHED,
    R_NO_DOC,
)
from app.mod04_plan.models import PlanRow
from app.mod04_plan.plan_manual import (
    assert_manual_editable,
    is_manual_row,
    manual_row_payload,
)
from app.mod04_plan.router import get_db, get_page_data
from app.mod04_plan.service import build_page_data
from app.mod03_notice.models import PaymentNotice
from app.mod04_plan.view import render_m04
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession, make_notice, make_plan_row
from tests.m03_action_helpers import FakeWriteSession


def _manual(**kw) -> PlanRow:
    """一条**手动行**（默认：单据号对得上、金额对得上 ⇒ 完全匹配）。"""
    vals = dict(
        id=90, year_month="2026-09", project_input="甲仓库", project_id=11,
        match_status="matched", match_candidates=1, doc_no="D1",
        flow_amount=Decimal("1000.00"), planned_amount=Decimal("800.00"),
        pay_date="", pay_method="", remark="", forced_through=False, forced_remark="",
        is_manual=True, raw={"来源": "手动新增"},
    )
    vals.update(kw)
    return PlanRow(**vals)


# ============================================================ 组装与校验


@acc()
def test_手动行字段校验():
    ok = manual_row_payload(year_month="2026-09", project_id=11, doc_no="D1",
                            flow_amount="1000", planned_amount="800", pay_method="承兑")
    v = ok.values
    assert v["is_manual"] is True and v["year_month"] == "2026-09"
    assert v["flow_amount"] == Decimal("1000.00") and v["planned_amount"] == Decimal("800.00")
    assert v["pay_method"] == "承兑"
    assert any("一样参与" in n for n in ok.notes)


@acc()
def test_手动行年月必填且要月度形态():
    with pytest.raises(MustReportError) as err:
        manual_row_payload(year_month="", flow_amount="1")
    assert "归月依据" in err.value.message
    with pytest.raises(MustReportError):
        manual_row_payload(year_month="2026", flow_amount="1")     # 年不是"归月"形态


@acc()
def test_手动行金额与付款方式校验():
    with pytest.raises(MustReportError):
        manual_row_payload(year_month="2026-09", planned_amount="-1")
    with pytest.raises(MustReportError) as err:
        manual_row_payload(year_month="2026-09", pay_method="现金")
    assert "付款方式只能是" in err.value.message
    # 付款方式留空 ⇒ 允许（Excel 导入里也常为空）
    assert manual_row_payload(year_month="2026-09").values["pay_method"] == ""


@acc("ACC-PLAN-MANUAL-001", "001-05")
def test_编辑只对手动行开放():
    with pytest.raises(MustReportError) as err:
        assert_manual_editable({"id": 1, "is_manual": False})
    assert "请**修正 Excel 后重新导入**" in err.value.message
    assert_manual_editable({"id": 1, "is_manual": True})           # 手动行不抛
    assert is_manual_row(_manual()) and not is_manual_row(make_plan_row(1))


@acc()
def test_单据号可空且会提示():
    payload = manual_row_payload(year_month="2026-09", doc_no="")
    assert payload.values["doc_no"] == ""
    assert any("无单据号" in n for n in payload.notes)


# ============================================================ ⭐ 手动行一样被审查


def _render(plan_rows, notices=(), flows=()):
    session = FakeSession({PlanRow: list(plan_rows), PaymentNotice: list(notices),
                           PaymentFlow: list(flows),
                           Project: [Project(id=11, project_type="normal", name_full="甲全名",
                                             warehouse_name="甲仓库", disp="甲仓库")]})
    data = build_page_data(session, year_month="", sort_col="", sort_dir=0)
    return data, render_m04(data)


@acc("ACC-PLAN-MANUAL-001", "001-01")
def test_手动行与导入行同一套判定():
    """⭐ 同数据 ⇒ **审查结果必须一致**（审查按行实时派生、不看来源）。"""
    manual = _manual(id=90, doc_no="D1", flow_amount=Decimal("1000.00"))
    auto = make_plan_row(1, doc_no="D2", flow_amount="1000.00", project_id=11)
    data, _ = _render([manual, auto],
                      notices=[make_notice(101, "D1", "1000.00"), make_notice(102, "D2", "1000.00")])
    by_id = {r["id"]: r for r in data["rows"]}
    assert by_id[90]["audit_result"] == by_id[1]["audit_result"] == R_MATCHED


@acc("ACC-PLAN-MANUAL-001", "001-03")
def test_手动行与导入行同号同样判重复上报():
    """同月同单据号两行 ⇒ **两条都判「重复上报」**（§4.3.4 / 001-05）——
    证明手动行与导入行**在同一个判重空间里**，不会因为"来源是手动"被跳过。"""
    manual = _manual(id=90, doc_no="D1", flow_amount=Decimal("1000.00"))
    auto = make_plan_row(1, doc_no="D1", flow_amount="1000.00", project_id=11)
    data, _ = _render([manual, auto], notices=[make_notice(101, "D1", "1000.00")])
    assert {r["audit_result"] for r in data["rows"]} == {"重复上报"}


@acc("ACC-PLAN-MANUAL-001", "001-01")
def test_手动行同样参与六种判定的分支():
    """同一份手动行数据，按单据号 / 金额不同 ⇒ 落到不同判定（证明它真的在被审）。"""
    session = FakeSession({PlanRow: [], PaymentNotice: [make_notice(101, "D1", "1000.00")],
                           PaymentFlow: [], Project: []})
    for doc_no, flow, expect in (
        ("D1", Decimal("1000.00"), R_MATCHED),
        ("D1", Decimal("900.00"), R_AMOUNT_MISMATCH),
        ("D9", Decimal("1000.00"), R_DOC_NOT_FOUND),
        ("", Decimal("1000.00"), R_NO_DOC),
    ):
        session.by_model[PlanRow] = [_manual(id=90, doc_no=doc_no, flow_amount=flow)]
        data = build_page_data(session, year_month="", sort_col="", sort_dir=0)
        assert data["rows"][0]["audit_result"] == expect, (doc_no, flow)


@acc("ACC-PLAN-MANUAL-001", "001-02")
def test_手动行同样进两档筛选与KPI():
    session = FakeSession({PlanRow: [_manual(id=90, doc_no="D1")],
                           PaymentNotice: [make_notice(101, "D1", "1000.00")],
                           PaymentFlow: [], Project: []})
    matched = build_page_data(session, year_month="", audit_bucket=BUCKET_MATCHED, sort_col="", sort_dir=0)
    assert [r["id"] for r in matched["rows"]] == [90]
    assert matched["counts"][R_MATCHED] == 1
    other = build_page_data(session, year_month="", audit_bucket=BUCKET_UNMATCHED, sort_col="", sort_dir=0)
    assert other["rows"] == []


@acc("ACC-PLAN-MANUAL-001", "001-02")
def test_手动行计入表内合计():
    a = _manual(id=90, planned_amount=Decimal("800.00"))
    b = make_plan_row(1, doc_no="D1", planned_amount="200.00", project_id=11)
    data, _ = _render([a, b])
    assert data["summary"]["planned_amount"] == "1000.00"       # 800 + 200，**手动行照算**


# ============================================================ 页面


@acc()
def test_页面有手动新增入口且草稿行列数一致():
    from app.mod04_plan.view import COLUMNS

    data, html = _render([])
    assert "＋ 手动新增计划行" in html

    session = FakeSession({PlanRow: [], PaymentNotice: [], PaymentFlow: [], Project: []})
    data = build_page_data(session, year_month="2026-09", sort_col="", sort_dir=0, draft="new")
    html = render_m04(data)
    assert 'class="draftrow"' in html
    assert '<form id="f-row" method="post" action="/m04/row/save">' in html
    assert html.count('<tr class="draftrow"') == 1
    # 列数一致（草稿行每格一个 <td>）
    seg = html.split('<tr class="draftrow"')[1].split("</tr>")[0]
    assert seg.count("<td") == len(COLUMNS)


@acc("ACC-PLAN-MANUAL-001", "001-06")
def test_页面上手动行有徽标与编辑_导入行没有():
    manual = _manual(id=90)
    auto = make_plan_row(1, doc_no="D1", project_id=11)
    _, html = _render([manual, auto])
    mrow = next(r for r in _rows(html) if ">90<" in r)
    arow = next(r for r in _rows(html) if ">1<" in r)
    assert "手动</span>" in mrow and "/m04/row/draft" in mrow
    assert "手动</span>" not in arow and "/m04/row/draft" not in arow
    assert ">删除<" in arow                                     # 删除**所有行都有**（§4.3.6）
    assert ">删除<" in mrow                                     # ⭐ 手动行同样可删（不得照抄「i8 行永不删」）


def _rows(html: str) -> list[str]:
    import re

    body = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", html)
    return re.findall(r"<tr\b[^>]*>[\s\S]*?</tr>", body.group(1) if body else "")


# ============================================================ 路由（PRG）


def _client(plan_rows=(), projects=()):
    app = create_app()
    fake = FakeWriteSession({PlanRow: list(plan_rows), Project: list(projects),
                             PaymentFlow: [], PaymentNotice: []})
    app.dependency_overrides[get_db] = lambda: fake
    return TestClient(app), fake


@acc()
def test_路由_新增手动行落库并标is_manual():
    client, fake = _client(projects=[Project(id=11, project_type="normal", name_full="甲全名",
                                             warehouse_name="甲仓库", disp="甲仓库")])
    r = client.post("/m04/row/save", data={
        "year_month": "2026-09", "project_id": "11", "doc_no": "D1",
        "flow_amount": "1000", "planned_amount": "800", "pay_method": "承兑",
    }, follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" not in r.headers["location"]
    added = [x for x in fake.added if isinstance(x, PlanRow)]
    assert len(added) == 1 and added[0].is_manual is True
    assert added[0].project_input == "甲仓库"                    # 项目 id → 填报值（展示名）
    assert added[0].match_status == "matched"


@acc("ACC-PLAN-MANUAL-001", "001-07")
def test_路由_校验失败保留草稿行():
    client, fake = _client()
    r = client.post("/m04/row/save", data={"year_month": "2026", "flow_amount": "1"},
                    follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" in r.headers["location"]
    assert "draft=new" in r.headers["location"] and fake.added == []


@acc()
def test_路由_编辑导入行被拒():
    client, fake = _client(plan_rows=[make_plan_row(1, doc_no="D1", project_id=11)])
    r = client.post("/m04/row/save", data={
        "row_id": "1", "year_month": "2026-09", "flow_amount": "1", "planned_amount": "1",
    }, follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" in r.headers["location"]
    assert fake.added == []


@acc()
def test_路由_编辑手动行成功():
    client, fake = _client(plan_rows=[_manual(id=90)])
    r = client.post("/m04/row/save", data={
        "row_id": "90", "year_month": "2026-09", "flow_amount": "1200", "planned_amount": "500",
    }, follow_redirects=False)
    assert r.status_code == 303 and "msgkind=err" not in r.headers["location"]
    row = fake.by_model[PlanRow][0]
    assert row.planned_amount == Decimal("500.00") and row.is_manual is True


@acc()
def test_路由_取消不留数据():
    client, fake = _client()
    r = client.post("/m04/row/cancel", data={}, follow_redirects=False)
    assert r.status_code == 303
    assert fake.added == [] and fake.deleted == []


@acc("ACC-PLAN-MANUAL-001", "001-05")
def test_路由_请求编辑导入行的草稿被拒并说明():
    """⚠️ 回归：`draft=1` 必须被当成**编辑行号 1**，**不能**被当成"新增"（曾把 "1" 当新增别名）。"""
    app = create_app()
    app.dependency_overrides[get_page_data] = lambda: (
        lambda **kw: build_page_data(FakeSession({PlanRow: [make_plan_row(1, doc_no="D1")],
                                                  PaymentNotice: [], PaymentFlow: [], Project: []}), **kw)
    )
    html = TestClient(app).get("/m04", params={"year_month": "2026-09", "draft": "1"}).text
    assert "编辑只对**手动新增的计划行**开放" in html
    assert 'class="draftrow"' not in html                       # 不是"新增草稿行"


@acc()
def test_路由_新增按钮真的开到新增草稿():
    """页头「＋ 手动新增计划行」⇒ POST `/m04/row/draft`（`new=1`）⇒ 303 带 `draft=new`。"""
    client, _ = _client()
    r = client.post("/m04/row/draft", data={"new": "1"}, follow_redirects=False)
    assert r.status_code == 303 and "draft=new" in r.headers["location"]


@acc()
def test_路由_编辑手动行走id而不是new():
    client, _ = _client(plan_rows=[_manual(id=90)])
    r = client.post("/m04/row/draft", data={"row_id": "90"}, follow_redirects=False)
    assert r.status_code == 303 and "draft=90" in r.headers["location"]
