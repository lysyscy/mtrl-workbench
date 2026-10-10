"""`ACC-FLOW-PST-001`（付款统计）6 个判据点的验收断言。"""

from __future__ import annotations

from datetime import date

from app.core.money import to_money
from app.mod05_flow.domain import (
    DEFAULT_GRANULARITY,
    GRAN_MONTH,
    GRAN_WEEK,
    LAYOUT,
    UNASSIGNED,
    NoticeDebtView,
    PaymentStatView,
    bucket_of,
    is_date_like,
    monthly_aggregate,
    payment_stats,
    project_labels,
    time_buckets,
    toggle_project_filter,
)
from app.mod05_flow.models import CATEGORY_MATERIAL
from tests.acc_plugin import acc


def _view(doc_date, pay, owner=1, excluded=False):
    return NoticeDebtView(
        notice_id=abs(hash((doc_date, str(pay), str(owner)))) % 100000,
        doc_date=doc_date,
        category=CATEGORY_MATERIAL,
        settle_stat=to_money("0"),
        pay_stat=to_money(pay),
        excluded=excluded,
        ownership_id=owner,
    )


@acc("ACC-FLOW-PST-001", "001-01")
def test_付款统计不受欠款人工调整影响():
    rows = [_view("2026-08-03", "150")]
    led_pay = monthly_aggregate(rows, CATEGORY_MATERIAL, 1)["2026-08"]["pay"]
    assert led_pay == to_money("150")
    stats = payment_stats([PaymentStatView("2026-09-02", to_money("100"), 1)], granularity=GRAN_MONTH)
    assert stats == {1: {"2026-09": to_money("100")}}


@acc("ACC-FLOW-PST-001", "001-02")
def test_默认粒度为按周():
    assert DEFAULT_GRANULARITY == GRAN_WEEK


@acc("ACC-FLOW-PST-001", "001-03")
def test_粒度可切月与周():
    months = time_buckets(GRAN_MONTH, year=2026)
    assert len(months) == 12 and months[0] == "2026-01" and months[-1] == "2026-12"
    weeks = time_buckets(GRAN_WEEK, year=2026, quarter=1)
    assert weeks and all(date.fromisoformat(w).weekday() == 0 for w in weeks)   # 标签取**周一**
    assert weeks[0] <= "2026-01-05" and weeks[-1] < "2026-04-01"


@acc("ACC-FLOW-PST-001", "001-04")
def test_左栏按项目右栏时间轴():
    assert LAYOUT == {"left": "by_project", "right": "timeline"}


@acc("ACC-FLOW-PST-001", "001-05")
def test_点项目条目联动再点取消():
    assert toggle_project_filter(None, 7) == 7      # 点 ⇒ 选中
    assert toggle_project_filter(7, 7) is None      # 再点一次 ⇒ 取消
    assert toggle_project_filter(7, 9) == 9         # 点别的 ⇒ 切换


@acc("ACC-FLOW-PST-001", "001-06")
def test_按项目列表为完整项目名不被当日期截断():
    rows = [_view("2026-08-03", "1", owner=1), _view("2026-08-04", "1", owner=2)]
    names = {1: "泗阳百通4#锅炉项目仓库", 2: "甲展示名"}
    labels = project_labels(rows, names)
    assert "泗阳百通4#锅炉项目仓库" in labels and "甲展示名" in labels   # **完整**项目名
    assert not any(is_date_like(x) for x in labels)                     # 不得形如日期（周粒度下会被误当日期）
    assert is_date_like("2026-08-17") is True                           # 反证：日期形态确实会被识别


@acc("ACC-FLOW-PST-001", "001-03")
def test_跨月周桶与周一标签():
    rows = [PaymentStatView("2026-08-31", to_money("20"), 1),
            PaymentStatView("2026-09-06", to_money("30"), 1)]
    assert payment_stats(rows, granularity=GRAN_WEEK) == {1: {"2026-08-31": to_money("50")}}
    assert payment_stats(rows, granularity=GRAN_MONTH) == {1: {"2026-08": to_money("20"), "2026-09": to_money("30")}}


@acc("ACC-FLOW-PST-001", "001-01")
def test_组装单笔调整与撤销剔除及台账日期():
    from app.mod03_notice.models import PaymentNotice
    from app.mod01_projects.models import Project
    from app.mod05_flow.models import PaymentFlow, FLOW_REVOKED
    from app.mod05_flow.service import build_stats, notice_debt_views
    from tests.m05_helpers import FakeSession, make_notice_row, make_flow, make_project

    s = FakeSession({Project: [make_project(11, "甲仓")],
        PaymentNotice: [make_notice_row(1, doc_date="2026-08-03", paid="150"),
                        make_notice_row(2, paid="999", excluded=True)],
        PaymentFlow: [make_flow(1, notice_id=1, amount="100", pay_date="2026-09-02"),
                      make_flow(2, notice_id=1, amount="900", status=FLOW_REVOKED),
                      make_flow(3, notice_id=2, amount="999"),
                      make_flow(4, notice_id=None, amount="999")]})
    st = build_stats(s, granularity=GRAN_MONTH, today=date(2026, 10, 10))
    ix = st["buckets"].index("2026-09")
    assert st["left"][0]["cells"][ix] == st["right"][ix] == "100.00"
    assert st["counts"][ix] == 1
    assert st["total"] == "100.00"
    assert monthly_aggregate(notice_debt_views(s), CATEGORY_MATERIAL, 11)["2026-08"]["pay"] == to_money("150")


@acc("ACC-FLOW-PST-001", "001-01")
def test_跨桶多笔付款与欠款调整独立():
    from app.mod05_flow.service import payment_stat_views
    from tests.m05_helpers import make_flow
    n = _view("2026-08-03", "150")
    fs = [make_flow(1, notice_id=n.notice_id, amount="40", pay_date="2026-09-02"),
          make_flow(2, notice_id=n.notice_id, amount="60", pay_date="2026-10-03")]
    rows = payment_stat_views([n], fs)
    expected = {1: {"2026-09": to_money("40"), "2026-10": to_money("60")}}
    assert payment_stats(rows, granularity=GRAN_MONTH) == expected
    n.pay_stat = to_money("20")
    n.settle_stat = to_money("50")
    assert payment_stats(payment_stat_views([n], fs), granularity=GRAN_MONTH) == expected
    fs[1].pay_date = "2026-09-03"
    assert payment_stats(payment_stat_views([n], fs), granularity=GRAN_MONTH) == {1: {"2026-09": to_money("100")}}
    assert payment_stat_views([n], []) == []  # 只有欠款旁路值不制造付款事实。
    from app.mod05_flow.models import FLOW_REVOKED
    fs[0].status = FLOW_REVOKED
    fs.append(make_flow(3, notice_id=n.notice_id, amount="55", pay_date="2026-10-09"))
    assert payment_stats(payment_stat_views([n], fs), granularity=GRAN_MONTH) == {1: {"2026-09": to_money("60"), "2026-10": to_money("55")}}
    assert n.pay_stat == to_money("20")  # 撤回重付修改事实，欠款人工值仍保留。
