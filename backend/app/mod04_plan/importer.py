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
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod04_plan.domain import ProjectBrief, match_project

# 表头识别用的**包含关键字**（表头是实拍长名，例：「材料：其他支出付资产处/贸易公司（编号）」）
_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("project_input", ("项目",)),
    ("material_doc", ("其他支出", "资产处", "贸易公司")),
    ("mechanical_doc", ("付款通知书",)),
    ("flow_amount", ("该流程金额",)),
    ("planned_amount", ("本月预付",)),
    ("pay_date", ("付款时间",)),
    ("pay_method", ("付款方式",)),
    ("remark", ("备注",)),
)

# 表头行扫描上限（真实表前面可能有一两行标题）
_HEADER_SCAN_ROWS = 12


@dataclass
class ParsedSheet:
    """解析结果（**纯数据**，不含 session）。"""

    columns: dict[str, str] = field(default_factory=dict)   # 字段 → 表头原文
    rows: list[dict] = field(default_factory=list)          # 每行：有效列 ＋ `raw`（无效列原样）
    header_row: int = 0                                     # 表头在第几行（1 起，便于回报）
    alerts: list[str] = field(default_factory=list)         # 只提示、不拦截


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _amount(value) -> object:
    """金额取原文（**禁 float 直传** ⇒ 先转字符串再归一，§9.1）。"""
    text = _text(value).replace(",", "")
    return to_money(text) if text else to_money(0)


def _classify(header: str) -> str | None:
    h = _text(header)
    if not h:
        return None
    for key, hints in _HINTS:
        if key == "project_input":
            if h == "项目" or h.startswith("项目"):
                return key
            continue
        if any(x in h for x in hints):
            return key
    return None


def _find_header(grid: list[list]) -> tuple[int, dict[str, int]]:
    """找出表头行与「字段 → 列号」映射（**不猜列位**，按表头文字识别）。"""
    for idx, row in enumerate(grid[:_HEADER_SCAN_ROWS]):
        mapping = {key: col for col, cell in enumerate(row) if (key := _classify(cell))}
        if "project_input" in mapping and len(mapping) >= 3:
            return idx, mapping
    raise MustReportError(
        "没认出付款计划的表头 —— 表头里至少要能看到「项目」列，"
        "以及「材料：其他支出付资产处/贸易公司（编号） / 外租机械：付款通知书（编号） / "
        "该流程金额 / 本月预付款金额 / 付款时间 / 付款方式 / 备注」这些列（§4.3.3）"
    )


def parse_workbook(data: bytes) -> ParsedSheet:
    """读 `.xlsx` → 一批计划行（**有效列**抽出，**无效列**原样进 `raw`）。"""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise MustReportError(f"这个文件读不成 Excel（.xlsx）：{exc}") from exc
    ws = wb.worksheets[0]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    if not grid:
        raise MustReportError("这个工作表是空的（第一行就是表头，请确认选对了 sheet）")

    header_idx, mapping = _find_header(grid)
    header = grid[header_idx]
    parsed = ParsedSheet(
        columns={k: _text(header[v]) for k, v in mapping.items()},
        header_row=header_idx + 1,
    )

    for row_no, row in enumerate(grid[header_idx + 1:], start=header_idx + 2):
        if all(_text(c) == "" for c in row):
            continue
        def cell(key: str):
            col = mapping.get(key)
            return row[col] if col is not None and col < len(row) else None

        material = _text(cell("material_doc"))
        mechanical = _text(cell("mechanical_doc"))
        doc_no = material or mechanical
        if material and mechanical:
            parsed.alerts.append(
                f"第 {row_no} 行：「材料（其他支出）」与「外租机械（付款通知书）」两列都填了编号 —— "
                f"本次取「{material}」；请核对（§4.3.3 一行对应一类单据）"
            )

        values = {
            "project_input": _text(cell("project_input")),
            "doc_no": doc_no,
            "flow_amount": _amount(cell("flow_amount")),
            "planned_amount": _amount(cell("planned_amount")),
            "pay_date": _text(cell("pay_date")),
            "pay_method": _text(cell("pay_method")),
            "remark": _text(cell("remark")),
        }
        # ⚠️ **无效列原样入库**（不参与审查、不要求修正，§4.3.3）
        raw = {
            _text(h) or f"列{i + 1}": _text(c)
            for i, (h, c) in enumerate(zip(header, row))
            if _text(c) != "" and _classify(h) is None
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


__all__ = ["ParsedSheet", "parse_workbook", "attach_projects", "render_import_page"]


# ---------------------------------------------------------------- 导入页（服务端渲染）


def render_import_page(*, message: str = "", message_kind: str = "ok", default_ym: str = "") -> str:
    """付款计划**导入页**（`/m04/import`）—— 口径说明 ＋ 「先选月份 ＋ 选文件」。

    ⚠️ 原型里导入是**弹窗**；服务端渲染下做成独立页（同一件事，且天然可分享 URL、无 JS）。
    """
    from app.mod03_notice.page import BASE_CSS, esc

    notice = f'<div class="notice {esc(message_kind)}">{esc(message)}</div>' if message else ""
    tips = [
        "**导入前先选「年月」**：本批数据**一律归入所选月份**（按月归档，§4.3.6）。",
        "**有效列**：项目 / 材料（其他支出·资产处·贸易公司）编号 / 外租机械（付款通知书）编号 / "
        "该流程金额 / 本月预付款金额 / 付款时间 / 付款方式 / 备注。",
        "**无效列**（科目 · 费用日期 · 收款单位 · 已付款金额 · 剩余付款金额）**原样入库、不参与审查、不要求修正**（§4.3.3）。",
        "**「项目」列**是**用户导入前手工添加**的，按**展示名 / 仓库名**唯一匹配档案："
        "命中 1 条 = 正常；0 条 = 标「未匹配」；多条 = 标「重名 N 条」。",
        "**导入幂等**（§9.5）：重复导入**覆盖同源数据、不产生重复行**；换月 / 减行**不留残影**；"
        "**可手改列**（付款时间 / 付款方式 / 备注）**不被导入覆盖**。",
        "⚠️ **同月同单据号两行不是导入的错** —— 那是审查里的「重复上报」判定：**导入照收、审查暴露、用户逐行删**（§4.3.4）。",
    ]
    li = "".join(f"<li>{t}</li>" for t in tips)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>导入付款计划</title>
<style>{BASE_CSS}
form.imp{{background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:14px;display:flex;
        flex-wrap:wrap;gap:14px;align-items:flex-end}}
form.imp label{{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--mut)}}
form.imp input{{border:1px solid var(--bd3);border-radius:5px;padding:6px 8px;font-size:13px}}
</style></head><body>
<div class="wrap">
<nav class="nav"><a href="/m04">← 返回付款计划</a></nav>
{notice}
<section class="view"><h3>导入付款计划（Excel）</h3>
<details class="tip" open><summary>口径说明 · {len(tips)} 条</summary><ul>{li}</ul></details>
<form class="imp" method="post" action="/m04/import" enctype="multipart/form-data">
<label>归入年月（先选月份）<input type="month" name="year_month" value="{esc(default_ym)}" required></label>
<label>付款计划文件（.xlsx）<input type="file" name="file" accept=".xlsx,.xlsm" required></label>
<button class="pri">开始导入</button>
</form>
</section></div>
</body></html>"""
