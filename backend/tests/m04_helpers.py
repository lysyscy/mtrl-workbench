"""`MOD-04` 页面自检的公共桩（**离线：不连库**）。

`FakeSession` 让 `service.build_page_data` / `repository` 的真实代码跑到，只是数据来自内存
⇒ 页面与组装层**端到端**可验，而不用起 Postgres。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod04_plan.models import MATCH_MATCHED, MATCH_UNMATCHED, PlanRow
from app.mod05_flow.models import FLOW_EFFECTIVE, PaymentFlow


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list:
        return list(self._rows)

    def first(self):
        """真 `Session.execute(...).scalars().first()` 的等价物（桩也要有，否则调用方会炸）。"""
        return self._rows[0] if self._rows else None


class FakeSession:
    """按**模型类型**分发的最小会话桩（只实现 `service` / `repository` 用到的那点 API）。"""

    def __init__(self, by_model: dict) -> None:
        self.by_model = dict(by_model)

    def execute(self, stmt):  # noqa: ANN001
        entity = stmt.column_descriptions[0]["entity"]
        return _Result(self.by_model.get(entity, []))

    def get(self, model, ident):  # noqa: ANN001
        for row in self.by_model.get(model, []):
            if getattr(row, "id", None) == ident:
                return row
        return None


def make_plan_row(
    row_id: int,
    *,
    year_month: str = "2026-09",
    doc_no: str = "",
    project_input: str = "",
    project_id: int | None = None,
    match_status: str = MATCH_UNMATCHED,
    flow_amount: str = "1000.00",
    planned_amount: str = "1000.00",
    pay_date: str = "",
    pay_method: str = "现汇",
    remark: str = "",
) -> PlanRow:
    return PlanRow(
        id=row_id, year_month=year_month, project_input=project_input, project_id=project_id,
        match_status=match_status, match_candidates=1 if project_id else 0,
        doc_no=doc_no, flow_amount=Decimal(flow_amount), planned_amount=Decimal(planned_amount),
        pay_date=pay_date, pay_method=pay_method, remark=remark, raw={},
    )


def make_notice(notice_id: int, bill_no: str, approved: str, *, bill_type: str = "material") -> PaymentNotice:
    return PaymentNotice(
        id=notice_id, ph_id=f"ph-{notice_id}", bill_no=bill_no, bill_type=bill_type,
        amount_approved=Decimal(approved), amount_paid=Decimal("0"),
        fields={},
    )


def make_flow(notice_id: int, amount: str, *, status: str = FLOW_EFFECTIVE) -> PaymentFlow:
    return PaymentFlow(id=notice_id * 10, flow_no=f"F{notice_id}", notice_id=notice_id,
                       amount=Decimal(amount), status=status, pay_method="现汇")


def make_project(pid: int, warehouse: str, disp: str = "", name_full: str = "") -> Project:
    return Project(id=pid, project_type="normal", name_full=name_full or f"全名{pid}",
                   warehouse_name=warehouse, disp=disp)


def dataset() -> dict:
    """一份小样本（1 个完全匹配 + 1 个未匹配 + 1 条已付流水）。"""
    return {
        PlanRow: [
            make_plan_row(1, doc_no="D1", project_input="甲仓库", project_id=11,
                          match_status=MATCH_MATCHED, flow_amount="1000.00", planned_amount="800.00"),
            make_plan_row(2, doc_no="", project_input="不存在的名字", match_status=MATCH_UNMATCHED,
                          flow_amount="500.00", planned_amount="500.00"),
            make_plan_row(3, year_month="2026-08", doc_no="D1", project_input="甲仓库", project_id=11,
                          match_status=MATCH_MATCHED, flow_amount="1000.00", planned_amount="1000.00"),
        ],
        PaymentNotice: [make_notice(101, "D1", "1000.00")],
        PaymentFlow: [make_flow(101, "200.00")],
        Project: [make_project(11, "甲仓库", "甲公司项目")],
    }


__all__ = [
    "FakeSession", "make_plan_row", "make_notice", "make_flow", "make_project", "dataset",
]
