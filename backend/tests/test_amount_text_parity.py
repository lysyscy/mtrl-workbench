"""`TAIL-63`（2026-09-21）· **金额洗净归一** ＋ **三处业务判定不许被搅**。

⭐ 为什么要有本件：原先 3 个 `parse_amount`（`mod03` / `mod09` / `mod11`）
   各自写一份"金额文本怎么洗干净"，**且写得不一样** ⇒ 实测实害：
   同一个 `¥ 1,234.56`，集采 / 特殊费用 / 都能过，**付款通知书手填却报「金额格式非法」**
   —— 用户在**同一张表单**里手填带 ¥ 的数会被拒（与当天"收款账号取错字段"同型：同一口径 N 个主人）。

⛔ **本件钉的是两件事，方向相反，别看混**：
   ① **洗净必须归一**（脏输入在 3 处解析出**同一个数**）；
   ② **业务判定必须保持不同**（`MOD-09` 允许 0 与负数、`MOD-11` 必须 > 0 —— 两边注释都写着
      「别把两套搅在一起」）⇒ 谁把判定也统一了，这里会红。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.money import amount_text
from app.mod03_notice import notice_pay_actions as M03
from app.mod09_fee import domain as M09
from app.mod11_jc import domain as M11
from tests.acc_plugin import acc          # ⭐ 工具自检：显式声明"不绑定判据点"（`@acc()`）

DIRTY = ["1,234.56", "¥ 1,234.56", "￥ 88 ", "  1 234.56  ", "1，234.56"]
CLEAN = ["1234.56", "1234.56", "88", "1234.56", "1234.56"]        # `amount_text` 的**洗净文本**
MONEY = ["1234.56", "1234.56", "88.00", "1234.56", "1234.56"]     # 各 `parse_amount` 的 `str(Decimal)`


@acc()
def test_洗净件_去千分位货币符号与空白():
    assert amount_text(None) == ""
    assert amount_text("") == ""
    assert amount_text("   ") == ""
    for dirty, want in zip(DIRTY, CLEAN):
        assert amount_text(dirty) == want, f"{dirty!r} 没洗干净"


@acc()
def test_三处对脏输入解析出同一个数():
    """⭐ 这条是 `TAIL-63` 的**目的**：洗净只有一个主人 ⇒ 同一个脏输入到处都是同一个数。

    ⚠️ 用 `'¥ 1,234.56'` 这种**曾经不一致**的输入（`mod03` 以前会报「金额格式非法」）。
    """
    for dirty, want in zip(DIRTY, MONEY):
        got = []
        for mod in (M03, M09, M11):
            try:
                got.append(str(mod.parse_amount(dirty)))
            except Exception as e:                              # noqa: BLE001
                got.append(f"{type(e).__name__}:{e}")
        assert got == [want] * 3, f"{dirty!r} 在三处解析结果不一致：{got}"


@acc()
def test_mod03_空即None_未手改():
    """`MOD-03`：空 ⇒ `None`（= 未手改，取「本次应付」）⇒ ⛔ 不是 0、不是报错。"""
    assert M03.parse_amount(None) is None
    assert M03.parse_amount("") is None
    assert M03.parse_amount("   ") is None
    assert M03.parse_amount("12.5") == Decimal("12.50")




@acc()
def test_mod09_空即0且允许负数():
    """`MOD-09` 手填：**允许 0 与负数** ⇒ ⛔ 别跟 `MOD-11` 搅在一起。"""
    assert M09.parse_amount(None) == Decimal("0.00")
    assert M09.parse_amount("") == Decimal("0.00")
    assert M09.parse_amount("-5.5") == Decimal("-5.50")
    assert M09.parse_amount("¥ 1,234.56") == Decimal("1234.56")


@acc()
def test_mod11_空报错且必须大于0_与mod09刻意不同():
    """`MOD-11` 子表：**必须 > 0**，与 `MOD-09` **刻意不同**（两边注释都写着"别搅"）。"""
    with pytest.raises(ValueError, match="不合法"):
        M11.parse_amount("")
    with pytest.raises(ValueError, match="不合法"):
        M11.parse_amount("-5.5")
    with pytest.raises(ValueError, match="不合法"):
        M11.parse_amount("0")
    assert M11.parse_amount("¥ 1,234.56") == Decimal("1234.56")


@acc()
def test_非数字一律报错_不静默取0():
    for mod in (M03, M09, M11):
        with pytest.raises((ValueError, Exception)):
            mod.parse_amount("abc")
