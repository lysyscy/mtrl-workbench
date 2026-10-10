"""付款流水 / 付款统计 / 欠款统计 / 逐月台账 域内核（**纯函数**）。

依据：《说明书》§4.2.3（分类三类）· §4.4.2（付款状态两态 / 一次付款一条流水）· §4.4.5（撤销必填原因）
      · §4.5.1（欠款三类口径）· §4.5.2（期初占位行）· §4.5.4（逐月台账）· §4.5.5（实际付款统计）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod05_flow.models import (
    CATEGORY_JC,
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    FLOW_EFFECTIVE,
    FLOW_REVOKED,
    PAY_STATUS_PAID,
    PAY_STATUS_UNPAID,
)

_ZERO = to_money(0)

# ============================================================ §4.2.3 分类

BIZ_TYPE_LEASE = "付设备租赁款"
PAYEE_JC = "资产处集中采购"


def classify(biz_type: str, payee: str) -> str:
    """分类（§4.2.3，**只有三类**）：① 付设备租赁款 → 机械；② 收付单位=资产处集中采购 → 集采；③ 否则 → 辅材。"""
    if (biz_type or "").strip() == BIZ_TYPE_LEASE:
        return CATEGORY_MECH
    if (payee or "").strip() == PAYEE_JC:
        return CATEGORY_JC
    return CATEGORY_MATERIAL


# ============================================================ §4.4.2 付款状态 / 流水


def payment_status(paid_total, approved) -> str:
    """付款状态（**只有两态**）：已付金额（流水汇总）≥ 审批金额 ⇒ 已付清，否则未付清。

    ⚠️ 判定基准 = **审批金额**；「统计付款金额」**不参与**状态判定（§4.4.2）。
    """
    return PAY_STATUS_PAID if to_money(paid_total) >= to_money(approved) else PAY_STATUS_UNPAID


def effective_total(flows: list[dict]) -> Decimal:
    """流水合计 —— **只算生效流水**（已撤销不计入）（LIST-001-03）。与「已付金额 = 流水汇总」同源。"""
    total = _ZERO
    for f in flows:
        if str(f.get("status") or FLOW_EFFECTIVE) == FLOW_EFFECTIVE:
            total += to_money(f.get("amount") or 0)
    return total


def revoke_flow(reason: str) -> dict:
    """撤销一条流水（§4.4.5）：**必须填撤销原因**（空 ⇒ 拦截，LIST-001-04）。

    撤销后 ⇒ 标记已撤销 + 保留原因；**已付金额回退**、付款状态按 §4.4.2 重判（LIST-001-05）。
    """
    text = (reason or "").strip()
    if not text:
        raise MustReportError("撤销必须填写原因 —— 空原因不被接受（撤销是留痕动作）")
    return {"status": FLOW_REVOKED, "revoke_reason": text, "revoked_at": datetime.now()}


def filter_flows(
    flows: list[dict],
    *,
    status: str | None = None,
    pay_method: str | None = None,
    project_id: int | None = None,
    keyword: str = "",
) -> list[dict]:
    """流水筛选（**即时生效**，LIST-001-02）：状态 / 付款方式 / 项目 / 关键词。"""
    kw = (keyword or "").strip()
    out = []
    for f in flows:
        if status and str(f.get("status") or "") != status:
            continue
        if pay_method and str(f.get("pay_method") or "") != pay_method:
            continue
        if project_id is not None and f.get("project_id") != project_id:
            continue
        if kw and kw not in str(f.get("flow_no") or "") and kw not in str(f.get("pay_date") or ""):
            continue
        out.append(f)
    return out


def default_flow_period(now: date | None = None) -> str:
    """流水默认月 = **北京时间当月**（不是「全部月份」）（LIST-001-01）。"""
    from app.core.period import default_period

    return default_period("flow", now)


# 流水列表不分页（LIST-001-01）
FLOW_PAGINATED = False


def empty_state_colspan(columns: list | tuple) -> int:
    """空态提示行的跨界数 = **表头列数**（LIST-001-06）。"""
    return len(columns)


# ============================================================ §4.5.1 / §4.5.2 欠款


@dataclass
class NoticeDebtView:
    """欠款计算用的通知书行视图（**只读口径字段**；真实模型在 `MOD-03` 扩展）。"""

    notice_id: int
    doc_date: str = ""                 # 归月依据 = 单据日期
    category: str = CATEGORY_MATERIAL
    settle_stat: Decimal = _ZERO       # 统计结算金额
    pay_stat: Decimal = _ZERO          # 统计付款金额
    excluded: bool = False             # 剔除记录**不计入欠款**
    ownership_id: int | None = None    # 归属（档案行 id）；None = 未判定


@dataclass
class OpeningView:
    """期初占位行视图（手填；**按其分类并入辅材/机械**，不单列第四类）。"""

    category: str
    project_id: int | None
    cutoff_ym: str = ""
    settle_amount: Decimal = _ZERO
    paid_amount: Decimal = _ZERO
    #: ⭐ **期初行的真 id**（2026-09-28 加）：`/api/m05/debt` 与 `/api/m05/ledger` **必须给同一个 id**
    #   —— 壳里"删除期初行"按钮在**台账行**上（拿的是 `ledger.opening_id`），而它要去 `debt.openings`
    #   那一侧找数据 ⇒ 两边对不上就**静默点不动**（实测缺陷：壳的 `adaptOpening` 曾把 id 写成 `''`）。
    opening_id: int = 0


def debt_by_category(
    rows: list[NoticeDebtView],
    openings: list[OpeningView],
    *,
    mech_settle_total: Decimal = _ZERO,
    jc_debt: Decimal | None = None,
) -> dict[str, Decimal]:
    """三类欠款（§4.5.1）—— **各按自己的口径独立复算**（DEBT-001-01）。

    - 辅材 = Σ(辅材统计结算) − Σ(辅材统计付款) **＋ 辅材期初**
    - 机械 = **机械费结算金额**（派生只读，外部注入）− Σ(机械统计付款) **＋ 机械期初**
    - 集采 = **不在本域计算**（由集采台账负责）⇒ 本域只作**合计展示**（DEBT-001-03）
    ⚠️ 期初占位行**按其分类并入**（DEBT-001-02）；**剔除记录不计入**（DEBT-001-05）。
    """
    live = [r for r in rows if not r.excluded]          # 剔除不计入（001-05）

    def _sum(cat: str, attr: str) -> Decimal:
        return sum((getattr(r, attr) for r in live if r.category == cat), _ZERO)

    def _opening(cat: str) -> Decimal:
        return sum(
            (to_money(o.settle_amount) - to_money(o.paid_amount) for o in openings if o.category == cat),
            _ZERO,
        )

    material = _sum(CATEGORY_MATERIAL, "settle_stat") - _sum(CATEGORY_MATERIAL, "pay_stat") + _opening(CATEGORY_MATERIAL)
    mech_pay = _sum(CATEGORY_MECH, "pay_stat")
    mechanical = to_money(mech_settle_total) - mech_pay + _opening(CATEGORY_MECH)
    return {
        CATEGORY_MATERIAL: material,
        CATEGORY_MECH: mechanical,
        CATEGORY_JC: to_money(jc_debt) if jc_debt is not None else _ZERO,   # 展示用，不由本域算
    }


def total_debt(by_category: dict[str, Decimal]) -> Decimal:
    """欠款合计 = 辅材 ＋ 机械 ＋ 集采（**三类**；期初已并入，不另加第四类）（DEBT-001-01/02）。"""
    return sum(by_category.values(), _ZERO)


UNASSIGNED = "__unassigned__"   # 未判定单列（不并入任何具体小微）


def debt_by_project(rows: list[NoticeDebtView]) -> dict:
    """「按项目看欠款」——**按归属归集**（DEBT-001-04）。

    - 壳全名下的行**拆到各自的具体小微**（用 `ownership_id`）
    - **未判定**的单列（`UNASSIGNED`），**不并入任何小微**
    - 剔除行不计入
    """
    out: dict = {}
    for r in rows:
        if r.excluded:
            continue
        key = r.ownership_id if r.ownership_id is not None else UNASSIGNED
        out.setdefault(key, _ZERO)
        if r.category == CATEGORY_MATERIAL:
            out[key] += r.settle_stat - r.pay_stat
        elif r.category == CATEGORY_MECH:
            out[key] += -r.pay_stat     # 机械侧结算来自过程资料，不在通知书行上
    return out


# ============================================================ §4.5.4 逐月台账


def next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y + 1:04d}-01" if m == 12 else f"{y:04d}-{m + 1:02d}"


def prev_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def months_span(start_ym: str | None, end_ym: str) -> list[str]:
    """**连续**月份列表（含首尾）。"""
    if not start_ym:
        return [end_ym]
    out, cur = [], start_ym
    while cur <= end_ym:
        out.append(cur)
        cur = next_month(cur)
    return out


@dataclass
class LedgerRow:
    seq: int
    month: str
    other_expense: Decimal = _ZERO
    payment: Decimal = _ZERO
    remark: str = ""
    is_opening: bool = False
    row_kind: str = "month"
    month_label: str = ""
    counts_in_total: bool = True

    @property
    def debt(self) -> Decimal:
        """欠款（**当月新增欠款**，不是累计）= 其他支出金额 − 付款（§4.5.4）。"""
        return self.other_expense - self.payment


def monthly_aggregate(
    rows: list[NoticeDebtView], category: str, project_id: int | None
) -> dict[str, dict]:
    """按「月 · 项目 · 分类」聚合 → `{ym: {settle, pay}}`（剔除行不计）。

    台账「其他支出金额」「付款」两列的**同源出口**（LED-001-02/03）。
    """
    out: dict[str, dict] = {}
    for r in rows:
        if r.excluded or r.category != category:
            continue
        if project_id is not None and r.ownership_id != project_id:
            continue
        ym = str(r.doc_date or "")[:7]
        if not ym:
            continue
        slot = out.setdefault(ym, {"settle": _ZERO, "pay": _ZERO})
        slot["settle"] += r.settle_stat
        slot["pay"] += r.pay_stat
    return out


def build_ledger(
    *,
    category: str,
    monthly: dict[str, dict],
    opening: OpeningView | None = None,
    mech_settle_by_month: dict[str, Decimal] | None = None,
    end_ym: str | None = None,
    remarks: dict[str, str] | None = None,
    opening_auto: Decimal | None = None,
) -> list[LedgerRow]:
    """逐月台账（`LED-001-01/02/03/04/06`）。

    - `opening_auto`给出时，历史段拆成手动、自动、合计；合计行不重复参与外层累计
    - 较晚截止月的已有期初仍保留其起点；只带本口径的期初
    - 其后从**期初次月**起**逐月连续**出行；**空月也出行**（三列记 0）
    - 「其他支出金额」：辅材 = 该月统计结算合计；**机械 = 派生只读**（`mech_settle_by_month`）
    - 「付款」：同分类的统计付款合计
    """
    remarks = remarks or {}
    rows: list[LedgerRow] = []
    seq = 1

    start_ym = None
    if opening_auto is not None:
        cutoff = "2025-11"
        manual = opening if opening is not None and opening.cutoff_ym <= cutoff else None
        settle = to_money(manual.settle_amount if manual else 0)
        paid = to_money(manual.paid_amount if manual else 0)
        auto = to_money(opening_auto)
        for kind, label, other, pay in (
            ("opening_manual", "手动", settle, paid),
            ("opening_auto", "自动", _ZERO, auto),
            ("opening_total", "合计", settle, paid + auto),
        ):
            rows.append(LedgerRow(
                seq=seq, month=cutoff, other_expense=other, payment=pay,
                is_opening=manual is not None and kind == "opening_manual",
                row_kind=kind, month_label=f"2025-11及之前 · {label}",
                counts_in_total=kind != "opening_total",
                remark=remarks.get(cutoff, "") if kind == "opening_manual" else "",
            ))
            seq += 1
        start_ym = "2025-12"
        if manual is not None:
            opening = None
    if opening is not None:
        start_ym = opening.cutoff_ym
        rows.append(
            LedgerRow(
                seq=seq,
                month=opening.cutoff_ym,
                other_expense=to_money(opening.settle_amount),
                payment=to_money(opening.paid_amount),
                remark=remarks.get(opening.cutoff_ym, ""),
                is_opening=True,
            )
        )
        seq += 1
        start_ym = next_month(opening.cutoff_ym) if opening.cutoff_ym else None

    months = [m for m in (monthly or {}).keys()]
    candidates = sorted(set(monthly or {}) | set(mech_settle_by_month or {}))
    last = end_ym or (max(candidates) if candidates else None)
    if last is None:
        return rows
    first = start_ym or (min(candidates) if candidates else last)

    for ym in months_span(first, last):
        if category == CATEGORY_MECH and mech_settle_by_month is not None:
            other = to_money(mech_settle_by_month.get(ym, 0))     # 派生只读（001-04）
        else:
            other = to_money((monthly.get(ym) or {}).get("settle", 0))
        pay = to_money((monthly.get(ym) or {}).get("pay", 0))
        rows.append(
            LedgerRow(seq=seq, month=ym, other_expense=other, payment=pay, remark=remarks.get(ym, ""))
        )
        seq += 1
    return rows


# 两侧（辅材 / 机械）共用同一套行结构（LED-001-05）
LEDGER_SIDES = (CATEGORY_MATERIAL, CATEGORY_MECH)
SHARED_PROJECT_SELECTOR = True     # 共用同一个「项目」选择器
SHARED_EXPORT_ENTRY = True         # 共用同一个导出入口
HAS_SWITCH_CALIBER_BUTTON = False  # **无**「切换口径」按钮
MECH_HAS_MANUAL_INPUT = False      # 机械侧「其他支出金额」**无手填入口**（001-04）


def ledger_remarks_key(category: str, project_id: int, ym: str) -> tuple:
    """台账备注键 = **口径 + 项目 + 月**（LED-001-06）。"""
    return (category, project_id, ym)


def opening_defaults(rows: list[NoticeDebtView], category: str, now: date | None = None) -> dict:
    """录入期初的两个默认值（§4.5.2）：
    ① 项目 = **台账当前选中的项目**（由调用方带）；② 截止年月 = 该项目**该分类**已有数据最早月份的前一月；
    **该分类完全没数据**时回退「上月」（§9.2）。
    """
    months = sorted(
        str(r.doc_date)[:7] for r in rows
        if r.category == category and not r.excluded and str(r.doc_date or "")[:7]
    )
    if months:
        return {"cutoff_ym": prev_month(months[0]), "fallback": False}
    from app.core.period import default_period

    return {"cutoff_ym": default_period("process", now), "fallback": True}


# ============================================================ §4.5.5 实际付款统计


GRAN_MONTH = "month"
GRAN_WEEK = "week"
DEFAULT_GRANULARITY = GRAN_WEEK       # 默认**按周**（PST-001-02）
WINDOW = {GRAN_MONTH: 6, GRAN_WEEK: 8}  # 最近 N 个桶（含当期）
LAYOUT = {"left": "by_project", "right": "timeline"}   # 左栏=按项目 · 右栏=时间轴（PST-001-04）

_DATE_LIKE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def bucket_of(value: str, granularity: str) -> str:
    """日期归桶：月 = `YYYY-MM`；周 = 该周**周一**日期 `YYYY-MM-DD`。"""
    d = date.fromisoformat(str(value)[:10])
    if granularity == GRAN_MONTH:
        return f"{d.year:04d}-{d.month:02d}"
    return (d - timedelta(days=d.weekday())).isoformat()   # 周一 ~ 周日，标签取周一


@dataclass
class PaymentStatView:
    """付款统计专用投影；金额和日期来自有效流水，项目取通知书归属。"""

    pay_date: str
    amount: Decimal
    ownership_id: int | None


def payment_stats(
    rows: list[PaymentStatView], *, granularity: str = GRAN_WEEK, buckets: list[str] | None = None
) -> dict:
    """付款统计：`{项目: {桶: Σ有效流水实际付款金额}}`。"""
    grid: dict = {}
    for r in rows:
        key = r.ownership_id if r.ownership_id is not None else UNASSIGNED
        b = bucket_of(r.pay_date, granularity)
        if buckets is not None and b not in buckets:
            continue
        grid.setdefault(key, {}).setdefault(b, _ZERO)
        grid[key][b] += r.amount
    return grid


def time_buckets(granularity: str, *, year: int, quarter: int | None = None) -> list[str]:
    """粒度切换（PST-001-03）：**月 = 选定年全部月**；**周 = 选定季度全部周**（周标签取该周周一）。"""
    if granularity == GRAN_MONTH:
        return [f"{year:04d}-{m:02d}" for m in range(1, 13)]
    if quarter is None:
        raise MustReportError("按周粒度需要指定季度")
    first_day = date(year, (quarter - 1) * 3 + 1, 1)
    start = first_day - timedelta(days=first_day.weekday())   # 该周周一
    end_month = quarter * 3
    end = date(year + 1, 1, 1) if end_month == 12 else date(year, end_month + 1, 1)
    out: list[str] = []
    cur = start
    while cur < end:
        out.append(cur.isoformat())
        cur += timedelta(days=7)
    return out


def project_labels(rows: list[NoticeDebtView], names: dict) -> list[str]:
    """按项目列表的**展示文字 = 完整项目名**（PST-001-06）——**不得被当成日期截断**。"""
    labels: list[str] = []
    for r in rows:
        key = r.ownership_id if r.ownership_id is not None else UNASSIGNED
        if key in names:
            labels.append(names[key])
    return sorted(set(labels))


def is_date_like(label: str) -> bool:
    """判断某标签是否形如日期 —— 用于钉住「不得在周粒度下把项目名当成日期」这一坑（PST-001-06）。"""
    return bool(_DATE_LIKE.match(str(label or "")))


def toggle_project_filter(current: int | None, clicked: int) -> int | None:
    """点「按项目」条目 ⇒ 联动下方流水按该项目筛选；**再点一次取消**（PST-001-05）。"""
    return None if current == clicked else clicked


__all__ = [
    "CATEGORY_MATERIAL", "CATEGORY_MECH", "CATEGORY_JC",
    "classify", "BIZ_TYPE_LEASE", "PAYEE_JC",
    "payment_status", "effective_total", "revoke_flow", "filter_flows",
    "default_flow_period", "FLOW_PAGINATED", "empty_state_colspan",
    "NoticeDebtView", "OpeningView", "debt_by_category", "total_debt", "debt_by_project", "UNASSIGNED",
    "next_month", "prev_month", "months_span", "LedgerRow", "monthly_aggregate", "build_ledger",
    "LEDGER_SIDES", "SHARED_PROJECT_SELECTOR", "SHARED_EXPORT_ENTRY",
    "HAS_SWITCH_CALIBER_BUTTON", "MECH_HAS_MANUAL_INPUT", "ledger_remarks_key", "opening_defaults",
    "GRAN_MONTH", "GRAN_WEEK", "DEFAULT_GRANULARITY", "WINDOW", "LAYOUT",
    "bucket_of", "PaymentStatView", "payment_stats", "time_buckets", "project_labels", "is_date_like",
    "toggle_project_filter",
]
