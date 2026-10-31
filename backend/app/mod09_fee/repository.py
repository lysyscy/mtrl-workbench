"""`MOD-09` 特殊费用月报表 · 仓储层（只做取数 / 落库，不写判定）。

⚠️ **判定一律调 `domain` 出口**（金额判据 / 取数 / 合计）。
⚠️ 自动项的取数**只读** `inv_detail`（库存单据明细，i8 源）—— 本模块**不写**那张表（§9.3 源数据只读）。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project  # typing
from app.mod01_projects import service as PS
from app.mod08_inv import service as inventory
from app.mod09_fee.models import FeeItem, FeeManualItem


def _require_manual(s, item_id):
    from .oil_linkage import is_bound, READONLY_MESSAGE
    if is_bound(s, item_id):
        raise ValueError(READONLY_MESSAGE)


def inv_rows(s: Session, *, ym: str) -> list[dict]:
    """自动项取数用的库存单据行 —— **只取该核算年月**（§9.2 一次一个月），别把整表搬进内存。"""
    return [
        {"ym": r.ym, "warehouse": r.warehouse_name, "direction": r.direction,
         "cbs": r.cbs_name, "amount": r.amount}
        for r in inventory.load_original_details(s, ym=ym)
        if r.ym == ym
    ]


def year_facts(s: Session, *, year: str, project_id: int | None, warehouse: str) -> tuple[list[dict], list[dict]]:
    """截至所选年末的原始事实；不改明细，不借用提取历史余额。"""
    end = f"{year}-12"
    items = [] if project_id is None else [
        {"id": r.id, "fee_item_id": r.fee_item_id, "key": f"fee:{r.fee_item_id}", "ym": r.ym, "name": name, "amount": r.amount}
        for r, name in s.execute(select(FeeManualItem, FeeItem.name).join(FeeItem, FeeItem.id == FeeManualItem.fee_item_id).where(
            FeeManualItem.project_id == project_id, FeeManualItem.ym <= end, FeeItem.deleted.is_(False)
        ).order_by(FeeManualItem.id))
    ]
    inv = [{"ym": r.ym, "warehouse": r.warehouse_name, "direction": r.direction,
            "cbs": r.cbs_name, "amount": r.amount}
           for r in inventory.load_original_details(s, warehouse=warehouse, through_ym=end)]
    return items, inv


def project_by_key(s: Session, warehouse_name: str) -> Project | None:
    """候选键（**仓库名**）→ 档案行（§2.7.4：比较用键、写库按 id）。"""
    key = str(warehouse_name or "").strip()
    if not key:
        return None
    return PS.warehouse_index(s).get(key)


def items_of(s: Session, *, ym: str, project_id: int) -> list[dict]:
    """该「核算年月 ＋ 项目」那一份的手填项（**按录入顺序** = id 升序）。"""
    stmt = (
        select(FeeManualItem, FeeItem.name).join(FeeItem, FeeItem.id == FeeManualItem.fee_item_id)
        .where(FeeManualItem.ym == ym, FeeManualItem.project_id == project_id, FeeItem.deleted.is_(False))
        .order_by(FeeManualItem.id)
    )
    return [
        {"id": r.id, "fee_item_id": r.fee_item_id, "name": name, "amount": Decimal(str(r.amount or 0))}
        for r, name in s.execute(stmt).all()
    ]


def item_of(s: Session, item_id: int, *, ym: str, project_id: int) -> FeeManualItem | None:
    """取一条手填项，**且必须落在当前那一份上**（防跨月 / 跨项目误改，§5.5）。"""
    row = s.get(FeeManualItem, int(item_id))
    if row is None or row.ym != ym or row.project_id != project_id:
        return None
    item = s.execute(select(FeeItem).where(FeeItem.id == row.fee_item_id, FeeItem.deleted.is_(False))
                     .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
    if item is None:
        return None
    return s.execute(select(FeeManualItem).where(FeeManualItem.id == item_id,
        FeeManualItem.ym == ym, FeeManualItem.project_id == project_id)
        .execution_options(populate_existing=True)).scalar_one_or_none()


def add_item(s: Session, *, ym: str, project_id: int, name: str, amount: Decimal) -> FeeManualItem:
    item = s.execute(select(FeeItem).where(FeeItem.project_id == int(project_id), FeeItem.name == str(name), FeeItem.deleted.is_(False)).with_for_update()
                     .execution_options(populate_existing=True)).scalar_one_or_none()
    if item is None:
        item = FeeItem(project_id=int(project_id), name=str(name))
        s.add(item)
        s.flush()
    _require_manual(s, item.id)
    existing = s.execute(select(FeeManualItem).where(FeeManualItem.fee_item_id == item.id, FeeManualItem.ym == ym)).scalar_one_or_none()
    if existing is not None:
        raise ValueError("该费用项在此月份已有记录")
    row = FeeManualItem(ym=ym, project_id=int(project_id), fee_item_id=item.id, item_name=str(name), amount=amount)
    s.add(row)
    s.flush()
    return row


def set_item_name(s: Session, row: FeeManualItem, name: str) -> None:
    _require_manual(s, row.fee_item_id)
    item = s.get(FeeItem, row.fee_item_id)
    if item is None:
        raise ValueError("费用项已不存在")
    name = str(name)
    other = s.execute(select(FeeItem.id).where(FeeItem.project_id == item.project_id, FeeItem.name == name, FeeItem.id != item.id, FeeItem.deleted.is_(False))).scalar_one_or_none()
    if other is not None:
        raise ValueError("费用项名称已存在")
    item.name = name
    s.flush()


def set_item_amount(s: Session, row: FeeManualItem, amount: Decimal) -> None:
    _require_manual(s, row.fee_item_id)
    row.amount = amount
    s.flush()


def delete_item(s: Session, row: FeeManualItem) -> None:
    _require_manual(s, row.fee_item_id)
    s.delete(row)
    s.flush()


def upsert_item(s: Session, *, ym: str, project_id: int, name: str, amount: Decimal) -> FeeManualItem:
    """⭐ `TAIL-156`（月度批量录入）用：按 **(核算月, 项目, 项名)** **幂等**写入 —— 已有 ⇒ 改金额，没有 ⇒ 新建。

    ⚠️ **为什么按项名、不按下标**：批量表里**每一列就是一个项名**（用户看到、能改的就是名字）；
       而按下标会把"第 3 行"这种**位置**概念带进一个**跨月**的界面（各月行数还不一样）⇒ 迟早改错格。
    ⚠️ 项名**允许重名**（`domain` 既有口径：可改、可重名）⇒ 重名时只认**最早那一条**（`order_by(id)`），
       ⛔ 不去猜用户想改哪条 —— 猜错就是**静默改错值**。
    """
    item = s.execute(select(FeeItem).where(FeeItem.project_id == int(project_id),
        FeeItem.name == str(name), FeeItem.deleted.is_(False)).with_for_update()
        .execution_options(populate_existing=True)).scalar_one_or_none()
    if item is None:
        return add_item(s, ym=ym, project_id=project_id, name=name, amount=amount)
    _require_manual(s, item.id)
    row = s.execute(select(FeeManualItem).where(FeeManualItem.fee_item_id == item.id,
        FeeManualItem.ym == ym).execution_options(populate_existing=True)).scalar_one_or_none()
    if row is None:
        return add_item(s, ym=ym, project_id=project_id, name=name, amount=amount)
    set_item_amount(s, row, amount)
    return row


__all__ = [
    "inv_rows", "project_by_key", "items_of", "item_of",
    "add_item", "set_item_name", "set_item_amount", "delete_item", "upsert_item",
]
