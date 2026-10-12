"""`import_kit.readers` —— 通用读表口：格式识别、值转换与失败解释。

机械读取与真实合并块展开在 workbook；本件保留数字类型、日期时间和空表口径。
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.errors import MustReportError, human_reason
from app.import_kit.parse import cell_text
from app.import_kit.workbook import fill_merges, open_workbook

HEADER_SCAN_ROWS = 12


def _kind(data: bytes) -> str:
    """按魔术字节判xlsx/xls；通用入口不依赖文件名。"""
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    return ""


def _open(data: bytes, kind: str, *, read_only: bool):
    """只包装加载失败；保留两种格式原有的人话与下一步。"""
    try:
        return open_workbook(data, kind, read_only=read_only)
    except Exception as exc:  # noqa: BLE001
        if kind == "xls":
            raise MustReportError(human_reason("这个文件读不成 Excel（老 .xls 格式）", exc,
                next_step="请确认它没损坏；先用 Excel 打开、另存为 .xlsx 再导也可以")) from exc
        raise MustReportError(human_reason("这个文件读不成 Excel（.xlsx）", exc,
            next_step="请确认它没损坏、也没被加密；另存一份再导也可以")) from exc


def _xls_cell(cell, datemode: int):
    """xls日期保留钟点；其他值仍走cell_text，不改布尔/空值语义。"""
    import xlrd

    if cell.ctype == xlrd.XL_CELL_DATE:
        y, m, d, *rest = xlrd.xldate_as_tuple(cell.value, datemode)
        clock = f" {rest[0]:02d}:{rest[1]:02d}:{rest[2]:02d}" if any(rest) else ""
        return f"{y:04d}-{m:02d}-{d:02d}{clock}"
    return cell_text(cell.value)


def _xlsx_value(value):
    """只文本化JSON装不下的值；数字/布尔/None仍保持原类型。"""
    return value if value is None or isinstance(value, (str, int, float, bool)) else cell_text(value)


def read_grid(data: bytes, *, sheet: str | None = None, max_rows: int | None = None,
              fill_merged_rows: int = 0) -> tuple[list[list], str]:
    """Excel字节→网格/表名；只展开前N行合并块，空表与缺表仍显式报错。

    保留数字类型（序列号换算依赖它）；公式读缓存值。max_rows沿用读完再截取的语义。
    """
    kind = _kind(data)
    if not kind:
        raise MustReportError("这个文件既不是 .xlsx 也不是 .xls（按**文件内容**判的，⛔ 不看后缀）—— "
                              "请确认导的是 Excel 文件")
    with _open(data, kind, read_only=not fill_merged_rows) as book:
        names = book.names
        if sheet and sheet not in names:
            raise MustReportError(f"没有叫「{sheet}」的工作表（现有：{' / '.join(names)}）")
        grid, merges, title = book.grid(sheet or None, xls_cell=_xls_cell, xlsx_value=_xlsx_value)
        if not grid:
            raise MustReportError("这个工作表是空的 —— 请确认选对了 sheet")
        if fill_merged_rows:
            fill_merges(grid, merges, rows=fill_merged_rows)
        return grid[:max_rows] if max_rows else grid, title


def list_sheets(data: bytes) -> list[str]:
    """按文件顺序列工作表；未知内容沿用xlsx加载失败的解释。"""
    with _open(data, "xls" if _kind(data) == "xls" else "xlsx", read_only=True) as book:
        return book.names


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
