"""`MOD-05` 页面自检的公共桩（**离线：不连库**）。

`FakeSession` 让 `service` / `repository` 的**真实代码**跑到，只是数据来自内存
⇒ 页面与组装层**端到端**可验，而不用起 Postgres。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import (
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    LedgerRemark,
    OpeningBalance,
    PaymentFlow,
)


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self) -> list:
        return list(self._rows)


class FakeSession:
    """按**模型类型**分发的最小会话桩（`execute` / `get` / `add` / `flush` / `delete`）。"""

    def __init__(self, by_model: dict) -> None:
        self.by_model = {k: list(v) for k, v in by_model.items()}
        self.added: list = []
        self.deleted: list = []

    def execute(self, stmt):  # noqa: ANN001
        entity = stmt.column_descriptions[0]["entity"]
        rows = self.by_model.get(entity, [])
        # `.where(...)` 的过滤在桩里**不还原** ⇒ 桩只用于「单条件/无条件」的取数场景；
        # 需要精确命中的用例请直接传更小的数据集。
        return _Result(rows)

    def get(self, model, ident):  # noqa: ANN001
        for row in self.by_model.get(model, []):
            if getattr(row, "id", None) == ident:
                return row
        return None

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 1000 + len(self.added)
        self.by_model.setdefault(type(obj), []).append(obj)

    def flush(self) -> None:
        return None

    def delete(self, obj) -> None:  # noqa: ANN001
        self.deleted.append(obj)
        rows = self.by_model.get(type(obj), [])
        self.by_model[type(obj)] = [r for r in rows if r is not obj]


# ---------------------------------------------------------------- 造数


def make_project(pid: int, warehouse: str, disp: str = "", name_full: str = "") -> Project:
    return Project(id=pid, project_type="normal", name_full=name_full or f"全名{pid}",
                   warehouse_name=warehouse, disp=disp)


def make_notice_row(
    nid: int,
    *,
    bill_no: str = "",
    doc_date: str = "2026-09-10",
    category: str = CATEGORY_MATERIAL,
    settle: str = "0",
    paid: str = "0",
    excluded: bool = False,
    ownership_id: int | None = 11,
) -> PaymentNotice:
    return PaymentNotice(
        id=nid, ph_id=f"ph-{nid}", bill_no=bill_no, bill_type=category,
        amount_approved=Decimal(settle), amount_paid=Decimal(paid),
        fields={},
        doc_date=doc_date, category=category, excluded=excluded,
        biz_type="", payee="", input_by="",
        stat_settle=Decimal(settle), stat_paid=Decimal(paid), ownership_id=ownership_id,
    )


def make_flow(
    fid: int,
    *,
    flow_no: str = "",
    notice_id: int | None = 101,
    project_id: int | None = 11,
    amount: str = "100.00",
    pay_date: str = "2026-09-12",
    pay_method: str = "现汇",
    status: str = FLOW_EFFECTIVE,
    revoke_reason: str = "",
) -> PaymentFlow:
    return PaymentFlow(
        id=fid, flow_no=flow_no or f"F{fid}", notice_id=notice_id, project_id=project_id,
        amount=Decimal(amount), pay_date=pay_date, pay_method=pay_method, status=status,
        revoke_reason=revoke_reason,
        revoked_at=datetime(2026, 9, 13, 10, 0) if status == FLOW_REVOKED else None,
        request_id="", created_at=datetime(2026, 9, 12, 9, 30),
    )


def make_opening(
    oid: int, *, category: str = CATEGORY_MATERIAL, project_id: int = 11,
    cutoff_ym: str = "2026-06", settle: str = "0", paid: str = "0",
) -> OpeningBalance:
    return OpeningBalance(
        id=oid, category=category, project_id=project_id, cutoff_ym=cutoff_ym,
        settle_amount=Decimal(settle), paid_amount=Decimal(paid), remark="",
        created_at=datetime(2026, 9, 1, 8, 0),
    )


def dataset() -> dict:
    """一份小样本：辅材 2 行（一期初）＋ 机械 1 行 ＋ 剔除 1 行 ＋ 生效/已撤销流水各 1 条。"""
    return {
        Project: [make_project(11, "甲仓库", "甲公司项目")],
        PaymentNotice: [
            make_notice_row(101, bill_no="D1", doc_date="2026-07-05", settle="1000", paid="200"),
            make_notice_row(102, bill_no="D2", doc_date="2026-09-08", settle="500", paid="0"),
            make_notice_row(103, bill_no="D3", doc_date="2026-09-09", category=CATEGORY_MECH,
                            settle="0", paid="300"),
            # 无归属 ⇒ 在「按项目看欠款」里**单列**、不并入任何小微
            make_notice_row(105, bill_no="D5", doc_date="2026-09-11", settle="50", paid="0",
                            ownership_id=None),
            make_notice_row(104, bill_no="D4", doc_date="2026-09-10", settle="9999", excluded=True),
        ],
        OpeningBalance: [make_opening(201, settle="100", paid="0")],
        PaymentFlow: [
            make_flow(301, flow_no="F301", amount="150.00"),
            make_flow(302, flow_no="F302", amount="60.00", status=FLOW_REVOKED, revoke_reason="付错单位"),
        ],
        LedgerRemark: [],
    }


TODAY = date(2026, 9, 15)      # 固定"今天"，让默认当月 / 默认周桶可复现


__all__ = [
    "FakeSession", "make_project", "make_notice_row", "make_flow", "make_opening",
    "dataset", "TODAY",
]
