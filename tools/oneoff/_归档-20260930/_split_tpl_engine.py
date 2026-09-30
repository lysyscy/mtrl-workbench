# -*- coding: utf-8 -*-
"""一次性拆件脚本：`tpl_engine.py` 934 行 > 600 禁合入（`TAIL-43` 加完显示区之后）。

拆法（**只搬代码**，不改逻辑）：
  ① `xl_common.py`   ← 「基础工具」段（最底层原语，谁都不当主人）
  ② `pivot_cache.py` ← 「透视缓存重建」段 ＋ 「对账」段（`verify_cache`）
  ③ `sheet_display.py` ← 「显示区重建」段（`TAIL-43`）
  ④ `tpl_engine.py`  ← 剩下：读数据 / sharedStrings / 数据 sheet / pivotTable 动态 / `rebuild()`
                       并**再导出**原语与两个中立件的函数（全站引用都是 `tpl_engine.X` 形式 ⇒ 零改动）

用法： backend/.venv/Scripts/python.exe tools/_split_tpl_engine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "backend" / "app" / "report_export"
SRC = PKG / "tpl_engine.py"

# (名称, 起行, 止行) —— 1-based，含两端（对照 `tpl_engine.py` 的段注释）
RANGES = {
    "tools": (48, 83),
    "read_data": (84, 126),
    "shared": (127, 152),
    "sheet": (153, 199),
    "cache": (200, 337),
    "pivot": (338, 394),
    "verify": (395, 481),
    "display": (482, 806),
    "rebuild": (807, 934),
}

HDR_XL = '''# -*- coding: utf-8 -*-
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


'''

HDR_CACHE = '''# -*- coding: utf-8 -*-
"""透视**缓存**的重建（`pivotCacheDefinition` / `pivotCacheRecords`）＋ **缓存级对账**。

**来源**：逐字移植自交付面 `PRD素材包-20260911/input/common_tpl.py`（⚠️ 只搬实现，口径不反推）；
2026-09-18 从 `tpl_engine.py` 拆出（该文件加完 `TAIL-43` 显示区后 >600 行 = 禁合入）。

**对账口径**：从**新文件的新缓存**重算 vs 从**原数据**重算，逐项比对 ⇒
这不是"生成了一眼看着像"的检查，是"两条独立路径算同一笔数"的检查。
⚠️ 它**看不见「显示区」**（显示区是 Excel 存的渲染结果）⇒ 那份对账在 `sheet_display.py`。
"""
import re
import zipfile
from html import unescape
from xml.sax.saxutils import escape

from app.core.errors import MustReportError
from app.report_export.xl_common import NS, fmt_num, norm_num, parse_shared_items


'''

HDR_DISPLAY = '''# -*- coding: utf-8 -*-
"""透视**显示区**的重建与对账 —— `TAIL-43`。

**它解决什么**（2026-09-18 真机实测根因）：模板法原先只重建「数据 sheet ＋ 缓存 ＋ 透视定义」，
**不重建显示区**（`xl/worksheets/sheetN.xml` 里 Excel 存下来的**静态单元格值**）。
本月数据**比模板少**时，透视的 `location` 会**收缩**，模板旧渲染行就落到新 `location`
**之外** ⇒ **任何应用都不会去清它们**（Excel 实测：新区域照渲染、区域外旧值原样留着）
⇒ 用户打开成品**读到的是模板那个月**的数（本片就是这么暴露的）。

⇒ 唯一可靠的做法 = **自己把显示区重建出来**，⛔ 不依赖"打开即刷新"是否被应用认：
   · `render_pivot_sheet`：整块换掉 `<sheetData>` —— **新显示区之外一格都不留**（清僵尸行的关键）；
   · `verify_display`：**显示区 vs 缓存重算**（独立于「数据 ↔ 缓存」的**第二条**对账）。

⚠️ 实测纠正两条（别走回头路）：
   1. **`refreshOnLoad` 只保证刷新缓存**（ECMA-376 `CT_PivotCacheDefinition`），
      **不保证**清掉 `location` 之外的残留 ⇒ "靠打开即刷新来顶"**靠不住**；
   2. **口径一律从模板读**（列序 / 分组映射 / 页筛选选中项）—— ⛔ 不在代码里另抄一份。
      页筛选是「`multipleItemSelectionAllowed="1"` ＋ `<item h="1">` 标未选」的**多选**形态，
      ⛔ **不许**改写成 `<pageField item="N"/>`（那是**单选**语义，会改变筛选行为）。
"""
import re
import zipfile
from html import unescape
from openpyxl.utils import column_index_from_string, get_column_letter

from app.core.errors import MustReportError
from app.report_export.xl_common import NS, fmt_num, norm_num


'''

HDR_ENGINE = '''# -*- coding: utf-8 -*-
"""模板法重建引擎（**编排 ＋ 数据侧**）—— 逐字移植自交付面素材包
`PRD素材包-20260911/input/common_tpl.py`（⚠️ 只搬**实现**，口径不反推）。

**它做什么**：以「用户手作的那份成品 xlsx」为基底做 `zip` 字节替换，动态重建当月文件：
  1) sharedStrings：保留模板全部字符串 + 追加当月新字符串
  2) 数据 sheet：表头保留模板原样，数据行按模板行样式生成（28 列内通用）
  3) pivotCacheDefinition / pivotCacheRecords → `pivot_cache.py`
  4) pivotTable：location / axisRow items / rowItems 动态
  5) **透视显示区**（`TAIL-43`）→ `sheet_display.py`
  6) 对账：数据 ↔ 缓存（`pivot_cache.verify_cache`）＋ 缓存 ↔ 显示区（`sheet_display.verify_display`）

## 拆件（2026-09-18 · `TAIL-43` 之后本文件曾 934 行 > 600 = 禁合入）
| 文件 | 职责 |
|---|---|
| `xl_common.py` | 最底层原语（`NS` / `fmt_num` / `norm_num` / `parse_shared_items`）· **中立件** |
| `pivot_cache.py` | 缓存两件重建 ＋ **缓存级对账** |
| `sheet_display.py` | **显示区**重建 ＋ 显示区对账（`TAIL-43`） |
| `tpl_engine.py` | 本文件 = 编排（`rebuild()`）＋ 数据侧（读数据 / sharedStrings / 数据 sheet / pivotTable） |

⚠️ 三个中立件里的函数**本文件一律再导出**（`from … import …`）—— 全站引用都是
   `tpl_engine.X` 形式（实测 grep 过），再导出 ⇒ 调用方**零改动**。

⭐ **本仓的三处适配**（其余与原文件逐字一致）：
1. **数据优先由调用方给**（`cfg['data']`）—— 生产环境的数据主人在**库里**；
   ⛔ 仍保留走 `src` 文件的能力（`cfg` 不给 `data` 时按原逻辑读）。
2. **对账不过 ⇒ 硬失败**（素材包只是打印；生产里必须 `raise`）。
3. **删掉模块级 `warnings.filterwarnings('ignore')`** —— 那是**库**，import 就全局静音全站告警。
"""
import re
import zipfile
from html import unescape
from xml.sax.saxutils import escape

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.errors import MustReportError
# ⭐ 再导出：全站引用都是 `tpl_engine.X` ⇒ 拆件对外**零改动**
from app.report_export.pivot_cache import rebuild_cache_def, rebuild_records, verify_cache
from app.report_export.sheet_display import (pivot_column_specs, pivot_page_filter,
                                            render_pivot_sheet, verify_display)
from app.report_export.xl_common import NS, fmt_num, norm_num, parse_shared_items


'''


def main() -> int:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    seg = {}
    for name, (a, b) in RANGES.items():
        seg[name] = "\n".join(lines[a - 1:b])

    def write(fn: str, text: str) -> None:
        p = PKG / fn
        p.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        n = len(p.read_text(encoding="utf-8").splitlines())
        print("  写出 %-22s %4d 行" % (fn, n))

    write("xl_common.py", HDR_XL + seg["tools"])
    write("pivot_cache.py", HDR_CACHE + seg["cache"] + "\n\n" + seg["verify"])
    write("sheet_display.py", HDR_DISPLAY + seg["display"])
    engine = (HDR_ENGINE + seg["read_data"] + "\n\n" + seg["shared"] + "\n\n"
              + seg["sheet"] + "\n\n" + seg["pivot"] + "\n\n" + seg["rebuild"])
    write("tpl_engine.py", engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
