"""MOD-06 机械手录金额校验，不连库。

机械六列含历史段均可手填。0合法，负数和非数字拒绝；兼容入口的空值
按0解析，过程单格入口显式选择None。旁路载体及明细来源确认由工作台和
repository.save_mech维护，不在此层改变。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import MoneyError, to_money
from app.mod06_proc import domain as D

PLACEHOLDER_YM = "YYYY-MM"


def parse_mech_values(raw, *, empty_as_none: bool = False) -> dict[str, Decimal | None]:
    """兼容表单空值为0；过程单格入口显式选择留空。非数字、负数仍拒绝。"""
    out: dict[str, Decimal | None] = {}
    for i, label in enumerate(D.MECH_COLUMNS):
        key = f"mech_{i}"
        value = (raw or {}).get(key)
        text = ("" if value is None else str(value)).strip().replace(",", "")
        if not text:
            out[key] = None if empty_as_none else Decimal("0.00")
            continue
        try:
            value = to_money(text)
        except (MoneyError, ArithmeticError, ValueError) as exc:
            raise ValueError(f"「{label}」不是数字：{text!r}") from exc
        if value < 0:
            raise ValueError(f"「{label}」不得为负数（当前 {value}）")
        out[key] = value
    return out


# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：本件原先还有三个**页面专用**件 ——
#    `_value_of`（表单回填现值）· `block_html`（「机械手录」区块）· `notice_html`（PRG 回执条）——
#    它们只服务**旧服务端页**；旧页整体删除（授权 `D18`）后三者**零调用方**
#    （`wiring_audit` 的 W1/W2 当场报出来 ✓）⇒ 一并删除。
#    剩下的 `parse_mech_values` 为兼容入口与过程单格入口共用的校验。


__all__ = ["PLACEHOLDER_YM", "parse_mech_values"]
