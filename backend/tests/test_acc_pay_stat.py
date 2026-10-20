"""`ACC-PAY-STAT-001`（统计金额可手动调整）7 个判据点的验收断言。

依据：《说明书》§4.5.3（手改上限 / 留痕 / 欠款实时重算）· §4.2.5（**三金额** + 两统计字段上限）
      · §4.4.7（**统计付款金额默认值 = 已付金额（流水汇总）**）
      · §4.2.7（再次导入：留痕 = 唯一判据）· `DEV-P-03`。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod03_notice.domain import (
    F_APPROVED,
    F_STAT_PAID,
    F_STAT_SETTLE,
    STAT_FIELDS,
    StatTrace,
    adjust_stat,
    apply_trace,
    default_stat_value,
    manual_edited_fields,
    recompute_debt,
    stat_value_on_reimport,
    was_manually_edited,
)
from app.mod05_flow.domain import NoticeDebtView
from app.mod05_flow.models import CATEGORY_MATERIAL

APPROVED = to_money("10000.00")
PAID_TOTAL = to_money("8000.00")      # 已付金额（有效流水汇总）—— 刻意**不等于**审批金额


def _view(settle="10000.00", pay="8000.00") -> NoticeDebtView:
    return NoticeDebtView(
        notice_id=7,
        doc_date="2026-08-12",
        category=CATEGORY_MATERIAL,
        settle_stat=to_money(settle),
        pay_stat=to_money(pay),
        ownership_id=3,
    )


def test_两个统计金额可手改且是否手改的唯一事实来源是留痕():
    # 默认值（§4.2.5 表 · §4.4.7）：统计结算金额 = 审批金额；
    # ⭐ 统计付款金额 = **已付金额（有效流水汇总）** —— 2026-09-16 起（原「= 付款金额（源）」已作废）
    assert default_stat_value(F_STAT_SETTLE, approved=APPROVED, paid_total=PAID_TOTAL) == APPROVED
    assert default_stat_value(F_STAT_PAID, approved=APPROVED, paid_total=PAID_TOTAL) == PAID_TOTAL
    # ⚠️ 关键区分力：已付 ≠ 审批金额时，统计付款金额必须跟**已付**、**不是**跟审批金额
    assert default_stat_value(F_STAT_PAID, approved=APPROVED, paid_total=to_money("0.00")) == to_money("0.00")
    # 两个统计字段是**旁路字段**，可手改；源字段与派生列都不在可改集合里
    assert STAT_FIELDS == (F_STAT_SETTLE, F_STAT_PAID)
    assert F_APPROVED not in STAT_FIELDS

    traces = [
        adjust_stat(
            notice_id=7, field=F_STAT_SETTLE, value="9000.00",
            approved=APPROVED, before=APPROVED, changed_by="SCY980803",
        )
    ]
    # 「是否手改」的唯一事实来源 = 留痕（不再另开状态位 —— 副本必然静默过期）
    assert was_manually_edited(traces, 7, F_STAT_SETTLE) is True
    assert manual_edited_fields(traces, 7) == (F_STAT_SETTLE,)
    # 没有留痕的字段一律视为「未手改」
    assert was_manually_edited(traces, 7, F_STAT_PAID) is False
    assert manual_edited_fields([], 7) == ()
    # 两个字段**各判各的**，不合并成一个「改没改过」
    traces.append(
        adjust_stat(
            notice_id=7, field=F_STAT_PAID, value="6000.00",
            approved=APPROVED, before=PAID_TOTAL, changed_by="SCY980803",
        )
    )
    assert manual_edited_fields(traces, 7) == (F_STAT_SETTLE, F_STAT_PAID)

    # 再次导入：留痕是唯一判据 —— 手改过保留人工值、未手改跟随新审批金额（§4.2.7）
    assert stat_value_on_reimport(
        field=F_STAT_SETTLE, current=to_money("9000.00"), approved_new=to_money("9500.00"),
        traces=traces, notice_id=7,
    ) == to_money("9000.00")
    assert stat_value_on_reimport(
        field=F_STAT_PAID, current=PAID_TOTAL, approved_new=to_money("9500.00"),
        traces=[traces[0]], notice_id=7,
    ) == to_money("9500.00")


def test_超过审批金额必须拦截并保留原值():
    # 上限 = 审批金额；超额 ⇒ 直接拦截、保留原值（不截断、不静默改写）
    with pytest.raises(MustReportError) as exc:
        adjust_stat(
            notice_id=7, field=F_STAT_SETTLE, value="10000.01",
            approved=APPROVED, before=to_money("9000.00"), changed_by="u",
        )
    msg = str(exc.value)
    assert "审批金额" in msg and "保留原值" in msg
    # 等于上限**不算超**（§9.1 判定容差 0，不得把等于上限判成超限）
    ok = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="10000.00",
        approved=APPROVED, before=to_money("9000.00"), changed_by="u",
    )
    assert ok.after == APPROVED
    # 统计付款金额同一上限口径
    with pytest.raises(MustReportError):
        adjust_stat(
            notice_id=7, field=F_STAT_PAID, value="12000.00",
            approved=APPROVED, before=to_money("5000.00"), changed_by="u",
        )


def test_往下调少付允许通过():
    t = adjust_stat(
        notice_id=7, field=F_STAT_PAID, value="6000.00",
        approved=APPROVED, before=PAID_TOTAL, changed_by="u",
    )
    assert (t.before, t.after) == (PAID_TOTAL, to_money("6000.00"))
    assert t.after < APPROVED
    t2 = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="1.00",
        approved=APPROVED, before=APPROVED, changed_by="u",
    )
    assert t2.after == to_money("1.00")
    # 下调为 0 也允许（≥ 0 档，§8.4）
    t3 = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="0",
        approved=APPROVED, before=APPROVED, changed_by="u",
    )
    assert t3.after == to_money("0.00")


def test_非法金额必须被拒绝且原值不变():
    before = to_money("9000.00")
    for bad in ("", "   ", "abc", "1.2.3", None, "-1", "-0.01"):
        with pytest.raises(MustReportError):
            adjust_stat(
                notice_id=7, field=F_STAT_SETTLE, value=bad,
                approved=APPROVED, before=before, changed_by="u",
            )
    # 字段名非法（源字段 / 派生列 / 未知列）同样拒绝 —— 可改集合只有那两个统计字段
    # ⚠️ `pay_amount_src`（原「付款金额（源）」）**已取消**（§4.2.5）⇒ 作为字段名同样必须被拒
    for bad_field in (F_APPROVED, "pay_amount_src", "pay_amount", "不存在的列"):
        with pytest.raises(MustReportError):
            adjust_stat(
                notice_id=7, field=bad_field, value="1.00",
                approved=APPROVED, before=before, changed_by="u",
            )


def test_手改不产生隐式副作用():
    t = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="9000.00",
        approved=APPROVED, before=APPROVED, changed_by="u",
    )
    v = apply_trace(_view(), t)
    assert v.settle_stat == to_money("9000.00")
    assert v.pay_stat == to_money("8000.00")          # 改一个**不带动**另一个
    # 反向同理
    t2 = adjust_stat(
        notice_id=7, field=F_STAT_PAID, value="5000.00",
        approved=APPROVED, before=to_money("8000.00"), changed_by="u",
    )
    v2 = apply_trace(v, t2)
    assert (v2.settle_stat, v2.pay_stat) == (to_money("9000.00"), to_money("5000.00"))
    # 一次手改只产出**一条**留痕、只动**一个**字段
    assert isinstance(t2, StatTrace) and t2.field == F_STAT_PAID


def test_调整后欠款实时重算():
    rows = [_view()]
    assert recompute_debt(rows)[CATEGORY_MATERIAL] == to_money("2000.00")   # 10000 − 8000
    t = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="9000.00",
        approved=APPROVED, before=APPROVED, changed_by="u",
    )
    assert recompute_debt([apply_trace(rows[0], t)])[CATEGORY_MATERIAL] == to_money("1000.00")
    # 统计付款金额下调 ⇒ 欠款随之上升（与欠款同一个出口）
    t2 = adjust_stat(
        notice_id=7, field=F_STAT_PAID, value="5000.00",
        approved=APPROVED, before=to_money("8000.00"), changed_by="u",
    )
    assert recompute_debt([apply_trace(rows[0], t2)])[CATEGORY_MATERIAL] == to_money("5000.00")


def test_手改必须留痕():
    at = datetime(2026, 9, 15, 20, 30, 0)
    t = adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="9000.00",
        approved=APPROVED, before=APPROVED, changed_by="SCY980803", at=at,
    )
    assert isinstance(t, StatTrace)
    assert (t.notice_id, t.field) == (7, F_STAT_SETTLE)
    assert (t.before, t.after) == (APPROVED, to_money("9000.00"))   # 改前值 / 改后值
    assert t.changed_by == "SCY980803" and t.changed_at == at        # 改动人 / 时间
    assert t.label == "统计结算金额"
    # 值没变就不动 —— 不产生无意义的留痕（§4.2.7「值没变就不动」）
    assert adjust_stat(
        notice_id=7, field=F_STAT_SETTLE, value="9000.00",
        approved=APPROVED, before=to_money("9000.00"), changed_by="u",
    ) is None
