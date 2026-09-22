"""`import_kit.readers` —— 读工作簿 ＋ 找表头行（**不猜列位，按表头文字识别**）。"""

from __future__ import annotations

import io
from collections.abc import Callable

from app.core.errors import MustReportError

#: 真实表前面可能有一两行标题 ⇒ 表头行扫描上限（默认值，可覆盖）
HEADER_SCAN_ROWS = 12


def read_grid(data: bytes, *, sheet: str | None = None,
              max_rows: int | None = None) -> tuple[list[list], str]:
    """xlsx 字节 → `(grid, sheet名)`；读不了 ⇒ **显式报错**（⛔ 不静默给空表）。

    ⚠️ `data_only=True`：公式取**值**（用户手里的是导出件，不是计算模型）。
    ⚠️ `max_rows`：各域的行数上限不同（m05=5000 / m06=2000）⇒ 由调用方给，底座不写死。
    """
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise MustReportError(f"这个文件读不成 Excel（.xlsx）：{exc}") from exc
    if sheet:
        if sheet not in wb.sheetnames:
            raise MustReportError(f"没有叫「{sheet}」的工作表（现有：{' / '.join(wb.sheetnames)}）")
        ws = wb[sheet]
    else:
        ws = wb.worksheets[0]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    if not grid:
        raise MustReportError("这个工作表是空的 —— 请确认选对了 sheet")
    return grid[:max_rows] if max_rows else grid, ws.title


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


__all__ = ["HEADER_SCAN_ROWS", "find_header", "read_grid"]
