"""`import_kit.readers` —— 读工作簿 ＋ 找表头行（**不猜列位，按表头文字识别**）。"""

from __future__ import annotations

import io
from collections.abc import Callable

from app.core.errors import MustReportError
from app.import_kit.parse import cell_text

#: 真实表前面可能有一两行标题 ⇒ 表头行扫描上限（默认值，可覆盖）
HEADER_SCAN_ROWS = 12


def _fill_merged(ws, grid: list[list], rows: int) -> list[list]:
    """把**合并区**的锚格值铺满其区域（**只铺前 `rows` 行**）—— ⭐ 只信 `merged_cells`。

    ⚠️ 为什么要有它（真文件逼出来的）：两级表头的**分组头是合并格** —— `外租机械（不含税）` 只写在
    `O2`，`P2` 是空的；不铺开就拼不出 `外租机械（不含税）包月`（那一列会**漏认**，甚至被"包含词"
    误认成**含税**那列 —— 实测踩过）。
    ⛔ **两条不能破**：① 不做"无脑向右/向下填充"（`m11` 的老教训：会把合法空列填满 ⇒ 认错表头行）；
    ② **不铺数据区** —— 数据区的竖合并一铺，就会把同一个金额复制到相邻行 ⇒ **历史账重记**（最贵的一类错）。
    """
    if not getattr(ws, "merged_cells", None):
        return grid
    for rng in list(ws.merged_cells.ranges):
        r0, c0 = rng.min_row - 1, rng.min_col - 1
        if r0 >= len(grid) or c0 >= len(grid[r0]) or rng.min_row > rows:
            continue
        value = grid[r0][c0]
        if value is None or str(value).strip() == "":
            continue
        for r in range(rng.min_row - 1, min(rng.max_row, len(grid), rows)):
            row = grid[r]
            for c in range(rng.min_col - 1, min(rng.max_col, len(row))):
                row[c] = value
    return grid


def _kind(data: bytes) -> str:
    """按**魔术字节**判真类型 ⇒ `"xlsx"`（zip）/ `"xls"`（OLE2 老格式）/ `""`。

    ⚠️ **不靠文件名**：用户给的可能是改名/无后缀的文件，而两种格式必须走**两个引擎**
      （`openpyxl` 读 `xlsx`、`xlrd` 读 `xls`）—— 拿错引擎的报错是"File is not a zip file"那种，
      用户看不出所以然（`B5b` 实测：两份真集采台账是 `.xls` ⇒ 早先通用面直接判它"读不成 Excel"）。
    """
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    return ""


def _read_xls(data: bytes, *, sheet: str | None, max_rows: int | None,
              fill_merged_rows: int) -> tuple[list[list], str]:
    """老 `.xls`（`xlrd`）→ `(grid, sheet名)`；**日期给 ISO 文本**（⛔ 不给序列号）。

    ⚠️ `xlrd` 的合并区上界是**开区间**、且要拿 `datemode` 才能换算日期 —— 两处都容易记错（照 `m11` 老路）。
    """
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=data)
    except Exception as exc:  # noqa: BLE001
        raise MustReportError(f"这个文件读不成 Excel（.xls）：{exc}") from exc
    names = [book.sheet_by_index(i).name for i in range(book.nsheets)]
    if sheet:
        if sheet not in names:
            raise MustReportError(f"没有叫「{sheet}」的工作表（现有：{' / '.join(names)}）")
        sh = book.sheet_by_name(sheet)
    else:
        sh = book.sheet_by_index(0)
    grid: list[list] = []
    for r in range(sh.nrows):
        row = []
        for c in range(sh.ncols):
            cell = sh.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_DATE:
                y, m, d, *rest = xlrd.xldate_as_tuple(cell.value, book.datemode)
                # ⚠️ `XL_CELL_DATE` 也可能是**纯时间**（`0.354` = 08:30）⇒ 有钟点就一并写出来
                #    （`xldate_as_tuple` 给 `(年, 月, 日, 时, 分, 秒)`）—— 与 `cell_text` 同口径。
                clock = f" {rest[0]:02d}:{rest[1]:02d}:{rest[2]:02d}" if any(rest) else ""
                row.append(f"{y:04d}-{m:02d}-{d:02d}{clock}")
            else:
                # ⭐ 与 xlsx 分支**共用同一个读表出口**（`parse.cell_text`）—— ⛔ 别在这里另写一套：
                #    两个引擎口径一分家，同一张表换个后缀就读出两种结果（本仓 2026-09-26 踩过）。
                row.append(cell_text(cell.value))
        grid.append(row)
    if not grid:
        raise MustReportError("这个工作表是空的 —— 请确认选对了 sheet")
    if fill_merged_rows:                      # `xlrd` 的合并区上界是**开的**
        merges = [(r1, r2 - 1, c1, c2 - 1) for r1, r2, c1, c2 in sh.merged_cells]
        for r1, r2, c1, c2 in merges:
            if r1 >= len(grid) or r1 >= fill_merged_rows or c1 >= len(grid[r1]):
                continue
            val = grid[r1][c1]
            if not val:
                continue
            for r in range(r1, min(r2, len(grid) - 1, fill_merged_rows - 1) + 1):
                for c in range(c1, min(c2, len(grid[r]) - 1) + 1):
                    grid[r][c] = val
    return grid[:max_rows] if max_rows else grid, sh.name


def read_grid(data: bytes, *, sheet: str | None = None, max_rows: int | None = None,
              fill_merged_rows: int = 0) -> tuple[list[list], str]:
    """Excel 字节 → `(grid, sheet名)`；读不了 ⇒ **显式报错**（⛔ 不静默给空表）。

    ⚠️ **两种格式都认**（`.xlsx` 走 `openpyxl` · 老 `.xls` 走 `xlrd`）—— 按**魔术字节**判，⛔ 不靠文件名。
    ⚠️ `data_only=True`：公式取**值**（用户手里的是导出件，不是计算模型）。
    ⚠️ `max_rows`：各域的行数上限不同（m05=5000 / m06=2000）⇒ 由调用方给，底座不写死。
    ⚠️ `fill_merged_rows=N`：**只把前 N 行**的合并区铺开（给两级表头用）；`read_only` 模式读不到合并区
       ⇒ 只有需要的调用方才开（并接受更慢）。
    """
    kind = _kind(data)
    if kind == "xls":
        return _read_xls(data, sheet=sheet, max_rows=max_rows, fill_merged_rows=fill_merged_rows)
    if not kind:
        raise MustReportError("这个文件既不是 .xlsx 也不是 .xls（按**文件内容**判的，⛔ 不看后缀）—— "
                              "请确认导的是 Excel 文件")
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=not fill_merged_rows)
    except Exception as exc:  # noqa: BLE001
        raise MustReportError(f"这个文件读不成 Excel（.xlsx）：{exc}") from exc
    if sheet:
        if sheet not in wb.sheetnames:
            raise MustReportError(f"没有叫「{sheet}」的工作表（现有：{' / '.join(wb.sheetnames)}）")
        ws = wb[sheet]
    else:
        ws = wb.worksheets[0]
    # ⚠️ **只文本化 JSON 装不下的那几种**（`datetime` / `date` / `time` / `Decimal` / `timedelta`…）；
    #    `str / int / float / bool / None` **一律原样留着**。
    #    ⭐ 两个理由（2026-09-26 用户报障那天实测出来的）：
    #    ① **必须文本化**：预览载具 `core.preview_store.save` 落盘是 `json.dumps`，
    #       而通用面的 `/parse` 把本函数给的 `grid_rows` **原样**塞进去 ⇒ 一个 `datetime.time`
    #       就是「解析失败：TypeError: Object of type time is not JSON serializable」（报障原话）；
    #    ② **⛔ 不能连数字一起文本化**：序列号/金额的换算**按值的类型判**（`date_text` 认 `int/float`
    #       的序列号、`m06._ym_from_number` 同）—— 真把 `45444` 变成 `"45444"`，
    #       「核算月」会被**静默认不出**（当场被 `test_imp_m06_api.py` 抓住，判据很有用）。
    grid = [[v if v is None or isinstance(v, (str, int, float, bool)) else cell_text(v)
             for v in r] for r in ws.iter_rows(values_only=True)]
    if fill_merged_rows:
        grid = _fill_merged(ws, grid, fill_merged_rows)
    title = ws.title
    wb.close()
    if not grid:
        raise MustReportError("这个工作表是空的 —— 请确认选对了 sheet")
    return grid[:max_rows] if max_rows else grid, title


def list_sheets(data: bytes) -> list[str]:
    """Excel 字节 → **工作表名清单**（真文件里常是 4~11 张，还有空表 ⇒ 由上层挑）。

    ⚠️ 单独一件：`read_grid` 只给"读到的那一张"，而**挑哪一张**是通用层的活（先看清单再逐张试）。
    ⚠️ 两种格式都认（`.xls` 走 `xlrd`，见 `_kind`）—— ⛔ 只认 `.xlsx` 会让 `.xls` 的台账**连清单都拿不到**。
    """
    if _kind(data) == "xls":
        import xlrd

        try:
            book = xlrd.open_workbook(file_contents=data)
        except Exception as exc:  # noqa: BLE001
            raise MustReportError(f"这个文件读不成 Excel（.xls）：{exc}") from exc
        return [book.sheet_by_index(i).name for i in range(book.nsheets)]
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise MustReportError(f"这个文件读不成 Excel（.xlsx）：{exc}") from exc
    names = list(wb.sheetnames)
    wb.close()
    return names


def find_header(
    grid: list[list],
    classify: Callable[[object], str | None],
    *,
    scan: int = HEADER_SCAN_ROWS,
    min_hits: int = 3,
    required: tuple[str, ...] = (),
) -> tuple[int, dict[str, int]] | None:
    """在前 `scan` 行里找表头行 ⇒ `(行下标 0 起, {字段→列号})`；找不到 ⇒ `None`（**报错话术归调用方**）。

    ⭐ 判定 = 该行能被 `classify` 认出 ≥ `min_hits` 个字段，且 `required` 里的字段**全部命中**。
    """
    for idx, row in enumerate(grid[:scan]):
        mapping = {key: col for col, cell in enumerate(row) if (key := classify(cell))}
        if len(mapping) >= min_hits and all(k in mapping for k in required):
            return idx, mapping
    return None


__all__ = ["HEADER_SCAN_ROWS", "find_header", "list_sheets", "read_grid"]
