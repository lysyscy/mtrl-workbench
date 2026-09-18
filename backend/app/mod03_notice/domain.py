"""付款通知书域内核（`MOD-03` · **纯函数**）—— 四金额 · 统计手改 · 付款核验。

依据：
- 《说明书》§4.2.5（四个金额字段 + 两统计字段「上限 = 审批金额」）· §4.2.6（手动行）· §4.2.7（再次导入的合并）
- §4.4.1（能不能付款：**唯一自动核验项 = 已批**）· §4.4.4（批量付款：前置禁用 · 逐行移出 · 兜底整批重算）
- §4.5.3（统计金额手改：上限拦截 · 留痕 · 欠款实时重算）· §9.1（金额口径）· §9.3（留痕范围）

⚠️ **本模块只做纯函数**（不算、不落库）：落库与路由由 `repository` / `router` 承担（同一 `MOD-03` 包内）。
⚠️ 金额一律经 `core.money`（全站唯一出口），**不得**自写 Decimal 量化。
⚠️ 欠款重算**复用 `mod05_flow.domain.debt_by_category`**（同一个出口）—— 不得另写一套欠款算法（副本必然漂移）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import MoneyError, require_non_negative, to_money
from app.mod05_flow.domain import NoticeDebtView, OpeningView, debt_by_category
from app.mod05_flow.models import PAY_METHODS

_ZERO = to_money(0)

# ============================================================ 未命中清单的「新鲜度」（`TAIL-41`）


def still_unsettled(items, projects, *, resolve=None) -> list[dict]:
    """把「未命中清单」按**当前档案现算**，**丢掉已经走完的那些**（`TAIL-41`）。

    **为什么需要**：清单是**当时那一刻的判定**（存在那次抓取的运行记录里）；而用户拿到清单之后
    会去**补关键词 / 建小微** —— 补完之后那些行**已经能归属了**，若清单照旧摆着，用户就会
    对着**已经解决**的清单白干一场（甚至把关键词塞到别的壳下 ⇒ 往档案里塞错行）。

    ⚠️ 判定**复用链路 C 的同一个出口** `resolve_ownership`（⛔ 不在这里另写一份"够不够格"）；
    ⚠️ `resolve=` 只为测试注入，生产一律用默认的那个。
    """
    from app.mod01_projects.domain import resolve_ownership       # 局部 import：本模块保持"纯函数 + 零环"
    resolve = resolve or resolve_ownership
    out: list[dict] = []
    for it in items or ():
        d = resolve(
            name_full=str(it.get("project_name") or ""),
            doc_name=str(it.get("doc_name") or ""),
            projects=projects,
        )
        if not getattr(d, "settled", False):
            out.append(it)
    return out

# ============================================================ §4.2.5 三个金额字段

F_APPROVED = "amount_approved"     # 审批金额（i8 源；只读、不被人工改覆盖）
F_STAT_SETTLE = "stat_settle"      # 统计结算金额（**旁路**；可手改、留痕）
F_STAT_PAID = "stat_paid"          # 统计付款金额（**旁路**；可手改、留痕）

DERIVED_PAY = "pay_amount"         # 列表「付款金额」= 派生默认值 + 会话级覆盖（**不属于那三个**）

SOURCE_FIELDS: tuple[str, ...] = (F_APPROVED,)   # ★ 唯一 i8 源字段（原「付款金额（源）」已取消）
STAT_FIELDS: tuple[str, ...] = (F_STAT_SETTLE, F_STAT_PAID)
THREE_AMOUNT_FIELDS: tuple[str, ...] = SOURCE_FIELDS + STAT_FIELDS

STAT_LABELS: dict[str, str] = {
    F_STAT_SETTLE: "统计结算金额",
    F_STAT_PAID: "统计付款金额",
}


def derived_pay_amount(approved, paid_total) -> Decimal:
    """列表上的「付款金额」= **审批金额 − 已付金额**（§4.2.5）。

    ⚠️ 它**不属于那三个金额**：可临时改（会话级覆盖、刷新恢复默认）、**不落库**、
       也**不参与欠款计算**（欠款只认两个统计旁路字段）。
    """
    return to_money(to_money(approved) - to_money(paid_total))


def default_stat_value(field: str, *, approved, paid_total) -> Decimal:
    """两个统计旁路字段的**默认值**（§4.2.5 表 · §4.4.7）：

    · 统计结算金额 = **审批金额**（i8 源）；
    · ⭐ 统计付款金额 = **已付金额**（该通知书**有效付款流水的金额汇总**）
      —— 2026-09-16 起（原「= 付款金额（源）」，该字段已取消）。
    """
    if field == F_STAT_SETTLE:
        return to_money(approved)
    if field == F_STAT_PAID:
        return to_money(paid_total)
    raise MustReportError(
        f"「{field}」不是统计旁路字段 —— 可手改的只有统计结算金额 / 统计付款金额（§4.2.5）"
    )


# ============================================================ §4.5.3 统计金额手改


@dataclass
class StatTrace:
    """统计金额手改**留痕**（§9.3：改前值 / 改后值 / 改动人 / 时间）。

    ⚠️ 它同时是「**是否手改**」的**唯一事实来源**（§4.2.7）—— 不另开状态位（副本必然静默过期）。
    """

    notice_id: int
    field: str
    before: Decimal
    after: Decimal
    changed_by: str
    changed_at: datetime
    note: str = ""

    @property
    def label(self) -> str:
        return STAT_LABELS.get(self.field, self.field)


def adjust_stat(
    *,
    notice_id: int,
    field: str,
    value: object,
    approved: object,
    before: object,
    changed_by: str,
    at: datetime | None = None,
    note: str = "",
) -> StatTrace | None:
    """手改一个统计金额（§4.5.3）—— 返回留痕；**该改的四种拒绝情形一律显式报出**。

    规则（**全部是硬拦截，不是提示**）：
    1. 只允许改 `STAT_FIELDS`（源字段 / 派生列一律不可改）；
    2. **非法金额**（空 / 非数 / 负数）⇒ 拒绝，**原值不变**；
    3. **上限 = 审批金额** ⇒ 超额**拦截并保留原值**（不截断、不静默改写；判定容差 0，等于上限不算超）；
    4. **值没变就不动** ⇒ 返回 `None`（不产生无意义的留痕，§4.2.7）。

    ⚠️ 单次调用**只动一个字段**、只产出**一条**留痕 ⇒ 天生**无隐式副作用**（改一个不带另一个，`DEV-P-03`）。
    """
    if field not in STAT_FIELDS:
        raise MustReportError(
            f"「{field}」不可手改 —— 只有统计结算金额 / 统计付款金额是旁路字段（§4.2.5）"
        )
    label = STAT_LABELS[field]
    try:
        new = require_non_negative(value, field=label)
    except MoneyError as exc:
        raise MustReportError(f"{label}输入不合法（{exc}）—— 已保留原值") from exc

    cap = to_money(approved)
    if new > cap:
        raise MustReportError(
            f"{label}不能超过审批金额 {cap}（按发票走，只能往下调、不能多付）—— 已保留原值"
        )

    old = to_money(before)
    if new == old:
        return None

    return StatTrace(
        notice_id=int(notice_id),
        field=field,
        before=old,
        after=new,
        changed_by=changed_by,
        changed_at=at or datetime.now(),
        note=note or "手工调整（旁路字段）",
    )


def manual_edited_fields(traces: list[StatTrace] | tuple | None, notice_id: int) -> tuple[str, ...]:
    """该行**已被人工手改过**的统计字段（判据 = **留痕**，§4.2.7）。两个字段**各判各的**。"""
    edited = {
        t.field
        for t in (traces or ())
        if t is not None and int(t.notice_id) == int(notice_id) and t.field in STAT_FIELDS
    }
    return tuple(f for f in STAT_FIELDS if f in edited)


def was_manually_edited(traces: list[StatTrace] | tuple | None, notice_id: int, field: str) -> bool:
    """该字段是否被人工手改过 —— **唯一事实来源 = 留痕**（§4.2.7）。"""
    return field in manual_edited_fields(traces, notice_id)


def stat_value_on_reimport(
    *,
    field: str,
    current: object,
    approved_new: object,
    traces: list[StatTrace] | tuple | None,
    notice_id: int,
) -> Decimal:
    """**再次导入**时该统计字段取何值（§4.2.7）：

    - **未手改过**（无留痕）⇒ **跟随**新审批金额
    - **手改过**（有留痕）⇒ **保留人工值**（哪怕已越界也**只提醒、绝不代替用户改写**）
    """
    if was_manually_edited(traces, notice_id, field):
        return to_money(current)
    return to_money(approved_new)


def apply_trace(view: NoticeDebtView, trace: StatTrace | None) -> NoticeDebtView:
    """把一次手改落到通知书视图上 —— **只动被改的那一个字段**（无隐式副作用，`DEV-P-03`）。"""
    if trace is None:
        return view
    if trace.field == F_STAT_SETTLE:
        return replace(view, settle_stat=trace.after)
    if trace.field == F_STAT_PAID:
        return replace(view, pay_stat=trace.after)
    raise MustReportError(f"「{trace.field}」不是统计旁路字段，无法落到欠款视图上")


def recompute_debt(
    rows: list[NoticeDebtView],
    openings: list[OpeningView] | None = None,
    *,
    mech_settle_total: Decimal = _ZERO,
    jc_debt: Decimal | None = None,
) -> dict[str, Decimal]:
    """手改后**欠款实时重算**（§4.5.3）—— **复用欠款统计的同一个出口**，不得另写一套算法。"""
    return debt_by_category(
        rows, openings or [], mech_settle_total=mech_settle_total, jc_debt=jc_debt
    )


# ============================================================ §4.4.1 能不能付款（唯一核验项）

APPROVE_STATUS_DONE = "已批"          # §4.4.1：唯一需要系统识别的审批状态字面量
# ⚠️ **核验项只剩 1 项**：发票核验、集采「先付款特例」均**不做**（`DEV-P-06`）。
VERIFY_ITEMS: tuple[str, ...] = ("approve_status",)

BLOCK_STATUS = "approve_status"        # 不可付原因①：审批状态非「已批」
BLOCK_NOTHING_DUE = "nothing_due"      # 不可付原因②：本次应付 ≤ 0（前置状态，不是核验项）


@dataclass
class PayRow:
    """批量付款的**行视图**（只带判定所需字段；真实模型见 `models.PaymentNotice`）。"""

    notice_id: int
    approve_status: str = ""
    payable: Decimal = _ZERO           # 本次应付 = 列表「付款金额」（默认=审批金额−已付，可会话级覆盖）

    def block(self) -> str | None:
        """不可付原因（`None` = 可付）。"""
        if str(self.approve_status or "").strip() != APPROVE_STATUS_DONE:
            return BLOCK_STATUS
        if to_money(self.payable) <= _ZERO:
            return BLOCK_NOTHING_DUE
        return None

    @property
    def label(self) -> str:
        reason = self.block()
        if reason == BLOCK_STATUS:
            return f"审批状态「{self.approve_status or '（空）'}」非「{APPROVE_STATUS_DONE}」"
        if reason == BLOCK_NOTHING_DUE:
            return "本次应付为 0（审批金额 − 已付金额）"
        return ""


def verify_row(row: PayRow) -> str | None:
    """单行核验（§4.4.1）：唯一自动核验项 = 审批状态「已批」；另附前置状态「本次应付 > 0」。"""
    return row.block()


@dataclass
class BatchCheck:
    """批量付款的前置状态（§4.4.4）—— **禁用 + 原因 + 解除方式**三件套。"""

    enabled: bool
    blocked: list[PayRow] = field(default_factory=list)
    reason: str = ""
    how_to_fix: str = ""

    @property
    def blocked_ids(self) -> list[int]:
        return [r.notice_id for r in self.blocked]


def check_batch(rows: list[PayRow]) -> BatchCheck:
    """存在不可付行 ⇒ 「确认付款」**直接禁用**（**不是点了才拦**）并说明原因与解决路径（§4.4.4）。"""
    blocked = [r for r in rows if r.block() is not None]
    if not blocked:
        return BatchCheck(enabled=True, blocked=[])
    kinds: list[str] = []
    for r in blocked:
        if r.label not in kinds:
            kinds.append(r.label)
    return BatchCheck(
        enabled=False,
        blocked=blocked,
        reason=f"有 {len(blocked)} 条不可付：" + "；".join(kinds) + " —— 不可付的行不得进入本次付款。",
        how_to_fix=(
            "请点该行的「删除」把它移出本次付款（**同时取消该行勾选**，已填的付款方式与金额不会丢），"
            "或关闭后调整勾选。"
        ),
    )


# ============================================================ §4.4.4 批量付款


@dataclass
class PayDraft:
    """批量窗口里的**行草稿**（付款方式 / 本次付款金额）—— 重建窗口时**不丢已填值**。"""

    pay_method: str = "现汇"           # 默认兜底「现汇」（§4.4.2）
    amount: Decimal | None = None      # `None` = 未手改 ⇒ 取「本次应付」


def remove_from_batch(
    rows: list[PayRow], drafts: dict, notice_id: int
) -> tuple[list[PayRow], dict]:
    """把某行**移出本次付款**（§4.4.4）：同步取消该行勾选、清掉它的草稿。

    ⚠️ **其它行已填的付款方式 / 金额一并返回、一个不动**（移出 / 重绘不得丢值）。
    """
    left = [r for r in rows if int(r.notice_id) != int(notice_id)]
    left_drafts = {k: v for k, v in (drafts or {}).items() if int(k) != int(notice_id)}
    return left, left_drafts


@dataclass
class ConfirmResult:
    flows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.flows)


def confirm_batch(
    rows: list[PayRow], drafts: dict, *, pay_date: str = "", remark: str = ""
) -> ConfirmResult:
    """提交时的**兜底校验**（§4.4.4）：**整批重算**，任一校验不过 ⇒ **整批不产生任何流水**（不落半批）。

    禁用是**预防**、校验是**兜底** —— 两者都要有（防"勾上之后才被改成不可付"这类状态错位）。
    """
    drafts = drafts or {}
    flows: list[dict] = []
    errors: list[str] = []

    for row in rows:
        reason = row.block()
        if reason is not None:
            errors.append(f"{row.notice_id} · {row.label}，不可付款")
            continue

        draft = drafts.get(row.notice_id) or drafts.get(str(row.notice_id)) or PayDraft()
        amount = to_money(draft.amount) if draft.amount is not None else to_money(row.payable)
        cap = to_money(row.payable)
        if amount <= _ZERO:
            errors.append(f"{row.notice_id} · 本次付款金额必须大于 0")
            continue
        if amount > cap:
            errors.append(f"{row.notice_id} · 本次 {amount} 超出本次应付 {cap}")
            continue

        method = str(draft.pay_method or "").strip()
        if method not in PAY_METHODS:
            errors.append(f"{row.notice_id} · 实际付款方式非法：{method or '（空）'}")
            continue
        if method == "其他" and not (remark or "").strip():
            errors.append(f"{row.notice_id} · 付款方式选「其他」必须填备注")
            continue

        flows.append(
            {
                "notice_id": row.notice_id,
                "amount": amount,
                "pay_method": method,
                "pay_date": pay_date,
            }
        )

    if errors:
        return ConfirmResult(flows=[], errors=errors)      # **不落半批**
    return ConfirmResult(flows=flows, errors=[])


__all__ = [
    "F_APPROVED", "F_PAY_SRC", "F_STAT_SETTLE", "F_STAT_PAID", "DERIVED_PAY",
    "SOURCE_FIELDS", "STAT_FIELDS", "THREE_AMOUNT_FIELDS", "STAT_LABELS",
    "derived_pay_amount", "default_stat_value",
    "StatTrace", "adjust_stat", "manual_edited_fields", "was_manually_edited",
    "stat_value_on_reimport", "apply_trace", "recompute_debt",
    "APPROVE_STATUS_DONE", "VERIFY_ITEMS", "BLOCK_STATUS", "BLOCK_NOTHING_DUE",
    "PayRow", "BatchCheck", "verify_row", "check_batch",
    "PayDraft", "remove_from_batch", "ConfirmResult", "confirm_batch",
]
