"""`API-02` 收发结存导出 → **解析**（xlsx 网格 → 域内规范**明细行**）。

依据：
- 《说明书》**§5.3.2**（交付形态：分仓库表 ＋ 总表）· **§9.2**（报表类按核算年月）· **§9.5**（导入幂等）
- 《说明书》附录 **E.1.1**：i8 导出是 **xlsx 网格（不是实体行）**，**列清单的现行来源 = i8 导出表头**
  ⇒ 本模块**按表头文字认列**，**不写死下标**
- 实现层借鉴 = `PRD素材包-20260911/input/{sfjc_export_http,schema_cols}.py`（⚠️ 只借鉴**解析规则**，口径不得反推）：
  **拆合并单元格填充**（合并区取左上角值）、**剔除「合计」行**、**去千分位逗号**

⚠️ **表头跨 1~2 行**（导出里是合并表头）⇒ 逐列把表头块各行的文字**拼接**成列名（重复片段去重），
   「期初」＋「数量」⇒ `期初数量`，与导出表头一致。
⚠️ **关键列缺失 / 数字列非数字 ⇒ 报错不猜**（带行号与原文，不静默丢行）。
⛔ 本模块**不连库、不写文件**（落库由 `repository.upsert_month` 负责）。
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from app.core.errors import MustReportError
from app.core.money import MoneyError, to_money

SHEET_PREFERRED: tuple[str, ...] = ("报表1",)
HEADER_SCAN_ROWS = 4          # 表头块只在前若干行里找
# 导出里的**合计行**（按素材包口径剔除：它按仓库汇总、不是明细）
TOTAL_WAREHOUSE = "合计"

# 表头 → 域内字段（**列映射的唯一出口**，与 i8 导出表头 17 列一一对应）
COLUMN_MAP: tuple[tuple[str, str], ...] = (
    ("仓库", "warehouse_name"),
    ("资源分类", "resource_class"),
    ("资源编码", "resource_code"),
    ("资源名称", "resource_name"),
    ("规格型号", "spec"),
    ("计量单位", "unit"),
    ("物料性质", "material_property"),
    ("期初数量", "begin_qty"),
    ("期初金额", "begin_amt"),
    ("收数量", "in_qty"),
    ("收单价", "in_price"),
    ("收金额", "in_amt"),
    ("发数量", "out_qty"),
    ("发单价", "out_price"),
    ("发金额", "out_amt"),
    ("结存数量", "end_qty"),
    ("结存金额", "end_amt"),
)

# 缺一列就**整批拒绝**（少了它这一行要么没有归属、要么对平无从谈起）
REQUIRED_HEADERS: tuple[str, ...] = (
    "仓库", "资源编码", "期初金额", "收金额", "发金额", "结存金额",
)

NUMERIC_FIELDS: frozenset[str] = frozenset(f for h, f in COLUMN_MAP if f.endswith(("_qty", "_amt", "_price")))


def _norm(value) -> str:
    return "" if value is None else str(value).strip()


def read_grid(content: bytes) -> list[list[str]]:
    """xlsx 字节 → `list[list[str]]`（取「报表1」那张工作表，**已拆合并填充**）。

    ⚠️ **不能用 `read_only=True`** —— 只读模式拿不到合并区范围，而本表的表头就是合并单元格；
       本表规模（百行级）用普通模式无压力。
    """
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(content), data_only=True)
    try:
        name = next((s for s in SHEET_PREFERRED if s in wb.sheetnames),
                    (wb.sheetnames[0] if wb.sheetnames else ""))
        if not name:
            raise MustReportError("导出文件里没有任何工作表")
        ws = wb[name]
        fill: dict[tuple[int, int], object] = {}
        for mr in ws.merged_cells.ranges:            # 合并区 → 左上角值填充
            v = ws.cell(row=mr.min_row, column=mr.min_col).value
            for r in range(mr.min_row, mr.max_row + 1):
                for c in range(mr.min_col, mr.max_col + 1):
                    fill[(r, c)] = v
        out: list[list[str]] = []
        for r in range(1, ws.max_row + 1):
            out.append([
                _norm(fill.get((r, c), ws.cell(row=r, column=c).value))
                for c in range(1, ws.max_column + 1)
            ])
        return out
    finally:
        wb.close()


def _column_names(grid: list[list[str]], depth: int) -> list[str]:
    """表头块（前 `depth` 行）→ 每列一个列名（多行**拼接**，重复片段去重）。"""
    width = max((len(grid[r]) for r in range(min(depth, len(grid)))), default=0)
    out: list[str] = []
    for c in range(width):
        parts: list[str] = []
        for r in range(min(depth, len(grid))):
            v = grid[r][c] if c < len(grid[r]) else ""
            if v and v not in parts:
                parts.append(v)
        out.append("".join(parts))
    return out


def find_header_block(grid: list[list[str]]) -> tuple[dict[str, int], int]:
    """定位**表头块** → `({列名: 下标}, 数据首行下标)`。

    表头可能是 **2 行**（合并表头）或 **1 行** ⇒ 两种都试；都不满足关键列 ⇒ **报错不猜**。
    """
    scan = grid[:HEADER_SCAN_ROWS]
    for depth in (2, 1):
        if len(scan) < depth:
            continue
        names = _column_names(scan, depth)
        index = {n: i for i, n in enumerate(names) if n}
        if all(h in index for h in REQUIRED_HEADERS):
            return index, depth
    raise MustReportError(
        f"在导出文件的前 {HEADER_SCAN_ROWS} 行里找不到表头（应含 {' / '.join(REQUIRED_HEADERS)}）"
        f" —— 文件形态可能变了，请核对后再导。前几行实际内容：{scan[:2]}"
    )


def _num_of(raw: str, *, header: str, row_no: int):
    """数字列：**空 ⇒ 0**（导出里空单元格就是 0 的含义）；**非数字 ⇒ 报错**（带行号与原文）。

    ⚠️ **千分位逗号不在这里剥** —— `core.money.to_money` 已统一处理（金额口径的全站唯一出口）；
       本处再剥一次就是"同一件事的第二个实现"，改了这边漏那边（本单元实测：两处都剥时，
       把任一处改坏测试都不会红 ⇒ 那条断言其实没有区分力）。
    """
    text = _norm(raw)
    if text == "":
        return Decimal("0.00")
    try:
        return to_money(text)
    except MoneyError as exc:
        raise MustReportError(f"第 {row_no} 行「{header}」不是数字：{raw!r}（{exc}）") from exc


def _row_has_amount(row: list[str], index: dict[str, int]) -> bool:
    return any(
        _norm(row[index[h]]).replace(",", "").strip() not in ("", "0", "0.00")
        for h in ("期初金额", "收金额", "发金额", "结存金额") if h in index and index[h] < len(row)
    )


def parse_rows(content: bytes, *, ym: str) -> list[dict]:
    """xlsx 字节 → 域内规范**明细行**（`list[dict]`，键为域内字段名）。**纯函数，不落库。**

    - 整行空 ⇒ 跳过；
    - 「合计」行 ⇒ **剔除**（按素材包口径；它是汇总、不是明细）；
    - **没有仓库名却有金额**的行 ⇒ **报错**（不静默丢数据）。
    """
    grid = read_grid(content)
    index, first = find_header_block(grid)

    out: list[dict] = []
    for offset, raw_row in enumerate(grid[first:], start=first + 1):
        if not any(_norm(c) for c in raw_row):
            continue
        warehouse = _norm(raw_row[index["仓库"]]) if index["仓库"] < len(raw_row) else ""
        if warehouse == TOTAL_WAREHOUSE:
            continue                                       # 导出的合计行
        if not warehouse:
            if _row_has_amount(raw_row, index):
                raise MustReportError(
                    f"第 {offset} 行没有「仓库」却有金额 —— 无法归属，拒绝整批导入（不静默丢行）"
                )
            continue
        row: dict = {"ym": str(ym or ""), "warehouse_name": warehouse}
        for header, field in COLUMN_MAP:
            col = index.get(header)
            if col is None or col >= len(raw_row):
                continue
            row[field] = (_num_of(raw_row[col], header=header, row_no=offset)
                          if field in NUMERIC_FIELDS else _norm(raw_row[col]))
        row["resource_code"] = _norm(row.get("resource_code"))
        out.append(row)
    return out


__all__ = [
    "SHEET_PREFERRED", "HEADER_SCAN_ROWS", "TOTAL_WAREHOUSE", "COLUMN_MAP",
    "REQUIRED_HEADERS", "NUMERIC_FIELDS",
    "read_grid", "find_header_block", "parse_rows",
]
