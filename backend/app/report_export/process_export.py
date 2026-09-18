# -*- coding: utf-8 -*-
"""过程资料成品（`TAIL-04` 路径① **片 4a**）—— 模板 `模板-过程资料.xlsx` 的 `汇总表`（18 列）。

## 形态（唯一登记处 = 交付面 `demo/模板/模板清单.md` §5.3 ＋ §二-4 ＋ §四-5）

| 列 | A | B | C–G | H–L | M–N | O–P | Q–R |
|---|---|---|---|---|---|---|---|
| 内容 | **序号**（系统行号 1..N · **B 类**） | 时间 | 线上入库（不含税）5 类 | 线下出库（不含税）5 类 | 分公司设备 / 内部设备 | 外租机械（含税）零租 / 包月 | 外租机械（不含税）零租 / 包月 |

- **序号是 B 类**（清单 §5.3）：由系统生成 —— 只给**数据行**编号，**小计 / 合计行不编号**；
- **时间 = `YYYY-MM` 文本**（清单 §四-4 裁定「按页面文本」；⚠️ 模板那格是 `0.00_ ` 数值格式
  ⇒ 写前必须设成文本，见引擎 `tpl_fill.set_text_format`）；
- 列序**以模板为准**（清单 §5.3 裁定②：**临时设施 在 周转材料 前** —— ⛔ 别按域内的 `CATEGORIES` 顺序排）。

## ⚠️⚠️ 本表是「**两段合计** ＋ 数据区下面还有一整块」（清单 §四-5 点名「最容易被漏」）

- `R12 小计` = 数据区**垂直**求和（**16 列全给**，值来自 `domain.column_totals`）；
- `R13 合计：` = **四段横向小计之和**（四个**合并格** `C13:G13` / `H13:L13` / `M13:P13` / `Q13:R13`）
  —— ⚠️ 公式口径是「**指向小计那一行**」而不是数据区，四个锚点**从 `domain.SUM_SEGMENTS` 推**
  （⛔ 不写死列字母）；值来自 `domain.segment_totals`；
- `R14:R15` = **固定脚注**（`A14:R15` 跨两行合并块）—— **原文照搬**（那是交付面写死的口径文案，
  ⛔ 不在这里改字），只随 offset 下移。

⇒ 尾块 = **4 行一块**（小计 / 合计 / 脚注 ×2）⇒ 引擎的**合并区平移**在本片**第一次真用上**
（`模板清单` §四-5 实测做法最后一条）。

⛔ 本模块只做**列映射 / 序号 / 标题 / 数字格式**：不算金额、不筛项目、不拼路径
（金额与行集合的主人 = `mod06_proc.domain`；文件名主人 = `mod06_proc.domain.export_file_name`；
模板路径唯一出口 = `report_export.resources`）。
"""

from __future__ import annotations

import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl

from app.core.errors import MustReportError
from app.mod06_proc import domain as D
from app.report_export import resources, tpl_fill

#: 该模板的 sheet（`模板清单` §二-4）
SHEET = "汇总表"

#: 标题后缀（**照模板**：`龙源纸业项目材料机械消耗汇总表` ⇒ 前缀 = 项目名）
TITLE_SUFFIX = "材料机械消耗汇总表"

#: 成品落盘那里的目录名（`<root>/过程资料/<期间标签>/…`）
FILE_SUFFIX = D.EXPORT_DOMAIN

#: ⭐ 列映射（`模板清单` §5.3）：**域内列 key → 模板列字母**。唯一出口，⛔ 别处不再写第二份。
#: ⚠️ 顺序**照模板**（临时设施 在 周转材料 前）—— 这就是"列序以模板为准"那条裁定的落点。
COL_OF_KEY: dict[str, str] = {
    D.YM_KEY: "B",
    "in_主辅材": "C", "in_工具": "D", "in_劳保": "E", "in_临时设施": "F", "in_周转材料": "G",
    "out_主辅材": "H", "out_工具": "I", "out_劳保": "J", "out_临时设施": "K", "out_周转材料": "L",
    "mech_0": "M", "mech_1": "N", "mech_2": "O", "mech_3": "P", "mech_4": "Q", "mech_5": "R",
}

#: 「时间」列（写文本前要设文本格式的那一列）
TIME_COL = COL_OF_KEY[D.YM_KEY]

#: 尾块行偏移：**0 = 小计**、**1 = 合计：**（2/3 = 固定脚注的两行 —— ⛔ 我方不覆盖）
OFF_SUB = 0
OFF_TOTAL = 1

#: 「合计：」的**四个合并格锚点** —— ⭐ **从分段推**（`domain.SUM_SEGMENTS` 的每段首列），
#: ⛔ 不写死 `C/H/M/Q`：分段一改（比如不含税那两列并回机械）这里跟着变。
TOTAL_ANCHORS: tuple[str, ...] = tuple(COL_OF_KEY[keys[0]] for _name, keys in D.SUM_SEGMENTS)


def title_of(project: str) -> str:
    """标题 = **项目名 ＋ 模板后缀**。

    ⚠️ 项目名取**页面所显示的那个**（本页项目键 = 仓库名，清单 §5.3 / `domain.export_file_name` 同口径）
       —— ⛔ 不另造一份"展示名"（那会让标题与文件名/清单预览三处对不上）。
    """
    return f"{project or ''}{TITLE_SUFFIX}"


def _num(value) -> Decimal | None:
    """金额列：空 ⇒ `None`（**留空**，清单 §六-2）；其余归一到 `Decimal`。

    ⚠️ `0` 是**合法值**（该月该列确实是 0）⇒ **照写 0**，⛔ 不按"算出来是 0 就留空"处理
       （留空留给的是**空态**：`build_matrix` 用 `None` 表示"该段该月没数据"）。
    """
    if value is None or value == "":
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def body_spec(rows: list[dict], *, project: str) -> dict:
    """表体 → 引擎 `spec`：数据行（`label` = **序号**）＋ **4 行尾块**（小计 / 合计 / 脚注×2）。

    ⚠️ 尾块只给**我方要覆盖的格**（小计 16 列 ＋ 合计 4 个锚点）—— 脚注那两行**原样留着**
       （引擎的守卫允许尾块里有**文本**，但**公式 / 数字**必须被覆盖，否则拒产）。
    """
    data: list[tuple] = []
    for i, row in enumerate(rows or (), start=1):
        cells: dict[str, object] = {}
        for key, col in COL_OF_KEY.items():
            value = row.get(key)
            if value is None:
                continue                                    # 空态 ⇒ 该格留空（⛔ 不写 0）
            cells[col] = str(value) if key == D.YM_KEY else _num(value)
        data.append((i, cells))

    totals = D.column_totals(list(rows or ()))
    sub = {COL_OF_KEY[k]: totals[k] for k in D.DATA_KEYS if totals.get(k) is not None}
    segments = D.segment_totals(list(rows or ()))
    total = {anchor: seg["total"] for anchor, seg in zip(TOTAL_ANCHORS, segments)}
    return {
        "sheet": SHEET,
        "rows": data,
        "tail": {OFF_SUB: ("小计", sub), OFF_TOTAL: ("合计：", total)},
    }


def build_xlsx(rows: list[dict], out_dir, *, project: str, tab, ym: str) -> str:
    """表体 → **一本 xlsx** ⇒ 返回成品绝对路径（文件名主人 = `domain.export_file_name`）。

    - 模板走 `resources.require_template`（缺失 / 被回退 ⇒ **显式拒做**）；
    - 产物一律过 `tpl_fill.verify_filled`（逐格 / 尾块以下残留 / 值覆盖不彻底 / 行属性空壳）。
    """
    template = resources.require_template(resources.PROC_TEMPLATE)
    out = Path(out_dir) / D.export_file_name(project, tab=tab, ym=ym)
    wb = openpyxl.load_workbook(str(template))
    try:
        ws = wb[SHEET]
        ws["A1"] = title_of(project)                        # 模板标题里写着**别的项目名** ⇒ 整格换掉
        spec = body_spec(rows, project=project)
        sheet_plan = tpl_fill.fill_sheet(ws, spec)
        tpl_fill.set_text_format(ws, sheet_plan, TIME_COL)  # 「时间」列：写文本前先设文本格式
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out))
    finally:
        wb.close()

    problems = tpl_fill.verify_filled(out, {"path": str(out), "sheets": [sheet_plan]})
    if problems:
        raise MustReportError(
            "过程资料成品**显示区对账未通过** ⇒ 已中止，未交付："
            + "；".join(problems[:5]) + ("" if len(problems) <= 5 else "（等共 %d 条）" % len(problems)))
    return str(out)


def build_zip(paths, out_dir, name: str) -> str:
    """把**每个项目一本**的工作簿打成一个 zip（≥2 个项目时的交付形态）⇒ 返回 zip 路径。"""
    out = Path(out_dir) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(str(p), Path(p).name)
    return str(out)


__all__ = ["SHEET", "TITLE_SUFFIX", "FILE_SUFFIX", "COL_OF_KEY", "TIME_COL", "OFF_SUB", "OFF_TOTAL",
           "TOTAL_ANCHORS", "title_of", "body_spec", "build_xlsx", "build_zip"]
