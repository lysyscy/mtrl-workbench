"""`ACC-FLOW-LED-001`（逐月欠款台账）7 个判据点的验收断言。"""

from __future__ import annotations

from app.core.money import to_money
from app.mod05_flow.domain import (
    HAS_SWITCH_CALIBER_BUTTON,
    LEDGER_SIDES,
    MECH_HAS_MANUAL_INPUT,
    SHARED_EXPORT_ENTRY,
    SHARED_PROJECT_SELECTOR,
    NoticeDebtView,
    OpeningView,
    build_ledger,
    ledger_remarks_key,
    monthly_aggregate,
    opening_defaults,
)
from app.mod05_flow.models import CATEGORY_MATERIAL, CATEGORY_MECH


def _view(ym, settle, pay, owner=1, cat=CATEGORY_MATERIAL):
    return NoticeDebtView(
        notice_id=abs(hash((ym, str(settle), str(owner), cat))) % 100000,
        doc_date=f"{ym}-10",
        category=cat,
        settle_stat=to_money(settle),
        pay_stat=to_money(pay),
        ownership_id=owner,
    )


def test_第一行为期初其后从次月起逐月连续():
    rows = [_view("2026-08", "100", "0"), _view("2026-10", "200", "0")]
    monthly = monthly_aggregate(rows, CATEGORY_MATERIAL, 1)
    opening = OpeningView(CATEGORY_MATERIAL, 1, "2026-07", to_money("50"), to_money("10"))
    led = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly, opening=opening)
    assert led[0].is_opening and led[0].month == "2026-07"      # 第 1 行 = 期初占位行
    assert [r.month for r in led][1:] == ["2026-08", "2026-09", "2026-10"]   # 次月起**连续**（空月也出行）
    assert [r.seq for r in led] == [1, 2, 3, 4]


def test_其他支出金额为该月该项该分类统计结算合计():
    rows = [_view("2026-08", "100", "0"), _view("2026-08", "50", "0"), _view("2026-09", "70", "0")]
    monthly = monthly_aggregate(rows, CATEGORY_MATERIAL, 1)
    led = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly)
    got = {r.month: r.other_expense for r in led}
    assert got["2026-08"] == to_money("150")     # 独立复算：100 + 50
    assert got["2026-09"] == to_money("70")
    # 别项目的行不混入
    rows2 = rows + [_view("2026-08", "9999", "0", owner=2)]
    m2 = monthly_aggregate(rows2, CATEGORY_MATERIAL, 1)
    assert build_ledger(category=CATEGORY_MATERIAL, monthly=m2)[0].other_expense == to_money("150")


def test_付款列取同口径统计付款合计():
    rows = [_view("2026-08", "1000", "300"), _view("2026-08", "0", "200")]
    monthly = monthly_aggregate(rows, CATEGORY_MATERIAL, 1)
    led = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly)
    assert led[0].payment == to_money("500")      # 300 + 200
    assert led[0].debt == to_money("500")         # 欠款 = 其他支出 − 付款


def test_机械其他支出为派生只读且无手填入口():
    mech_monthly = {"2026-08": to_money("600"), "2026-09": to_money("400")}
    led = build_ledger(
        category=CATEGORY_MECH,
        monthly={},
        mech_settle_by_month=mech_monthly,
        end_ym="2026-09",
    )
    assert [r.other_expense for r in led] == [to_money("600"), to_money("400")]   # 派生值
    assert sum(r.other_expense for r in led) == to_money("1000")                  # 各月之和 = 该项目机械费结算额
    assert MECH_HAS_MANUAL_INPUT is False                                        # **无手填入口**


def test_两侧共用同一选择器与导出入口且无切换按钮():
    assert LEDGER_SIDES == (CATEGORY_MATERIAL, CATEGORY_MECH)
    assert SHARED_PROJECT_SELECTOR is True and SHARED_EXPORT_ENTRY is True
    assert HAS_SWITCH_CALIBER_BUTTON is False


def test_备注键为口径项目月且可写可清():
    assert ledger_remarks_key(CATEGORY_MATERIAL, 7, "2026-08") == (CATEGORY_MATERIAL, 7, "2026-08")
    monthly = monthly_aggregate([_view("2026-08", "1", "0")], CATEGORY_MATERIAL, 1)
    led = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly, remarks={"2026-08": "备注A"})
    assert led[0].remark == "备注A"
    # 清空 ⇒ 空串（可清）
    led2 = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly, remarks={"2026-08": ""})
    assert led2[0].remark == ""


def test_期初默认截止年月与录入后台账可见该行():
    rows = [_view("2026-08", "1", "0"), _view("2026-09", "1", "0")]
    d = opening_defaults(rows, CATEGORY_MATERIAL)
    assert d["cutoff_ym"] == "2026-07"        # 最早月份(2026-08)的前一月
    assert d["fallback"] is False
    # 该分类无数据 ⇒ 回退「上月」
    d2 = opening_defaults([], CATEGORY_MATERIAL)
    assert d2["fallback"] is True
    # 录入期初后，台账**第一行就是它** ⇒ 界面上一定看得到（否则"看不到刚录入的那一行"）
    opening = OpeningView(CATEGORY_MATERIAL, 1, d["cutoff_ym"], to_money("50"), to_money("0"))
    led = build_ledger(category=CATEGORY_MATERIAL, monthly=monthly_aggregate(rows, CATEGORY_MATERIAL, 1), opening=opening)
    assert led[0].is_opening and led[0].month == "2026-07"
