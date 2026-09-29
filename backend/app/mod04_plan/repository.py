"""`MOD-04` 落库层（付款计划行）。

⚠️ 薄层：判定与形态全在 `domain.py` / `plan_ui.py`（纯函数），**本文件只做读写**。
⚠️ 金额一律经 `core.money` 归一后再落列（`MONEY = numeric(18,2)`）。
"""

from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod04_plan.models import PlanRow


def list_rows(s: Session) -> list[PlanRow]:
    """取全部计划行（**从小到大**，与界面行号一致）。"""
    return list(s.execute(select(PlanRow).order_by(PlanRow.id.asc())).scalars().all())


def get_row(s: Session, row_id: int) -> PlanRow | None:
    return s.get(PlanRow, int(row_id))


def set_cell(s: Session, row: PlanRow, column: str, value: str) -> None:
    """行内改列落库（**立刻生效、不被导入覆盖、不留痕**，§4.3.3）。

    ⚠️ 可改范围由调用方用 `plan_ui.inline_editable_columns(result)` 判过；本函数只落库。
    """
    setattr(row, column, str(value or "").strip())


def set_force(s: Session, row: PlanRow, *, forced: bool, remark: str = "") -> None:
    """**强制通过 / 取消**落库（§4.3.4 · `ACC-PLAN-AUDIT-001`-09）。

    ⚠️ **判定不在这里**：放行要走 `domain.force_through(remark)`（**空备注即拒**）、
       取消要走 `domain.cancel_force()` —— 本函数**只落两列**（`forced_through` / `forced_remark`）。
    ⚠️ 取消 = 回到原判定且备注清空、**不产生留痕**（§4.3.4）⇒ `forced=False` 时 `remark` 传空。
    ⚠️ 两列都在 `KEEP_ON_REIMPORT` 里 ⇒ **再次导入不会把手动放行冲掉**。
    """
    row.forced_through = bool(forced)
    row.forced_remark = str(remark or "").strip()


def delete_by_ids(s: Session, ids: list[int]) -> int:
    """按 id 删除（只删该行）—— **只影响付款计划表**（§4.3.6）。"""
    if not ids:
        return 0
    res = s.execute(sa_delete(PlanRow).where(PlanRow.id.in_([int(i) for i in ids])))
    return int(res.rowcount or 0)


# ---------------------------------------------------------------- 导入（§4.3.3 · §9.5 幂等）

# 再次导入时**必须保留**的列（§4.3.3：可手改列「落库、不被导入覆盖、不留痕」＋ 强制通过）
KEEP_ON_REIMPORT: tuple[str, ...] = (
    "pay_date", "pay_method", "remark", "forced_through", "forced_remark",
)


def list_rows_of_month(s: Session, year_month: str, *, only_auto: bool = True) -> list[PlanRow]:
    """某月的计划行（`only_auto=True` ⇒ **只取自动行** —— §9.5：手动行不被触碰）。"""
    rows = [r for r in list_rows(s) if str(r.year_month or "") == str(year_month or "")]
    if only_auto:
        rows = [r for r in rows if not bool(getattr(r, "is_manual", False))]
    return rows


def merge_month(s: Session, *, year_month: str, rows: list[dict]) -> dict:
    """**按所选月份「清该月自动行 → 重写该批」**（§9.5 导入幂等 ＋ §4.3.6 按月归档）。

    实现要点：
    1. **只碰自动行**（`is_manual=False`）；该月的**手动行原样保留**（§9.5）；
    2. **同源匹配** —— 单据号非空按单据号、为空按顺序 ⇒ 命中的行**复用同一个 id**
       （不这么做，"减行不留残影"与"手改列不被覆盖"这两条不可能同时成立）；
    3. 未命中的旧行 ⇒ **删除**（换月 / 减行不留残影）；
    4. 复用行只更新**非手改列**（§4.3.3）—— `pay_date` / `pay_method` / `remark` / `forced_*` **一律保留**；
    5. ⚠️ **不做判重拦截**：同月同单据号两行是 §4.3.4 的「重复上报」判定 —— **导入照收、审查暴露、用户逐行删**。
    """
    ym = str(year_month or "").strip()
    if not ym:
        raise MustReportError("导入前**必须先选「年月」**（本批数据一律归入所选月份，§4.3.3）")

    auto = list_rows_of_month(s, ym, only_auto=True)
    manual = [r for r in list_rows_of_month(s, ym, only_auto=False) if bool(getattr(r, "is_manual", False))]

    by_doc: dict[str, list] = {}
    for row in auto:
        doc = str(row.doc_no or "").strip()
        if doc:
            by_doc.setdefault(doc, []).append(row)
    blanks = [row for row in auto if not str(row.doc_no or "").strip()]

    used: set[int] = set()
    blank_i = 0
    created = updated = kept_handedited = 0

    for item in rows:
        doc = str(item.get("doc_no") or "").strip()
        cand = None
        if doc:
            cand = next((r for r in by_doc.get(doc, []) if id(r) not in used), None)
        elif blank_i < len(blanks):
            cand = blanks[blank_i]
            blank_i += 1

        # ⚠️⚠️ **按前缀筛**旁路键（`_` 开头的是"界面 / 预览用"的键，⛔ 不是表字段）——
        #    此前写的是**单点排除** `k != "_row_no"`，于是 2026-09-27 新加的
        #    `match_candidate_labels`（预览要列"重名对上了哪几条"）**当场漏进 `PlanRow(**payload)`**
        #    ⇒ `TypeError: 'match_candidate_labels' is an invalid keyword argument for PlanRow`
        #    （真机与 pytest 一起红）。⭐ 教训：**约定要写进筛子**，别每个键单点排除一次。
        payload = {k: v for k, v in item.items() if not str(k).startswith("_")}
        if cand is None:
            s.add(PlanRow(year_month=ym, is_manual=False, **payload))
            created += 1
            continue

        used.add(id(cand))
        for key, value in payload.items():
            if key in KEEP_ON_REIMPORT:
                continue
            setattr(cand, key, value)
        kept_handedited += 1
        updated += 1

    deleted = 0
    for row in auto:
        if id(row) not in used:
            s.delete(row)
            deleted += 1

    s.flush()
    return {
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "manual_kept": len(manual),
        "kept_handedited": kept_handedited,
    }


__all__ = [
    "list_rows", "get_row", "set_cell", "delete_by_ids",
    "KEEP_ON_REIMPORT", "list_rows_of_month", "merge_month",
    "MANUAL_EDITABLE_FIELDS", "create_manual_row", "update_manual_row", "delete_row",
]


# ---------------------------------------------------------------- 手动行（§4.3 ＋ 用户 2026-09-16）

# 手动行**编辑**时允许改动的列（编辑入口与新增共用同一套，见 `plan_manual.manual_row_payload`）
MANUAL_EDITABLE_FIELDS: tuple[str, ...] = (
    "year_month", "project_input", "project_id", "match_status", "match_candidates",
    "doc_no", "flow_amount", "planned_amount", "pay_date", "pay_method", "remark", "raw",
)


def create_manual_row(s: Session, values: dict) -> PlanRow:
    """落一条**手动新增**付款计划行（字段由 `plan_manual.manual_row_payload` 组装）。

    ⚠️ `is_manual=True` ⇒ **导入不会清理它**（§9.5：导入只重写自动行）；
       **但它一样参与 §4.3.4 的 6 种审查判定**（审查按行实时派生、不看来源）。
    """
    row = PlanRow(**values)
    s.add(row)
    s.flush()
    return row


def update_manual_row(s: Session, row: PlanRow, values: dict) -> list[str]:
    """改一条手动行 —— 返回被改动的列名。"""
    touched: list[str] = []
    for key, value in (values or {}).items():
        if key not in MANUAL_EDITABLE_FIELDS or not hasattr(row, key):
            continue
        if getattr(row, key) != value:
            setattr(row, key, value)
            touched.append(key)
    s.flush()
    return touched


def delete_row(s: Session, row: PlanRow) -> int:
    """删除一条计划行（**只删该行**，§4.3.6）—— 付款计划**所有行都可删**（与付款通知书不同）。

    ⚠️ 调用方（路由）负责"**先列影响范围再确认**"（§4.3.6：行号 / 所属年月 / 审查结果）。
    """
    s.delete(row)
    return 1
