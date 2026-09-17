"""`MOD-06` 过程资料页的数据组装（筛选状态 → 表①② ／ 差异表）。

⚠️ **本层不写判定**：一切归集 / 合计 / 分段都调 `domain` 的出口。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.mod06_proc import domain as D
from app.mod06_proc.repository import (
    load_batches,
    load_cutoff,
    load_history,
    load_inv_rows,
    load_mech,
)


def _many(p: dict, name: str) -> list[str]:
    """同名多值参数 → 去空去重的 `list`（`query_params` 对多值给 `list`、单值给 `str`）。"""
    v = p.get(name, [])
    vals = list(v) if isinstance(v, (list, tuple)) else [v]
    out: list[str] = []
    for item in vals:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def parse_state(params: dict | None = None) -> dict:
    """筛选状态：**项目（单选 · 键 = 仓库名）＋ 表签 ＋ 导出展开区状态**。

    ⚠️ 筛选栏**不设只读年月框**（001-03）：核算月只作**表内列**。
    ⚠️ 导出展开区的「选过项目没有」由 `expopen` 令牌声明 —— 见 `D.export_selection` 的说明。
    """
    p = params or {}

    def one(name: str, default: str = "") -> str:
        v = p.get(name, default)
        if isinstance(v, (list, tuple)):
            v = v[0] if v else ""
        if v is None:
            v = ""
        # ⚠️ 不能写 `v or ""` —— 会把 **0 / 整型的表签** 当成空串（`tab=0` 会静默变默认表）
        return str(v).strip()

    expset = one("expset")
    exp_pjs = _many(p, "exppj")
    return {
        "warehouse": one("pj"),
        "tab": D.tab_of(one("tab")),
        "exp_open": one("expopen") != "",
        "exp_set": expset,
        "exp_selected": exp_pjs,
        "exp_touched": one("expopen") != "" or expset != "" or bool(exp_pjs),
    }


def projects_of(inv_rows: list[dict], history_rows: list[dict]) -> list[str]:
    """候选项目 = 库存单据里出现过的仓库名 ∪ 只有历史段快照的仓库名（**项目键 = 仓库名**，§2.7.4）。

    ⚠️ 唯一出口：过程资料页与**历史导入页**共用同一份候选（各写一份 ⇒ 两页会给出不同的项目列表）。
    """
    out = {str(r.get("warehouse") or "") for r in inv_rows if r.get("warehouse")}
    out |= {str(r.get("warehouse") or "") for r in history_rows if r.get("warehouse")}
    return sorted(out)


def build_import_data(s: Session, *, warehouse: str = "") -> dict:
    """**历史导入页**的数据（§5.2.5 ①②）—— 项目候选 ＋ 当前截止核算月 ＋ 已登记批次。

    ⚠️ 本页**读取**现有数据，**不写任何东西**；写路径在 `importer.commit`（只写历史段）。
    """
    projects = projects_of(load_inv_rows(s), load_history(s))
    current = warehouse if warehouse in projects else (projects[0] if projects else "")
    return {
        "projects": projects,
        "warehouse": current,
        "cutoff_ym": load_cutoff(s, warehouse=current) if current else "",
        "batches": [b for b in load_batches(s) if not current or b.warehouse_name == current],
    }


def build_page_data(s: Session, state: dict | None = None) -> dict:
    st = dict(state or parse_state())
    inv_rows = load_inv_rows(s)
    mech_rows = load_mech(s)
    history_rows = load_history(s)                     # 历史段快照（只取未回滚批次）

    # 候选项目 = **库存单据里出现过的仓库名** ＋ **只有历史段的项目**（照原型；项目键 = 仓库名，§2.7.4）
    projects = projects_of(inv_rows, history_rows)
    warehouse = st["warehouse"] if st["warehouse"] in projects else (projects[0] if projects else "")

    cutoff = load_cutoff(s, warehouse=warehouse)       # 分界 = 截止核算月（§5.2.5 ①）
    raw = D.build_matrix(inv_rows=inv_rows, manual_rows=mech_rows, history_rows=history_rows,
                         warehouse=warehouse, adjusted=False, cutoff_ym=cutoff)
    adjusted = D.build_matrix(inv_rows=inv_rows, manual_rows=mech_rows, history_rows=history_rows,
                              warehouse=warehouse, adjusted=True, cutoff_ym=cutoff)
    diffs = D.diff_rows(inv_rows, warehouse=warehouse)
    rows = adjusted if st["tab"] == D.TAB_ADJUSTED else raw
    return {
        "state": {**st, "warehouse": warehouse},
        "projects": projects,
        "warehouse": warehouse,
        "rows_raw": raw,
        "rows_adjusted": adjusted,
        "rows": raw if st["tab"] == D.TAB_RAW else (None if st["tab"] == D.TAB_DIFF else adjusted),
        "totals": D.column_totals(rows) if st["tab"] in (D.TAB_RAW, D.TAB_ADJUSTED) else {},
        "segments": D.segment_totals(rows) if st["tab"] in (D.TAB_RAW, D.TAB_ADJUSTED) else (),
        "grand_total": D.grand_total(rows) if st["tab"] in (D.TAB_RAW, D.TAB_ADJUSTED) else None,
        "diffs": diffs,
        "diff_totals": D.diff_totals(diffs),
        # 分段（§5.2.5）：截止核算月 ＋ ⛔ 历史段**不提供行内编辑入口**（要改只能再导一次）
        "cutoff_ym": cutoff,
        "history_batches": load_batches(s),
        # 机械手录：**已手录的月份**（录入口要显示「录过哪几个月」，2026-09-17）
        "mech_months": sorted(D.mech_by_month(mech_rows, warehouse=warehouse)),
        "can_edit_history": False,
        "export": _export_data(st, projects=projects, warehouse=warehouse),
    }


def _export_data(state: dict, *, projects: list[str], warehouse: str) -> dict:
    """导出展开区的状态 ＋ 清单（§7.1 · `ACC-RPT-EXP-001`）。

    - **默认选中本页当前项目**（001-02）—— 只认「展开区没被提交过」这一次；
    - 全选 / 清空（`expset`）优先于逐项勾选；
    - ⚠️ 只认**真候选**（URL 里塞进来的陌生项目一律丢弃 ⇒ 不导出不存在的东西）；
    - 年月取**北京时间当月**（§7.1「文件名含日期」）。
    """
    from app.core.timing import today_cn, ym_of

    set_kind = str(state.get("exp_set") or "")
    if set_kind == "all":
        selected = list(projects)
    elif set_kind == "none":
        selected = []
    else:
        selected = D.export_selection(
            warehouse, state.get("exp_selected"), touched=bool(state.get("exp_touched"))
        )
    selected = [p for p in selected if p in projects]
    ym = ym_of(today_cn())
    return {
        **D.export_manifest(selected, tab=state.get("tab"), ym=ym),
        "projects": projects,
        "selected": selected,
        "open": bool(state.get("exp_open")),
    }


__all__ = ["parse_state", "build_page_data", "build_import_data", "projects_of"]
