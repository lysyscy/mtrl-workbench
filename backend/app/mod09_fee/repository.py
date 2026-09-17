"""`MOD-09` 特殊费用月报表 · 仓储层（只做取数 / 落库，不写判定）。

⚠️ **判定一律调 `domain` 出口**（金额判据 / 取数 / 合计）。
⚠️ 自动项的取数**只读** `inv_detail`（库存单据明细，i8 源）—— 本模块**不写**那张表（§9.3 源数据只读）。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project
from app.mod08_inv.models import InvDetail
from app.mod09_fee.models import FeeManualItem


def inv_rows(s: Session, *, ym: str) -> list[dict]:
    """自动项取数用的库存单据行 —— **只取该核算年月**（§9.2 一次一个月），别把整表搬进内存。"""
    stmt = select(InvDetail).where(InvDetail.ym == ym).order_by(InvDetail.id)
    return [
        {"ym": r.ym, "warehouse": r.warehouse_name, "direction": r.direction,
         "cbs": r.cbs_name, "amount": r.amount}
        for r in s.execute(stmt).scalars().all()
    ]


def project_by_key(s: Session, warehouse_name: str) -> Project | None:
    """候选键（**仓库名**）→ 档案行（§2.7.4：比较用键、写库按 id）。"""
    key = str(warehouse_name or "").strip()
    if not key:
        return None
    return s.execute(select(Project).where(Project.warehouse_name == key)).scalars().first()


def items_of(s: Session, *, ym: str, project_id: int) -> list[dict]:
    """该「核算年月 ＋ 项目」那一份的手填项（**按录入顺序** = id 升序）。"""
    stmt = (
        select(FeeManualItem)
        .where(FeeManualItem.ym == ym, FeeManualItem.project_id == project_id)
        .order_by(FeeManualItem.id)
    )
    return [
        {"id": r.id, "name": r.item_name, "amount": Decimal(str(r.amount or 0))}
        for r in s.execute(stmt).scalars().all()
    ]


def item_of(s: Session, item_id: int, *, ym: str, project_id: int) -> FeeManualItem | None:
    """取一条手填项，**且必须落在当前那一份上**（防跨月 / 跨项目误改，§5.5）。"""
    row = s.get(FeeManualItem, int(item_id))
    if row is None or row.ym != ym or row.project_id != project_id:
        return None
    return row


def add_item(s: Session, *, ym: str, project_id: int, name: str, amount: Decimal) -> FeeManualItem:
    row = FeeManualItem(ym=ym, project_id=int(project_id), item_name=str(name), amount=amount)
    s.add(row)
    s.flush()
    return row


def set_item_name(s: Session, row: FeeManualItem, name: str) -> None:
    row.item_name = str(name)
    s.flush()


def set_item_amount(s: Session, row: FeeManualItem, amount: Decimal) -> None:
    row.amount = amount
    s.flush()


def delete_item(s: Session, row: FeeManualItem) -> None:
    s.delete(row)
    s.flush()


__all__ = [
    "inv_rows", "project_by_key", "items_of", "item_of",
    "add_item", "set_item_name", "set_item_amount", "delete_item",
]
