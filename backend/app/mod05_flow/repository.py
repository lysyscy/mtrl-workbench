"""`MOD-05` 落库层（付款流水 / 期初占位行 / 台账备注 / 撤销留痕）。

⚠️ 薄层：口径与形态全在 `domain.py`（纯函数），**本文件只做读写**。
⚠️ 金额一律经 `core.money` 归一后再落列（`MONEY = numeric(18,2)`）。
⚠️ **撤销必填原因**由 `domain.revoke_flow` 把关（空 ⇒ 抛 `MustReportError`）—— 本层**不另写判定**，
   只负责「落状态 + 写留痕」这一件事（§4.4.5 · §9.3）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.identity import current_operator
from app.core.money import to_money
from app.mod03_notice.models import NoticeStatLog, PaymentNotice
from app.mod05_flow.domain import effective_total, revoke_flow
from app.mod05_flow.models import (
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    FLOW_SOURCE_IMPORTED,
    FLOW_SOURCE_MANUAL,
    FlowRevokeLog,
    LedgerRemark,
    OpeningBalance,
    PaymentFlow,
)

# ---------------------------------------------------------------- 付款流水


def list_flows(s: Session) -> list[PaymentFlow]:
    """全部流水（**按付款日期倒序**，同日按 id 倒序）—— 列表与统计共用同一批数据。"""
    stmt = select(PaymentFlow).order_by(PaymentFlow.pay_date.desc(), PaymentFlow.id.desc())
    return list(s.execute(stmt).scalars().all())


def flows_of_notices(s: Session, notice_ids: list[int]) -> list[PaymentFlow]:
    """一次取指定通知书的全部流水，供合同明细分笔展示。"""
    if not notice_ids:
        return []
    return list(s.execute(select(PaymentFlow).where(
        PaymentFlow.notice_id.in_(notice_ids)
    ).order_by(PaymentFlow.pay_date, PaymentFlow.id)).scalars().all())


def get_flow(s: Session, flow_id: int, *, for_update: bool = False) -> PaymentFlow | None:
    if for_update:
        return s.get(PaymentFlow, int(flow_id), with_for_update=True, populate_existing=True)
    return s.get(PaymentFlow, int(flow_id))


def list_flows_of_notice(s: Session, notice_id: int) -> list[PaymentFlow]:
    """某张通知书的**全部流水**（含已撤销）—— 「撤销付款」与「查看关联」的取数出口（§4.4.5 · R18）。

    ⚠️ 含已撤销：撤销入口要判断"有几条**生效**流水"、查看关联要**同时列出已撤销的那几条及其原因**。
    """
    stmt = (
        select(PaymentFlow)
        .where(PaymentFlow.notice_id == int(notice_id))
        .order_by(PaymentFlow.id.asc())
    )
    return list(s.execute(stmt).scalars().all())


def next_flow_no(*, at: datetime | None = None) -> str:
    """生成流水号（撤销**按流水号**执行，§4.4.5）。

    用时间戳 + 短随机后缀 ⇒ 两个人同时提交也不会撞号（不依赖 `SELECT MAX` 的取号）。
    """
    ts = (at or datetime.now()).strftime("%Y%m%d%H%M%S")
    return f"FL{ts}{uuid4().hex[:4].upper()}"


def has_request_id(s: Session, request_id: str) -> bool:
    """该 `request_id` 是否已经产生过流水 —— **防重复提交**（§4.4.4：提交按钮按下即锁定）。"""
    rid = str(request_id or "").strip()
    if not rid:
        return False
    row = s.execute(select(PaymentFlow).where(PaymentFlow.request_id == rid)).scalars().first()
    # ⚠️ 再比一次值：即便取数层多给了行（或桩会话不过滤 where），也**不得**误判成"已提交过"
    return row is not None and str(row.request_id or "") == rid


def _method_of(pay_method, source) -> str:
    """付款方式落地值（§4.4.2 vs §4.4.6 的**分叉口**）。

    - **付款动作**（`manual`）⇒ 取不到兜底「**现汇**」（§4.4.2 既有口径，行为不变）；
    - **历史导入**（`imported`）⇒ **允许为空**：历史台账常常没记付款方式，
      那是**事实记录，不得编造**（§4.4.6）⇒ **原样存空**。
    """
    text = str(pay_method or "").strip()
    if text:
        return text
    return "" if str(source or FLOW_SOURCE_MANUAL) == FLOW_SOURCE_IMPORTED else "现汇"


def create_flow(
    s: Session,
    *,
    notice_id: int,
    project_id: int | None,
    amount,
    pay_date: str = "",
    pay_method: str = "现汇",
    request_id: str = "",
    source: str = FLOW_SOURCE_MANUAL,
    import_batch: str = "", remark: str = "",
    created_by: str = "",
) -> PaymentFlow:
    """登记**一条**付款流水（§4.4.2：**一次付款一条独立流水**，不做金额累计覆盖）。

    ⚠️ 金额与付款方式的**合法性判定不在此层** —— 由 `mod03_notice.domain.confirm_batch` 把关
       （禁用是预防、校验是兜底；本层只落已通过的批次）。

    ⭐ **`created_by`（操作人）**：§1.5.1 末行「留痕的改前人 / 录入人**一律取当前登录用户**」。
    ⚠️ 传空时**就地兜** `current_operator()` —— 而不是让每个调用方自己记得传：
       这条流水**必然**是"某个人在界面上点的"（历史导入由 `commit_plan` 单独写 `operator`），
       漏传的后果是**留痕字段变空串**，而那种错**不报错、只静默**（本项目最贵的一类）。
    ⛔ 兜底**也不是写死名字** —— `current_operator()` 是唯一出口（登录态 → `.env` → 中性占位）。
    """
    row = PaymentFlow(
        flow_no=next_flow_no(),
        notice_id=int(notice_id),
        project_id=int(project_id) if project_id is not None else None,
        amount=to_money(amount),
        pay_date=str(pay_date or ""),
        pay_method=_method_of(pay_method, source),
        status=FLOW_EFFECTIVE,
        request_id=str(request_id or ""),
        source=str(source or FLOW_SOURCE_MANUAL),
        import_batch=str(import_batch or ""),
        remark=str(remark or ""),
        created_by=str(created_by or "") or current_operator(),
    )
    s.add(row)
    s.flush()
    # ⭐ 重算唯一出口（§4.4.7）—— 付款也走它，保证"付了款欠款会变"（别在别处再算一遍）
    sync_stat_paid(s, int(notice_id))
    return row


def revoke(s: Session, flow: PaymentFlow, *, reason: str, changed_by: str = "", stat_choice: str = "") -> dict:
    """撤销一条流水（§4.4.5）—— 原因**先过 `domain.revoke_flow`**（空原因直接抛错、不落库）。

    ⚠️ 撤销不动 i8 源数据；人工统计保留或恢复自动由显式选择决定（§4.4.5 · §9.3 旁路思路）。
    """
    from app.core.errors import MustReportError
    from app.mod03_notice import domain as notices_domain, service as notices_repo
    if flow.status != FLOW_EFFECTIVE:
        raise MustReportError("该流水已撤销，请刷新页面")
    notice = notices_repo.get_notice(s, int(flow.notice_id)) if flow.notice_id is not None else None
    traces = notices_repo.list_stat_traces(s, notice.id) if notice else []
    choice = notices_domain.revoke_stat_choice(stat_choice, manual=bool(notice and notices_domain.stat_paid_is_manual(traces, notice.id)))
    patch = revoke_flow(reason)
    flow.status = str(patch["status"])
    flow.revoke_reason = str(patch["revoke_reason"])
    flow.revoked_at = patch["revoked_at"]
    s.add(
        FlowRevokeLog(
            flow_id=flow.id,
            reason=flow.revoke_reason,
            changed_by=str(changed_by or ""),
        )
    )
    if choice == "auto":
        s.flush()
        notices_repo.restore_stat_paid_auto(s, notice, changed_by=changed_by or current_operator(),
                                           total=effective_total_of(s, notice.id))
    # ⭐ 撤销后同样重算（§4.4.5 / §4.4.7）—— 漏了会出「撤销了但欠款没变」
    if flow.notice_id is not None:
        sync_stat_paid(s, int(flow.notice_id))
    return {"flow_id": flow.id, "status": flow.status, "reason": flow.revoke_reason}


# ---------------------------------------------------------------- §4.4.7 重算（**唯一出口**）


def effective_total_of(s: Session, notice_id: int) -> Decimal:
    """该通知书**有效流水**的金额汇总（撤销的不算）—— 「已付金额」的唯一定义。

    ⚠️ 归属**双保险**：SQL 已按 `notice_id` 过滤，这里再按字段过一遍 ——
       让"已付金额只认本单流水"这条在**任何会话实现**（含离线桩）下都成立。
    """
    rows = list_flows_of_notice(s, int(notice_id))
    mine = [f for f in rows if int(f.notice_id or 0) == int(notice_id)]
    return effective_total([{"status": f.status, "amount": f.amount} for f in mine])


def sync_stat_paid(s: Session, notice_id: int) -> Decimal | None:
    """⭐ **「统计付款金额」的重算 —— 全工程唯一出口**（§4.4.7）。

    规则：
    - **未被人工改过**（无留痕）⇒ `stat_paid` = 该通知书的**有效流水汇总**；
    - **当前人工覆盖生效** ⇒ 保留人工值；最后状态事件为恢复自动时继续跟随流水；
    - ⚠️ **流水驱动写入不受"手改拦截"约束、也不封顶** —— 实付 > 审批金额是既成事实，
      照实写入并由调用侧挂提醒（§4.4.6；与 §4.4.4「付款动作禁止超付」不冲突）。

    ⚠️ 由 **付款**（`create_flow`）· **撤销**（`revoke`）· **历史导入**（`commit_plan`）·
       **撤销付款**后统一调用 —— ⛔ 不得在别处再算一遍。
    """
    from app.mod03_notice import service as notices_service    # 延迟导入，避免环；⭐ 包间出口（§2.3）
    from app.mod03_notice.domain import F_STAT_PAID, was_manually_edited

    notice = notices_service.get_notice(s, int(notice_id), with_for_update={"key_share": True}, populate_existing=True)
    if notice is None:
        return None
    traces = notices_service.list_stat_traces(s, int(notice_id))  # 留痕 = 「是否手改」的唯一事实来源
    if was_manually_edited(traces, int(notice_id), F_STAT_PAID):
        return to_money(notice.stat_paid)                 # 保护人工值（§4.2.5）
    total = effective_total_of(s, int(notice_id))
    notice.stat_paid = total          # 对象来自同会话通知书出口 ⇒ 本就是 persistent，无需 add
    s.flush()
    return total


# ---------------------------------------------------------------- §4.4.6 导入批次


# ---------------------------------------------------------------- 期初占位行


def list_openings(
    s: Session, *, project_id: int | None = None, category: str | None = None
) -> list[OpeningBalance]:
    """期初占位行（手填；**按其分类并入辅材 / 机械**，§4.5.1 / §4.5.2）。"""
    stmt = select(OpeningBalance).order_by(OpeningBalance.cutoff_ym.asc(), OpeningBalance.id.asc())
    if project_id is not None:
        stmt = stmt.where(OpeningBalance.project_id == int(project_id))
    if category:
        stmt = stmt.where(OpeningBalance.category == category)
    return list(s.execute(stmt).scalars().all())


def get_opening(s: Session, opening_id: int) -> OpeningBalance | None:
    return s.get(OpeningBalance, int(opening_id))


def upsert_opening(
    s: Session,
    *,
    category: str,
    project_id: int,
    cutoff_ym: str,
    settle_amount,
    paid_amount,
    remark: str = "",
) -> OpeningBalance:
    """录入 / 覆盖**期初占位行**。

    「口径 + 项目 + 截止年月」三者为同一行（重复录入 = 覆盖，不产生第二行）——
    与 `ledger_remark` 的唯一键同构（都是「同一格子只存一个值」）。
    """
    row = s.execute(
        select(OpeningBalance).where(
            OpeningBalance.category == category,
            OpeningBalance.project_id == int(project_id),
            OpeningBalance.cutoff_ym == str(cutoff_ym or ""),
        )
    ).scalars().first()
    if row is None:
        row = OpeningBalance(category=category, project_id=int(project_id), cutoff_ym=str(cutoff_ym or ""))
        s.add(row)
    row.settle_amount = to_money(settle_amount or 0)
    row.paid_amount = to_money(paid_amount or 0)
    row.remark = str(remark or "")
    s.flush()
    return row


def delete_opening(s: Session, opening_id: int) -> int:
    """删除一条期初占位行（**只删该行**）—— 用 ORM 删除，不走 `sa_delete`（薄层更好测）。"""
    row = s.get(OpeningBalance, int(opening_id))
    if row is None:
        return 0
    s.delete(row)
    return 1


# ---------------------------------------------------------------- 台账备注


def remarks_map(s: Session, *, category: str, project_id: int) -> dict[str, str]:
    """台账备注 `{月: 备注}`（键 = 口径 + 项目 + 月，§4.5.4）。"""
    rows = s.execute(
        select(LedgerRemark).where(
            LedgerRemark.category == category, LedgerRemark.project_id == int(project_id)
        )
    ).scalars().all()
    return {str(r.ym): str(r.remark or "") for r in rows}


def set_remark(s: Session, *, category: str, project_id: int, ym: str, remark: str) -> str:
    """写 / 清一条台账备注（**空串 = 清除该格**，但保留行、不产生垃圾行）。"""
    row = s.execute(
        select(LedgerRemark).where(
            LedgerRemark.category == category,
            LedgerRemark.project_id == int(project_id),
            LedgerRemark.ym == str(ym or ""),
        )
    ).scalars().first()
    text = str(remark or "")
    if row is None:
        if not text:
            return text                       # 本来就没有、又传空 ⇒ 什么都不做
        row = LedgerRemark(category=category, project_id=int(project_id), ym=str(ym or ""))
        s.add(row)
    row.remark = text
    s.flush()
    return text


# ---------------------------------------------------------------- 通知书行（欠款 / 台账 / 统计的输入）


def notice_rows(s: Session) -> list[PaymentNotice]:
    """付款通知书行 —— `NoticeDebtView` 的来源（欠款 / 台账 / 统计**共用同一批行**）。"""
    from app.mod03_notice import service as notices
    return notices.all_notice_rows(s)


def debt_notice_rows(s: Session):
    from app.mod03_notice import service as notices
    return notices.debt_notice_rows(s)


__all__ = [
    "list_flows", "get_flow", "list_flows_of_notice", "next_flow_no", "has_request_id",
    "create_flow", "revoke", "revoke_info",
    "effective_total_of", "sync_stat_paid",
    "latest_effective_dates",

    "FLOW_SOURCE_MANUAL", "FLOW_SOURCE_IMPORTED", "FLOW_EFFECTIVE", "FLOW_REVOKED",
    "list_openings", "get_opening", "upsert_opening", "delete_opening",
    "remarks_map", "set_remark", "notice_rows", "debt_notice_rows",
]


def revoke_info(s: Session, flow: PaymentFlow) -> dict:
    """撤销窗口的当前模式和事实快照；提交时在行锁内重读比对。"""
    from hashlib import sha256
    from app.mod03_notice import domain as notices_domain, service as notices_repo
    notice = notices_repo.get_notice(s, int(flow.notice_id)) if flow.notice_id is not None else None
    traces = notices_repo.list_stat_traces(s, notice.id) if notice else []
    facts = (flow.id, flow.notice_id, flow.project_id, str(flow.amount), flow.pay_date,
             flow.pay_method, flow.remark, flow.status, str(notice.stat_paid) if notice else None,
             [(t.field, str(t.before), str(t.after), t.changed_at.isoformat()) for t in traces])
    return {"manual": bool(notice and notices_domain.stat_paid_is_manual(traces, notice.id)),
            "notice_id": flow.notice_id, "expected": sha256(repr(facts).encode()).hexdigest()}


def latest_effective_dates(s: Session, notice_ids: list[int]) -> dict[int, str]:
    """一批通知书的最近生效流水日期；撤销流水不参与。"""
    from sqlalchemy import func
    if not notice_ids:
        return {}
    stmt = select(PaymentFlow.notice_id, func.max(PaymentFlow.pay_date)).where(
        PaymentFlow.notice_id.in_(notice_ids), PaymentFlow.status == FLOW_EFFECTIVE
    ).group_by(PaymentFlow.notice_id)
    return {int(nid): str(at or "") for nid, at in s.execute(stmt).all()}
