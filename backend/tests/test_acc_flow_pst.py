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
    bucket_of,
    is_date_like,
    monthly_aggregate,
    payment_stats,
    project_labels,
    sum_pay_stat,
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
def test_取值与台账付款列同一出口():
    rows = [_view("2026-08-03", "100"), _view("2026-08-04", "50"), _view("2026-08-05", "999", excluded=True)]
    # 同一取值出口：sum_pay_stat
    assert sum_pay_stat(rows) == to_money("150")
    # 与逐月台账「付款」列一致（同源）
    led_pay = monthly_aggregate(rows, CATEGORY_MATERIAL, 1)["2026-08"]["pay"]
    assert led_pay == sum_pay_stat(rows)
    # 统计网格的桶内合计同样由该出口累加
    stats = payment_stats(rows, granularity=GRAN_MONTH)
    assert stats[1]["2026-08"] == sum_pay_stat(rows)


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
