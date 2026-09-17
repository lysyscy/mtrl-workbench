"""`MOD-08` 库存单据与调整单 —— **域内核（纯函数：不连库、不写路由）**。

口径主人（本文件**只落形态**，取值一律回主人处读）：
- 《说明书》**§5.4**（定位 = 对账主工具 / 三张产出）· **§3.4**（关键字段）· **§9.2**（默认核算年月）
- 《说明书》**§5.2.4** · `DEV-R-07`（**调整单**：打在单据行上 · 不改源数据 · 留痕 + 必填备注）
- 《说明书》**§9.3**（留痕范围：调整单 → 改前 / 改后 / 改动人 / 时间 + 备注）· **§8.4 第②档**（可改金额判据 = **≥ 0**）
- 列清单的**现行来源 = i8 导出文件的表头**（附录 `E.1.1`）；**旁证** = `PRD素材包-20260911/input/schema_cols.py`
  （⚠️ 旁证只作实现参考，冲突以实跑导出为准）
- 页面 / 交互 = `demo/` 原型 `V.m08`（**原型即交互规格**）；导出形态 = `demo/模板/模板清单.md` §二 第 10–12 行

⚠️ **两处刻意与原型演示实现不同（口径 > 原型，非"另立"）**：
1. **「核算年月」筛的是行的「核算年月」**，不是「单据日期」—— 口径主人 = §9.2（报表类按核算年月）
   与 §3.4（导出条件 = 核算年月 + 指定项目）；原型演示数据里没有核算月列，故用单据日期前缀代替。
2. **合计只求有业务含义的数值列**（数量 / 金额 / 调整后金额 / 价税合计），两个**单价列不求和** —— 与原型一致。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import MoneyError, require_non_negative, sum_money
from app.core.period import default_period, in_period, month_of

# ============================================================ 出入库方向（§3.4）

DIRECTION_ALL = "全部"
DIRECTION_IN = "入库"
DIRECTION_OUT = "出库"
DIRECTIONS: tuple[str, ...] = (DIRECTION_ALL, DIRECTION_IN, DIRECTION_OUT)

# ============================================================ 页面「明细总表」列（唯一出口）
# 主人 = **原型 `INV_THEAD`**（交互规格）；`key` = 域内规范字段名（视图 / API 一律用它，**不得写列名字面量**）。
# 列型：`text` / `enum` / `date` → 「包含」输入 + 值清单；`num` → 「≥ / ≤」区间 **＋** 值清单。
# ⚠️ 末列「操作」是**页面专有**（按钮 HTML）⇒ `/api/*` 导出必须剔除（全站同款，见 `mod03_notice`）。
INV_TABLE_COLUMNS: tuple[dict, ...] = (
    {"key": "doc_no", "label": "单据编号", "type": "text"},
    {"key": "seq", "label": "序号", "type": "text"},
    {"key": "direction", "label": "方向", "type": "enum"},
    {"key": "material", "label": "物料", "type": "text"},
    {"key": "spec", "label": "规格", "type": "text"},
    {"key": "unit", "label": "单位", "type": "enum"},
    {"key": "qty", "label": "数量", "type": "num"},
    {"key": "price_excl", "label": "不含税单价", "type": "num"},
    {"key": "price_incl", "label": "含税单价", "type": "num"},
    {"key": "amount", "label": "金额", "type": "num"},
    {"key": "adj_amount", "label": "调整后金额", "type": "num"},
    {"key": "tax_total", "label": "价税合计", "type": "num"},
    {"key": "biz_type", "label": "业务类型", "type": "enum"},
    {"key": "vendor", "label": "供应商 / 班组", "type": "text"},
    {"key": "doc_date", "label": "单据日期", "type": "date"},
    {"key": "audit_date", "label": "审核日期", "type": "date"},
    {"key": "warehouse", "label": "仓库", "type": "enum"},
    {"key": "wbs_name", "label": "wbs 名称", "type": "text"},
    {"key": "cbs_name", "label": "cbs 名称", "type": "text"},
    {"key": "ops", "label": "操作", "type": "page"},
)

# 页面专有列（**不进 `/api/*` 导出**）
PAGE_ONLY_KEYS: tuple[str, ...] = ("ops",)

# ⭐ 表内「合计」行**只求有业务含义的数值列**；两个单价列**刻意不求和**（单位价求和无业务含义）
SUM_KEYS: tuple[str, ...] = ("qty", "amount", "adj_amount", "tax_total")
NO_SUM_KEYS: tuple[str, ...] = ("price_excl", "price_incl")
# 调整后金额（派生列；**不落 i8 源数据**，来自调整单 —— `ENT-04`）
ADJ_KEY = "adj_amount"

# ============================================================ §3.4 关键字段 → 页面列（001-01 的对照表）

# 口径主人 =《说明书》§3.4「关键字段」行。`None` = **本系统刻意不建**（`NG-06`），须在此显式登记。
KEY_FIELD_MAP: tuple[tuple[str, str | None], ...] = (
    ("单据编号", "doc_no"),
    ("序号", "seq"),
    ("出入库方向", "direction"),
    ("物料信息", "material"),
    ("数量", "qty"),
    ("不含税单价", "price_excl"),
    ("含税单价", "price_incl"),
    ("金额", "amount"),
    ("价税合计", "tax_total"),
    ("业务类型", "biz_type"),
    ("供应商·班组·部门", "vendor"),
    ("单据日期", "doc_date"),
    ("审核日期", "audit_date"),
    ("是否作废", None),          # ⛔ NG-06：i8 源里有、本系统**不建**
    ("wbs 名称", "wbs_name"),
    ("cbs 名称", "cbs_name"),
)

# ⛔ 硬边界（`MOD-08.md` §三）
FORBIDDEN_FIELDS: tuple[str, ...] = ("是否作废",)      # NG-06
FORBIDDEN_ACTIONS: tuple[str, ...] = ("delete", "del")  # NG-03：本页**不新增删除入口**

# ============================================================ i8 导出网格（旁证）
# 旁证 = `PRD素材包-20260911/input/schema_cols.py::KCDJ_COLS`（**现行来源 = i8 导出表头**，§E.1.1）
INV_GRID_COLUMNS: tuple[str, ...] = (
    "序号", "核算年", "核算月", "业务类型", "项目名称", "单据编号", "供应商", "安全费用",
    "物料名称", "计量单位", "规格型号", "物料性质", "数量", "不含税单价", "含税单价",
    "金额", "价税合计", "出入库方向", "仓库", "班组", "部门", "单据日期", "审核日期",
    "是否作废", "wbs编号", "wbs名称", "cbs编号", "cbs名称",
)
INV_GRID_NUM_FIELDS: frozenset[str] = frozenset(
    {"数量", "不含税单价", "含税单价", "金额", "价税合计"}
)


def grid_index(name: str) -> int:
    """网格列名 → 下标（0 起算）。未登记 ⇒ **报错不猜**（§7.1「清单里没有的模板列 ⇒ 报错不猜」同款）。"""
    try:
        return INV_GRID_COLUMNS.index(name)
    except ValueError as exc:  # pragma: no cover - 兜底
        raise KeyError(f"i8 导出网格里没有这一列：{name}") from exc


# ============================================================ 列元数据 / 取值


def column_meta(key: str) -> dict | None:
    for col in INV_TABLE_COLUMNS:
        if col["key"] == key:
            return col
    return None


def filterable_keys() -> tuple[str, ...]:
    """**可筛的列** —— 除末列「操作」外每列都有筛选入口（001-05）。"""
    return tuple(c["key"] for c in INV_TABLE_COLUMNS if c["key"] not in PAGE_ONLY_KEYS)


def is_adjusted(row: dict) -> bool:
    """该行是否被**调整单**改过（`ENT-04`）。"""
    return row.get(ADJ_KEY) is not None and str(row.get(ADJ_KEY)) != ""


def raw_value(row: dict, key: str):
    """某列的**原始取值**（用于筛选 / 值清单 / 合计）：调整后金额 = 调整单的值，未被调过 ⇒ 空。"""
    if key == ADJ_KEY:
        return row.get(ADJ_KEY) if is_adjusted(row) else ""
    return row.get(key, "")


def cell_text(row: dict, key: str) -> str:
    value = raw_value(row, key)
    return "" if value is None else str(value)


# ============================================================ 筛选（001-03 / 004 / 005 / 006）


def _num(value) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:  # noqa: BLE001 - 非数值一律视为不可比
        return None


def col_pass(row: dict, key: str, f: dict | None) -> bool:
    """该行是否通过**某一列**的列筛选条件。

    语义（与原型 `ivColPass` 一致）：**多选值之间是「或」，与「包含」「≥ / ≤」之间是「与」**。
    ⚠️ 数值列的**值清单勾选必须真的生效**（原型曾漏判、已更正）—— 本出口一并钉住。
    """
    if not f:
        return True
    meta = column_meta(key)
    if meta is None:
        return True
    values = [str(v) for v in (f.get("v") or [])]
    if meta["type"] == "num":
        raw = raw_value(row, key)
        num = _num(raw)
        if num is None:
            return False                      # 空值不参与数值列筛选
        lo, hi = f.get("min"), f.get("max")
        if lo not in (None, "") and not num >= _num(lo):
            return False
        if hi not in (None, "") and not num <= _num(hi):
            return False
        if values and str(raw) not in values:
            return False
        return True
    text = cell_text(row, key)
    q = f.get("q")
    if q not in (None, "") and str(q).lower() not in text.lower():
        return False
    if values and text not in values:
        return False
    return True


def coarse_rows(
    rows: list[dict],
    *,
    ym: str | None = None,
    projects: tuple[str, ...] | list[str] = (),
    direction: str = DIRECTION_ALL,
    only_adjusted: bool = False,
) -> list[dict]:
    """**粗筛**（核算年月 + 项目 + 出入库方向 + 只看被调整行）—— 值清单就是按它算的。

    `ym` = **时间范围取值**（§9.2 四种模式共用一套解析：`2026-08` / `2026-01~2026-06` / `2026` / 空），
    匹配的是行的**核算年月**（拿 `YM + "-01"` 走 `core.period.in_period` 的闭区间判定，**不另写一套**）。

    ⚠️ 与原型同款：值清单 = 「当前可见范围内出现过的值」，**不把列条件自身算进去**（否则自我循环）。
    """
    wanted = {str(p) for p in (projects or ()) if str(p) != ""}
    out: list[dict] = []
    for row in rows or ():
        if ym and not in_period(f"{row.get('ym') or ''}-01", ym):
            continue
        if wanted and str(row.get("warehouse") or "") not in wanted:
            continue
        if direction != DIRECTION_ALL and str(row.get("direction") or "") != direction:
            continue
        if only_adjusted and not is_adjusted(row):
            continue
        out.append(row)
    return out


def filter_rows(
    rows: list[dict],
    *,
    ym: str | None = None,
    projects: tuple[str, ...] | list[str] = (),
    direction: str = DIRECTION_ALL,
    only_adjusted: bool = False,
    col_filters: dict | None = None,
) -> list[dict]:
    """粗筛 ＋ **列条件（列内「与」、列间「与」）**（001-03 / 004 / 005 / 006）。"""
    filters = col_filters or {}
    coarse = coarse_rows(rows, ym=ym, projects=projects, direction=direction,
                         only_adjusted=only_adjusted)
    return [r for r in coarse if all(col_pass(r, k, filters.get(k)) for k in filterable_keys())]


def distinct_values(
    rows: list[dict],
    key: str,
    *,
    ym: str | None = None,
    projects: tuple[str, ...] | list[str] = (),
    direction: str = DIRECTION_ALL,
    only_adjusted: bool = False,
) -> list[str]:
    """某列的**值清单**：粗筛范围内出现过的值（去重、字典序）。"""
    coarse = coarse_rows(rows, ym=ym, projects=projects, direction=direction,
                         only_adjusted=only_adjusted)
    return sorted({cell_text(r, key) for r in coarse if cell_text(r, key) != ""})


def active_column_count(col_filters: dict | None) -> int:
    """已设条件的列数（页头提示用）。"""
    n = 0
    for key in filterable_keys():
        f = (col_filters or {}).get(key) or {}
        if (f.get("v") or []) or (f.get("q") not in (None, "")) \
                or (f.get("min") not in (None, "")) or (f.get("max") not in (None, "")):
            n += 1
    return n


# ============================================================ 表内合计（001-07）


def sum_cells(rows: list[dict]) -> dict[str, Decimal | None]:
    """**表内「合计」行**的取值（唯一出口）—— 逐列独立复算、随筛选变动。

    只求 `SUM_KEYS`；两个单价列给 `None`（合计行里留空，**不臆造 0**）；其余列同样留空。
    """
    out: dict[str, Decimal | None] = {}
    for key in SUM_KEYS:
        picked = [raw_value(r, key) for r in rows or () if raw_value(r, key) not in (None, "")]
        out[key] = sum_money(picked) if picked else None
    for key in NO_SUM_KEYS:
        out[key] = None
    return out


# ============================================================ 调整单（001-09 / 010）


def adjustment_problem(new_amount, remark: str) -> str | None:
    """调整单的**输入判据**（唯一出口）：返回错误文本，`None` = 合法。

    档位 = **§8.4 第②档 ≥ 0**（与付款通知书三金额同档）：**0 合法**（把某行修正为 0）、**负值无意义 ⇒ 拦**。
    备注**必填**（`ENT-04`：留痕 + 留备注）。
    """
    try:
        require_non_negative(new_amount, field="调整后金额")
    except MoneyError as exc:
        return str(exc)
    if not str(remark or "").strip():
        return "调整备注必填（调整单必须留痕 + 留备注，ENT-04）"
    return None


def make_adjustment(
    row: dict, new_amount, remark: str, *, operator: str, at: str = ""
) -> dict:
    """生成一条调整单记录（**纯函数**：不改动传入的源行 —— 源数据永不被人工修改，§9.3）。

    ⚠️ 调整单**打在单据行**上（不是按项目 / 月打总单）；`before` 取的是**该行的 i8 原始金额**。
    """
    problem = adjustment_problem(new_amount, remark)
    if problem:
        raise ValueError(problem)
    return {
        "row_id": row.get("id"),
        "before": row.get("amount"),
        "after": new_amount,
        "remark": str(remark).strip(),
        "operator": operator,
        "at": at or None,
    }


def with_adjustment(row: dict, adj: dict) -> dict:
    """叠加调整单后的行（**返回新 dict**：`amount` 等原始值一字不动，只多出派生列）。"""
    merged = dict(row)
    merged[ADJ_KEY] = adj.get("after")
    merged["adj_remark"] = adj.get("remark", "")
    merged["adj_operator"] = adj.get("operator", "")
    merged["adj_at"] = adj.get("at")
    return merged


# ============================================================ 抓取弹窗（001-11）


def fetch_dialog_default(current_period: str) -> str:
    """「按月抓取」弹窗的**默认月份** = **本页当前所选核算年月**（001-11）。

    ⚠️ 抓取只允许「单月」（§9.2）；当前所选不是单月（跨月 / 整年 / 全部）时，回落到本表的默认年月。
    """
    return month_of(current_period) or default_period("inventory")


# ============================================================ 导出（001-12）

EXPORT_PLAIN = "plain"
EXPORT_PIVOT = "pivot"

# 「导出（含数据透视表）」的**工作簿形态** —— 主人 = `demo/模板/模板清单.md` §二 第 10–12 行
# ⚠️ 提示文案**必须与该形态一致**（不得声称与实例不符的形态）；它是**路径②**（脚本直接改 i8 导出源文件），
#    与主表那份朴素导出**互不影响**。
PIVOT_SHEETS: tuple[str, ...] = ("报表1", "「过程资料」透视", "「安全文明施工费」透视")


def export_kinds() -> tuple[dict, ...]:
    """本页**并存**的两种导出（001-12）。"""
    return (
        {"id": EXPORT_PLAIN, "label": "导出 Excel（R1）", "hint": "按页面列朴素导出，与列筛选结果一致"},
        {"id": EXPORT_PIVOT, "label": "导出（含数据透视表）", "hint": pivot_hint()},
    )


def pivot_hint() -> str:
    """「含数据透视表」那份的提示 —— **逐项写明工作簿里有什么**（与模板实际形态一致）。"""
    detail = "；".join(
        f"工作表 {i + 1} = {name}" for i, name in enumerate(PIVOT_SHEETS)
    )
    return (
        f"额外导出一份带「数据透视表」的工作簿：{detail}。"
        "该份走路径②（脚本直接改 i8 导出源文件、含真·透视表），"
        "主表那份朴素导出不受影响。"
    )


# ============================================================ 硬边界（001-13）


def boundary_violations(column_keys=(), action_ids=()) -> list[str]:
    """硬边界自检（空 = 合规）：**不新增删除入口**（`NG-03`）· **不建「是否作废」字段**（`NG-06`）。

    `column_keys` 可传**列 key** 或**列名**（未登记的取值按原样比对 ⇒ 也能挡住"新加的野列"）。
    """
    bad: list[str] = []
    labels: list[str] = []
    for k in column_keys or ():
        meta = column_meta(k)
        labels.append(str(meta["label"]) if meta else str(k))
    for name in FORBIDDEN_FIELDS:
        if name in labels:
            bad.append(f"本页不得出现「{name}」字段（NG-06）")
    for act in action_ids or ():
        if str(act).lower() in FORBIDDEN_ACTIONS:
            bad.append(f"本页不得出现删除入口（动作 {act}，NG-03）")
    return bad


__all__ = [
    "DIRECTIONS", "DIRECTION_ALL", "DIRECTION_IN", "DIRECTION_OUT", "INV_TABLE_COLUMNS",
    "PAGE_ONLY_KEYS", "SUM_KEYS", "NO_SUM_KEYS", "ADJ_KEY", "KEY_FIELD_MAP",
    "FORBIDDEN_FIELDS", "FORBIDDEN_ACTIONS", "INV_GRID_COLUMNS", "INV_GRID_NUM_FIELDS",
    "grid_index", "column_meta", "filterable_keys", "is_adjusted", "raw_value", "cell_text",
    "col_pass", "coarse_rows", "filter_rows", "distinct_values", "active_column_count",
    "sum_cells", "adjustment_problem", "make_adjustment", "with_adjustment",
    "fetch_dialog_default", "EXPORT_PLAIN", "EXPORT_PIVOT", "PIVOT_SHEETS", "export_kinds",
    "pivot_hint", "boundary_violations",
]
