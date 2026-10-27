"""`MOD-08` 库存单据明细 / 调整单的读写。

- 明细行**只读**（源数据永不被人工修改，§9.3）；
- **调整单**是唯一写路径 —— 写入前判据走 `domain.adjustment_problem`（§8.4 第②档，唯一出口），
  留痕（改前 / 改后 / 改动人 / 时间 + 备注）一并落库（`ENT-04`）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.mod08_inv.domain import adjustment_problem
from app.mod08_inv.models import InvAdjustment, InvDetail
from app.core.money import to_money
from app.mod08_inv.adjustment_values import adjustment_values


def _with_adjustment(row: dict, adj: InvAdjustment | None) -> dict:
    if adj is not None:
        values = adjustment_values(adj)
        if "amount" in values:
            row["adj_amount"] = to_money(values["amount"])
        if adj.overrides is not None:
            row["adjusted_values"] = values
            row["adjustment_before_values"] = dict(adj.before_values or {})
        row["adj_remark"] = adj.remark or ""
        row["adj_operator"] = adj.operator or ""
        row["adj_at"] = adj.changed_at.strftime("%Y-%m-%d %H:%M") if adj.changed_at else ""
    return row


def to_row(detail: InvDetail | Row, adj: InvAdjustment | None = None) -> dict:
    """明细或只读投影 → 域内规范行（`domain` 的纯函数一律吃这种 dict）。"""
    row = {
        "id": detail.id,
        "ym": detail.ym or "",
        "warehouse": detail.warehouse_name or "",
        "project_full_name": detail.bill_name_full or "",
        "doc_no": detail.doc_no or "",
        "seq": detail.seq or "",
        "direction": detail.direction or "",
        "material": detail.material_name or "",
        "material_property": detail.material_property or "",
        "spec": detail.spec or "",
        "unit": detail.unit or "",
        "qty": detail.qty,
        "price_excl": detail.price_excl,
        "price_incl": detail.price_incl,
        "amount": detail.amount,
        "tax_total": detail.tax_total,
        "biz_type": detail.biz_type or "",
        "vendor": detail.vendor or "",
        "doc_date": detail.doc_date or "",
        "audit_date": detail.audit_date or "",
        "wbs_name": detail.wbs_name or "",
        "cbs_name": detail.cbs_name or "",
    }
    return _with_adjustment(row, adj)


def list_details(s: Session, *, ym: str | None = None, warehouse: str | None = None, through_ym: str | None = None) -> list[InvDetail]:
    """按核算年月取明细行（`ym` 空 ⇒ 全部）。"""
    stmt = select(InvDetail)
    if ym:
        stmt = stmt.where(InvDetail.ym == ym)
    if warehouse is not None:
        stmt = stmt.where(InvDetail.warehouse_name == warehouse)
    if through_ym is not None:
        stmt = stmt.where(InvDetail.ym <= through_ym)
    return list(s.execute(stmt.order_by(InvDetail.id)).scalars())


def adjustments(s: Session) -> dict[int, InvAdjustment]:
    """`row_id → 调整单`（一行至多一张）。"""
    return {a.row_id: a for a in s.execute(select(InvAdjustment)).scalars()}


def load_rows(
    s: Session, *, ym: str | None = None, adjs: dict[int, InvAdjustment] | None = None
) -> list[dict]:
    """明细行（**已叠加调整单**的规范行）。"""
    if adjs is None:
        adjs = adjustments(s)
    # 规范行只消费这些列；ORM/raw 仍由 list_details 提供给原单与刷新调用者。
    stmt = select(
        InvDetail.id, InvDetail.ym, InvDetail.warehouse_name, InvDetail.bill_name_full,
        InvDetail.doc_no, InvDetail.seq, InvDetail.direction, InvDetail.material_name,
        InvDetail.material_property, InvDetail.spec, InvDetail.unit, InvDetail.qty,
        InvDetail.price_excl, InvDetail.price_incl, InvDetail.amount, InvDetail.tax_total,
        InvDetail.biz_type, InvDetail.vendor, InvDetail.doc_date, InvDetail.audit_date,
        InvDetail.wbs_name, InvDetail.cbs_name,
    )
    if ym:
        stmt = stmt.where(InvDetail.ym == ym)
    return [to_row(d, adjs.get(d.id)) for d in s.execute(stmt.order_by(InvDetail.id))]


def load_original_inbound(s: Session) -> list[dict]:
    """原单入库的物料名、仓库、核算月及金额，供焊材/气体领域提取。"""
    stmt = select(
        InvDetail.material_name, InvDetail.warehouse_name, InvDetail.ym, InvDetail.amount
    ).where(InvDetail.direction == "入库").order_by(InvDetail.id)
    return [dict(resource_name=d.material_name, warehouse=d.warehouse_name, ym=d.ym,
                 **{"in": d.amount}) for d in s.execute(stmt)]


def load_process_rows(s: Session) -> list[dict]:
    """过程资料归集与差异定位：只读所需九列，保行序、空值及原调整痕迹。"""
    adjs = adjustments(s)
    stmt = select(
        InvDetail.id, InvDetail.ym, InvDetail.warehouse_name, InvDetail.doc_no,
        InvDetail.seq, InvDetail.direction, InvDetail.material_name,
        InvDetail.material_property, InvDetail.amount,
    ).order_by(InvDetail.id)
    return [_with_adjustment({
        "id": row_id, "ym": ym or "", "warehouse": warehouse or "",
        "doc_no": doc_no or "", "seq": seq or "", "direction": direction or "",
        "material": material or "", "material_property": material_property or "", "amount": amount,
    }, adjs.get(row_id)) for row_id, ym, warehouse, doc_no, seq, direction, material, material_property, amount
        in s.execute(stmt)]


def save_adjustment(
    s: Session, *, row_id: int, new_amount, remark: str, operator: str, at: datetime | None = None
) -> InvAdjustment:
    """写入 / 更新调整单（**判据不过 = 抛错，不静默写入**）。"""
    detail = s.get(InvDetail, row_id, with_for_update=True, populate_existing=True)
    if detail is None:
        raise ValueError(f"库存单据行不存在：{row_id}")
    problem = adjustment_problem(new_amount, remark)
    if problem:
        raise ValueError(problem)

    from app.core.money import require_non_negative  # 局部导入：避免与判据出口重复实现

    amount = require_non_negative(new_amount, field="调整后金额")
    now = at or datetime.now()
    adj = s.execute(select(InvAdjustment).where(InvAdjustment.row_id == row_id)
                    .with_for_update().execution_options(populate_existing=True)).scalars().first()
    if adj is None:
        adj = InvAdjustment(row_id=row_id, before_amount=detail.amount)
        s.add(adj)
    adj.amount = amount
    if adj.overrides is not None:
        values = {**adj.overrides, 'amount': format(amount, '.2f')}
        qty = to_money(values.get('qty', detail.qty))
        if qty:
            values['price_excl'] = format(to_money(amount / qty), '.2f')
        adj.overrides = values
    adj.remark = str(remark).strip()
    adj.operator = operator
    adj.changed_at = now
    s.flush()
    return adj



def save_linked_adjustment(s: Session, *, row_id: int, values: dict, basis: dict,
                           expected: str, remark: str, operator: str) -> InvAdjustment:
    """Keep imported facts immutable and reject an old editor before writing."""
    from app.core.errors import DataConflictError
    from app.mod06_proc.domain import MATERIAL_PROPERTIES
    from app.mod08_inv.adjustment_values import (
        NUMERIC_FIELDS, adjustment_values, calculate_values, edit_token, original_values,
    )
    detail = s.scalar(select(InvDetail).where(InvDetail.id == row_id).with_for_update().execution_options(populate_existing=True))
    if detail is None:
        raise ValueError(f"库存单据行不存在：{row_id}")
    adj = s.scalar(select(InvAdjustment).where(InvAdjustment.row_id == row_id).with_for_update().execution_options(populate_existing=True))
    source = to_row(detail)
    if not expected or expected != edit_token(source, adj):
        raise DataConflictError("原单或调整单已变化，请重读后重新确认，当前输入仍可保留")
    if not isinstance(remark, str) or not remark.strip():
        raise ValueError("调整备注必填")
    if len(remark.strip()) > 512:
        raise ValueError("调整备注不能超过512字")
    before = original_values(source)
    previous = adjustment_values(adj)
    baseline = {**before, **previous}
    calculated = calculate_values(values, basis, baseline=baseline)
    prop = calculated['material_property']
    if prop not in (*MATERIAL_PROPERTIES, '', '-', before['material_property']):
        raise ValueError("物料性质无效，请从现有类别选择")
    linked = any(mode != 'unchanged' for mode in basis.values())
    overrides = ({field: calculated[field] for field in NUMERIC_FIELDS} if linked
                 else {key: value for key, value in previous.items() if key in NUMERIC_FIELDS})
    if prop != before['material_property'] or 'material_property' in previous:
        overrides['material_property'] = prop
    if not overrides:
        raise ValueError("没有需要保存的调整内容")
    if adj is None:
        adj = InvAdjustment(row_id=row_id, before_amount=detail.amount, before_values=before)
        s.add(adj)
    elif adj.before_values is None:
        adj.before_values = before
    adj.overrides = overrides
    adj.amount = to_money(overrides.get('amount', detail.amount))
    adj.remark = remark.strip()
    adj.operator = operator
    adj.changed_at = datetime.now()
    s.flush()
    return adj

def clear_adjustment(s: Session, *, row_id: int, expected: str | None = None) -> None:
    """撤销调整单（**原始数据未受影响** —— 本表与 `inv_detail` 物理分离）。"""
    if expected is not None:
        from app.core.errors import DataConflictError
        from app.mod08_inv.adjustment_values import edit_token
        detail = s.scalar(select(InvDetail).where(InvDetail.id == row_id).with_for_update().execution_options(populate_existing=True))
        adj = s.scalar(select(InvAdjustment).where(InvAdjustment.row_id == row_id).with_for_update().execution_options(populate_existing=True))
        if detail is None or edit_token(to_row(detail), adj) != expected:
            raise DataConflictError("原单或调整单已变化，请重读后再撤销")
    else:
        adj = adjustments(s).get(row_id)
    if adj is not None:
        s.delete(adj)
        s.flush()


# ============================================================ 抓取落库（幂等刷新，§9.5）


def _key_of(d: InvDetail) -> tuple:
    return (d.ym or "", d.warehouse_name or "", d.doc_no or "", d.seq or "")


def _key_of_row(row: dict) -> tuple:
    return (str(row.get("ym") or ""), str(row.get("warehouse_name") or ""),
            str(row.get("doc_no") or ""), str(row.get("seq") or ""))


def upsert_details(s: Session, *, ym: str, warehouse: str, rows: list[dict]) -> dict:
    """把一次导出的行**幂等刷新**进 `inv_detail`（范围 = 该「核算年月 ＋ 仓库」）。

    匹配键 = **核算年月 ＋ 仓库名 ＋ 单据编号 ＋ 序号**（重复抓同一月**不产生重复行**，§9.5）。

    ⭐ **与调整单的关系**（`ENT-04` / §5.2.4「调整单不被 i8 导出覆盖」）：
    - 匹配到的行 ⇒ **只更新源字段**（`amount` 跟随 i8 新值），**调整单一行不动**；
    - 本次不再出现、且**没有调整单**的行 ⇒ 删除（换月 / 减行**不留残影**，§9.5）；
    - 本次不再出现、但**有调整单**的行 ⇒ ⛔ **保留**（否则调整单会被 CASCADE 连带删掉），
      并把条数报回调用方（**不静默**）。
    """
    adjs = adjustments(s)
    # ⚠️ **幂等范围 = 「核算年月 ＋ 仓库」**（与 `_key_of` 同口径）—— 2026-09-17 真机抓出：
    #    原先只按 `ym` 取 existing ⇒ 同月多仓库时，**后一个仓库的刷新会把前一个仓库的行删掉**
    #    （实测：解析 559 行、只落库 18 行）。FakeSession 忽略 `where` ⇒ 这里必须在 **Python 侧**过滤。
    existing = {_key_of(d): d for d in list_details(s, ym=(ym or None))
                if str(d.warehouse_name or "") == str(warehouse or "")}
    seen: set[tuple] = set()
    inserted = updated = 0

    for row in rows:
        key = _key_of_row(row)
        if key in seen:
            continue
        seen.add(key)
        if key in existing:
            found = existing[key]
            updated += 1
        else:
            found = InvDetail(ym=ym, warehouse_name=warehouse)
            s.add(found)
            inserted += 1
        for field in ("warehouse_name", "bill_name_full", "doc_no", "seq", "direction",
                      "material_name", "material_property", "spec", "unit", "qty",
                      "price_excl", "price_incl", "amount", "tax_total", "biz_type", "vendor",
                      "doc_date", "audit_date", "wbs_name", "cbs_name"):
            if field in row:
                setattr(found, field, row[field])

    deleted = kept = 0
    for key, found in existing.items():
        if key in seen:
            continue
        if found.id in adjs:
            kept += 1                                  # ⛔ 有调整单 ⇒ 保留
            continue
        s.delete(found)
        deleted += 1

    s.flush()
    return {"inserted": inserted, "updated": updated, "deleted": deleted, "kept_with_adjustment": kept}


__all__ = ["to_row", "list_details", "adjustments", "load_rows", "load_original_inbound", "load_process_rows",
           "save_adjustment", "clear_adjustment", "upsert_details"]
