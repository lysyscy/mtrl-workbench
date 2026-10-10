# -*- coding: utf-8 -*-
"""common_time 时间边界统一工具测试（2026-09-10，核算期=自然月 1号~月末）。"""
import pytest

from common_time import month_bounds, export_range, parse_range_or_month


def test_month_bounds_normal():
    assert month_bounds('2026-09') == ('2026-09-01', '2026-09-30')
    assert month_bounds('2026-02') == ('2026-02-01', '2026-02-28')
    assert month_bounds('2024-02') == ('2024-02-01', '2024-02-29')  # 闰年
    assert month_bounds('2026-12') == ('2026-12-01', '2026-12-31')
    assert month_bounds('2026-01') == ('2026-01-01', '2026-01-31')


def test_month_bounds_invalid():
    assert month_bounds('2026-13') == (None, None)
    assert month_bounds('2026-00') == (None, None)
    assert month_bounds('') == (None, None)
    assert month_bounds(None) == (None, None)
    assert month_bounds('abc') == (None, None)


def test_export_range_prefers_start_end():
    assert export_range({'start_date': '2026-08-01', 'end_date': '2026-08-31'}) == \
        ('2026-08-01', '2026-08-31')


def test_export_range_compat_sy_sm():
    # 单月
    assert export_range({'sy': 2026, 'sm': 8}) == ('2026-08-01', '2026-08-31')
    # 起止年月（跨月）
    assert export_range({'sy': 2026, 'sm': 8, 'ey': 2026, 'em': 9}) == ('2026-08-01', '2026-09-30')


def test_export_range_missing():
    assert export_range({}) == (None, None)
    assert export_range(None) == (None, None)
    assert export_range({'sy': 2026}) == (None, None)   # 缺 sm


class _Args(dict):
    """模拟 request.args（ImmutableMultiDict 的简化版，支持 .get）"""


def test_parse_range_or_month_prefers_start_end():
    assert parse_range_or_month({'start_date': '2026-08-01', 'end_date': '2026-08-31'}) == \
        ('2026-08-01', '2026-08-31')


def test_parse_range_or_month_from_month():
    assert parse_range_or_month({'month': '2026-08'}) == ('2026-08-01', '2026-08-31')


def test_parse_range_or_month_none():
    assert parse_range_or_month({}) == (None, None)
    assert parse_range_or_month(None) == (None, None)
    assert parse_range_or_month({'month': ''}) == (None, None)
