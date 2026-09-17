"""`MOD-03` **批量付款窗口**（能力 8 · §4.4.4）的验收断言（离线 · 不连库）。

判据点归属（2026-09-16 起）：
- `ACC-PAY-VERIFY-001` —— **能不能付款**的判定本身（§4.4.1 唯一核验项）由 `domain` 纯函数钉住；
- `ACC-PAY-BATCH-001`  —— **窗口这一层**（§4.4.4）：四类不可付的排除与**显式告知** ·
  两出口不合并（进统计 ≠ 进付款批次）· 逐行移出且**不丢已填值** · 兜底整批重算不落半批 ·
  付款方式默认取计划兜底现汇 · `request_id` 防连点。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_pay import build_pay_window, render_pay_page
from app.mod03_notice.notice_router import get_session
from app.mod05_flow.models import PaymentFlow
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession
from tests.m03_action_helpers import FakeWriteSession, _notice


def _window(notices, ids, *, plan_methods=None, overrides=None):
    session = FakeSession({PaymentNotice: list(notices), Project: [], PaymentFlow: []})
    return build_pay_window(
        session, ids, flows_of=lambda nid: [],
        plan_methods=plan_methods if plan_methods is not None else {},
        overrides=overrides or {},
    )


def _client(notices, flows=()):
    app = create_app()
    fake = FakeWriteSession(
        {PaymentNotice: list(notices), Project: [], PaymentFlow: list(flows)}
    )
    app.dependency_overrides[get_session] = lambda: fake
    return TestClient(app), fake


# ============================================================ 前置状态（R14① / §4.4.4）


@acc("ACC-PAY-BATCH-001", "001-01")
def test_存在不可付行则确认付款禁用并给原因与解决路径():
    data = _window([_notice(1, approve_status="未批")], [1])
    check = data["check"]
    assert check.enabled is False
    assert "1 条不可付" in check.reason and "不得进入本次付款" in check.reason
    assert "移出本次付款" in check.how_to_fix                # 解决路径必须给到
    html = render_pay_page(data)
    assert "确认付款（禁用）" in html
    assert "不可付" in html


@acc("ACC-PAY-BATCH-001", "001-02")
def test_本次应付为0也不可付():
    data = _window([_notice(1, amount_approved=Decimal("100.00"))], [1])
    # 已付金额来自流水；此处无流水 ⇒ 本次应付 = 100 ⇒ 可付
    assert data["check"].enabled is True
    data2 = _window([_notice(1, amount_approved=Decimal("0.00"))], [1])
    assert data2["check"].enabled is False
    assert "本次应付为 0" in data2["check"].reason


@acc("ACC-PAY-BATCH-001", "001-03")
def test_付款方式默认取付款计划_取不到兜底现汇():
    data = _window([_notice(1, bill_no="D1"), _notice(2, bill_no="D2")], [1, 2],
                   plan_methods={"D1": "承兑"})
    by_id = {i["notice_id"]: i for i in data["items"]}
    assert by_id[1]["pay_method"] == "承兑"                  # 取到计划值（§4.4.2）
    assert by_id[2]["pay_method"] == "现汇"                  # 取不到 ⇒ 兜底「现汇」


@acc("ACC-PAY-BATCH-001", "001-04")
def test_撤单行与剔除行不得进入付款():
    data = _window([_notice(1), _notice(2, i8_revoked=True), _notice(3, excluded=True)], [1, 2, 3])
    assert [i["notice_id"] for i in data["items"]] == [1]
    reasons = dict((nid, why) for nid, why in data["skipped"])
    assert "i8 已撤单" in reasons[2]                          # §4.2.7：勾选→付款链一律排除撤单行
    assert "剔除" in reasons[3]


# ============================================================ 移出 / 已填值不丢（R14③）


@acc("ACC-PAY-BATCH-001", "001-05")
def test_移出本次付款只去掉该行():
    data = _window([_notice(1), _notice(2)], [1, 2], overrides={"m_2": "供应链"})
    ids = [i["notice_id"] for i in data["items"]]
    assert ids == [1, 2]
    by_id = {i["notice_id"]: i for i in data["items"]}
    assert by_id[2]["pay_method"] == "供应链"                 # 已填值被带回（overrides）


@acc("ACC-PAY-BATCH-001", "001-06")
def test_路由_移出后其它行已填值仍在():
    client, _ = _client([_notice(1), _notice(2)])
    r = client.post("/m03/pay", data={"ids": ["1", "2"], "m_2": "供应链", "move": "1"},
                    follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers["location"]
    assert "ids=2" in loc and "ids=1" not in loc
    assert "m_2=%E4%BE%9B%E5%BA%94%E9%93%BE" in loc           # 供应链（URL 编码）—— 已填值不丢


# ============================================================ 提交：整批重算 / 不落半批


@acc("ACC-PAY-BATCH-001", "001-07")
def test_提交成功落流水且一条付款一条流水():
    client, fake = _client([_notice(1, bill_no="D1")])
    r = client.post("/m03/pay", data={
        "ids": ["1"], "m_1": "承兑", "a_1": "300", "pay_date": "2026-09-10",
        "confirm": "1", "request_id": "R-1",
    }, follow_redirects=False)
    assert r.status_code == 303
    flows = [f for f in fake.added if isinstance(f, PaymentFlow)]
    assert len(flows) == 1
    assert flows[0].amount == Decimal("300.00")
    assert flows[0].pay_method == "承兑" and flows[0].notice_id == 1
    assert flows[0].request_id == "R-1"
    assert "/m03/notices?" in r.headers["location"]            # 成功 ⇒ 回列表页


@acc("ACC-PAY-BATCH-001", "001-08")
def test_提交时库中已变不可付则整批不落():
    # 窗口打开时是「已批」，提交时库里已变「未批」⇒ 整批重算必须拦下、**不产生任何流水**
    client, fake = _client([_notice(1, approve_status="未批")])
    r = client.post("/m03/pay", data={"ids": ["1"], "a_1": "100", "confirm": "1",
                                      "request_id": "R-2"}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert [f for f in fake.added if isinstance(f, PaymentFlow)] == []


@acc("ACC-PAY-BATCH-001", "001-09")
def test_付款金额超过本次应付被拦():
    client, fake = _client([_notice(1, amount_approved=Decimal("100.00"))])
    r = client.post("/m03/pay", data={"ids": ["1"], "a_1": "500", "confirm": "1",
                                      "request_id": "R-3"}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert [f for f in fake.added if isinstance(f, PaymentFlow)] == []


@acc("ACC-PAY-BATCH-001", "001-10")
def test_付款方式选其他必须填备注():
    client, fake = _client([_notice(1)])
    r = client.post("/m03/pay", data={"ids": ["1"], "m_1": "其他", "a_1": "10",
                                      "confirm": "1", "request_id": "R-4"}, follow_redirects=False)
    assert r.status_code == 303 and "err" in r.headers["location"]
    assert [f for f in fake.added if isinstance(f, PaymentFlow)] == []


@acc("ACC-PAY-BATCH-001", "001-11")
def test_重复提交被拒():
    client, fake = _client([_notice(1)])
    r1 = client.post("/m03/pay", data={"ids": ["1"], "a_1": "10", "confirm": "1",
                                       "request_id": "R-5"}, follow_redirects=False)
    assert r1.status_code == 303 and "err" not in r1.headers["location"]
    r2 = client.post("/m03/pay", data={"ids": ["1"], "a_1": "10", "confirm": "1",
                                       "request_id": "R-5"}, follow_redirects=False)
    assert r2.status_code == 303 and "err" in r2.headers["location"]
    assert len([f for f in fake.added if isinstance(f, PaymentFlow)]) == 1     # 只产生一条


@acc("ACC-PAY-BATCH-001", "001-12")
def test_取消不产生任何流水():
    client, fake = _client([_notice(1)])
    r = client.post("/m03/pay", data={"ids": ["1"], "cancel": "1"}, follow_redirects=False)
    assert r.status_code == 303
    assert [f for f in fake.added if isinstance(f, PaymentFlow)] == []
