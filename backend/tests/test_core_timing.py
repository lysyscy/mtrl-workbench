"""时间口径换算的单元测试（工具层自检，不绑定业务判据点）。"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.timing import (
    TimeRangeError,
    month_range_closed,
    parse_ym,
    shift_ym,
    to_iso,
    validate_closed_range,
    ym_of,
    ym_to_closed_range,
)


def test_年月换算为闭区间_含月末():
    assert month_range_closed("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_range_closed("2026-04") == (date(2026, 4, 1), date(2026, 4, 30))


def test_闰年二月():
    assert ym_to_closed_range("2024-02") == ("2024-02-01", "2024-02-29")


def test_年月加减跨年():
    assert shift_ym("2026-01", -1) == "2025-12"
    assert shift_ym("2026-12", 1) == "2027-01"
    assert shift_ym("2026-06", -6) == "2025-12"


def test_归月展示():
    assert ym_of(date(2026, 9, 15)) == "2026-09"
    assert ym_of(date(2026, 10, 1)) == "2026-10"


def test_年月格式非法显式报错():
    for bad in ("", "2026", "2026-13", "2026-00", "abc-def"):
        with pytest.raises(TimeRangeError):
            parse_ym(bad)


def test_起止颠倒显式报错_不静默交换():
    with pytest.raises(TimeRangeError):
        validate_closed_range("2026-02-10", "2026-02-01")
    s, e = validate_closed_range("2026-02-01", "2026-02-10")
    assert (to_iso(s), to_iso(e)) == ("2026-02-01", "2026-02-10")
