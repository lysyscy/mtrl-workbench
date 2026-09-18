# -*- coding: utf-8 -*-
"""`report_export` 包的**最底层共用件**（纯函数 · 只依赖 stdlib）。

**为什么单独立一份**（§八「多路由共用件必须抽中立件」）：`tpl_engine`（缓存/数据 sheet）与
`sheet_display`（显示区重建）**两边都要用**这几件 ⇒ 谁当主人都会造出**循环 import**（本仓踩过）。

| 成员 | 用途 |
|---|---|
| `NS` | 主命名空间；`pivotCacheDefinition` / `pivotCacheRecords` / sheet 三处 XML 都用 |
| `fmt_num` | 数值 → 不带多余 0 的十进制串（写进 XML 的 `<v>`） |
| `norm_num` | 数字 / 数字字符串 → `float`；空 → `None`（⭐「**空 ≠ 0**」的第一道闸） |
| `parse_shared_items` | 从 `cacheField` 的 `<sharedItems>` 段解析 → `(typ, [值], attrs)` |

⚠️ **本文件只是搬运**（`tpl_engine.py` 拆件，2026-09-18 `TAIL-43`），逻辑未改动。
"""
import re
from html import unescape

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


# ================= 基础工具 =================
def fmt_num(x):
    s = ('%.10f' % float(x)).rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'


def norm_num(v):
    """数字/数字字符串 -> float；空 -> None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(',', '').strip()
    if s == '' or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_shared_items(seg):
    """从 cacheField 的 sharedItems 段解析 -> (typ, [values], attrs)"""
    si = re.search(r'<sharedItems([^>]*)>(.*?)</sharedItems>', seg, re.S)
    if not si:
        return None, [], {}
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', si.group(1)))
    body = si.group(2)
    vals = []
    typ = None
    for m in re.finditer(r'<(n|s|b|d)\s[^>]*v="([^"]*)"', body):
        typ = m.group(1)
        vals.append(unescape(m.group(2)))
    return typ, vals, attrs
