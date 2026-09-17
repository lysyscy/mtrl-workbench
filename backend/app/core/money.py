"""金额口径的**全站唯一出口**。

依据：
- 《材料科业务全流程说明书》**§9.1 金额口径**（单位 / 精度 / 舍入 / 判定容差）
- 《技术栈选型分析》**§3.2「金额口径」行**（存储形态 = `numeric(18,2)`；比较转分属实现细节）

硬约束：
1. **计算一律 `Decimal`、禁 float**；
2. 舍入一律 `ROUND_HALF_UP`；
3. 判定**容差 0**（各自归一为 2 位小数后判等）；
4. ⚠️ **任何模块都不得自写金额处理** —— 一律经本模块（改这里要验证所有调用方）。

`to_cents()` 仅供**代码内比较**使用，**不是存储口径**（不出现在任何模型列上）。
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

logger = logging.getLogger(__name__)

# 金额精度：元 / 2 位小数（§9.1）
QUANT = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    """金额相关的输入非法 —— 必须显式报出，不得静默取 0。"""


def _reject_bool(value: object) -> None:
    # bool 是 int 的子类，混进来基本都是 bug（True -> Decimal(1)）
    if isinstance(value, bool):
        raise MoneyError("金额不接受布尔值")


def to_money(value: object) -> Decimal:
    """把任意输入归一为金额 `Decimal`（2 位小数，HALF_UP）。

    接受 `Decimal` / `int` / `str`（千分位与空白会被清理）。
    `float` 会**先经 `str()` 再解析**并记一条 warning —— 见下方说明。
    """
    _reject_bool(value)

    if value is None:
        raise MoneyError("金额不得为空")

    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, str):
        raw = value.strip().replace(",", "").replace("，", "")
        if raw == "":
            raise MoneyError("金额不得为空字符串")
        try:
            dec = Decimal(raw)
        except InvalidOperation as exc:
            raise MoneyError(f"金额格式非法：{value!r}") from exc
    elif isinstance(value, float):
        # ⚠️ 禁 float 是本项目的硬口径（§9.1）。这里不直接抛，是为了不把
        #    上游（如 Excel 读取）的既有形态一刀切断；但走 str() 往返，
        #    对金额量级是精确的。**数据入口应尽量从源头避免 float**
        #    （读 Excel 时用 converters=str / dtype=object 保原文）。
        logger.warning("金额收到 float 输入，已按 str() 往返解析：%r", value)
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise MoneyError(f"金额格式非法：{value!r}") from exc
    else:
        raise MoneyError(f"不支持的金额类型：{type(value).__name__}")

    if not dec.is_finite():
        raise MoneyError(f"金额必须是有限数：{value!r}")

    return dec.quantize(QUANT, rounding=ROUND_HALF_UP)


def try_money(value: object) -> Decimal | None:
    """宽松版：空值返回 `None`，非法值抛 `MoneyError`。用于可空字段。"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return to_money(value)


def sum_money(values: Iterable[object]) -> Decimal:
    """求和（逐一归一到 2 位小数后相加）—— 全站合计行的唯一入口。"""
    total = ZERO
    for v in values:
        total += to_money(v)
    return to_money(total)


def sub_money(a: object, b: object) -> Decimal:
    return to_money(to_money(a) - to_money(b))


def is_equal(a: object, b: object) -> bool:
    """判定容差 0（§9.1）：各自归一为 2 位小数后比较。"""
    return to_money(a) == to_money(b)


def to_cents(value: object) -> int:
    """转整数分 —— **仅供代码内比较**，不是存储口径（技术栈 §3.2）。"""
    return int(to_money(value).scaleb(2).to_integral_value(rounding=ROUND_HALF_UP))


def is_zero(value: object) -> bool:
    return to_money(value) == ZERO


# --- 各字段的取值判据分三档，**有意不同、勿统一**（§8.4 口径一致性清单）---


def require_positive(value: object, *, field: str = "金额") -> Decimal:
    """必须 > 0（集采发票金额 / 贸易公司发票金额 / 付款金额）。"""
    dec = to_money(value)
    if dec <= ZERO:
        raise MoneyError(f"{field}必须大于 0（当前 {dec}）")
    return dec


def require_non_negative(value: object, *, field: str = "金额") -> Decimal:
    """必须 ≥ 0（付款通知书三金额 / 手动新增 / 机械 6 列 / 大表手填 / 调整单金额）。"""
    dec = to_money(value)
    if dec < ZERO:
        raise MoneyError(f"{field}不得为负数（当前 {dec}）")
    return dec
