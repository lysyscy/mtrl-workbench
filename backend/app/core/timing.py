"""时间口径的**全站唯一出口**。

依据：《材料科业务全流程说明书》**§9.2 时间口径**。
- **对外参数一律 `start_date` / `end_date`（ISO 闭区间）**；核算期仅作向后兼容保留
- **各表默认年月**（仅默认值、用户可改）：
  付款域（通知书 / 计划 / 流水）= **当月**；材料报表类（过程资料 / 收发结存 / 库存单据 / 特殊费用 / 大表）= **上月**
- **系统不设「全局核算期」概念**
- ⚠️ **月份过滤必须用日期闭区间**，不得用 `substr`（否则复合索引失效 —— 工程坑 1.2-6）；
  `substr` **只允许用于归月展示**（SELECT / GROUP BY）
- ⚠️ 抓取与导入**只允许「单月」**（业务上就是"一次一个月"）

⚠️ 本模块**不含**任何"默认年月"以外的业务判断；值一律以 §9.2 为准。
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

# 北京时间（§9.2 的"当月 / 上月"均按北京时间判定）
CN_TZ = timezone(timedelta(hours=8))


class TimeRangeError(ValueError):
    """时间入参非法 —— 必须显式报出。"""


# ------------------------------------------------------------------ 当前时间


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def today_cn() -> date:
    return now_cn().date()


# -------------------------------------------------------------- 年月与闭区间


def ym_of(d: date) -> str:
    """`date` → `YYYY-MM`（归月展示用）。"""
    return f"{d.year:04d}-{d.month:02d}"


def parse_ym(ym: str) -> tuple[int, int]:
    """`YYYY-MM` → `(year, month)`。"""
    raw = (ym or "").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise TimeRangeError(f"年月格式非法（应为 YYYY-MM）：{ym!r}")
    try:
        year, month = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise TimeRangeError(f"年月格式非法（应为 YYYY-MM）：{ym!r}") from exc
    if not (1 <= month <= 12) or year < 1900:
        raise TimeRangeError(f"年月超出合理范围：{ym!r}")
    return year, month


def month_range_closed(ym: str) -> tuple[date, date]:
    """`YYYY-MM` → 该月**首日 ~ 末日**（ISO 闭区间）。"""
    year, month = parse_ym(ym)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def shift_ym(ym: str, months: int) -> str:
    """年月加减（`months` 可为负）。"""
    year, month = parse_ym(ym)
    total = year * 12 + (month - 1) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


# ------------------------------------------------------------------ 默认年月


def default_ym_payment() -> str:
    """付款域默认年月 = **北京时间当月**（§9.2；仅默认值，用户可改）。"""
    return ym_of(today_cn())


def default_ym_report() -> str:
    """材料报表类默认年月 = **北京时间上月**（§9.2；月度报表做的是上一个月的账）。"""
    return shift_ym(ym_of(today_cn()), -1)


# ---------------------------------------------------------------- ISO 互转


def to_iso(d: date | datetime) -> str:
    return d.strftime("%Y-%m-%d")


def parse_iso_date(value: str | date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = (value or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise TimeRangeError(f"日期格式非法（应为 YYYY-MM-DD）：{value!r}") from exc


def validate_closed_range(start: str | date, end: str | date) -> tuple[date, date]:
    """校验闭区间：起 ≤ 止，否则显式报错（不静默交换）。"""
    s, e = parse_iso_date(start), parse_iso_date(end)
    if s > e:
        raise TimeRangeError(f"起止日期颠倒：start={s} > end={e}")
    return s, e


def ym_to_closed_range(ym: str) -> tuple[str, str]:
    """核算年月 → `(start_date, end_date)` 的 ISO 串（抓取/导出的统一换算出口）。"""
    s, e = month_range_closed(ym)
    return to_iso(s), to_iso(e)
