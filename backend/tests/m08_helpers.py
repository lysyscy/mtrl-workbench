"""`MOD-08` 页面 / 域自检的公共桩（**离线：不连库**）。

`FakeSession` 让 `service.build_page_data` / `repository` 的真实代码跑到，只是数据来自内存
⇒ 页面与组装层**端到端**可验，而不用起 Postgres。
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.mod08_inv.models import InvAdjustment, InvDetail


class _Projection(SimpleNamespace):
    """SQLAlchemy只读Row同时支持列属性与按投影顺序迭代。"""

    def __iter__(self):
        return iter(vars(self).values())


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list:
        return list(self._rows)

    def __iter__(self):
        return iter(list(self._rows))

    def __len__(self) -> int:
        return len(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        """聚合出口（`select(func.max(...))` 之类）。

        ⚠️ 桩里**没有真聚合能力** ⇒ 一律 `None`（不假装能算）——
           调用方那类 `int(x or 0) + 1` 的写法会自然取到 **1**，正是「空表从头开始」的语义。
        """
        return None


class FakeSession:
    """按**模型类型**分发的最小会话桩（只实现 `service` / `repository` 用到的那点 API）。"""

    def __init__(self, by_model: dict | None = None) -> None:
        self.by_model: dict = {k: list(v) for k, v in (by_model or {}).items()}

    def execute(self, stmt):  # noqa: ANN001
        entity = stmt.column_descriptions[0]["entity"]
        rows = self.by_model.get(entity, [])
        if entity is InvAdjustment:
            for condition in stmt._where_criteria:
                rows = [r for r in rows if getattr(r, condition.left.key) == condition.right.value]
        if entity is InvDetail and stmt.column_descriptions[0]["expr"] is not InvDetail:
            # 库存只读列投影的两个等值条件；完整 ORM 桩仍保持刷新用例的既有行为。
            for condition in stmt._where_criteria:
                rows = [r for r in rows if getattr(r, condition.left.key) == condition.right.value]
            rows = [_Projection(**{col["name"]: getattr(r, col["name"])
                                       for col in stmt.column_descriptions}) for r in rows]
        return _Result(rows)

    def get(self, model, ident, **kwargs):  # noqa: ANN001
        for row in self.by_model.get(model, []):
            if getattr(row, "id", None) == ident:
                return row
        return None

    def add(self, obj) -> None:
        self.by_model.setdefault(type(obj), []).append(obj)

    def delete(self, obj) -> None:
        rows = self.by_model.get(type(obj), [])
        if obj in rows:
            rows.remove(obj)

    def flush(self) -> None:
        pass

    @contextmanager
    def begin_nested(self):
        before = deepcopy(self.by_model)
        try:
            yield self
        except Exception:
            self.by_model = before
            raise


def make_detail(
    row_id: int,
    *,
    ym: str = "2026-08",
    warehouse: str = "甲仓",
    doc_no: str = "KCDJ-001",
    seq: str = "1",
    direction: str = "入库",
    material: str = "焊条",
    spec: str = "J422",
    unit: str = "kg",
    qty: str = "10.00",
    price_excl: str = "10.00",
    price_incl: str = "11.30",
    amount: str = "100.00",
    tax_total: str = "113.00",
    biz_type: str = "采购入库",
    vendor: str = "某供应商",
    doc_date: str = "2026-08-05",
    audit_date: str = "2026-08-06",
    wbs_name: str = "W1",
    cbs_name: str = "C1",
) -> InvDetail:
    return InvDetail(
        id=row_id, ym=ym, warehouse_name=warehouse, bill_name_full=f"{warehouse}项目",
        doc_no=doc_no, seq=seq, direction=direction, material_name=material, spec=spec,
        unit=unit, qty=Decimal(qty), price_excl=Decimal(price_excl),
        price_incl=Decimal(price_incl), amount=Decimal(amount), tax_total=Decimal(tax_total),
        biz_type=biz_type, vendor=vendor, doc_date=doc_date, audit_date=audit_date,
        wbs_name=wbs_name, cbs_name=cbs_name, raw={},
    )


def make_adj(row_id: int, amount: str, *, before: str = "100.00", remark: str = "对账差异",
             operator: str = "科室用户", at: datetime | None = None) -> InvAdjustment:
    return InvAdjustment(
        id=row_id * 100, row_id=row_id, before_amount=Decimal(before), amount=Decimal(amount),
        remark=remark, operator=operator, changed_at=at or datetime(2026, 9, 16, 10, 30),
    )


def dataset() -> dict:
    """一份小样本：2 个仓库 / 2 个方向 / 2 个核算月 / 1 行被调整过。"""
    return {
        InvDetail: [
            make_detail(1, ym="2026-08", warehouse="甲仓", direction="入库",
                        doc_no="K1", amount="100.00", tax_total="113.00", qty="10.00"),
            make_detail(2, ym="2026-08", warehouse="甲仓", direction="出库",
                        doc_no="K2", amount="40.00", tax_total="40.00", qty="4.00"),
            make_detail(3, ym="2026-08", warehouse="乙仓", direction="入库",
                        doc_no="K3", amount="200.00", tax_total="226.00", qty="20.00"),
            make_detail(4, ym="2026-07", warehouse="甲仓", direction="入库",
                        doc_no="K4", amount="500.00", tax_total="565.00", qty="50.00"),
        ],
        InvAdjustment: [make_adj(2, "30.00", before="40.00", remark="金额录错")],
    }


__all__ = ["FakeSession", "make_detail", "make_adj", "dataset"]
