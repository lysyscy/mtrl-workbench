"""`MOD-03` **「按本月计划勾选」**（能力 6 · §4.3.5）的验收断言 —— `ACC-PAY-PICK-001`（离线 · 不连库）。

判据点守的是这条链路本身：**预勾选**是否落对行 · **跨月单据**是否也能勾上 ·
**项目筛选不动**且被挡的行要报数 · **可点窗口 = 每月 10 号 → 月底**（窗口外**先禁用**，不是点了才拦）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_page import build_page_data, render_notice_page
from app.mod03_notice.notice_router import get_session
from app.mod04_plan.models import PlanRow
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession
from tests.m03_action_helpers import FakeWriteSession, _notice, _row_of


def _render(notices, *, plan_docs, plan_ym="2026-09", **fkwargs):
    from app.mod03_notice.list_view import NoticeFilters

    session = FakeSession({PaymentNotice: list(notices), Project: [], PaymentFlow: []})
    f = NoticeFilters(**fkwargs) if fkwargs else None
    data = build_page_data(
        session, filters=f, sort_col="", sort_dir=0, plan_ym=plan_ym, plan_docs=plan_docs,
        flows_of=lambda nid: [],
    )
    return render_notice_page(data)


@acc("ACC-PAY-PICK-001", "001-01")
def test_计划命中的行被预勾选():
    html = _render([_notice(1, bill_no="D1"), _notice(2, bill_no="D2")], plan_docs=["D1"])
    assert 'value="1" checked' in _row_of(html, "D1")   # 命中的勾上
    assert 'value="2" checked' not in html              # 没命中的不勾
    assert "已按 2026-09 的付款计划勾选 1 条" in html


@acc("ACC-PAY-PICK-001", "001-02")
def test_跨月单据也能勾上():
    """视图放宽到「全部月份」⇒ 计划行指向的通知书**落在别的月份也能勾上**（§4.3.5）。"""
    notices = [_notice(1, bill_no="D1", doc_date="2026-09-05"),
               _notice(2, bill_no="D9", doc_date="2026-08-20")]     # 上月单据
    html = _render(notices, plan_docs=["D1", "D9"], period="")      # 放宽后 = 全部月份
    assert html.count(" checked") == 2
    assert "跨月" in html or "全部月份" in html


@acc("ACC-PAY-PICK-001", "001-03")
def test_项目筛选不动且被挡的行要报数():
    """「项目」筛选**一律不动**（它是用户表达的业务范围）；被挡掉的行跳过并**报数**（§4.3.5）。"""
    notices = [_notice(1, bill_no="D1", ownership_id=11), _notice(2, bill_no="D9", ownership_id=22)]
    html = _render(notices, plan_docs=["D1", "D9"], period="", project_ids=("11",))
    assert 'value="1" checked' in html
    assert ">D9<" not in html                           # 被项目挡掉的行不出现（项目筛选**不动**）
    assert "另有 1 条被当前项目筛选挡掉" in html          # 但要**报数**


@acc("ACC-PAY-PICK-001", "001-04")
def test_空单据号不参与勾选():
    """§4.3.3：单据号**允许为空** ⇒ 空号认不出对应哪张通知书，不参与勾选。"""
    html = _render([_notice(1, bill_no="")], plan_docs=[""])
    assert "勾选 0 条" in html


@acc("ACC-PAY-PICK-001", "001-05")
def test_窗口外先禁用且点不了():
    from app.mod03_notice.notice_pay import PAY_URL  # noqa: F401  （仅确保模块已装配）

    client, fake = _client([_notice(1)])
    r = client.post("/m03/notices/pick-plan", data={}, follow_redirects=False)
    assert r.status_code == 303
    assert "err" not in r.headers["location"]           # 今天在窗口内（10 号 → 月底）
    loc = r.headers["location"]
    assert "plan=2026-09" in loc                        # 月份不可自选 = 北京时间当月
    assert "pay_status=unpaid" in loc                   # 放宽到「未付清」
    assert "period=&" in loc or loc.endswith("period=")  # 放宽到「全部月份」


def _client(notices, plans=()):
    app = create_app()
    fake = FakeWriteSession(
        {PaymentNotice: list(notices), Project: [], PaymentFlow: [], PlanRow: list(plans)}
    )
    app.dependency_overrides[get_session] = lambda: fake
    return TestClient(app), fake


@acc("ACC-PAY-PICK-001", "001-06")
def test_路由_窗口外回报错误(monkeypatch):
    """可点窗口 = 每月 10 号 → 月底（§4.3.2）；窗口外**不执行**并说明原因。"""
    import app.mod04_plan.domain as pd

    monkeypatch.setattr(pd, "in_effective_window", lambda day: False)
    client, _ = _client([_notice(1)])
    r = client.post("/m03/notices/pick-plan", data={}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert "窗口" in r.headers["location"] or "10" in r.headers["location"]


@acc("ACC-PAY-PICK-001", "001-07")
def test_路由_计划单据号来自所选月份():
    plans = [
        PlanRow(id=1, year_month="2026-09", doc_no="D1", flow_amount=Decimal("1"),
                planned_amount=Decimal("1"), pay_method="承兑", raw={}),
        PlanRow(id=2, year_month="2026-08", doc_no="D9", flow_amount=Decimal("1"),
                planned_amount=Decimal("1"), pay_method="现汇", raw={}),
    ]
    client, _ = _client([_notice(1, bill_no="D1"), _notice(2, bill_no="D9")], plans)
    html = client.get("/m03/notices", params={"period": "", "plan": "2026-09"}).text
    assert 'value="1" checked' in html        # 9 月计划里的 D1 ⇒ 勾上
    assert 'value="2" checked' not in html    # 8 月计划里的 D9 ⇒ 本次不勾（月份不可自选）
