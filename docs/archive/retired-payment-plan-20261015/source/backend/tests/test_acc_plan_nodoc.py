"""`ACC-PLAN-NODOC-001`（无单据号行的处置）5 个判据点的验收断言。"""

from __future__ import annotations

from app.core.money import to_money
from app.mod04_plan.domain import (
    COLUMN_ORDER,
    R_DOC_NOT_FOUND,
    R_MATCHED,
    R_NO_DOC,
    NoticeAmounts,
    audit_rows,
    can_edit_doc,
    column_order_ok,
    derived_columns,
    re_audit,
)
from tests.acc_plugin import acc


def _notices() -> dict[str, NoticeAmounts]:
    return {"DOC-1": NoticeAmounts("DOC-1", to_money("1000.00"), to_money("200.00"))}  # 未付 800


def row(**kw) -> dict:
    base = {"year_month": "2026-08", "doc_no": "", "flow_amount": "0", "planned_amount": "0"}
    base.update(kw)
    return base


@acc("ACC-PLAN-NODOC-001", "001-01")
def test_空单据号不参与判重():
    rows = [
        row(doc_no="", flow_amount="1", planned_amount="1"),
        row(doc_no="", flow_amount="2", planned_amount="2"),
        row(doc_no="   ", flow_amount="3", planned_amount="3"),
    ]
    got = audit_rows(rows, _notices())
    assert got == [R_NO_DOC, R_NO_DOC, R_NO_DOC]     # 判「无单据号」，**不判「重复」**


@acc("ACC-PLAN-NODOC-001", "001-02")
def test_单据号只对未匹配行开放编辑():
    assert can_edit_doc(R_MATCHED) is False                 # 「完全匹配」行只读
    for r in (R_NO_DOC, R_DOC_NOT_FOUND, "金额不符", "超过未付", "重复上报"):
        assert can_edit_doc(r) is True


@acc("ACC-PLAN-NODOC-001", "001-03")
def test_改单据号后再次匹配触发重判():
    n = _notices()
    r = row(doc_no="WRONG", flow_amount="1000", planned_amount="800")
    assert re_audit(r, n) == R_DOC_NOT_FOUND
    r["doc_no"] = "DOC-1"                     # 改成正确号 ⇒ 点「再次匹配」
    assert re_audit(r, n) == R_MATCHED         # 由「未匹配」转为「完全匹配」


@acc("ACC-PLAN-NODOC-001", "001-04")
def test_单据号命不中则派生两列留空():
    assert derived_columns(None) == ("", "")   # 不猜、不留假数据


@acc("ACC-PLAN-NODOC-001", "001-05")
def test_命中后派生两列取值与列序():
    n = _notices()["DOC-1"]
    paid, unpaid = derived_columns(n)
    assert (paid, unpaid) == ("200.00", "800.00")          # 已付（流水汇总）/ 未付（审批 − 已付）
    assert to_money(paid) == n.paid and to_money(unpaid) == n.unpaid
    # 列序：派生两列夹在「i8 流程金额」与「本月预付款金额」之间
    assert column_order_ok() is True
    i_flow, i_planned = COLUMN_ORDER.index("flow_amount"), COLUMN_ORDER.index("planned_amount")
    assert COLUMN_ORDER[i_flow + 1:i_planned] == ("paid_amount", "unpaid_amount")
