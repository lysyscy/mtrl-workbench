"""`MOD-07` 收发结存的读写。

- **明细行**（`setl_detail`）是唯一存储形态；按仓汇总在域内核做（`domain.aggregate_by_warehouse`）。
- 明细分文的写入路径**只有抓取落库**（`upsert_month`）—— 收发结存页**没有人工改数的入口**（§5.3.1：用途仅两个）。
- ⭐ **另有一处人工写入**：焊材 / 气体提取成品的**「结余」列**（`weldgas_balance`）——
  2026-09-18 用户裁定 = **历史结余、由用户手工录入**（系统没有来源）⇒ 见本文件末段的
  `load_balances` / `save_balance`（**粒度 = 类别 × 仓库 · 不按月**）。两者**互不相干**，⛔ 别混。

⚠️ 幂等语义（照素材包 `app/importer.py::import_sfjc` 的实测结论）：**先看该月、再对齐**——
   否则「当月数据变少 / 换月」时旧行会残留（素材包实测过：9 月库里混进 636 行 8 月残留）。
⛔ **`source` 非 `auto` 的行一律不动**（人工数据不被抓取覆盖）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import to_money
from app.mod07_setl.models import SOURCE_AUTO, SetlDetail, WeldGasBalance

# 域内 key → 库列名（**唯一映射处**；domain 永远不认列名）
AMOUNT_FIELDS: dict[str, str] = {
    "begin": "begin_amt", "in": "in_amt", "out": "out_amt", "end": "end_amt",
}
SOURCE_FIELDS: tuple[str, ...] = (
    "resource_class", "resource_name", "spec", "unit", "material_property",
    "begin_qty", "begin_amt", "in_qty", "in_price", "in_amt",
    "out_qty", "out_price", "out_amt", "end_qty", "end_amt",
)


def to_row(d: SetlDetail) -> dict:
    """ORM → 域内规范行（**域内 key，不是列名**；四个金额列映射到 `domain.AMOUNT_KEYS`）。"""
    row: dict = {
        "id": d.id,
        "ym": str(d.ym or ""),
        "warehouse": str(d.warehouse_name or ""),
        "resource_code": str(d.resource_code or ""),
        "resource_name": str(d.resource_name or ""),
        "material_property": str(d.material_property or ""),
    }
    for key, column in AMOUNT_FIELDS.items():
        row[key] = getattr(d, column, 0)
    return row


def load_rows(s: Session) -> list[dict]:
    """全部**明细行**（不分月过滤：月筛在域内核 `domain.rows_of`，全站同款）。"""
    return [to_row(d) for d in s.execute(select(SetlDetail)).scalars()]


# ============================================================ 抓取落库（幂等刷新，§9.5）


def _key_of(d: SetlDetail) -> tuple[str, str, str]:
    return (str(d.ym or ""), str(d.warehouse_name or ""), str(d.resource_code or ""))


def _key_of_row(row: dict, ym: str) -> tuple[str, str, str]:
    """行的匹配键 —— ⚠️ 核算年月**取函数入参**，不取 `row["ym"]`。

    理由：`ym` 是本函数**唯一的范围声明**（同时也是"要删哪个月"的依据）。
    若改取 `row` 里的值，一旦调用方给的 `rows` 与入参不一致，就会出现
    「**按 8 月删、按 7 月插**」这种错位（两个真相）；钉死在入参上就没有这个可能。
    """
    return (str(ym or ""), str(row.get("warehouse_name") or ""),
            str(row.get("resource_code") or ""))


def upsert_month(s: Session, *, ym: str, rows: list[dict]) -> dict:
    """把一次导出的**明细行**幂等刷新进 `setl_detail`（范围 = 该**核算月**）。

    匹配键 = **核算年月 ＋ 仓库名 ＋ 资源编码**（同月重抓**不产生重复行**，§9.5）。

    - 匹配到的行 ⇒ 更新源字段；
    - 本次不再出现、且 `source = auto` 的行 ⇒ **删除**（当月变少 / 换月**不留残影**）；
    - `source` 非 `auto` 的行 ⇒ ⛔ **保留**，并把条数报回调用方（**不静默**）。

    返回 `{"inserted", "updated", "deleted", "kept_manual"}`。
    """
    existing = {_key_of(d): d for d in s.execute(select(SetlDetail)).scalars()
                if str(d.ym or "") == str(ym or "")}
    seen: set[tuple[str, str, str]] = set()
    inserted = updated = 0
    now = datetime.now()

    for row in rows:
        key = _key_of_row(row, ym)
        if key in seen:
            continue
        seen.add(key)
        if key in existing:
            found = existing[key]
            updated += 1
        else:
            found = SetlDetail(ym=ym, warehouse_name=str(row.get("warehouse_name") or ""),
                               resource_code=str(row.get("resource_code") or ""))
            s.add(found)
            inserted += 1
        found.warehouse_name = str(row.get("warehouse_name") or "")
        found.resource_code = str(row.get("resource_code") or "")
        for field in SOURCE_FIELDS:
            if field in row:
                setattr(found, field, row[field])
        found.source = SOURCE_AUTO
        found.updated_at = now

    deleted = kept_manual = 0
    for key, found in existing.items():
        if key in seen:
            continue
        if str(found.source or SOURCE_AUTO) != SOURCE_AUTO:
            kept_manual += 1
            continue
        s.delete(found)
        deleted += 1

    s.flush()
    return {"inserted": inserted, "updated": updated,
            "deleted": deleted, "kept_manual": kept_manual}


# ============================================================ 焊材 / 气体「结余」（手工录入）

def load_balances(s: Session) -> dict[str, dict[str, Decimal]]:
    """「结余」手工录入值 → `{类别: {仓库名: 金额}}`（**唯一取数出口**）。

    ⚠️ **未录入的 `(类别, 仓库)` 键不出现**（域值 = `None`）—— 导出里据此**如实留空**；
       **0 是合法录入值**（有行、金额 `0.00`），照常出现。两者**不得混为一谈**。
    """
    out: dict[str, dict[str, Decimal]] = {}
    for r in s.execute(select(WeldGasBalance)).scalars():
        kind = str(r.kind or "")
        warehouse = str(r.warehouse_name or "")
        if not kind or not warehouse:
            continue                                  # 键不完整的行无从使用 ⇒ 跳过（不臆造归属）
        out.setdefault(kind, {})[warehouse] = to_money(r.amount)
    return out


def save_balance(s: Session, *, kind: str, warehouse: str, amount) -> WeldGasBalance | None:
    """写**一格**「结余」⇒ 返回该行（`amount is None` ⇒ **删掉该行**、返回 `None`）。

    ⚠️ 粒度 = **类别 × 仓库（不按月）** ⇒ 同一格重复保存 = **覆盖**，不会产生第二行。
    ⚠️ 金额一律过 `to_money`（2 位小数、HALF_UP）—— 非负判据在服务层（`big_domain.parse_manual`）。
    """
    row = _find_balance(s, kind, warehouse)
    if amount is None:                                 # 清空 ⇒ 回到"未录入"（行都没有 = 导出留空）
        if row is not None:
            s.delete(row)
            s.flush()
        return None
    if row is None:
        row = WeldGasBalance(kind=str(kind), warehouse_name=str(warehouse))
        s.add(row)
    row.kind = str(kind)
    row.warehouse_name = str(warehouse)
    row.amount = to_money(amount)
    row.updated_at = datetime.now()
    s.flush()
    return row


def _find_balance(s: Session, kind: str, warehouse: str) -> WeldGasBalance | None:
    for r in s.execute(select(WeldGasBalance)).scalars():
        if str(r.kind or "") == str(kind) and str(r.warehouse_name or "") == str(warehouse):
            return r
    return None


__all__ = ["AMOUNT_FIELDS", "SOURCE_FIELDS", "to_row", "load_rows", "upsert_month",
           "load_balances", "save_balance"]
