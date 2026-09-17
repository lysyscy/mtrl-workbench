"""金额唯一出口的单元测试（工具层自检，不绑定业务判据点）。

⚠️ 这些是**函数级**自检 —— 它们**不等于** `ACC-*` 判据点通过
（判据点是行为级、端到端的口径）。故一律用 `@acc()` 显式声明不绑定。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.money import (
    MoneyError,
    is_equal,
    is_zero,
    require_non_negative,
    require_positive,
    sub_money,
    sum_money,
    to_cents,
    to_money,
    try_money,
)
from tests.acc_plugin import acc


@acc()
def test_归一为两位小数且四舍五入():
    assert to_money("1.005") == Decimal("1.01")   # HALF_UP（不是银行家舍入）
    assert to_money("1.004") == Decimal("1.00")
    assert to_money("1.004999") == Decimal("1.00")
    assert to_money(0) == Decimal("0.00")
    assert to_money("1,234.5") == Decimal("1234.50")  # 千分位容错


@acc()
def test_拒绝布尔空值与非法串():
    for bad in (True, False, None, "", "   ", "abc", "1.2.3"):
        with pytest.raises(MoneyError):
            to_money(bad)


@acc()
def test_不接受无穷与非数():
    with pytest.raises(MoneyError):
        to_money(Decimal("NaN"))
    with pytest.raises(MoneyError):
        to_money(Decimal("Infinity"))


@acc()
def test_判定容差为零():
    assert is_equal("1.00", Decimal("1"))
    assert not is_equal("1.00", "1.01")
    assert is_zero("0.000")


@acc()
def test_求和逐个归一后相加():
    assert sum_money(["0.005", "0.005", "0.005"]) == Decimal("0.03")
    assert sum_money([]) == Decimal("0.00")
    assert sub_money("10.00", "3.33") == Decimal("6.67")


@acc()
def test_取值判据三档有意不同():
    # ① 必须 > 0
    assert require_positive("0.01") == Decimal("0.01")
    for bad in ("0", "0.00", "-1"):
        with pytest.raises(MoneyError):
            require_positive(bad)
    # ② 必须 >= 0（0 合法）
    assert require_non_negative("0") == Decimal("0.00")
    with pytest.raises(MoneyError):
        require_non_negative("-0.01")


@acc()
def test_可空字段用_try_money():
    assert try_money(None) is None
    assert try_money("") is None
    assert try_money("1.5") == Decimal("1.50")


@acc()
def test_转分仅供比较_不进存储():
    assert to_cents("1.00") == 100
    assert to_cents("1.005") == 101
    # 负值也支持（特殊费用手填项允许负数）
    assert to_cents("-0.01") == -1
