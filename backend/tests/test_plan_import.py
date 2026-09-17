"""付款计划**导入**（§4.3.3 数据入口 · §9.5 幂等）的工程自检（离线 · 不连库）。

⚠️ `@acc()` **显式不绑定判据点**（`ACC-PLAN-IMPORT-001` 的 7 条判据已由 `domain` 的纯函数钉住）；
   本文件守的是**导入这层**：表头识别 · 无效列原样入库 · 项目匹配 · **幂等重写**（不产生重复行 / 减行不留残影）·
   **可手改列不被覆盖** · 手动行不被触碰 · **同月同号照收不拦**（那是审查的「重复上报」）。
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.errors import MustReportError
from app.main import create_app
from app.mod01_projects.models import Project
from app.mod04_plan import repository as repo
from app.mod04_plan.domain import MATCH_AMBIGUOUS, MATCH_MATCHED, MATCH_UNMATCHED, ProjectBrief
from app.mod04_plan.importer import attach_projects, parse_workbook
from app.mod04_plan.models import PlanRow
from app.mod04_plan.router import get_db
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession
from tests.m03_action_helpers import FakeWriteSession

HEADER = (
    "项目", "材料：其他支出付资产处/贸易公司（编号）", "外租机械：付款通知书（编号）",
    "该流程金额", "本月预付款金额", "付款时间", "付款方式", "备注",
    "科目", "费用日期", "收款单位", "已付款金额", "剩余付款金额",
)


def _xlsx(rows: list[tuple]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _row(project="甲仓库", material="D1", mech="", flow=1000, planned=800,
         pay_date="2026-09-15", method="现汇", remark="", subject="辅材费", payee="某公司"):
    return (project, material, mech, flow, planned, pay_date, method, remark,
            subject, "2026-09-01", payee, 0, 0)


def _plan_row(row_id: int, **kw) -> PlanRow:
    vals = dict(
        id=row_id, year_month="2026-09", project_input="甲仓库", project_id=11,
        match_status=MATCH_MATCHED, match_candidates=1, doc_no="D1",
        flow_amount=Decimal("1000.00"), planned_amount=Decimal("800.00"),
        pay_date="", pay_method="现汇", remark="", forced_through=False,
        forced_remark="", is_manual=False, raw={},
    )
    vals.update(kw)
    return PlanRow(**vals)


# ============================================================ 解析（§4.3.3）


@acc()
def test_表头识别与有效列抽取():
    parsed = parse_workbook(_xlsx([_row()]))
    assert parsed.header_row == 1
    assert parsed.columns["project_input"] == "项目"
    r = parsed.rows[0]
    assert r["project_input"] == "甲仓库" and r["doc_no"] == "D1"
    assert r["flow_amount"] == Decimal("1000.00") and r["planned_amount"] == Decimal("800.00")
    assert r["pay_date"] == "2026-09-15" and r["pay_method"] == "现汇"


@acc()
def test_无效列原样入库不参与审查():
    """§4.3.3：科目 / 费用日期 / 收款单位 / 已付款金额 / 剩余付款金额 —— **原样入库、不要求修正**。"""
    r = parse_workbook(_xlsx([_row(subject="辅材费", payee="某公司")])).rows[0]
    assert r["raw"]["科目"] == "辅材费"
    assert r["raw"]["收款单位"] == "某公司"
    assert r["raw"]["_row_no"] == 2
    # 无效列**不出现在**有效字段里
    assert "subject" not in r and "payee" not in r


@acc()
def test_表头认不出就显式报错():
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(("序号", "名称", "金额"))
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(MustReportError) as err:
        parse_workbook(buf.getvalue())
    assert "没认出付款计划的表头" in err.value.message


@acc()
def test_两列单据号都填时取材料列并提示():
    parsed = parse_workbook(_xlsx([_row(material="D1", mech="D2")]))
    assert parsed.rows[0]["doc_no"] == "D1"
    assert parsed.rows[0]["raw"]["_mechanical_doc"] == "D2"      # 原样留在 raw 里
    assert any("两列都填了编号" in a for a in parsed.alerts)      # 只提示、不拦截


# ============================================================ 项目列匹配（§4.3.3）


@acc()
def test_项目按展示名或仓库名唯一匹配():
    briefs = [
        ProjectBrief(id=11, disp="甲仓库", warehouse_name="甲仓库"),
        ProjectBrief(id=12, disp="乙小微", warehouse_name="乙仓库"),
    ]
    rows = attach_projects(
        [{"project_input": "甲仓库"}, {"project_input": "乙仓库"}, {"project_input": "查无此项"}],
        briefs,
    )
    assert [r["match_status"] for r in rows] == [MATCH_MATCHED, MATCH_MATCHED, MATCH_UNMATCHED]
    assert rows[0]["project_id"] == 11 and rows[1]["project_id"] == 12


@acc()
def test_项目重名标重名N条且不猜():
    briefs = [
        ProjectBrief(id=11, disp="重名", warehouse_name="仓库A"),
        ProjectBrief(id=12, disp="重名", warehouse_name="仓库B"),
    ]
    rows = attach_projects([{"project_input": "重名"}], briefs)
    assert rows[0]["match_status"] == MATCH_AMBIGUOUS
    assert rows[0]["match_candidates"] == 2
    assert rows[0]["project_id"] is None                        # **不猜**


# ============================================================ 幂等重写（§9.5）


def _merge(existing, rows, *, ym="2026-09"):
    s = FakeWriteSession({PlanRow: list(existing), Project: []})
    result = repo.merge_month(s, year_month=ym, rows=attach_projects(rows, []))
    return s, result


@acc()
def test_重复导入不产生重复行():
    s, r1 = _merge([], [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                         "planned_amount": Decimal("800.00"), "pay_date": "", "pay_method": "现汇",
                         "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                         "match_candidates": 1}])
    assert r1["created"] == 1 and r1["updated"] == 0
    again = list(s.by_model[PlanRow])
    s2, r2 = _merge(again, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                             "planned_amount": Decimal("900.00"), "pay_date": "", "pay_method": "现汇",
                             "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                             "match_candidates": 1}])
    assert r2["created"] == 0 and r2["updated"] == 1            # **复用同一行**
    assert len(s2.by_model[PlanRow]) == 1                        # 不产生重复行


@acc()
def test_减行不留残影():
    existing = [_plan_row(1, doc_no="D1"), _plan_row(2, doc_no="D2")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                              "planned_amount": Decimal("800.00"), "pay_date": "", "pay_method": "现汇",
                              "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                              "match_candidates": 1}])
    assert r["deleted"] == 1                                     # D2 那行被清掉
    assert [x.id for x in s.deleted] == [2]
    assert len(s.by_model[PlanRow]) == 1


@acc()
def test_可手改列不被导入覆盖():
    """§4.3.3：付款时间 / 付款方式 / 备注 落库、**不被导入覆盖**、不留痕。"""
    existing = [_plan_row(1, pay_method="承兑", pay_date="2026-09-01", remark="改过")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                              "planned_amount": Decimal("800.00"), "pay_date": "2026-09-20",
                              "pay_method": "现汇", "remark": "导入值", "raw": {},
                              "project_id": None, "match_status": "matched", "match_candidates": 1}])
    row = s.by_model[PlanRow][0]
    assert (row.pay_method, row.pay_date, row.remark) == ("承兑", "2026-09-01", "改过")
    assert row.planned_amount == Decimal("800.00")               # 其余字段照常更新


@acc("ACC-PLAN-MANUAL-001", "001-04")
def test_手动行不被触碰():
    """§9.5：导入**只清理并重写自动行**，手动行原样保留。"""
    existing = [_plan_row(1, doc_no="M1", is_manual=True), _plan_row(2, doc_no="D1")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D9", "flow_amount": Decimal("1.00"),
                              "planned_amount": Decimal("1.00"), "pay_date": "", "pay_method": "现汇",
                              "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                              "match_candidates": 1}])
    assert r["manual_kept"] == 1
    assert [x.doc_no for x in s.deleted] == ["D1"]                # 只删了自动行
    assert all(not x.is_manual for x in s.deleted)                # 手动行**没被删**
    assert any(getattr(x, "doc_no", "") == "M1" and x.is_manual for x in s.by_model[PlanRow])
    assert r["deleted"] == 1                                     # 只清了自动行 D1


@acc()
def test_同月同单据号照收不拦():
    """§4.3.4：同月同单据号两行 = **审查里的「重复上报」** ⇒ 导入照收、审查暴露、用户逐行删。"""
    row = {"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1.00"),
           "planned_amount": Decimal("1.00"), "pay_date": "", "pay_method": "现汇",
           "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
           "match_candidates": 1}
    s, r = _merge([], [dict(row), dict(row)])
    assert r["created"] == 2 and r["deleted"] == 0               # **不拦、不去重**


@acc()
def test_未选月份直接报错():
    with pytest.raises(MustReportError) as err:
        repo.merge_month(FakeWriteSession({PlanRow: []}), year_month="", rows=[])
    assert "必须先选「年月」" in err.value.message


# ============================================================ 路由 / 页面


def _client(rows=(), projects=()):
    app = create_app()
    fake = FakeWriteSession({PlanRow: list(rows), Project: list(projects)})
    app.dependency_overrides[get_db] = lambda: fake
    return TestClient(app), fake


@acc()
def test_导入页给出先选月份与口径说明():
    client, _ = _client()
    html = client.get("/m04/import").text
    assert 'name="year_month"' in html and 'type="month"' in html
    assert 'type="file"' in html
    assert "导入前先选「年月」" in html
    assert "原样入库、不参与审查、不要求修正" in html
    assert "重复上报" in html                                     # 明确"这不是导入要拦的错"


@acc()
def test_路由_导入成功回报四个数():
    client, fake = _client()
    resp = client.post(
        "/m04/import",
        data={"year_month": "2026-09"},
        files={"file": ("plan.xlsx", _xlsx([_row()]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    loc = resp.headers["location"]
    assert loc.startswith("/m04?")
    assert fake.added and isinstance(fake.added[0], PlanRow)
    assert fake.added[0].year_month == "2026-09"
    assert fake.added[0].raw["科目"] == "辅材费"                   # 无效列原样入库


@acc()
def test_路由_月份缺失回报错误():
    client, _ = _client()
    resp = client.post(
        "/m04/import",
        data={"year_month": ""},
        files={"file": ("plan.xlsx", _xlsx([_row()]), "application/octet-stream")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/m04/import?" in resp.headers["location"] and "err" in resp.headers["location"]
