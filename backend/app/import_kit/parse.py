"""`import_kit.parse` —— 金额 / 日期 / 文本的**统一解析出口**（`TAIL-69`）。

⭐ 为什么收编：`parse_amount` 曾有 4 份实现、日期多格式 2 份 —— **同一口径 N 个主人**
   （2026-09-21 通用件审计 `TAIL-63` 的结论同型）。导入与 i8 抓取**必须走同一套解析**，
   两条路的结果才会一致（m08「同一条解析管线」判据是它的原型）。
⚠️ **金额禁 float 直传**（§9.1）—— 一律先转字符串再 `to_money`（唯一真源 = `app.core.money`）。
"""

from __future__ import annotations

from datetime import date, datetime, time

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


def cell_text(value) -> str:
    """**读表出口**：任意单元格值 → 文本（日期/时间按 ISO 文本、整数值的浮点去掉小数点、其余走文本）。

    ⭐ 为什么必须有这一件（2026-09-26 用户报障 · 真上传台账 ⇒ 界面「解析失败：TypeError:
       Object of type time is not JSON serializable」）：
       读表底座 `readers.read_grid` 的 **xlsx 分支**原先把 `openpyxl` 的原生值**原样返回**
       （`datetime` / `date` / `time` / `Decimal`…），而预览载具 `core.preview_store` 落盘是
       `json.dumps(payload)`、装的正是读表给的 `grid_rows` ⇒ **遇到 `datetime.time` 当场抛**
       （用户原话：`解析失败：TypeError: Object of type time is not JSON serializable`）。
       ⚠️ 而 **`.xls` 分支早就文本化了** ⇒ 同一张台账存成两种格式曾是"一条能导、一条报错"
       —— 所以修在**读表这一层**，两个引擎共用本函数。
    ⚠️ 与 `text()` 的分工：`text()` 是"取某一格的值"的**通用出口**（值域宽松，域内解析都用它）；
       本件是**读表**出口 —— 比它多认 `time`（`08:30:00`）与"整数值的浮点"（Excel 里 `174`
       常被读成 `174.0`，写给用户看应当是 `174`，与 `.xls` 分支同口径）。
    ⚠️⚠️ **调用方注意**：`read_grid` 只把**JSON 装不下的**类型交给本函数，`str/int/float/bool/None`
       **原样保留** —— 序列号 / 金额的换算靠"值的类型"来判（见 `readers` 里那段注释）。
    """
    if value is None:
        return ""
    if isinstance(value, datetime):                    # ⚠️ 必须先判 datetime（它是 date 的子类）
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()                       # `08:30:00`（课表那种"上课时间"格）
    if isinstance(value, float) and value.is_integer():
        return str(int(value))                         # `174.0` ⇒ `174`
    return str(value).strip()                          # Decimal / str / bool / 其余


def amount(value):
    """金额取原文（禁 float 直传 ⇒ 先转字符串再归一，§9.1）；空 ⇒ 0。"""
    raw = text(value).replace(",", "")
    return to_money(raw) if raw else to_money(0)


#: Excel 日期序列号的合理区间（1900 日期系统：约 1954-10 ~ 2064-01）
_SERIAL_LO, _SERIAL_HI = 20000, 60000


def date_text(value) -> str:
    """日期多格式 → `YYYY-MM-DD` 文本（datetime/date 直取；**Excel 序列号**换算；字符串原样交域内校验）。

    ⭐ **Excel 序列号**（`45444` ⇒ `2024-06-01`）是设计 §六-补 列的"时间列 6 种形态"之一：
      真文件里那列常是**数字**（不是日期格式的单元格）⇒ `read_grid` 给的还是数字 ⇒ 在这一层换算。
    ⚠️ 只认 `20000~60000`：那以外的数字（`2025.09` 这种年月、金额）**原样返回**，由**域**去裁
      （年份 2025 落在区间外 ⇒ 不会被误当序列号）。
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return text(value)
    if isinstance(value, (int, float)) and _SERIAL_LO <= float(value) <= _SERIAL_HI:
        from datetime import timedelta

        return (datetime(1899, 12, 30) + timedelta(days=int(value))).date().isoformat()
    return text(value)


__all__ = ["text", "cell_text", "amount", "date_text"]
