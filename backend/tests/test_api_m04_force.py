"""`MOD-04` **强制通过 / 取消强制**的**写端点**自检（离线 · 不连库）—— `ACC-PLAN-AUDIT-001`-09。

⭐ 为什么在这儿（2026-09-18 · `TAIL-27` · `§19` **批 2**）：这三条判据点原先钉在**旧服务端页**的 PRG 表单
   （`POST /m04/force`）上。旧渲染层整体删除（授权 `D18`）⇒ **判据不能跟着删** ——
   `§19` 铁律：形态变了要**搬断言**（先例 `TAIL-43`「导出已落地为真下载」），⛔ 不删判据。
   故改指**新壳真正在用**的 JSON 端点：`POST /api/m04/plans/{row_id}/force` 与 `…/force-cancel`。
   **claim 一字未改**：① 放行 ⇒ 落库 ＋ 留痕；② 空备注 ⇒ 拒且**一行都不改**；③ 取消 ⇒ 回原判定且备注清空。

⚠️ 注入手法（本轮查证所得）：这两个端点用 `session_scope()`（`router.py:200,212`），**不是** FastAPI 依赖
   ⇒ `dependency_overrides[get_db]` 那一套对它们**无效**，只能 monkeypatch **router 模块里的那个名字**。
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

import app.mod04_plan.router as m04_router


def _row(**kw) -> PlanRow:
    """一条**未匹配**计划行（`forced_through` 初始为假）—— 与旧页测试同一份造数（claim 不变）。"""
    vals = dict(
        id=2, year_month="2026-09", project_input="乙仓库", project_id=None,
        match_status="unmatched", match_candidates=0, doc_no="D9",
        flow_amount=Decimal("1000.00"), planned_amount=Decimal("800.00"),
        pay_date="", pay_method="", remark="", forced_through=False, forced_remark="",
        is_manual=False, raw={},
    )
    vals.update(kw)
    return PlanRow(**vals)


def _client(monkeypatch, plan_rows=()):
    """离线 client：把 `router.session_scope` 换成**假上下文管理器**（yield 一个假写会话）。

    ⚠️ 假会话复用 `tests/m03_action_helpers.FakeWriteSession`（已带 `add/flush/commit`）——
       `repo.get_row` 走 `s.get(PlanRow, id)`、`repo.set_force` 只改两列 ⇒ 够用，⛔ 不必另造一个。
    """
    app = create_app()
    fake = FakeWriteSession({PlanRow: list(plan_rows), Project: [], PaymentFlow: []})

    @contextmanager
    def _scope():
        yield fake

    monkeypatch.setattr(m04_router, "session_scope", _scope)
    return TestClient(app, raise_server_exceptions=False), fake


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_强制通过_落库并留痕(monkeypatch):
    """⭐ 请求级：**真打一次 API** ⇒ 两列都落库（`forced_through` ＋ `forced_remark`）。"""
    row = _row()
    client, _ = _client(monkeypatch, [row])
    r = client.post("/api/m04/plans/2/force", params={"remark": "已向项目核实，金额无误"})
    assert r.status_code == 200, f"应成功，实际 {r.status_code}：{r.text[:150]}"
    assert row.forced_through is True
    assert row.forced_remark == "已向项目核实，金额无误"
    assert r.json().get("forced_remark") == "已向项目核实，金额无误", "回执要把留痕内容带回来"


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_强制通过_空备注被拒且不落库(monkeypatch):
    """★ 口径：系统**只提示不拦截**，但**放行必须写备注** ⇒ 空备注 ⇒ 显式拒 ＋ **一行都不改**。"""
    row = _row()
    client, _ = _client(monkeypatch, [row])
    r = client.post("/api/m04/plans/2/force", params={"remark": "   "})
    assert r.status_code >= 400, f"空备注要**显式拒**（实际 {r.status_code}）—— 不许静默放行"
    assert "备注" in r.text, f"拒绝理由要说清「为什么」（{r.text[:160]}）"
    assert row.forced_through is False and row.forced_remark == "", "被拒 ⇒ 一行都不许改"


@acc("ACC-PLAN-AUDIT-001", "001-09")
def test_取消强制通过_回到原判定且备注清空(monkeypatch):
    """★ 口径：**取消不留痕** —— 备注清空、判定回到原值，且**不产生任何残余**。"""
    row = _row(forced_through=True, forced_remark="上次的理由")
    client, _ = _client(monkeypatch, [row])
    r = client.post("/api/m04/plans/2/force-cancel")
    assert r.status_code == 200, f"应成功，实际 {r.status_code}：{r.text[:150]}"
    assert row.forced_through is False and row.forced_remark == ""
