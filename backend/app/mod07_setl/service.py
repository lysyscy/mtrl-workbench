"""`MOD-07` 两个页面的数据组装。

- `/m07` 收发结存月报：筛选状态解析 → 按月取数 → 按仓汇总 → 合计 / 计数 / 产出物清单
- `/m07/extract` 焊材 / 气体提取：**核对工具**（§5.3.3）—— 明细 → 规则命中 → 按仓 × 月金额

⚠️ **本层不写判定**：一切取数 / 对平 / 计数 / 提取规则都调 `domain` 的出口；
   项目**状态与顺序**一律走 `MOD-01` 的出口（`ordered` / `status_label`），不在这里另立一套。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.mod07_setl import domain as D
from app.mod07_setl import extract as X
from app.mod07_setl.repository import load_rows


def _one(p: dict, name: str, default: str = "") -> str:
    v = p.get(name, default)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    if v is None:
        v = ""
    # ⚠️ 不能写 `v or ""` —— 会把 0 当空串（同族坑见 `mod08_inv/service.py`）
    return str(v).strip()


def parse_state(params: dict | None = None) -> dict:
    """收发结存页的筛选状态 —— 本页**只有一个筛选**：核算年月（单月，§9.2）。

    ⚠️ 不给月份时用**本表默认年月**（上月）；「重置」= 回到不带参数的 `/m07`。
    """
    p = params or {}
    period = _one(p, "period")
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
    """提取页的筛选状态：**项目状态**（默认「在建」）＋ **金额月份**（默认上月，四种模式）。

    ⚠️ **「不带这个参数」与「显式传空」是两件事**：
    - 不带 `ext_period` ⇒ 用本表默认年月（上月，§9.2）；
    - **显式传空串 ⇒ 不筛月份（= 全部）** —— 页面上那格写着「留空=全部」，
      再把空串当"没选"回落成上月，就是**占位符骗人**（清空筛选后看到的数据不是全部）。
    """
    p = params or {}
    status = _one(p, "status") or X.STATUS_DEFAULT
    if status not in X.STATUS_OPTIONS:
        status = X.STATUS_DEFAULT                                   # 认不出的取值 ⇒ 回落默认，不臆造
    period = _one(p, "ext_period") if "ext_period" in p else D.default_month()
    return {"status": status, "period": period, "explicit": bool(_one(p, "status"))}


def _project_context(s: Session) -> tuple[dict[str, str], list[str]]:
    """项目档案 → `(仓库名 → 状态标签, 按档案顺序的仓库名)`。

    ⭐ 顺序走 `mod01_projects.domain.ordered`（「归档后置 > ord > 原序」的**唯一出口**，§2.7.3）。
    """
    from app.mod01_projects.domain import ordered, status_label
    from app.mod01_projects.repository import all_projects

    statuses: dict[str, str] = {}
    order: list[str] = []
    for p in ordered(all_projects(s)):
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
    amounts = X.extract_amounts(load_rows(s))
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
    }


__all__ = ["parse_state", "state_to_query", "build_page_data",
           "parse_extract_state", "build_extract_data"]
