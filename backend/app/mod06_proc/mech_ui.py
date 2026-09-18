"""`MOD-06` **机械手录**（§5.2.5 ③）—— 区块渲染 ＋ 表单校验（**不连库**）。

口径：
- ⭐ **机械 6 列全段手录**（含历史段）—— 与材料列**相反**：材料列**恒只读**（引用 / 快照，§5.2.3），
  机械列**两段都能录**（出口 = `domain.column_editable`）。
- ⭐ 值落**旁路载体** `proc_mech_manual` ⇒ **不被重抓 i8 / 重导历史覆盖**（§5.2.5 ③ 与 §9.3 同源思路）。
- ⚠️ **0 是合法录入值**（表单空框与「录了 0」在金额上不可区分 ⇒ 空按 0 记）；
  **负数 / 非数字 ⇒ 报错且一个字都不写库**（`core.money.require_non_negative` 是值的唯一出口）。

⚠️ 本文件**只渲染与校验**：落库唯一出口 = `repository.save_mech`；路由只做「校验 → 调它 → PRG 回跳」。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import MoneyError, to_money
from app.mod06_proc import domain as D
from app.mod03_notice.page import esc

PLACEHOLDER_YM = "YYYY-MM"


def parse_mech_values(raw) -> dict[str, Decimal]:
    """表单 6 个框 → `{mech_i: Decimal}`。**空 ⇒ 0**；**非数字 / 负数 ⇒ `ValueError`**（带列名）。"""
    out: dict[str, Decimal] = {}
    for i, label in enumerate(D.MECH_COLUMNS):
        key = f"mech_{i}"
        text = str((raw or {}).get(key) or "").strip().replace(",", "")
        if not text:
            out[key] = Decimal("0.00")
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
#    ⚠️ 剩下的 `parse_mech_values` 才是**口径所在**（空按 0 / 负数与非数字报错 ✓ 壳与 `/api/m06/mech` 共用）；


__all__ = ["PLACEHOLDER_YM", "parse_mech_values", "block_html", "notice_html"]
