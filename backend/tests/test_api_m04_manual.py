"""`MOD-04` **手动行**的**写端点**自检（离线 · 不连库）—— `ACC-PLAN-MANUAL-001` 的 API 半边。

⭐ 为什么有它（2026-09-18 · `TAIL-27` · `§19` **批 2**）：手动行的"能增能改 / 校验不过要拒"原先由
   **旧服务端页**的 PRG 端点（`POST /m04/row/save`）观测 ⇒ 旧页整体删除（授权 `D18`）后那些判据点
   **不能跟着死** ⇒ 按 `§19` 铁律改成打**新壳真正在用**的 JSON 端点（`POST /api/m04/plans`）。
   **claim 一字未改**：① 编辑只对**手动行**开放（`001-05`）；② 校验失败 ⇒ **拒 ＋ 原样报出原因**
   （`001-07`）；③ 新增 ⇒ 落库且标 `is_manual`。

⚠️ 与 `test_plan_manual.py` 的**分工**（⛔ 别重复）：
   · 那边守**判定纯函数**（`manual_row_payload` / `assert_manual_editable`）与**审查链路**（手动行同样参与
     6 种判定 / 两档筛选 / KPI / 合计）；
   · 本文件只守**写端点**这一层（拒的形态与原因、落库标记）。
⚠️ 注入：端点走 `session_scope()`（**不是** FastAPI 依赖）⇒ monkeypatch **模块里的那个名字**
   （同 `tests/test_api_m04_force.py`）。
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod04_plan.models import PlanRow
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m03_action_helpers import FakeWriteSession
from tests.m04_helpers import make_plan_row

import app.mod04_plan.plan_api_router as m04_api


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


def _client(monkeypatch, plan_rows=(), projects=()):
    """离线 client：把 `plan_api_router.session_scope` 换成**假上下文**（yield 假写会话）。"""
    fake = FakeWriteSession({PlanRow: list(plan_rows), Project: list(projects),
                             PaymentFlow: []})

    @contextmanager
    def _scope():
        yield fake

    monkeypatch.setattr(m04_api, "session_scope", _scope)
    return TestClient(create_app(), raise_server_exceptions=False), fake


def _text(r) -> str:  # noqa: ANN001
    """响应正文（⚠️ 兜住"JSON 把中文转义成 \\uXXXX"这种情况，否则断言会假红）。"""
    body = r.text
    return body.encode("latin-1", "backslashreplace").decode("unicode_escape") if "\\u" in body else body


# ------------------------------------------------------------------ 001-05 编辑只对手动行开放


@acc("ACC-PLAN-MANUAL-001", "001-05")
def test_编辑导入行被拒_打API(monkeypatch):
    """★ 口径：**只有手动行可编辑** —— 导入行要改就**去改 Excel 再导入**（§4.3.3.1）。"""
    client, _ = _client(monkeypatch, plan_rows=[make_plan_row(1, doc_no="D1", project_id=11)])
    r = client.post("/api/m04/plans", json={
        "row_id": "1", "row_ym": "2026-09", "flow_amount": "1", "planned_amount": "1",
    })
    assert r.status_code >= 400, f"编辑导入行要**显式拒**（实际 {r.status_code}）"
    body = _text(r)
    assert "重新导入" in body or "手动" in body, f"要说清「为什么不能改」：{body[:180]}"


@acc("ACC-PLAN-MANUAL-001", "001-05")
def test_编辑手动行成功_打API(monkeypatch):
    """反向看住：**手动行**改得动（⛔ 别把"只有手动行可编辑"做成"谁都改不动"）。"""
    client, fake = _client(monkeypatch, plan_rows=[_manual(id=90)])
    r = client.post("/api/m04/plans", json={
        "row_id": "90", "row_ym": "2026-09", "flow_amount": "1200", "planned_amount": "500",
    })
    assert r.status_code == 200, f"手动行应改得动：{_text(r)[:180]}"
    assert fake.by_model[PlanRow][0].planned_amount == Decimal("500.00")


# ------------------------------------------------------------------ 001-07 校验失败：拒 ＋ 不落库


@acc("ACC-PLAN-MANUAL-001", "001-07")
def test_校验失败被拒且不落库_打API(monkeypatch):
    """★ 口径：校验不过 ⇒ **拒 ＋ 原样报出原因**（壳侧据此**保留用户已填内容**、⛔ 不清空草稿）。

    ⚠️ 「保留草稿」是**壳侧**行为 —— 本文件守端点半边（拒的形态与原因）；
       壳那半边由 `tests/test_wired_m04.py` 的静态断言守（`§19`：形态变了搬断言，两边都要）。
    """
    client, fake = _client(monkeypatch)
    r = client.post("/api/m04/plans", json={"row_ym": "2026", "flow_amount": "1"})
    assert r.status_code >= 400, "归月形态不合法 ⇒ 要显式拒"
    body = _text(r)
    assert "归月" in body, f"要把原因原样报出来（⛔ 不吞成「保存失败」）：{body[:180]}"
    assert fake.added == [], "被拒 ⇒ 一行都不许落库"


# ------------------------------------------------------------------ 新增（落库标记）


@acc()
def test_新增手动行落库并标is_manual_打API(monkeypatch):
    client, fake = _client(monkeypatch, projects=[Project(id=11, project_type="normal", name_full="甲全名",
                                                          warehouse_name="甲仓库", disp="甲仓库")])
    r = client.post("/api/m04/plans", json={
        "row_ym": "2026-09", "project_id": "11", "doc_no": "D1",
        "flow_amount": "1000", "planned_amount": "800", "pay_method": "承兑",
    })
    assert r.status_code == 200, f"应成功：{_text(r)[:180]}"
    added = [x for x in fake.added if isinstance(x, PlanRow)]
    assert len(added) == 1 and added[0].is_manual is True
    assert added[0].project_input == "甲仓库", "项目 id → 填报值（展示名）"
    # ⚠️ 只断言"回执里**带**行号字段" —— **离线桩不派 id**（`row.id` 由真库在 flush 时给）
    #    ⇒ 这里断言 `is not None` 是**桩的能力问题**，不是产品缺陷（真 id 由真库 e2e `_e2e_m04_wired.py` 覆盖）。
    assert r.json().get("ok") is True and "row_id" in r.json()
