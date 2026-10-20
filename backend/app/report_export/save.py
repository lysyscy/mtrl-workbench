"""**落盘的唯一出口**（`TAIL-68` · 2026-09-21）。

## 为什么要有这一件

原先落盘散在 6 处（`mod05_flow/debt_export` · `big_export` · `ledger_export` · `process_export` ·
`setl_export` · `tpl_fill`），每处自己 `mkdir` ＋ `wb.save()` ＋（有的）返回路径。
⭐ **重复本身不值钱（各 2~4 行），值钱的是"漏做 mkdir"这一类错没人兜** ——
2026-09-21 普查当场抓到：**`setl_export` 落盘时没有 `mkdir`**（目录不存在就崩）。

## ⛔ 本件**只管落盘**，⛔ 不管命名

命名规则的主人是**各个报表模块**（`file_name` / `title_of`，`period_label` 已是期间标签的唯一主人）
⇒ 本件**不提供**任何拼名函数 —— 抽它就是"给同一个规则找第二个主人"（本轮明确不做，见销号依据）。

## 契约

`save_workbook(wb, out) -> Path`
- `out` 可以是 `str` 或 `Path`（相对路径按**当前工作目录**解，与旧行为一致）；
- ⭐ **`mkdir(parents=True, exist_ok=True)` 必做** —— 这是本件存在的理由；
- 落盘后 `wb.close()`（旧 `debt_export` 就有这一步，其余省了也没事 ⇒ 统一做掉）；
- 返回**绝对路径**（旧 `debt_export` 返回 `str(out.resolve())` ⇒ 这里给 `Path`，调用方要字符串就 `str()`）。
"""

from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from io import BytesIO
import xml.etree.ElementTree as ET
from zipfile import ZipFile


class Formula(str):
    """An Excel formula with its independently computed initial display value."""

    def __new__(cls, expression, result):
        value = super().__new__(cls, expression)
        if not expression.startswith('='):
            raise ValueError('Excel公式必须以=开头')
        if result is not None and not Decimal(str(result)).is_finite():
            raise ValueError('公式缓存必须为有限数值')
        value.result = result
        return value


def set_formula(cell, formula):
    cell.value = formula
    # openpyxl coerces string subclasses; retain the cache metadata until serialization.
    cell._value = formula


def _cache_formulas(wb, payload):
    cached = {i: {c.coordinate: c.value.result for row in sheet for c in row
                  if isinstance(c.value, Formula)} for i, sheet in enumerate(wb, 1)}
    if not any(cached.values()):
        return payload
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    ET.register_namespace('', ns)
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as source, ZipFile(output, 'w') as target:
        sheets = {f'xl/worksheets/sheet{i}.xml': values for i, values in cached.items() if values}
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename in sheets:
                root = ET.fromstring(content)
                for cell in root.findall(f'.//{{{ns}}}sheetData/{{{ns}}}row/{{{ns}}}c'):
                    if cell.get('r') not in sheets[info.filename]:
                        continue
                    value = sheets[info.filename][cell.get('r')]
                    cache = cell.find(f'{{{ns}}}v')
                    if cache is None:
                        cache = ET.SubElement(cell, f'{{{ns}}}v')
                    if value is None:
                        cell.set('t', 'str')
                        cache.text = None
                    else:
                        cell.attrib.pop('t', None)
                        cache.text = format(Decimal(str(value)), 'f')
                content = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            target.writestr(info, content)
    return output.getvalue()


def save_workbook(wb, out: str | Path) -> Path:
    """把工作簿**落盘** ⇒ 返回**绝对路径**。

    ⭐⭐ **`out` 的父目录不存在时先建**（⛔ 别省这一步 —— 2026-09-21 普查发现
       `setl_export` 就省了 ⇒ 换一个不存在的导出目录会直接崩）。
    ⚠️ `wb` 之后**不要再复用**（已 `close()`）。
    """
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(workbook_bytes(wb))
    try:
        wb.close()
    except Exception:                        # noqa: BLE001 —— close 失败不影响"文件已经写出来了"
        pass
    return p.resolve()


def workbook_bytes(wb) -> bytes:
    """把工作簿**序列化为字节**（不落盘 —— 调用方决定给谁：HTTP 响应 / 再落盘）。

    ⭐ 与 `save_workbook` 同属**出口**：有了它，全站就不会再有第二处 `wb.save(`
    ⇒ `tests/test_export_save.py::test_落盘出口只剩一个` 的静态扫描才能成立。
    ⚠️ **不 `close()`** —— 这里没有文件句柄要还；调用方拿着 `bytes` 该干嘛干嘛。
    """
    buf = BytesIO()
    wb.save(buf)
    return _cache_formulas(wb, buf.getvalue())


__all__ = ["save_workbook", "workbook_bytes", "Formula", "set_formula"]
