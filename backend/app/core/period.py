"""核算年月 / 时间口径（`§9.2`）—— **全站共用**（`MOD-01` · `MOD-02` 等）。

依据：《说明书》**§9.2 时间口径** · `ACC-I8-TIME-001`。

要点（口径回主人，本处只落形态）：
- 对外参数一律 `start_date` / `end_date`（ISO **闭区间**）；核算期仅作**向后兼容**。
- 四种模式 **共用一个选择器**：单月 / 跨月 / 整年 / 全部；**能力由调用点声明**。
- **抓取与导入只允许「单月」**（业务上就是"一次一个月"）。
- **不设「全局核算期」**。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from app.core.errors import MustReportError

MODE_MONTH = "month"
MODE_SPAN = "span"
MODE_YEAR = "year"
MODE_ALL = "all"
ALL_MODES = (MODE_MONTH, MODE_SPAN, MODE_YEAR, MODE_ALL)

# ⚠️ 本系统**不设「全局核算期」**（§9.2 / 001-07）；顶栏不再有全局年月控件。
GLOBAL_PERIOD = None

# 组件规格（全站唯一，001-01）
PERIOD_COMPONENT = {
    "id": "acc-period",
    "modes": ALL_MODES,
    "note": "全站唯一的时间选择组件；顶栏无全局年月控件",
}

# 调用点声明（001-02）：列表页放开 4 种；**抓取弹窗 / 期初截止年月 / 特殊费用月报表只声明「月」**
# （`fee` = `MOD-09` 特殊费用月报表：业务上就是"一次一个月"，§5.5 能力 8 ⇒ 只开放按月）
_LIST_MODES = (MODE_MONTH, MODE_SPAN, MODE_YEAR, MODE_ALL)
_MONTH_ONLY = (MODE_MONTH,)


def period_capabilities(context: str) -> tuple[str, ...]:
    """**能力由调用点声明**（001-02）—— 返回该调用点允许的时间模式。"""
    return _MONTH_ONLY if context in ("fetch", "opening", "fee") else _LIST_MODES


def default_period(table: str, now: date | None = None) -> str:
    """各表**默认年月**（§9.2）：付款侧（通知书/计划/流水）= **当月**；材料报表类 = **上月**。

    ⚠️ 只是**默认值**，用户可改；本函数只钉默认口径。
    """
    now = now or date.today()
    first = now.replace(day=1)
    if table in ("notice", "plan", "flow"):
        return first.strftime("%Y-%m")
    return (first - timedelta(days=1)).replace(day=1).strftime("%Y-%m")


def parse_period(value: str) -> tuple[str, str]:
    """解析时间范围取值 → `(mode, value)`。形态：`2026-08` / `2026-01~2026-06` / `2026` / 空。

    ⚠️ 跨月 = **两击选区间**，形态 `YYYY-MM~YYYY-MM`（001-03）。
    """
    v = (value or "").strip()
    if not v:
        return MODE_ALL, ""
    if re.fullmatch(r"\d{4}-\d{2}~\d{4}-\d{2}", v):
        return MODE_SPAN, v
    if re.fullmatch(r"\d{4}-\d{2}", v):
        return MODE_MONTH, v
    if re.fullmatch(r"\d{4}", v):
        return MODE_YEAR, v
    raise MustReportError(f"时间范围取值格式非法：「{value}」（应为 YYYY-MM / YYYY-MM~YYYY-MM / YYYY / 空）")


def period_range(value: str) -> tuple[str | None, str | None]:
    """时间范围 → **闭区间** ISO 起止日期 `(start, end)`（001-03 / 001-04）。

    - 单月 → 该月 1 日 ~ 该月最后一日
    - 跨月 → 起月 1 日 ~ 止月最后一日（**闭区间**）
    - 年 → 1/1 ~ 12/31
    - 全部 → `(None, None)`
    """
    mode, v = parse_period(value)
    if mode == MODE_ALL:
        return None, None
    if mode == MODE_MONTH:
        return _month_bounds(v)
    if mode == MODE_YEAR:
        return f"{v}-01-01", f"{v}-12-31"
    a, b = v.split("~")
    if a > b:
        raise MustReportError(f"时间范围起止颠倒：「{value}」")
    return _month_bounds(a)[0], _month_bounds(b)[1]


def _month_bounds(ym: str) -> tuple[str, str]:
    y, m = int(ym[:4]), int(ym[5:7])
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return f"{y:04d}-{m:02d}-01", (nxt - timedelta(days=1)).isoformat()


def in_period(row_date: str | None, value: str) -> bool:
    """行日期是否落在所选时间范围内（**闭区间**）。空值 / 非法值 → 不命中。"""
    if not row_date:
        return False
    start, end = period_range(value)
    if start is None:
        return True
    d = str(row_date)[:10]
    return start <= d <= end


def month_of(value: str) -> str | None:
    """单月取值的月份（供导出文件名等用）；非单月 → None。"""
    mode, v = parse_period(value)
    return v if mode == MODE_MONTH else None


def export_filename(table: str, value: str, now: datetime | None = None) -> str:
    """导出文件名用**当前年月**（001-07）—— 单月取该月、否则取「当前年月」；**不得硬编码固定月**。"""
    m = month_of(value)
    if m:
        return f"{table}-{m}"
    return f"{table}-{(now or datetime.now()).strftime('%Y-%m')}"


__all__ = [
    "MODE_MONTH", "MODE_SPAN", "MODE_YEAR", "MODE_ALL", "ALL_MODES",
    "GLOBAL_PERIOD", "PERIOD_COMPONENT",
    "period_capabilities", "default_period", "parse_period", "period_range",
    "in_period", "month_of", "export_filename",
]
