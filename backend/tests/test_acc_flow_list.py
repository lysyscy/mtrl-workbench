"""`ACC-FLOW-LIST-001`（付款流水）6 个判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.core.money import to_money
from app.core.period import default_period
from app.mod05_flow.domain import (
    FLOW_PAGINATED,
    default_flow_period,
    effective_total,
    empty_state_colspan,
    filter_flows,
    payment_status,
    revoke_flow,
)
from app.mod05_flow.models import FLOW_EFFECTIVE, FLOW_REVOKED

_COLUMNS = ["流水号", "项目", "单据号", "实付金额", "付款方式", "付款时间", "状态"]


def _flows():
    return [
        {"flow_no": "F1", "project_id": 1, "amount": "100.00", "pay_method": "现汇",
         "pay_date": "2026-08-05", "status": FLOW_EFFECTIVE},
        {"flow_no": "F2", "project_id": 1, "amount": "50.00", "pay_method": "承兑",
         "pay_date": "2026-08-06", "status": FLOW_EFFECTIVE},
        {"flow_no": "F3", "project_id": 2, "amount": "30.00", "pay_method": "现汇",
         "pay_date": "2026-08-07", "status": FLOW_REVOKED},
    ]


def test_流水默认月为当月且不分页():
    assert default_flow_period() == default_period("flow")
    assert FLOW_PAGINATED is False


def test_筛选即时生效四维():
    rows = _flows()
    assert [f["flow_no"] for f in filter_flows(rows, status=FLOW_EFFECTIVE)] == ["F1", "F2"]
    assert [f["flow_no"] for f in filter_flows(rows, pay_method="承兑")] == ["F2"]
    assert [f["flow_no"] for f in filter_flows(rows, project_id=2)] == ["F3"]
    assert [f["flow_no"] for f in filter_flows(rows, keyword="F3")] == ["F3"]


def test_合计只算生效流水():
    rows = _flows()
    assert effective_total(rows) == to_money("150.00")     # 已撤销的 30 不计入
    # 与「已付金额 = 流水汇总」同源：撤销一条 ⇒ 汇总随之减少
    rows[1]["status"] = FLOW_REVOKED
    assert effective_total(rows) == to_money("100.00")


def test_撤销必填原因空原因被拦截():
    with pytest.raises(MustReportError):
        revoke_flow("")
    with pytest.raises(MustReportError):
        revoke_flow("   ")
    r = revoke_flow("重复登记，误操作")
    assert r["status"] == FLOW_REVOKED and r["revoke_reason"] == "重复登记，误操作"


def test_撤销后已付回退且状态回到未付清():
    approved = to_money("1000.00")
    flows = _flows()
    assert payment_status(effective_total(flows), approved) == "unpaid"      # 150 < 1000
    # 付满 ⇒ 已付清
    flows.append({"flow_no": "F4", "amount": "850.00", "status": FLOW_EFFECTIVE})
    assert effective_total(flows) == to_money("1000.00")
    assert payment_status(effective_total(flows), approved) == "paid"
    # 撤销那条 850 ⇒ 已付回退、状态回到未付清
    rev = revoke_flow("退款")
    flows[-1] = {**flows[-1], **rev}
    assert effective_total(flows) == to_money("150.00")
    assert payment_status(effective_total(flows), approved) == "unpaid"


def test_空态提示行跨列数等于表头列数():
    assert empty_state_colspan(_COLUMNS) == len(_COLUMNS)
