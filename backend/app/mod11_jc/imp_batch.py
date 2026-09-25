"""集采台账导入 · **批次与整批回滚**（`TAIL-98` · §6.8）—— 照过程资料 `proc_history_batch` 的形态。

**一句话**：一次导入 = 一个批次（`JC-YYYYMMDDHHMMSS`）＋ **逐行的「改前/改后」回滚点**
⇒ 导错了**整批退回**，不必一列列手工改回去。

**三条纪律**（⛔ 都别破）：
1. **判定与落库一个字都不另行** —— 本件只**包一层**：调的还是
   `import_service.match_and_apply`（锚点匹配 ⇒ 更新已有行）；
2. **回滚点必须在改之前取** —— 做法是"**先给该项目的全部合同拍快照 → 落库 → 逐条 diff**"，
   ⛔ 不预设"哪些行会被改"（那等于把匹配逻辑再写一遍）；
3. **回滚要能说出"哪里对不上"** —— 导入之后被人手改过的行**照还原**，但**逐条报出来**
   （⛔ 禁静默抹掉人工的改动）；批次**不许重复回滚**（第二遍会把回滚后的值再改一次）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod11_jc import import_service as IS
from app.mod11_jc.models import (
    BATCH_ACTIVE,
    BATCH_ROLLED_BACK,
    JcContract,
    JcImportBatch,
    JcImportUndo,
    JcInvoice,
)

#: 批次号前缀（与过程资料的 `PROC-` 并列；⛔ 别共用前缀 —— 两个域的批次互不通用）。
BATCH_PREFIX = "JC-"


def next_batch(*, at: datetime | None = None) -> str:
    """批次号 = `JC-<yyyymmddHHMMSS>`（整批回滚按它 · 与 `proc.next_batch()` 同款）。"""
    return BATCH_PREFIX + (at or datetime.now()).strftime("%Y%m%d%H%M%S")


def unique_batch(s: Session, *, at: datetime | None = None) -> str:
    """**保证唯一**的批次号 —— ⚠️ 秒级粒度 ⇒ **同一秒内连导两次会撞号**（`batch_no` 有唯一键）。

    ⭐ 这是实测出来的（`test_imp_m11_api.py` 的"同源重跑"那条）：撞号 ⇒ 唯一键报错 ⇒
      **第二次导入直接落库失败**，而用户看到的只是一句"导入失败"。
    ⇒ 撞了就**把秒数顺延**（保持 `JC-<14 位数字>` 这个形态 ⇒ 壳侧/判据里那条正则仍然成立）。
    """
    t = at or datetime.now()
    for _ in range(600):                                  # 600 秒还撞 ⇒ 不是"同一秒"的问题了
        bno = next_batch(at=t)
        if s.execute(select(JcImportBatch.id).where(JcImportBatch.batch_no == bno)).first() is None:
            return bno
        t = t + timedelta(seconds=1)
    raise MustReportError("批次号连试 600 次都撞 —— 库里 `JC-*` 的号段异常，请人工看一下")


def _snap(c: JcContract) -> dict:
    """6 列（`EXCEL_COLS`）的**当前值** —— 回滚点与"有没有变"都按它判。"""
    return {k: str(getattr(c, k) or "") for k in IS.EXCEL_COLS}


def _contracts_of(s: Session, project_id: int) -> list[JcContract]:
    return list(s.execute(
        select(JcContract).where(JcContract.project_id == int(project_id))).scalars())


def _invoices_of(s: Session, cids: list[int]) -> dict[int, set[int]]:
    """`{合同 id: {发票行 id…}}`（**一次查完** ⇒ ⛔ 不逐条查 = N+1）。"""
    out: dict[int, set[int]] = {}
    if not cids:
        return out
    for cid, iid in s.execute(
            select(JcInvoice.contract_id, JcInvoice.id).where(JcInvoice.contract_id.in_(cids))):
        out.setdefault(int(cid), set()).add(int(iid))
    return out


def apply_batch(s: Session, rows: list[dict], *, project_id: int, project_key: str = "",
                operator: str = "", mapped: set[str] | None = None,
                batch_no: str | None = None) -> dict:
    """**落库 ＋ 记批次与回滚点**（`TAIL-98`）—— 匹配与更新**全部交给** `match_and_apply`。

    ⭐ 回滚点怎么取（这是本件的关键取舍）：**改之前**给"该项目全部合同 ＋ 它们的发票行"拍快照，
      落库后**逐条 diff** ⇒ 只有**真变了的**才写回滚点（既不漏、也不把匹配逻辑抄一遍）。
    """
    bno = str(batch_no or unique_batch(s))
    cs = _contracts_of(s, project_id)
    cids = [int(c.id) for c in cs]
    before = {int(c.id): _snap(c) for c in cs}
    inv_before = _invoices_of(s, cids)

    out = IS.match_and_apply(s, rows, project_id=int(project_id), mapped=mapped)
    s.flush()

    inv_after = _invoices_of(s, cids)          # ⚠️ 下面的发票行可能是本批**新加**的
    undo_rows = 0
    for c in cs:
        cid = int(c.id)
        new = _snap(c)
        added = sorted(inv_after.get(cid, set()) - inv_before.get(cid, set()))
        if new == before[cid] and not added:
            continue                            # 这一行没被动过 ⇒ 不写回滚点（回滚点只记"真改了啥"）
        s.add(JcImportUndo(batch_no=bno, contract_id=cid,
                           before_json=json.dumps(before[cid], ensure_ascii=False),
                           after_json=json.dumps(new, ensure_ascii=False),
                           invoice_ids=json.dumps(added)))
        undo_rows += 1
    s.add(JcImportBatch(batch_no=bno, project_id=int(project_id),
                        project_key=str(project_key or ""), row_count=len(out.get("items") or []),
                        operator=str(operator or ""), status=BATCH_ACTIVE))
    s.flush()
    out["batch"] = bno
    out["undo_rows"] = undo_rows
    return out


def rollback(s: Session, batch_no: str, operator: str = "") -> dict:  # noqa: ARG001 —— 留签名（通用面传它）
    """**整批回滚**：那 6 列逐列还原 ＋ 摘掉本批**新加**的发票行；批次置 `rolled_back`（⛔ 不物理删）。

    ⚠️ 一条批次只许回滚一次（第二遍会把"回滚后的值"再改一次 ⇒ 数据被搅乱）。
    """
    bno = str(batch_no or "").strip()
    if not bno:
        raise MustReportError("请给批次号（导入回执里那个，形如 `JC-…`）")
    b = s.execute(select(JcImportBatch).where(JcImportBatch.batch_no == bno)).scalars().first()
    if b is None:
        raise MustReportError(f"找不到批次 {bno!r} —— 批次号从导入回执里拿（形如 `JC-…`）")
    if str(b.status) == BATCH_ROLLED_BACK:
        raise MustReportError(f"批次 {bno} **已经回滚过了**（⛔ 不重复回滚 —— 否则会把回滚后的值再改一次）")

    rows = list(s.execute(select(JcImportUndo).where(JcImportUndo.batch_no == bno)).scalars())
    restored = 0
    removed_invoices = 0
    missing: list[int] = []
    drifted: list[dict] = []
    for u in rows:
        c = s.get(JcContract, int(u.contract_id))
        if c is None:                            # 合同不在了 ⇒ **报出来**（⛔ 不静默跳过）
            missing.append(int(u.contract_id))
            continue
        after = json.loads(u.after_json or "{}")
        cur = _snap(c)
        changed = sorted(k for k in IS.EXCEL_COLS if cur.get(k) != str(after.get(k) or ""))
        if changed:
            # ⚠️ 导入之后又被人工改过 ⇒ **照还原，但必须说清**（禁静默抹掉人工的改动）
            drifted.append({"id": int(c.id), "fields": changed})
        for k, v in (json.loads(u.before_json or "{}")).items():
            setattr(c, k, v)
        restored += 1
        for iid in json.loads(u.invoice_ids or "[]"):
            inv = s.get(JcInvoice, int(iid))
            if inv is not None:
                s.delete(inv)
                removed_invoices += 1

    b.status = BATCH_ROLLED_BACK
    s.flush()
    return {
        "batch": bno, "restored": restored, "undo_rows": len(rows),
        "removed_invoices": removed_invoices, "missing_contracts": missing, "drifted": drifted,
        "message": (f"批次 {bno} 已回滚：**还原 {restored} 条**（那 6 列）· "
                    f"摘掉本批新加的发票行 {removed_invoices} 条"
                    + (f" · ⚠️ 其中 **{len(drifted)} 条在导入之后又被人工改过**（已一并还原，见清单）"
                       if drifted else "")
                    + (f" · ⚠️ **{len(missing)} 个回滚点在库里找不到对应合同**（已跳过）" if missing else "")),
    }


__all__ = ["BATCH_PREFIX", "next_batch", "unique_batch", "apply_batch", "rollback"]
