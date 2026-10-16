"""`ACC-PLAN-AUDIT-001`（付款计划审查引擎）5 个纯规则判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod04_plan.domain import (
    ALL_RESULTS,
    BUCKET_MATCHED,
    BUCKET_UNMATCHED,
    FILTER_BUCKETS,
    R_AMOUNT_MISMATCH,
    R_DOC_NOT_FOUND,
    R_DUPLICATE,
    R_MATCHED,
    R_NO_DOC,
    R_OVER_UNPAID,
    NoticeAmounts,
    audit_rows,
    bucket,
)
from app.mod04_plan.models import EDITABLE_COLUMNS, PlanRow
from tests.acc_plugin import acc


def _notices() -> dict[str, NoticeAmounts]:
    return {
        "DOC-1": NoticeAmounts("DOC-1", to_money("1000.00"), to_money("200.00")),  # 未付 800
        "DOC-2": NoticeAmounts("DOC-2", to_money("500.00"), to_money("500.00")),    # 未付 0
    }


def row(**kw) -> dict:
    base = {"year_month": "2026-08", "doc_no": "", "flow_amount": "0", "planned_amount": "0"}
    base.update(kw)
    return base


@acc("ACC-PLAN-AUDIT-001", "001-01")
def test_审查结果不存字段按行实时派生():
    # 表里**没有** audit_result 列
    assert "audit_result" not in PlanRow.__table__.columns
    # 同一行，通知书数据一变 ⇒ 判定随之变（说明是现算）
    r = row(doc_no="DOC-1", flow_amount="1000", planned_amount="100")
    assert audit_rows([r], _notices())[0] == R_MATCHED
    changed = {"DOC-1": NoticeAmounts("DOC-1", to_money("999.00"), to_money("200.00"))}
    assert audit_rows([r], changed)[0] == R_AMOUNT_MISMATCH


@acc("ACC-PLAN-AUDIT-001", "001-02")
def test_判定分支齐备六种都有样本():
    rows = [
        row(year_month="2026-07", doc_no="DOC-1", flow_amount="1000", planned_amount="800"),  # 完全匹配
        row(year_month="2026-08", doc_no="DOC-1", flow_amount="999", planned_amount="100"),   # 金额不符
        row(year_month="2026-09", doc_no="DOC-1", flow_amount="1000", planned_amount="900"),  # 超过未付
        row(year_month="2026-08", doc_no="NOPE", flow_amount="1", planned_amount="1"),        # 单据号查不到
        row(year_month="2026-08", doc_no="", flow_amount="1", planned_amount="1"),            # 无单据号
        row(year_month="2026-08", doc_no="DOC-2", flow_amount="500", planned_amount="0"),     # 重复上报
        row(year_month="2026-08", doc_no="DOC-2", flow_amount="500", planned_amount="0"),     # 重复上报（同月同号）
    ]
    got = audit_rows(rows, _notices())
    assert set(got) == set(ALL_RESULTS) and len(set(got)) == 6


@acc("ACC-PLAN-AUDIT-001", "001-03")
def test_完全匹配三条件同时成立():
    n = _notices()
    # 三条件齐 ⇒ 完全匹配（planned == 未付 也算「不超未付」）
    assert audit_rows([row(doc_no="DOC-1", flow_amount="1000", planned_amount="800")], n)[0] == R_MATCHED
    # 号对 + 金额对，但**超未付** ⇒ 超过未付
    assert audit_rows([row(doc_no="DOC-1", flow_amount="1000", planned_amount="801")], n)[0] == R_OVER_UNPAID
    # 号对 + 不超未付，但**金额不符** ⇒ 金额不符
    assert audit_rows([row(doc_no="DOC-1", flow_amount="999", planned_amount="1")], n)[0] == R_AMOUNT_MISMATCH
    # 号对不上 ⇒ 查不到
    assert audit_rows([row(doc_no="X", flow_amount="1000", planned_amount="1")], n)[0] == R_DOC_NOT_FOUND


@acc("ACC-PLAN-AUDIT-001", "001-04")
def test_金额不符比的是流程金额与审批金额():
    n = _notices()
    # 该流程金额 999 ≠ 审批金额 1000 ⇒ 金额不符（与 planned 无关：planned=1 不超未付）
    assert audit_rows([row(doc_no="DOC-1", flow_amount="999", planned_amount="1")], n)[0] == R_AMOUNT_MISMATCH
    # 该流程金额 = 审批金额 ⇒ 不判金额不符
    assert audit_rows([row(doc_no="DOC-1", flow_amount="1000", planned_amount="1")], n)[0] == R_MATCHED


@acc("ACC-PLAN-AUDIT-001", "001-05")
def test_同月同单据号两行都判重():
    n = _notices()
    rows = [
        row(year_month="2026-08", doc_no="DOC-2", flow_amount="500", planned_amount="0"),
        row(year_month="2026-08", doc_no="DOC-2", flow_amount="500", planned_amount="0"),
    ]
    got = audit_rows(rows, n)
    assert got == [R_DUPLICATE, R_DUPLICATE]     # **双向**：两行都判重
    # 跨月不算
    cross = [
        row(year_month="2026-08", doc_no="DOC-2", flow_amount="500", planned_amount="0"),
        row(year_month="2026-09", doc_no="DOC-2", flow_amount="500", planned_amount="0"),
    ]
    assert R_DUPLICATE not in audit_rows(cross, n)
