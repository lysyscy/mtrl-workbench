"""`MOD-07` 两个页面的数据组装。

- `/m07` 收发结存月报：筛选状态解析 → 按月取数 → 按仓汇总 → 合计 / 计数 / 产出物清单
- `/m07/extract` 焊材 / 气体提取：**核对工具**（§5.3.3）—— 明细 → 规则命中 → 按仓 × 月金额

⚠️ **本层不写判定**：一切取数 / 对平 / 计数 / 提取规则都调 `domain` 的出口；
   项目**状态与顺序**一律走 `MOD-01` 的出口（`ordered` / `status_label`），不在这里另立一套。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.query import query_one

from app.mod07_setl import domain as D
from app.mod07_setl import extract as X
from app.mod07_setl import inventory_extract as I
from app.mod07_setl.repository import load_balances, load_rows, save_balance


def parse_state(params: dict | None = None) -> dict:
    """收发结存页的筛选状态 —— 本页**只有一个筛选**：核算年月（单月，§9.2）。

    ⚠️ 不给月份时用**本表默认年月**（上月）；「重置」= 回到不带参数的 `/m07`。
    """
    p = params or {}
    period = query_one(p, "period")
    return {"period": period or D.default_month(), "explicit": bool(period)}


def state_to_query(state: dict) -> str:
    """筛选状态 → 查询串（PRG 回跳 / 弹窗默认月共用）。"""
    from urllib.parse import urlencode

    return urlencode([("period", state.get("period") or "")])


def build_page_data(s: Session, state: dict | None = None) -> dict:
    """页面所需的一切：按月取数**＋ 按仓汇总** → 表体 / 合计 / 空态文字 / 三项计数 / 产出物清单。"""
    st = dict(state or parse_state())
    ym = st["period"]
    rows = D.warehouse_rows(load_rows(s), ym)
    return {
        "state": st,
        "ym": ym,
        "rows": rows,
        "summary": D.sum_row(rows),
        "empty_text": D.empty_text(ym),
        "counts": D.counts(rows, ym),
        "manifest": D.zip_manifest(rows, ym),
        "zip_name": D.zip_name(ym),
        "fetch_default_month": D.fetch_dialog_default(ym),
        "balance_ok": all(D.is_balanced(r) for r in rows) and bool(rows),
    }


# ============================================================ 焊材 / 气体提取（§5.3.3）


def parse_extract_state(params: dict | None = None) -> dict:
    """提取页的筛选状态：**项目状态**（默认「在建」）＋ **年份**（默认报表核算期所属年；旧期间参数兼容）。

    ⚠️ **「不带这个参数」与「显式传空」是两件事**：
    - 不带 `ext_period` ⇒ 上月所属年（§9.2）；
    - 旧调用显式空串仍表示全部期间；年度页面只提交年份。
      原模板保留旧期间兼容，新增年度网格使用默认年。
    """
    p = params or {}
    status = query_one(p, "status") or X.STATUS_DEFAULT
    if status not in X.STATUS_OPTIONS:
        status = X.STATUS_DEFAULT                                   # 认不出的取值 ⇒ 回落默认，不臆造
    period = query_one(p, "ext_period") if "ext_period" in p else D.default_month()[:4]
    return {"status": status, "period": period, "explicit": bool(query_one(p, "status"))}


def _project_context(s: Session) -> tuple[dict[str, str], list[str]]:
    """项目档案 → `(仓库名 → 状态标签, 按档案顺序的仓库名)`。

    ⭐ 顺序走 `mod01_projects.domain.ordered`（「归档后置 > ord > 原序」的**唯一出口**，§2.7.3）。
    """
    from app.mod01_projects import service as P1S
    from app.mod01_projects.domain import ordered, status_label

    statuses: dict[str, str] = {}
    order: list[str] = []
    for p in ordered(P1S.all_projects(s)):
        warehouse = str(getattr(p, "warehouse_name", "") or "")
        if not warehouse:
            continue
        order.append(warehouse)
        statuses[warehouse] = status_label(p.status)
    return statuses, order


def _visible(amounts: dict, kind: str, st: dict, statuses: dict, order: list[str]) -> list[str]:
    """该类别在**当前筛选**下的数据行（项目状态过滤 ＋ 档案顺序）。"""
    return X.visible_warehouses(amounts.get(kind), statuses=statuses,
                                status=st["status"], order=order)


def build_extract_data(s: Session, state: dict | None = None) -> dict:
    """提取页所需的一切：两个分组块（含**紧贴**本类数据行的合计行）＋ 计数 ＋ 导出矩阵。"""
    st = dict(state or parse_extract_state())
    amounts = I.load_amounts(s)
    statuses, order = _project_context(s)
    blocks: list[dict] = []
    for kind in X.KINDS:
        warehouses = _visible(amounts, kind, st, statuses, order)
        blocks.append(X.extract_block(amounts, kind, warehouses=warehouses, period=st["period"]))
    return {
        "state": st,
        "blocks": blocks,
        "months": X.extract_months(amounts),
        "counts": {b["kind"]: len(b["rows"]) for b in blocks},
        "export": [X.extract_export_matrix(
            amounts, kind, warehouses=_visible(amounts, kind, st, statuses, order))
            for kind in X.KINDS],
        "rules": X.default_rules(),
        "annual": annual_grids(s, amounts, st),
    }


def export_report_ym(period: str, months) -> str:
    """导出的**报告月**（`YYYY-MM`）：**止月** —— 单月取该月 · 跨月取止月 · 年取 12 月；
    **「全部」⇒ 取数据里的最新一期**（⛔ 不回落成"本月"，那会把一个不存在的月份当报告期）。

    ⚠️ 时间口径走 `core.period`（唯一主人），本处不另解一遍。
    """
    from app.core.period import period_range

    _start, end = period_range(period)
    if end is None:
        return max(months) if months else ""
    return end[:7]


def build_extract_export(s: Session, state: dict | None = None) -> dict:
    """导出（**路径① 模板填充**）所需的一切：两个类别各一份**年度网格** ＋ 期间口径。

    - **行 = 所筛选项目**（项目状态 ＋ 档案顺序）—— 与页面 `build_extract_data` **同一份口径**
      （`_visible`）⇒ 导出的行集合永远与页面看到的一致（⛔ 不各写一份筛选）；
    - 月份列 = **报告年**的 12 个月（`模板清单` 裁定④：模板表头没写年份 ⇒ 都属该年）；
    - 「结余」= ⚠️ **历史结余、由用户手工录入**（2026-09-18 用户裁定）⇒ 取自 `load_balances`
      （**唯一取数出口**）；未录入 ⇒ `None` ⇒ 产物该格**如实留空**（⛔ 不写 0）。
    """
    st = dict(state or parse_extract_state())
    amounts = I.load_amounts(s)
    balances = load_balances(s)
    statuses, order = _project_context(s)
    report_ym = export_report_ym(st["period"], X.extract_months(amounts))
    grids = {}
    for kind in X.KINDS:
        grids[kind] = X.extract_template_grid(
            amounts, kind,
            warehouses=_visible(amounts, kind, st, statuses, order),
            year=report_ym[:4] if report_ym else "", balances=balances)
    return {"state": st, "report_ym": report_ym, "year": report_ym[:4] if report_ym else "",
            "grids": grids, "annual_grids": annual_grids(s, amounts, st)}


def annual_grids(s: Session, amounts: dict, state: dict) -> dict:
    """页面、合计和年度导出共用网格；筛选、档案顺序仍走现有出口。"""
    year = str(state.get('period') or D.default_month())[:4]
    if len(year) != 4 or not year.isdigit():
        year = D.default_month()[:4]
    statuses, order = _project_context(s)
    balances = load_balances(s)
    return {kind:I.annual_grid(amounts, kind, warehouses=_visible(amounts, kind, state, statuses, order), year=year, balances=balances)
            for kind in X.KINDS}


def save_balance_cell(s: Session, *, kind: str, warehouse: str, raw) -> dict:
    """保存提取页**「结余」一格的录入值** → `{"ok", "message", "value"}`。

    ⛔ **判定一律在域内核**（`extract.parse_balance`）：非法输入（非数字 / 负数）**不写库、原值不变**；
    ⭐ **只动这一格**（粒度 = 类别 × 仓库，不按月）；空输入 ⇒ **清空**（删行 ⇒ 导出如实留空）。
    ⚠️ `warehouse` 只校验**非空** —— 「结余」挂在**仓库名**上（§2.7.4），陌生仓库**也可能有**结余
       （档案里没有它 ≠ 它没有物料账）⇒ 这里**不拿档案当闸门**（那会把陌生仓库的录入挡掉）。
    """
    if str(kind or "") not in X.KINDS:
        return {"ok": False, "message": X.MSG_BAL_NO_KIND, "value": None}
    wh = str(warehouse or "").strip()
    if not wh:
        return {"ok": False, "message": X.MSG_BAL_NO_WH, "value": None}
    parsed = X.parse_balance(raw)
    if not parsed["ok"]:
        return {"ok": False, "message": parsed["message"], "value": None}
    save_balance(s, kind=str(kind), warehouse=wh, amount=parsed["value"])
    return {"ok": True,
            "message": X.MSG_BAL_SAVED if parsed["value"] is not None else X.MSG_BAL_CLEARED,
            "value": parsed["value"]}


__all__ = ["project_references", "parse_state", "state_to_query", "build_page_data",
           "parse_extract_state", "build_extract_data",
           "export_report_ym", "build_extract_export", "save_balance_cell"]


def extract_year_totals(amounts: dict, balances: dict) -> dict:
    """大表页面读取各年同源合计；项目状态筛选不影响会议选题。"""
    years = {ym[:4] for ym in X.extract_months(amounts)}
    return {year:{kind:{row['warehouse']:str(row['total'])
        for row in X.extract_template_grid(amounts, kind,
            warehouses=set(amounts.get(kind, {})) | set(balances.get(kind, {})),
            year=year, balances=balances)['rows']} for kind in X.KINDS}
        for year in years}


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import SetlDetail, WeldGasBalance, AnalysisBigProject, AnalysisBigManual

    return read(session, ((SetlDetail, '收发结存'), (WeldGasBalance, '焊材气体结余'), (AnalysisBigProject, '大表项目排序'), (AnalysisBigManual, '大表手录'),), project_id, warehouse, lock=lock)


def opening_months(session, warehouses, months):
    """机械费只读复用大表同核算月的开工年月及上次值带入口径。"""
    from . import big_repository as R, big_domain as B
    own = R.load_manual(session)
    return {wh: {ym: B.parse_month(B.manual_cell(own, ym, wh, 'open_ym')['value'])
                 for ym in months} for wh in warehouses}
