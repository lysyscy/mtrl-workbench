"""`MOD-07` 活动大表的**持久化**（手填 6 列 ＋ 大表自己的项目顺序）。

⚠️ 旧全局名单只读；只写本月名单与手填，自动列及派生列一律现场算。
⚠️ 列名映射**唯一处** = `big_domain.MANUAL_COLUMN`（本文件不写第二份）。
⚠️ **手填值不参与欠款计算**（§5.7.2）：本文件**不调用任何**付款域的重算出口。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import require_non_negative
from app.mod07_setl import big_domain as B
from app.mod07_setl.models import AnalysisBigManual, AnalysisBigMonthProject, AnalysisBigProject


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


def load_selection(s: Session, ym: str) -> dict:
    """精确月 → 最近更早配置月（含选空）→ 旧全局基线 → 默认候选；读取不落库。"""
    rows = [r for r in s.execute(select(AnalysisBigMonthProject)).scalars() if r.ym <= ym]
    source = max((r.ym for r in rows), default="")
    if source:
        rows = [r for r in rows if r.ym == source and r.warehouse_name != CHOICE_MARKER]
        rows.sort(key=lambda r: (r.seq or 0, r.id or 0))
        return {"fixed": source == ym, "source": source, "order": [r.warehouse_name for r in rows]}
    return {"fixed": False, "source": "legacy" if has_choice(s) else "default", "order": load_order(s)}


def save_order(s: Session, ym: str, warehouses) -> list[str]:
    """只改指定月；保留共同项目的行身份，让撤销/重做可靠恢复。"""
    seq = [str(w) for w in (warehouses or ()) if str(w or "")]
    wanted = {CHOICE_MARKER: -1, **{wh: i for i, wh in enumerate(seq)}}
    current = {r.warehouse_name: r for r in s.execute(select(AnalysisBigMonthProject)).scalars() if r.ym == ym}
    for wh, row in current.items():
        if wh not in wanted:
            s.delete(row)
    for wh, position in wanted.items():
        if wh in current:
            current[wh].seq = position
        else:
            s.add(AnalysisBigMonthProject(ym=ym, warehouse_name=wh, seq=position))
    s.flush()
    return seq


__all__ = ["load_manual", "load_order", "has_choice", "load_selection", "save_cell", "save_order", "CHOICE_MARKER"]
