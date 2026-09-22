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


def save_workbook(wb, out: str | Path) -> Path:
    """把工作簿**落盘** ⇒ 返回**绝对路径**。

    ⭐⭐ **`out` 的父目录不存在时先建**（⛔ 别省这一步 —— 2026-09-21 普查发现
       `setl_export` 就省了 ⇒ 换一个不存在的导出目录会直接崩）。
    ⚠️ `wb` 之后**不要再复用**（已 `close()`）。
    """
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(p))
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
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


__all__ = ["save_workbook", "workbook_bytes"]
