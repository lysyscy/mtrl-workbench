"""`MOD-01` 项目档案的 **Excel 导出**（`TAIL-04` · `REQ-R1` · §7.1）。

⭐ 本件是 `TAIL-04`（**所有列表页都要有「导出 Excel」**）的第 1 张页 ——
   样板取自 `report_export/jc_export.py`（**朴素导出**那一档）。

**口径（§7.1）**：

- **行** = **页面上当前看到的那些**（调用方传 id 列表）⇒ 前端筛选口径与后端 **100% 一致**。
  ⭐ **为什么不传"筛选条件"让后端自己筛**：页面的筛选是**前端**算的
  （状态 / 类型 / 全名·仓库名·展示名模糊搜）⇒ 传条件就得在后端**再实现一遍**
  ⇒ **两套口径必打架**（本项目的旧账）。
  ⭐ 而且**排序也是页面的**（`pjSort` = 自定义 `ord`，归档后置）⇒ 传 id 列表能连**顺序**一起带上；
  传条件则还要把排序规则也说清一遍。
- **列** = **页面表头去掉「操作」那一列**（操作是按钮，不是数据）。
  ⚠️ 页面第一列是「**排序**」（`ord` 数字 ＋ ↑↓ 按钮）—— 那格里的**数字是真数据**（自定义排序号），
  所以**导它**，但⛔ **不导那对按钮**。
- **取值** = **页面显示的那个值**（不是原始外键 / 英文枚举）⇒
  ⚠️ 「类型」要**中文文案**（页面是 `普通项目 / 小微壳 / 具体小微`）、
  「所属壳」要**父项目的全名**（页面显示的就是全名，⛔ 不是 `parent_shell_id`）⇒
  这两处由**调用方**（`mod01_projects.router`）在传进来之前解析好（见 `COLUMNS` 的键名约定）。

⚠️ **不做"看起来像个表"的假合计**：项目档案**没有金额列** ⇒ **没有合计行** ✓
  （样板 `jc_export` 有合计行是因为它有 7 个金额列；这里硬凑一个"合计 = 12"只会让人误解。）
"""

from __future__ import annotations

from io import BytesIO

#: 导出的列（**顺序 = 页面表头顺序**去掉「操作」）⇒ 导出的表与屏幕**并排看能对上**。
#: 第二项 = 行字典里的键；⚠️ 其中 `type_text` / `parent_full` / `keywords` 是
#: **调用方解析好的"展示值"**（页面显示什么就导什么 —— 见模块头「取值」那条）。
COLUMNS: tuple[tuple[str, str], ...] = (
    ("排序", "ord"),
    ("类型", "type_text"),
    ("展示名", "disp"),
    ("仓库名", "warehouse_name"),
    ("项目全名", "name_full"),
    ("phid", "phid"),
    ("状态", "status"),
    ("所属壳", "parent_full"),
    ("小微识别关键词", "keywords"),
)

SHEET_NAME = "项目档案"

#: ⛔ **本页没有金额列** ⇒ 不设 `MONEY_KEYS`、不写合计行（见模块头末段）。
NUMBER_KEYS: frozenset[str] = frozenset({"ord"})

#: ⚠️ 本件**不做**「类型 → 中文」的映射 —— 那是**业务口径**（`mod01_projects` 的事）。
#:    这里只负责"把给我的一行渲染进 Excel"。
#:    ⭐ 放在这份注释里是**故意的**：免得下一个人看到 `type_text` 这个键名，
#:      以为"builder 里应该有张 type 表"，然后在两个地方各写一份。


def build_xlsx(rows: list[dict]) -> bytes:
    """行字典列表 ⇒ 一本 xlsx 的**字节**（不落盘：调用方决定给谁）。

    ⚠️ 表头**加粗**＋**冻结首行**：几十行的表滚起来没有冻结行，人对不上哪列是哪列。
    ⚠️ `ord` 写**数字**（⛔ 不写字符串）：这样用户在 Excel 里能直接排序
       —— 写成 `"3"` 那种"看着是数、其实是文本"的表，是本项目最讨厌的一类假象。
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    ws.append([label for label, _ in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for r in rows or ():
        vals = []
        for _, key in COLUMNS:
            v = r.get(key)
            # `ord` 是数字 ⇒ 清成 int；其余一律**原样**（空 / None ⇒ 空单元格，⛔ 不写 0）
            if key in NUMBER_KEYS and v not in (None, ""):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    pass
            vals.append("" if v is None else v)
        ws.append(vals)

    # 列宽：按内容给个**可读的**初值（⛔ 不写死窄宽 —— 那是"表挤"的另一半原因）
    for i, (label, _) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(10, min(32, len(label) * 2 + 4))

    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


__all__ = ["COLUMNS", "NUMBER_KEYS", "SHEET_NAME", "build_xlsx"]
