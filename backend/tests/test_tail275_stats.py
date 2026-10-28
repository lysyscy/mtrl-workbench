"""付款统计用真实组装输出验证选桶、金额、笔数与台账日期。"""
from datetime import date
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import PaymentFlow
from app.mod05_flow.service import build_stats, notice_debt_views
from app.mod05_flow.domain import monthly_aggregate, CATEGORY_MATERIAL
from tests.m05_helpers import FakeSession, make_notice_row, make_flow, make_project


def test_empty_payment_window_keeps_time_controls():
    st = build_stats(FakeSession({Project: [], PaymentNotice: [], PaymentFlow: []}),
                     granularity='week', today=date(2026, 10, 10))
    assert not st['left'] and st['buckets']


def test_week_picker_refetches_early_and_cross_quarter_weeks():
    s = FakeSession({Project: [], PaymentNotice: [], PaymentFlow: []})
    for week in ('2026-06-29', '2026-07-06', '2026-08-03', '2026-09-28'):
        st = build_stats(s, granularity='week', year=2026, quarter=3,
                         today=date(2026, 10, 10), bucket=week)
        assert week in st['buckets'] and len(st['buckets']) >= 13


def test_stats_axis_and_selected_bucket_are_independent():
    s = FakeSession({Project: [], PaymentNotice: [], PaymentFlow: []})
    a = build_stats(s, granularity='week', year=2026, quarter=4, bucket='2026-07-06')
    b = build_stats(s, granularity='week', year=2026, quarter=4, bucket='2026-10-26')
    assert a['buckets'] == b['buckets'] and len(a['buckets']) >= 13
    assert a['right'] == b['right']
    assert a['selected']['bucket'] == '2026-07-06'
    assert b['selected']['bucket'] == '2026-10-26'
    c = build_stats(s, granularity='month', year=2026, bucket='2025-09')
    assert c['buckets'] == [f'2026-{m:02d}' for m in range(1, 13)]
    assert c['selected']['bucket'] == '2025-09'


def test_selected_bucket_window_total_count_and_ledger():
    s = FakeSession({Project: [make_project(11, '甲仓', '甲项目')],
        PaymentNotice: [make_notice_row(1, doc_date='2026-08-03', paid='150'),
                        make_notice_row(2, doc_date='2026-08-04', paid='80'),
                        make_notice_row(3, doc_date='2026-01-04', paid='900')],
        PaymentFlow: [make_flow(1, notice_id=1, amount='100', pay_date='2026-09-02'),
                      make_flow(2, notice_id=2, amount='80', pay_date='2026-08-03'),
                      make_flow(3, notice_id=3, amount='900', pay_date='2025-01-03')]})
    st = build_stats(s, granularity='month', today=date(2026, 10, 10), bucket='2026-09')
    assert st['total'] == '1080.00' and sum(map(float, st['right'])) == 180
    assert len(st['buckets']) == 12
    assert monthly_aggregate(notice_debt_views(s), CATEGORY_MATERIAL, 11)['2026-08']['pay'] == 230
