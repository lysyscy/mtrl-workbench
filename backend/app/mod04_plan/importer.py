"""付款计划 **Excel 导入**（§4.3.3 数据入口 · §9.5 幂等）—— 解析 ＋ 幂等重写编排。

口径（《说明书》）：
- **导入前先选「年月」**：本批数据**一律归入所选月份**（按月归档，§4.3.6）。
- **有效列** = 项目 / 两个**单据号**列 / 该流程金额 / 本月预付款金额 / 付款时间 / 付款方式 / 备注；
  **无效列**（科目 · 费用日期 · 收款单位 · 已付款金额 · 剩余付款金额）**原样入库、不参与审查、不要求修正**。
- **导入幂等**（§9.5）：重复导入**覆盖同源数据、不产生重复行**·换月 / 减行**不留残影**·
  **只清理并重写「自动行」**，手动行与其手改内容不被触碰。
- **可手改列**（付款时间 / 付款方式 / 备注）**落库、不被导入覆盖、不留痕**（§4.3.3）。
- ⚠️ **同月同单据号出现两行不是导入时要拦的错** —— 它是 §4.3.4 的「重复上报」判定：
  **导入照收、审查暴露、用户逐行删**（本模块**不做**判重拦截）。

⚠️ 项目列匹配走 `domain.match_project`（**展示名 / 仓库名**唯一匹配，**全名不作匹配键**）。

⭐ **2026-09-22（`TAIL-75` B2）：识别层收编到 `import_kit` 引擎**（落库口径一字未改）。真文件逼出来的四件：
1. **一个工作簿 4 张表**（预收款 / 分包 / 人工费 / **材机付款计划明细**），而现状**只读第 1 张** ⇒ 真文件直接报错
   ⇒ 现在按「**哪张认得出表头**」自动挑（`_pick_sheet`）；
2. **二级表头续行**：真实表 `r1` 是表头、`r2` **只给"单据号"那一列**补一行（`外租机械：付款通知书（编号）`）、
   数据从 `r3` 起 —— 现状会把 `r2` 当**数据行**收进来（凭空多一行垃圾）⇒ 现在识别为**表头续行**并跳过；
3. **同一列两种单据号**（材料 / 外租机械 二选一）⇒ 见 `_doc_kind`（**域内口径**）；
4. **付款时间是「9月11号」**（中文月日）⇒ 按所选**年月**补年份（`_norm_pay_date`；⛔ 认不出就原样留着）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.errors import MustReportError
from app.import_kit import mapping
from app.import_kit.mapping import Field
from app.import_kit.parse import amount as _amount          # ⭐ `TAIL-69`：统一解析出口
from app.import_kit.parse import text as _text
from app.import_kit.readers import HEADER_SCAN_ROWS, list_sheets, read_grid
from app.mod04_plan.domain import ProjectBrief, match_project

#: ⭐ **域声明**：字段名 ＋ 实拍长表头的**别名**（原 `_HINTS` 的包含词搬到这里）—— 识别归引擎、口径归本域。
FIELDS: tuple[Field, ...] = (
    Field("project_input", "项目", aliases=("项目名称", "工程名称"), type="text", required=True),
    Field("material_doc", "材料单据",
          aliases=("材料：其他支出付资产处/贸易公司（编号）", "其他支出", "资产处", "贸易公司"), type="code"),
    Field("mechanical_doc", "机械单据",
          aliases=("外租机械：付款通知书（编号）", "外租机械", "付款通知书"), type="code"),
    Field("flow_amount", "该流程金额", aliases=("流程金额",), type="amount", required=True),
    Field("planned_amount", "本月预付款金额", aliases=("本月预付", "预付款金额"), type="amount"),
    Field("pay_date", "付款时间", aliases=("付款日期",), type="date"),
    Field("pay_method", "付款方式", aliases=("支付方式",), type="enum"),
    Field("remark", "备注", aliases=("说明",), type="text"),
)
#: 挑表门槛：一张表至少要认出这么多字段（且**必须含「项目」**）才算"这张是付款计划"
_MIN_HITS = 3
#: 机械侧单据号形态：`FKTZS…`（**付款通知书**）—— 见 `_doc_kind`
_MECH_DOC = re.compile(r"^[A-Za-z]{2,}ZS\d+")
#: 「9月11号」这类**中文月日**
_CN_MD = re.compile(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]$")


@dataclass
class ParsedSheet:
    """解析结果（**纯数据**，不含 session）。"""

    columns: dict[str, str] = field(default_factory=dict)   # 字段 → 表头原文
    rows: list[dict] = field(default_factory=list)          # 每行：有效列 ＋ `raw`（无效列原样）
    header_row: int = 0                                     # 表头在第几行（1 起，便于回报）
    sheet: str = ""                                         # 读的是哪张工作表（真文件里要说得清）
    alerts: list[str] = field(default_factory=list)         # 只提示、不拦截


def _columns_of(row: list) -> dict[int, str]:
    """一行表头 → `{列号: 字段key}`。

    ⚠️ **只认 `auto` 档（≥0.90）** ——「需确认」档（0.70~0.90）留给**界面**（有人看着才敢用），
       引擎级自动识别不放它进来：实测踩过 —— `已付款金额` 与 `本月预付款金额` 字形相似 0.83，
       放进来会**抢走本该给「本月预付款金额」的那一列**（金额取错列 = 最贵的一类错）。
    """
    out: dict[int, str] = {}
    for col, cell in enumerate(row):
        got = mapping.guess([cell], FIELDS)[0]
        if got.field is None or got.level != "auto":
            continue
        key = next(f.key for f in FIELDS if f.label == got.field)
        out[col] = key
    return out


def _pick_sheet(data: bytes) -> tuple[str, list[list], int]:
    """挑工作表 ＋ 表头行 ⇒ `(sheet, grid, header_idx)`；都不认得出 ⇒ **显式报错**并列出工作表。

    ⭐ 规则：**哪张认得出表头就用哪张**（认出字段最多者胜，且**必须含「项目」**)——
    真文件的第 1 张是「计划预收款明细」（只认得出"项目名称/备注"两张牌）⇒ 自然落选。
    """
    sheets = list_sheets(data)
    best: tuple[int, str, list[list], int] | None = None
    for name in sheets:
        try:
            grid, _ = read_grid(data, sheet=name)
        except MustReportError:
            continue                          # 空表（真文件里就有）/ 读不了 ⇒ 跳过
        for idx, row in enumerate(grid[:HEADER_SCAN_ROWS]):
            cols = _columns_of(row)
            if "project_input" in cols.values() and len(set(cols.values())) >= _MIN_HITS:
                if best is None or len(set(cols.values())) > best[0]:
                    best = (len(set(cols.values())), name, grid, idx)
                break                          # 这一张已经认出来了 ⇒ 不用再往下扫它的其他行
    if best is None:
        raise MustReportError(
            "没认出付款计划的表头 —— 表头里至少要能看到「项目」列，"
            "以及「材料：其他支出付资产处/贸易公司（编号） / 外租机械：付款通知书（编号） / "
            "该流程金额 / 本月预付款金额 / 付款时间 / 付款方式 / 备注」这些列（§4.3.3）"
            f"。现有工作表：{' / '.join(sheets)}"
        )
    return best[1], best[2], best[3]


def doc_kind(value: str) -> str:
    """⭐ **单列两种单据号的域内消歧**（材料 / 外租机械 二选一，§4.3.3）。

    依据 = 真文件实测：该列填的是 `FKTZS…`（**付款通知书**编号 ⇒ 外租机械侧），
    而材料侧走的是其他支出单（`QTZC…` 一类）⇒ **`FKTZS` 形态归机械，其余归材料**。
    ⛔ 本函数只判"这一格属于哪一类"，不做任何取值改写。
    """
    return "mechanical_doc" if _MECH_DOC.match(value) else "material_doc"


def norm_pay_date(value: str, year_month: str) -> str:
    """付款时间归一：**「9月11号」按所选年月补成完整日期**（其余原样，⛔ 不猜）。

    ⚠️ 两条边界（自测踩过第一条）：
    1. `year_month` 本身就含月份 ⇒ **只补"日"**（写成 `f"{ym}-{月}-{日}"` 会得到 `2026-09-09-11`）；
    2. 单元格里的月份与所选年月**不同月** ⇒ 原样返回（跨月不猜年份/月份，交人核对）。
    """
    m = _CN_MD.match(value)
    if not m or not year_month:
        return value
    month, day = int(m.group(1)), int(m.group(2))
    if year_month.endswith(f"-{month:02d}"):
        return f"{year_month}-{day:02d}"
    return value


def parse_workbook(data: bytes, *, year_month: str = "") -> ParsedSheet:
    """读 `.xlsx` → 一批计划行（**有效列**抽出，**无效列**原样进 `raw`）。

    ⚠️ `year_month` **只为把「9月11号」这类中文月日补成完整日期**（§4.3.3 导入前先选月份）；
       缺省空 ⇒ 原文保留（落库那一步仍会拦「没选年月」）。
    """
    sheet, grid, header_idx = _pick_sheet(data)
    head = grid[header_idx]
    cols = _columns_of(head)
    parsed = ParsedSheet(
        columns={key: _text(head[col]) for col, key in sorted(cols.items())},
        header_row=header_idx + 1,
        sheet=sheet,
    )

    # ⭐ **二级表头续行**（真文件 r2）：整行非空格子**都还能认成字段** ⇒ 它还是表头，不是数据。
    lvl2 = grid[header_idx + 1] if header_idx + 1 < len(grid) else []
    lvl2_cols = _columns_of(lvl2)
    if lvl2_cols and all(_columns_of([cell]).get(0) or not _text(cell) for cell in lvl2):
        # 同一列出现**第二个字段** ⇒ 这一列是"二选一"（材料 / 机械）
        duo = {c: (cols[c], f2) for c, f2 in lvl2_cols.items() if c in cols and f2 != cols[c]}
        parsed.alerts.append(f"工作表「{sheet}」的第 {header_idx + 1}、{header_idx + 2} 行是**两级表头**（已合并识别）")
        data_from = header_idx + 2
    else:
        duo = {}
        data_from = header_idx + 1

    for row_no, row in enumerate(grid[data_from:], start=data_from + 1):
        if all(_text(c) == "" for c in row):
            continue

        def cell(key: str):
            col = next((c for c, k in cols.items() if k == key), None)
            return row[col] if col is not None and col < len(row) else None

        material = _text(cell("material_doc"))
        mechanical = _text(cell("mechanical_doc"))
        for col, pair in duo.items():                    # ⭐ 一列两义 ⇒ 按编号形态归位
            v = _text(row[col]) if col < len(row) else ""
            if v:
                holder = doc_kind(v)
                if holder == "mechanical_doc":
                    mechanical, material = v, ""
                else:
                    material, mechanical = v, ""
        doc_no = material or mechanical
        if material and mechanical:
            parsed.alerts.append(
                f"第 {row_no} 行：「材料（其他支出）」与「外租机械（付款通知书）」两列都填了编号 —— "
                f"本次取「{material}」；请核对（§4.3.3 一行对应一类单据）"
            )

        pay_date_raw = _text(cell("pay_date"))
        pay_date = norm_pay_date(pay_date_raw, year_month)
        if pay_date != pay_date_raw:
            parsed.alerts.append(f"第 {row_no} 行：付款时间「{pay_date_raw}」按所选年月补成「{pay_date}」")

        values = {
            "project_input": _text(cell("project_input")),
            "doc_no": doc_no,
            "flow_amount": _amount(cell("flow_amount")),
            "planned_amount": _amount(cell("planned_amount")),
            "pay_date": pay_date,
            "pay_method": _text(cell("pay_method")),
            "remark": _text(cell("remark")),
        }
        # ⚠️ **无效列原样入库**（不参与审查、不要求修正，§4.3.3）
        raw = {
            _text(h) or f"列{i + 1}": _text(c)
            for i, (h, c) in enumerate(zip(head, row))
            if _text(c) != "" and i not in cols
        }
        raw["_row_no"] = row_no
        raw["_material_doc"] = material
        raw["_mechanical_doc"] = mechanical
        values["raw"] = raw
        values["_row_no"] = row_no
        parsed.rows.append(values)

    if not parsed.rows:
        raise MustReportError("表头认出来了，但下面一行数据都没有 —— 请确认文件内容")
    return parsed


def attach_projects(rows: list[dict], projects: list[ProjectBrief]) -> list[dict]:
    """给每行补**项目匹配结论**（§4.3.3：命中 1 条 = 正常；0 条 = 未匹配；多条 = 重名 N 条）。"""
    out: list[dict] = []
    for row in rows:
        result = match_project(str(row.get("project_input") or ""), projects)
        item = dict(row)
        item["project_id"] = result.project_id
        item["match_status"] = result.status
        item["match_candidates"] = result.candidates
        out.append(item)
    return out


# ----------------------------------------------------------- ⭐ `TAIL-69` 预览态（不写库）

def stage_payload(parsed: ParsedSheet, rows: list[dict], year_month: str) -> dict:
    """解析结果 → **JSON 安全**的暂存载荷（金额转字符串；确认时还原）。

    ⚠️ 项目匹配**在解析时已完成**（`attach_projects`）—— 确认时**不重算**：
       暂存里存的是用户在预览界面**看到的那一份**（「所见即所落」，⛔ 确认时偷偷重算 = 第二份口径）。
    """
    safe_rows = []
    for r in rows:
        item = dict(r)
        item["flow_amount"] = str(r.get("flow_amount"))
        item["planned_amount"] = str(r.get("planned_amount"))
        safe_rows.append(item)
    return {
        "year_month": year_month,
        "sheet": parsed.sheet,
        "columns": dict(parsed.columns),
        "header_row": parsed.header_row,
        "alerts": list(parsed.alerts or []),
        "rows": safe_rows,
    }


def restore_rows(payload: dict) -> tuple[str, list[dict]]:
    """暂存载荷 → `(年月, rows)`（金额字符串 → `to_money`，与解析时同一出口）。"""
    from app.import_kit.parse import amount as kit_amount

    ym = str(payload.get("year_month") or "").strip()
    rows = []
    for r in payload.get("rows") or []:
        item = dict(r)
        item["flow_amount"] = kit_amount(r.get("flow_amount"))
        item["planned_amount"] = kit_amount(r.get("planned_amount"))
        rows.append(item)
    return ym, rows


def match_summary(rows: list[dict]) -> dict:
    """预览用的**项目匹配盘点**（命中 / 未匹配 / 重名 —— 让人先看见再确认）。"""
    from app.mod04_plan.domain import MATCH_AMBIGUOUS, MATCH_UNMATCHED   # noqa: PLC0415 常量避免循环导入

    unmatched = [
        {"row": r.get("_row_no"), "project_input": str(r.get("project_input") or "")}
        for r in rows if r.get("match_status") == MATCH_UNMATCHED
    ]
    multi = [
        {"row": r.get("_row_no"), "project_input": str(r.get("project_input") or ""),
         "candidates": list(r.get("match_candidates") or [])}
        for r in rows if r.get("match_status") == MATCH_AMBIGUOUS
    ]
    return {
        "rows_total": len(rows),
        "matched": len(rows) - len(unmatched) - len(multi),
        "unmatched": unmatched,
        "multi": multi,
    }


__all__ = ["FIELDS", "ParsedSheet", "attach_projects", "doc_kind", "match_summary",
           "norm_pay_date", "parse_workbook", "restore_rows", "stage_payload"]

# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：**导入页 `render_import_page` 已随旧渲染层删除**（授权 `D18`）——
#    那是**页面件**；本文件保留的两件是**业务**（解析工作簿 / 挂项目），新壳的导入走
#    `POST /api/m04/import`（multipart）。⚠️ 原型里导入是**弹窗** ⇒ 不再需要服务端渲染的独立页。
# ⚠️ 2026-09-22（`TAIL-75` B2）：识别层（`_HINTS` / `_classify` / `_find_header`）**已收编**到
#    `import_kit`（声明 = `FIELDS`）—— ⛔ 别再在本文件里长回第二套表头识别。
