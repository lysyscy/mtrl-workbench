"""`API-03` 库存单据明细导出 → **解析**（xlsx 网格 → 域内规范行）。

依据：
- 《说明书》**§3.4**（库存单据明细 = 对账主工具；「仓库 + 项目全名」两把钥匙）· **§9.2**（核算年月）
- 《说明书》附录 **E.1.1**：i8 导出是 **xlsx 网格（不是实体行）**，**列清单的现行来源 = i8 导出文件的表头**
  （旁证 = 素材包 `input/schema_cols.py`，⚠️ 冲突以实跑导出为准）⇒ 本模块**按表头文字认列**，**不写死下标**
- ⛔ `NG-06`：i8 源里有「是否作废」、**本系统不建** ⇒ 解析时**显式丢弃该列**（不落库、也不塞进 `raw`）

⚠️ **认不出的列 ⇒ 报错不猜**；**关键列缺失 ⇒ 整批拒绝并指出行号**（不静默丢行）。
⚠️ 金额一律经 `core.money`（元 / 2 位小数 / `ROUND_HALF_UP`）。
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from app.core.errors import MustReportError
from app.core.money import MoneyError, to_money

# 表头关键字（用于**定位表头行**；导出文件表头不在固定行，见素材包 `common_tpl.read_data` 同款思路）
HEADER_KEYWORDS: tuple[str, ...] = ("序号", "金额")

# 表头 → 域内字段（**列映射的唯一出口**）
COLUMN_MAP: tuple[tuple[str, str], ...] = (
    ("单据编号", "doc_no"),
    ("序号", "seq"),
    ("出入库方向", "direction"),
    ("物料名称", "material_name"),
    ("物料性质", "material_property"),
    ("规格型号", "spec"),
    ("计量单位", "unit"),
    ("数量", "qty"),
    ("不含税单价", "price_excl"),
    ("含税单价", "price_incl"),
    ("金额", "amount"),
    ("价税合计", "tax_total"),
    ("业务类型", "biz_type"),
    ("单据日期", "doc_date"),
    ("审核日期", "audit_date"),
    ("仓库", "warehouse_name"),
    ("wbs名称", "wbs_name"),
    ("cbs名称", "cbs_name"),
    ("项目名称", "bill_name_full"),
)

# 缺一列就**整批拒绝**的列（少了它这行就没有意义）
REQUIRED_HEADERS: tuple[str, ...] = (
    "核算年", "核算月", "单据编号", "序号", "出入库方向",
    "仓库", "物料名称", "物料性质", "数量", "金额",
)
# 核算年月由这两列拼（§9.2 报表类按核算年月）
YM_HEADERS: tuple[str, ...] = ("核算年", "核算月")
# 「供应商 · 班组 · 部门」在页面上合成一列（§3.4 关键字段）
VENDOR_HEADERS: tuple[str, ...] = ("供应商", "班组", "部门")
# ⛔ 明确**不采**的源列（`NG-06`：i8 有、本系统不建）—— 丢弃，且**不塞进 raw**
IGNORED_HEADERS: tuple[str, ...] = ("是否作废",)

NUMERIC_FIELDS: frozenset[str] = frozenset(
    {"qty", "price_excl", "price_incl", "amount", "tax_total"}
)

SHEET_PREFERRED = ("报表1", "Sheet1")
HEADER_SCAN_ROWS = 10          # 表头只在**前若干行**里找


def _norm(value) -> str:
    return "" if value is None else str(value).strip()


def read_grid(content: bytes) -> list[list]:
    """xlsx 字节 → `list[list]`（取「报表1 / Sheet1」那张工作表）。"""
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(content), data_only=True, read_only=True)
    try:
        name = next((s for s in SHEET_PREFERRED if s in wb.sheetnames), wb.sheetnames[0])
        ws = wb[name]
        return [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def find_header_row(rows: list[list]) -> int:
    """定位表头行：前若干行里**同时含 `HEADER_KEYWORDS`** 的那一行。找不到 ⇒ 报错。"""
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        cells = {_norm(c) for c in row}
        if all(k in cells for k in HEADER_KEYWORDS):
            return idx
    raise MustReportError(
        f"在导出文件的前 {HEADER_SCAN_ROWS} 行里找不到表头（应同时含 {' / '.join(HEADER_KEYWORDS)}）"
        f" —— 文件形态可能变了，请核对后再导"
    )


def map_columns(header: list[str]) -> dict[str, int]:
    """表头 → `{列名: 下标}`（**按文字认列**，不写死下标）；**关键列缺失 ⇒ 报错不猜**。"""
    names = [_norm(c) for c in header]
    index = {n: i for i, n in enumerate(names) if n}
    missing = [h for h in REQUIRED_HEADERS if h not in index]
    if missing:
        raise MustReportError(
            f"导出文件缺少关键列：{' / '.join(missing)} —— 导出表头可能变了（列清单主人 = i8 导出表头），"
            f"实际表头：{names}"
        )
    return index


def _ym_of(row: list, index: dict[str, int]) -> str:
    year = _norm(row[index["核算年"]]).split(".")[0]
    month = _norm(row[index["核算月"]]).split(".")[0]
    if not year or not month:
        raise MustReportError("核算年 / 核算月 为空 —— 无法定位核算年月")
    return f"{int(year):04d}-{int(float(month)):02d}"


def _num_of(raw, *, header: str, row_no: int):
    """数字列：**空 ⇒ 0**；**非数字 ⇒ 报错**（带行号与原文，不静默吞掉）。"""
    text = _norm(raw).replace(",", "").replace("，", "")
    if text == "":
        return Decimal("0.00")
    try:
        return to_money(text)
    except MoneyError as exc:
        raise MustReportError(f"第 {row_no} 行「{header}」不是数字：{raw!r}（{exc}）") from exc


def parse_rows(content: bytes) -> list[dict]:
    """xlsx 字节 → 域内规范行（`list[dict]`）。**行内一次都不落库**（纯函数）。"""
    grid = read_grid(content)
    head = find_header_row(grid)
    index = map_columns([_norm(c) for c in grid[head]])

    out: list[dict] = []
    for offset, raw_row in enumerate(grid[head + 1:], start=head + 2):
        if not any(_norm(c) for c in raw_row):
            continue                                    # 整行空 ⇒ 跳过
        row: dict = {"ym": _ym_of(raw_row, index)}
        for header, field in COLUMN_MAP:
            col = index.get(header)
            if col is None or col >= len(raw_row):
                continue
            row[field] = (_num_of(raw_row[col], header=header, row_no=offset)
                          if field in NUMERIC_FIELDS else _norm(raw_row[col]))
        row["vendor"] = " / ".join(
            _norm(raw_row[index[h]]) for h in VENDOR_HEADERS
            if h in index and index[h] < len(raw_row) and _norm(raw_row[index[h]])
        )
        row.setdefault("spec", "")
        row.setdefault("unit", "")
        row.setdefault("biz_type", "")
        row.setdefault("doc_date", "")
        row.setdefault("audit_date", "")
        row.setdefault("wbs_name", "")
        row.setdefault("cbs_name", "")
        row.setdefault("bill_name_full", "")
        out.append(row)
    if not out:
        raise MustReportError("导出文件里没有数据行（表头之后全空）—— 该月可能确实没有库存单据")
    return out


__all__ = [
    "HEADER_KEYWORDS", "COLUMN_MAP", "REQUIRED_HEADERS", "YM_HEADERS", "VENDOR_HEADERS",
    "IGNORED_HEADERS", "NUMERIC_FIELDS", "SHEET_PREFERRED", "HEADER_SCAN_ROWS",
    "read_grid", "find_header_row", "map_columns", "parse_rows",
]
