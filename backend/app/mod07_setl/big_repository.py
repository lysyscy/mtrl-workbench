"""`MOD-07` 活动大表的**持久化**（手填 6 列 ＋ 大表自己的项目顺序）。

⚠️ **只碰大表自己的两张表**：自动列（提取 / 机械）与派生列**一律不落库**（现场算）。
⚠️ 列名映射**唯一处** = `big_domain.MANUAL_COLUMN`（本文件不写第二份）。
⚠️ **手填值不参与欠款计算**（§5.7.2）：本文件**不调用任何**付款域的重算出口。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import require_non_negative
from app.mod07_setl import big_domain as B
from app.mod07_setl.models import AnalysisBigManual, AnalysisBigProject


def load_manual(s: Session) -> dict[str, dict[str, dict]]:
    """手填值 → `{年月: {仓库名: {key: 值}}}`（`None` = 该月未录入）。"""
    out: dict[str, dict[str, dict]] = {}
    for r in s.execute(select(AnalysisBigManual)).scalars():
        ym, wh = str(r.ym or ""), str(r.warehouse_name or "")
        if not ym or not wh:
            continue
        bucket = out.setdefault(ym, {}).setdefault(wh, {})
        for key, column in B.MANUAL_COLUMN.items():
            bucket[key] = getattr(r, column, None)
    return out


#: 选题的**标记行** —— 用来区分「**从未选题**」（⇒ 默认全部候选）与「**选了空**」（⇒ 表里 0 个项目）。
#: ⚠️ 两者**不能靠"表里有没有行"区分**：不写标记行的话，清空之后就会被当成"从未选题"而**悄悄回到全部候选**。
CHOICE_MARKER = "（已选题）"


def has_choice(s: Session) -> bool:
    """**是否已经选过题**（只看有没有行 —— 标记行也算）。"""
    return bool(list(s.execute(select(AnalysisBigProject)).scalars()))


def load_order(s: Session) -> list[str]:
    """大表自己的行序（按 `seq`）—— **不含标记行**；空 = 本次没有项目。"""
    rows = list(s.execute(select(AnalysisBigProject)).scalars())
    rows = [r for r in rows if str(r.warehouse_name or "") != CHOICE_MARKER]
    rows.sort(key=lambda r: (int(getattr(r, "seq", 0) or 0), int(getattr(r, "id", 0) or 0)))
    return [str(r.warehouse_name or "") for r in rows if str(r.warehouse_name or "")]


def _find(s: Session, ym: str, warehouse: str) -> AnalysisBigManual | None:
    for r in s.execute(select(AnalysisBigManual)).scalars():
        if str(r.ym or "") == ym and str(r.warehouse_name or "") == warehouse:
            return r
    return None


def save_cell(s: Session, *, ym: str, warehouse: str, key: str,
              value, project_id: int | None = None) -> AnalysisBigManual:
    """写**一格**手填值（`value=None` = 清空 ⇒ 回到带入态）。

    ⭐ **只动这一格** —— 同行其它格保持原样（**编辑一格不连带确认同行其他格**，001-06）。
    """
    column = B.MANUAL_COLUMN[key]
    fmt = B.MANUAL_FMT[key]
    if value is not None and fmt == B.FMT_MONEY:
        value = require_non_negative(value, field=B.label_of(key))
    row = _find(s, ym, warehouse)
    if row is None:
        row = AnalysisBigManual(ym=ym, warehouse_name=warehouse, project_id=project_id)
        s.add(row)
    setattr(row, column, value)
    if project_id is not None:
        row.project_id = project_id
    s.flush()
    return row


def save_order(s: Session, warehouses) -> list[str]:
    """整体保存选题结果（顺序即所设顺序）—— **先清后写**，避免残留旧项。

    ⚠️ **中间必须 `flush()`**：SQLAlchemy 的工作单元默认**先 INSERT 后 DELETE**
       ⇒ 不 flush 就会撞 `uq_big_project_wh`（同一仓库名"先插后删"）。
    """
    seq = [str(w) for w in (warehouses or ()) if str(w or "")]
    for r in list(s.execute(select(AnalysisBigProject)).scalars()):
        s.delete(r)
    s.flush()
    s.add(AnalysisBigProject(warehouse_name=CHOICE_MARKER, seq=-1))    # 标记行（见常量说明）
    for i, wh in enumerate(seq):
        s.add(AnalysisBigProject(warehouse_name=wh, seq=i))
    s.flush()
    return seq


__all__ = ["load_manual", "load_order", "has_choice", "save_cell", "save_order", "CHOICE_MARKER"]
