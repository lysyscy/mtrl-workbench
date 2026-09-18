"""`MOD-07` **焊材 / 气体提取**（§5.3.3）—— 纯函数域内核（从 `domain.py` 拆出，>400 行纪律）。

口径回主人处读，本处只落形态：
- 《说明书》**§5.3.3**（来源 = 收发结存原始数据、**按关键词提取**；去向 = **经济活动分析大表**）
- 配件：原型 `EXT_THEAD`（列结构 = 类别 / 仓库 / 总金额（累计）/ 金额（按所选月份））
- 实现层借鉴 = `PRD素材包-20260911/input/sfjc_extract.py`（⚠️ 只借鉴**规则形态**）：
  **气体 = 资源名称白名单精确匹配** · **焊材 = 关键词包含 ＋ 排除子串** · **统计列 = 收金额**

⚠️ **名单 / 关键词的取值**目前在素材包与代码里（《说明书》§5.3.3 未写取值）⇒ 见 `DEFAULT_*` 的注记。
⚠️ 取数源 = **收发结存明细**（`setl_detail.resource_name` 命中规则 ⇒ 汇总 `in_amt`）；
   金额的时间口径走 `core.period`（月 / 跨月 / 年 / 全部），**不在本处另解一遍**。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import sum_money
from app.mod07_setl.domain import TOTAL_LABEL, WAREHOUSE_KEY

# ⚠️ 本表**刻意不可排**（`sortable=False`）：一排序，分组合计就被卷到表尾（001-03）
EXTRACT_COLUMNS: tuple[dict, ...] = (
    {"key": "kind", "label": "类别", "type": "text", "sortable": False},
    {"key": "warehouse", "label": "仓库", "type": "text", "sortable": False},
    {"key": "total", "label": "总金额（累计）", "type": "num", "sortable": False},
    {"key": "amount", "label": "金额（按所选月份）", "type": "num", "sortable": False},
)

KINDS: tuple[str, ...] = ("焊材", "气体")

# 提取的**统计字段** = 收金额（入库金额；域内 key 见 `domain.AMOUNT_KEYS`）
EXTRACT_FIELD = "in"

# 项目状态（取值 = 原型 `pjStatus: ['在建','归档']` ＋「全部」；**DB 值与标签的映射在 `MOD-01`**）
STATUS_LABELS: tuple[str, ...] = ("在建", "归档")
STATUS_DEFAULT = STATUS_LABELS[0]
STATUS_ALL = "全部"
STATUS_OPTIONS: tuple[str, ...] = (*STATUS_LABELS, STATUS_ALL)

# ⭐ 提取规则的**默认值**（主人 = 素材包 `input/sfjc_extract.py` 的 `DEFAULT_GAS` / `weld_kw` / `not_weld`）
#    —— 气体：**白名单精确匹配**；焊材：**关键词（包含）＋ 排除子串**。
#    ⚠️ 三条都可覆盖（`extract_rules(...)`），取值口径**待回写《说明书》§5.3.3 并追认**。
DEFAULT_GAS_LIST: tuple[str, ...] = (
    "液氩", "氩气", "二氧化碳", "二氧化碳气", "液氧", "丙烷", "氧气",
)
DEFAULT_WELD_KEYWORDS: tuple[str, ...] = ("焊丝", "焊条", "焊锡丝")
DEFAULT_NOT_WELD: tuple[str, ...] = ()


def default_rules() -> dict:
    """提取规则的默认取值（三类）。"""
    return {"gas": DEFAULT_GAS_LIST, "weld": DEFAULT_WELD_KEYWORDS, "not_weld": DEFAULT_NOT_WELD}


def extract_rules(gas=None, weld=None, not_weld=None) -> dict:
    """提取规则的**唯一出口**（不给就是默认值）。"""
    base = default_rules()
    return {
        "gas": tuple(base["gas"] if gas is None else gas),
        "weld": tuple(base["weld"] if weld is None else weld),
        "not_weld": tuple(base["not_weld"] if not_weld is None else not_weld),
    }


def match_kind(resource_name: str, kind: str, rules: dict) -> bool:
    """资源名称是否属于 `kind` 类。

    - **气体** = 白名单**精确**匹配（`in`，不是包含）—— 免误伤（「氧气瓶」不是「氧气」）；
    - **焊材** = 关键词**包含**命中，且**不含**任一排除子串。
    ⚠️ 关键词按**子串**匹配、**不按正则**（素材包用 pandas 的 `contains` 默认带 regex；
       本项目按"关键词"本义实现，避免把配置文本当正则执行）。
    """
    name = str(resource_name or "")
    if not name:
        return False
    if kind == "气体":
        return name in {str(x) for x in rules.get("gas") or ()}
    if kind == "焊材":
        hit = any(str(kw) in name for kw in rules.get("weld") or () if str(kw))
        blocked = any(str(ex) in name for ex in rules.get("not_weld") or () if str(ex))
        return hit and not blocked
    return False


def extract_amounts(details, rules: dict | None = None) -> dict[str, dict[str, dict[str, Decimal]]]:
    """明细 → `{类别: {仓库: {月份: 金额}}}`（**取数唯一出口**；金额 = 收金额）。"""
    rules = rules or default_rules()
    out: dict[str, dict[str, dict[str, Decimal]]] = {k: {} for k in KINDS}
    for d in details or ():
        name = str(d.get("resource_name") or "")
        for kind in KINDS:
            if not match_kind(name, kind, rules):
                continue
            wh = str(d.get(WAREHOUSE_KEY) or "")
            ym = str(d.get("ym") or "")
            bucket = out[kind].setdefault(wh, {})
            bucket[ym] = sum_money([bucket.get(ym, Decimal("0.00")), d.get(EXTRACT_FIELD)])
    return out


def extract_months(amounts) -> list[str]:
    """**有数据的月份**（全部类别取并集、升序）—— 导出矩阵的月份列从它来（001-06）。"""
    months: set[str] = set()
    for _kind, whs in (amounts or {}).items():
        for _wh, by_ym in (whs or {}).items():
            months |= set(by_ym)
    return sorted(m for m in months if m)


def month_in_period(ym: str, period: str) -> bool:
    """月份是否落在所选**时间范围**内（月 / 跨月 / 年 / 全部）—— 口径走 `core.period`。"""
    from app.core.period import period_range

    start, end = period_range(period)
    if start is None:
        return True
    return start[:7] <= str(ym or "") <= end[:7]


def extract_total(by_ym: dict) -> Decimal:
    """「**总金额**」= **全部月份累计**（⛔ 不随所选月份变）。"""
    return sum_money(list((by_ym or {}).values()))


def extract_sum(by_ym: dict, period: str) -> Decimal:
    """「**金额**」= 所选**月份范围**内的金额（走统一年月控件）。"""
    return sum_money([v for ym, v in (by_ym or {}).items() if month_in_period(ym, period)])


def order_warehouses(names, preferred) -> list[str]:
    """按**项目档案顺序**排（`preferred` = 档案顺序）；不在档案里的（陌生仓库）排最后、按名字升序。"""
    pref = list(preferred or ())
    rank = {str(w): i for i, w in enumerate(pref)}
    return sorted(
        {str(n) for n in (names or ()) if n},
        key=lambda w: (rank.get(w, len(rank)), w),
    )


def visible_warehouses(wh_map, *, statuses=None, status: str = STATUS_DEFAULT,
                       order=None) -> list[str]:
    """该类别的**数据行**：按项目状态过滤（默认「在建」）＋ 按档案顺序排。

    ⚠️ 项目状态取自**项目档案行**（§5.3.3 / 原型 `extStatusOf`）；档案里没有的仓库（陌生仓库）
       状态视为空 ⇒ **只在「全部」下出现**（不臆造它是"在建"）。
    """
    st = dict(statuses or {})
    names = [w for w in (wh_map or {}) if w]
    if status and status != STATUS_ALL:
        names = [w for w in names if st.get(w, "") == status]
    return order_warehouses(names, order)


def extract_block(amounts, kind: str, *, warehouses, period: str) -> dict:
    """一个分组的**数据行 ＋ 合计行**（页面与导出共用这一份取数）。

    - 数据行：`{warehouse, total（全月累计）, amount（所选月份）}`
    - 合计行：只求 `total` / `amount` 两列（**逐项独立复算**，001-01）；
      ⚠️ 合计行由调用方**紧贴**本类数据行渲染（不得走到表尾，001-03）。
    """
    by_ym_all = (amounts or {}).get(kind) or {}
    rows = [
        {"kind": kind, "warehouse": w,
         "total": extract_total(by_ym_all.get(w) or {}),
         "amount": extract_sum(by_ym_all.get(w) or {}, period)}
        for w in (warehouses or ())
    ]
    total_row = {
        "kind": kind, "warehouse": f"{kind}{TOTAL_LABEL}",
        "total": sum_money([r["total"] for r in rows]),
        "amount": sum_money([r["amount"] for r in rows]),
    }
    return {"kind": kind, "rows": rows, "total_row": total_row}


# ============================================================ 成品导出（路径① 模板填充）

#: 模板的月份列数（`1月`…`12月`）
YEAR_MONTHS = 12


def month_columns(year: str) -> list[str]:
    """一年的 **12 个月**（`YYYY-MM` 升序）—— 模板 `1月`…`12月` 那 12 列。

    ⚠️ 模板表头**没写年份**（裁定④：月份列都属**该年**）⇒ 年份由调用方按报告期给。
    """
    return ["%s-%02d" % (str(year or "").strip(), m) for m in range(1, YEAR_MONTHS + 1)]


def extract_template_grid(amounts, kind: str, *, warehouses, year: str, balances=None) -> dict:
    """**模板形态**的显示网格（行 = 项目 · 列 = `结余` ＋ 该年 12 个月 ＋ `合计`）。

    - 行 = `warehouses`（调用方已按**项目状态 + 档案顺序**筛好 —— 与页面同一份口径）；
    - `结余` = `balances[kind][仓库]` —— ⚠️ **2026-09-18 用户裁定：结余 = 历史结余、由用户手动录入**
      ⇒ **系统没有任何来源**（⛔ 不是收发结存的 `end_amt` 派生，那是错的）；
      未录入 / 尚无录入入口 ⇒ `None` ⇒ 实现层**写空**（⛔ 既不写 0、也不把模板里的示例值带走）。
      ⇒ `balances` 是**留好的接缝**：录入入口落地后由调用方传进来，本函数不动。
    - 月份格 = 该月金额（**该月无数据 ⇒ `None`**，⛔ 不写 0 —— 0 会被读成"确实为 0"）；
    - `合计` = **该年 12 个月之和**（= 模板「合计」列 / 页面「总金额（累计）」在该年的口径；
      与页面 `extract_total` 的差别只在于**限年**，而 12 列本身就是该年 ⇒ 两者同源）；
    - `sum_row` = 各月列之和 ＋ 合计列之和（模板合计行那一行）。⚠️ `结余` 列**不参与**（模板即如此）。
    """
    months = month_columns(year)
    by_ym_all = (amounts or {}).get(kind) or {}
    bal = (balances or {}).get(kind) or {}
    rows: list[dict] = []
    for w in warehouses or ():
        by_ym = by_ym_all.get(w) or {}
        cells = [(by_ym.get(m) or None) for m in months]
        rows.append({
            "warehouse": w,
            "balance": bal.get(w),
            "cells": cells,
            "total": sum_money([c for c in cells if c is not None]),
        })
    sums = [sum_money([r["cells"][i] for r in rows if r["cells"][i] is not None])
            for i in range(len(months))]
    return {"kind": kind, "year": str(year or ""), "months": months, "rows": rows,
            "sum_row": sums + [sum_money([r["total"] for r in rows])]}


def extract_export_matrix(amounts, kind: str, *, warehouses) -> dict:
    """导出矩阵（001-06）：**行 = 所筛选项目 · 列 = 项目 → 最早有数据的月 → …（逐月连续）→ 求和**。

    ⚠️ 月份列 = **全部类别有数据的月份并集**（原型 `extMons()` 同款）⇒ 两个分组的列一致。
    ⚠️ 末列「求和」= 该项目**全月累计**（= 页面「总金额」列，同源）。
    """
    months = extract_months(amounts)
    by_ym_all = (amounts or {}).get(kind) or {}
    rows: list[dict] = []
    for w in warehouses or ():
        by_ym = by_ym_all.get(w) or {}
        rows.append({
            "warehouse": w,
            "cells": [(by_ym.get(m) or Decimal("0.00")) for m in months],   # 该月金额（缺省 0）
            "total": extract_total(by_ym),
        })
    sums = [sum_money([r["cells"][i] for r in rows]) for i in range(len(months))]
    return {"kind": kind, "months": months, "rows": rows,
            "sum_row": sums + [sum_money([r["total"] for r in rows])]}


__all__ = [
    "EXTRACT_COLUMNS", "KINDS", "EXTRACT_FIELD",
    "STATUS_LABELS", "STATUS_DEFAULT", "STATUS_ALL", "STATUS_OPTIONS",
    "DEFAULT_GAS_LIST", "DEFAULT_WELD_KEYWORDS", "DEFAULT_NOT_WELD",
    "YEAR_MONTHS",
    "default_rules", "extract_rules", "match_kind", "extract_amounts", "extract_months",
    "month_in_period", "extract_total", "extract_sum", "order_warehouses",
    "visible_warehouses", "extract_block", "extract_export_matrix",
    "month_columns", "extract_template_grid",
]
