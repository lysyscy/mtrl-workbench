"""付款通知书 / 运行记录 仓储（切片 1 最小）。

依据：
- 工程坑 1.2-5：schema 经迁移；**落库走 ORM**，不手建表。
- 幂等：取数按 `ph_id` upsert（再次导入合并，§9.5）。
- 运行记录属**技术台账**，不参与业务统计。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod02_i8.models import RunRecord
from app.mod02_i8.repository import (  # noqa: F401  ← 运行记录仓储归 MOD-02，此处再导出
    create_run_record,
    finish_run_record,
)
from app.mod03_notice.domain import StatTrace, adjust_stat
from app.mod03_notice.models import NoticeStatLog, PaymentNotice


def get_notice(session: Session, notice_id: int) -> PaymentNotice | None:
    return session.get(PaymentNotice, notice_id)


#: 运行记录 `detail` 里的「**这是付款通知书抓取**」标记 —— 读侧靠它认"最近一次"（⛔ 不靠 `target` 猜）
FETCH_MARK = "notice_fetch"

#: 找"最近一次付款通知书抓取"时**最多回看**多少条运行记录（技术台账，量很小；够用即可）
LOOKBACK = 50


def fetch_detail(**extra) -> dict:
    """付款通知书抓取**每条运行记录**的 `detail`（**写侧唯一出口**）：一律带标记 ＋ 本次的附加字段。

    ⚠️ **三种结局都必须写**（i8 取数失败 / 归属未走完 / 抓取成功）—— 漏掉任何一条，
       "最近一次"就指不住，读侧会掉回**更早**的记录 ⇒ 那正是 `TAIL-41`：
       **抓取成功之后仍摆着上一次的未命中清单**，用户对着已解决的清单白干。
    """
    return {FETCH_MARK: True, **extra}


def latest_unresolved(session: Session) -> list[dict]:
    """**最近一次付款通知书抓取**带的**未命中清单**（`TAIL-29`-② 弹窗的数据源）。

    ⚠️⚠️ **只认最近一次**（`TAIL-41` 修复 · 2026-09-18）：原先**回溯 20 条** `run_type=fetch`、
       取最新一条 `reason=ownership_unsettled` 的 —— 那条记录会**长期留着** ⇒ 抓取**成功之后**
       仍可能把它当"当前待办"（用户白干一场，还可能往档案里塞错行）。
       现在只认「**最近一条带 `notice_fetch` 标记的记录**」：它**不是**未走完 ⇒ **没有清单**
       （⛔ 不回溯更早的记录；材料侧的 `pending.latest_pending` 是同一条口径）。
    ⚠️ 清单里存的是**当时的判定** ⇒ 调用方必须按**当前档案现算**（`domain.still_unsettled`）。
    ⛔ 这里**不涉及任何暂存**（用户裁定 `B`：补完词**再抓一次**，不在库里留半成品）。
    """
    recs = list(session.execute(
        select(RunRecord)
        .where(RunRecord.run_type == "fetch")
        .order_by(RunRecord.id.desc())
        .limit(LOOKBACK)
    ).scalars().all())
    # ⚠️ 离线桩（`tests.m09_helpers.M09Session`）**不处理 `order_by`** ⇒ 再显式按 id 倒序一次
    #    （真库本来就有序 ⇒ 语义不变，只是让断言与真机走同一条路）。
    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):
        detail = getattr(r, "detail", None) or {}
        if not isinstance(detail, dict) or not detail.get(FETCH_MARK):
            continue                       # 不是付款通知书抓取的记录（材料侧 / 手工抓取）⇒ 跳过
        if detail.get("reason") != "ownership_unsettled":
            return []                      # ⭐ 最近一次**已走完** ⇒ 没有清单（⛔ 不回溯更早的）
        return list(detail.get("unresolved") or [])
    return []


def get_notice_by_ph_id(session: Session, ph_id: str) -> PaymentNotice | None:
    """按 i8 主键找现有行 —— **再次导入合并（§4.2.7）的入口**。"""
    return session.execute(
        select(PaymentNotice).where(PaymentNotice.ph_id == str(ph_id))
    ).scalar_one_or_none()


def notice_as_dict(notice: PaymentNotice) -> dict:
    """ORM 行 → 普通字典（供 `merge.plan_merge()` 这类**纯函数**使用）。"""
    return {c.name: getattr(notice, c.name) for c in notice.__table__.columns}


def list_stat_traces(session: Session, notice_id: int) -> list[StatTrace]:
    """读该通知书的**统计手改留痕** —— §4.2.7 的「判据 = 留痕」就靠这个事实来源。

    ⚠️ 不留任何"是否手改"的开关位：留痕本就是既有事实，另开状态位等于同一件事存两份（副本必然过期）。
    """
    rows = session.execute(
        select(NoticeStatLog)
        .where(NoticeStatLog.notice_id == int(notice_id))
        .order_by(NoticeStatLog.changed_at)
    ).scalars().all()
    return [
        StatTrace(
            notice_id=r.notice_id, field=r.field, before=r.before_amount, after=r.after_amount,
            changed_by=r.changed_by, changed_at=r.changed_at, note=r.note,
        )
        for r in rows
    ]


def add_stat_trace(session: Session, trace: StatTrace) -> NoticeStatLog:
    """写一条统计手改留痕（能力 11「统计金额可手动调整」的落库侧）。"""
    row = NoticeStatLog(
        notice_id=int(trace.notice_id), field=trace.field, before_amount=trace.before,
        after_amount=trace.after, changed_by=trace.changed_by, changed_at=trace.changed_at,
        note=trace.note,
    )
    session.add(row)
    session.flush()
    return row


def stat_trace_index(session: Session) -> dict[int, list[StatTrace]]:
    """**一次查完**全部统计手改留痕，按通知书分组（`notice_id -> [StatTrace]`）。

    ⚠️ 供列表页判「这两格有没有被手改过」（R8 的"已改"态）—— **不得逐行查**（那是 N+1，工程底线一票否决）。
    """
    rows = session.execute(
        select(NoticeStatLog).order_by(NoticeStatLog.changed_at)
    ).scalars().all()
    out: dict[int, list[StatTrace]] = {}
    for r in rows:
        out.setdefault(int(r.notice_id), []).append(
            StatTrace(
                notice_id=r.notice_id, field=r.field, before=r.before_amount, after=r.after_amount,
                changed_by=r.changed_by, changed_at=r.changed_at, note=r.note,
            )
        )
    return out


def adjust_notice_stat(
    session: Session,
    notice: PaymentNotice,
    *,
    field: str,
    value: object,
    changed_by: str,
    note: str = "",
) -> StatTrace | None:
    """**统计金额手改**（§4.5.3）—— 判定走 `domain.adjust_stat`，本层只落"值 + 留痕"这两件事。

    返回 `None` 表示**值没变、什么都没做**（§4.2.7：不做无意义的重算，也不产生空留痕）。
    四种拒绝（非法金额 / 非旁路字段 / 超上限 / 值没变）里前三种由 `adjust_stat` **显式抛出**。
    """
    trace = adjust_stat(
        notice_id=int(notice.id),
        field=field,
        value=value,
        approved=notice.amount_approved,
        before=getattr(notice, field),
        changed_by=changed_by,
        note=note,
    )
    if trace is None:
        return None
    setattr(notice, field, trace.after)
    add_stat_trace(session, trace)
    session.flush()
    return trace


def get_notices_by_ids(session: Session, ids: list[int]) -> list[PaymentNotice]:
    if not ids:
        return []
    return list(session.execute(select(PaymentNotice).where(PaymentNotice.id.in_(ids))).scalars().all())


# ---------------------------------------------------------------- 行级动作（能力 2 / 3 / 4）

# 手动行**编辑**时允许改动的列（§4.2.6「一切信息都可以手动修改」；归属 / 分类 / 金额都可改）
MANUAL_EDITABLE_FIELDS: tuple[str, ...] = (
    "bill_no", "doc_date", "project_name", "biz_type", "payee",
    "category", "amount_approved", "stat_paid", "ownership_id", "fields",
)


def notices_as_dicts(session: Session, *, ids: list[int] | None = None) -> list[dict]:
    """行 → 普通字典列表（供 `notice_actions` 这类**纯函数**使用）。"""
    rows = get_notices_by_ids(session, ids) if ids else notice_rows(session)
    return [notice_as_dict(r) for r in rows]


def apply_category(session: Session, ids: list[int], category: str) -> int:
    """把勾选行的分类改为指定值 —— 返回**实际改动**的行数（原值相同的不计）。

    ⚠️ 手改分类**不留痕**（§9.3 ❌ 清单），且**不被再次抓取覆盖**（`merge.PROTECTED`，§4.2.4）。
    ⚠️ 写操作**按 id 定位**（§9.8.2-5）：即便取数层多给了行，也只动 `ids` 集合内的。
    """
    want = {int(i) for i in ids or []}
    if not want:
        return 0
    changed = 0
    for row in get_notices_by_ids(session, ids):
        if int(row.id) not in want:
            continue
        if str(row.category or "").strip() != category:
            row.category = category
            changed += 1
    session.flush()
    return changed


def set_excluded(session: Session, ids: list[int], *, excluded: bool, source: str) -> int:
    """写剔除标记（人工批量剔除 / 恢复）—— 返回实际改动的行数。

    ⚠️ 撤销剔除时 `source` 用 `EXCLUDE_NONE`（**只放开人工剔除**的判定在 `classify.restore_excluded`）。
    """
    want = {int(i) for i in ids or []}
    if not want:
        return 0
    changed = 0
    for row in get_notices_by_ids(session, list(want)):
        if int(row.id) not in want:
            continue
        if bool(row.excluded) != bool(excluded) or str(row.exclude_source or "") != str(source or ""):
            row.excluded = bool(excluded)
            row.exclude_source = str(source or "")
            changed += 1
    session.flush()
    return changed


def create_manual_notice(session: Session, values: dict) -> PaymentNotice:
    """落一条**手动新增**付款通知书行（字段由 `notice_actions.manual_row_payload` 组装）。"""
    row = PaymentNotice(**values)
    session.add(row)
    session.flush()
    return row


def update_manual_notice(session: Session, notice: PaymentNotice, values: dict) -> list[str]:
    """改一条手动行（§4.2.6：编辑入口与新增**共用同一套**）—— 返回被改动的列名。"""
    touched: list[str] = []
    for key, value in (values or {}).items():
        if key not in MANUAL_EDITABLE_FIELDS or not hasattr(notice, key):
            continue
        if getattr(notice, key) != value:
            setattr(notice, key, value)
            touched.append(key)
    session.flush()
    return touched


def delete_notice(session: Session, notice: PaymentNotice) -> int:
    """删除一条**手动行** —— 只删该行（调用方须先过 `notice_actions.assert_manual_editable`）。

    ⚠️ i8 抓取回来的行**永不删**（§4.2.7 明确"不提供删除付款通知书按钮"）；
       本函数只服务手动行（人工补录的数据，删除 = 撤回自己的录入，欠款随取数实时重算）。
    """
    session.delete(notice)
    return 1


def list_notices(session: Session, *, bill_type: str | None = None, limit: int = 200) -> list[PaymentNotice]:
    stmt = select(PaymentNotice)
    if bill_type:
        stmt = stmt.where(PaymentNotice.bill_type == bill_type)
    return list(session.execute(stmt.limit(limit)).scalars().all())


def notice_rows(session: Session, *, limit: int = 5000) -> list[PaymentNotice]:
    """全部通知书行（按单据日期倒序）—— **列表页的取数出口**（剔除/撤单行**也返回**）。

    ⚠️ 剔除与撤单行的「默认隐藏」是**筛选层**的事（`list_view.filter_rows`），不是取数层 ——
       取数层必须给全，否则计数与「分类 = 剔除」视图都算不出来。
    """
    stmt = select(PaymentNotice).order_by(PaymentNotice.doc_date.desc(), PaymentNotice.id.desc())
    return list(session.execute(stmt.limit(limit)).scalars().all())


def upsert_notice(session: Session, *, ph_id: str, **fields) -> PaymentNotice:
    """按 `ph_id` 幂等 upsert。再次导入只覆盖自动字段（切片 1 无手动行，整行可覆盖）。"""
    existing = session.execute(
        select(PaymentNotice).where(PaymentNotice.ph_id == ph_id)
    ).scalar_one_or_none()
    if existing is None:
        existing = PaymentNotice(ph_id=ph_id)
        session.add(existing)
    for key, value in fields.items():
        if hasattr(existing, key):
            setattr(existing, key, value)
    existing.fetched_at = datetime.now()
    session.flush()
    return existing


# ⚠️ 运行记录（RunRecord）的读写已归 MOD-02（`app.mod02_i8.repository`），
#    本文件顶部已**再导出** `create_run_record` / `finish_run_record`，调用方无需改。

