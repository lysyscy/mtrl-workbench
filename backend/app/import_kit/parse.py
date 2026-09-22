"""`import_kit.parse` —— 金额 / 日期 / 文本的**统一解析出口**（`TAIL-69`）。

⭐ 为什么收编：`parse_amount` 曾有 4 份实现、日期多格式 2 份 —— **同一口径 N 个主人**
   （2026-09-21 通用件审计 `TAIL-63` 的结论同型）。导入与 i8 抓取**必须走同一套解析**，
   两条路的结果才会一致（m08「同一条解析管线」判据是它的原型）。
⚠️ **金额禁 float 直传**（§9.1）—— 一律先转字符串再 `to_money`（唯一真源 = `app.core.money`）。
"""

from __future__ import annotations

from datetime import date, datetime

from app.core.money import to_money


def text(value) -> str:
    """单元格 → 干净文本（`None` ⇒ 空；日期 ⇒ ISO；其余 `str().strip()`）。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def amount(value):
    """金额取原文（禁 float 直传 ⇒ 先转字符串再归一，§9.1）；空 ⇒ 0。"""
    raw = text(value).replace(",", "")
    return to_money(raw) if raw else to_money(0)


def date_text(value) -> str:
    """日期多格式 → `YYYY-MM-DD` 文本（datetime/date 直取；字符串**原样交域内校验**）。"""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return text(value)


__all__ = ["text", "amount", "date_text"]
