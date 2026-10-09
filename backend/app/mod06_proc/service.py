"""`MOD-06` 过程资料页的数据组装（筛选状态 → 表①② ／ 差异表）。

⚠️ **本层不写判定**：一切归集 / 合计 / 分段都调 `domain` 的出口。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.mod06_proc import domain as D
from app.mod06_proc.repository import (
    load_batches,
    load_cutoffs,
    load_mechanical_cutoffs,
)


# ⭐ **包间出口**（`TAIL-195` 批 2c）：下面四个 `load_*` 是**跨包取数**的口 ——
#    计划 §2.3：「包间只经 `service` 调用，**不得跨包直查对方表**」⇒ 别的包（真例 = `report_export`
#    的 `export_proc`）要取这些行，**经本模块**取，⛔ 别去 `import app.mod06_proc.repository`。
#    守卫 = `backend/tests/test_layering.py` **规则 D**。
# ⚠️⚠️ **必须写成函数、且每次经 `repository` 模块取** —— ⛔ 别写成模块级别名（`load_inv_rows = R.load_inv_rows`）：
#    那会在导入时把函数对象**绑死**，测试里 `monkeypatch.setattr(mod06_proc.repository, "load_inv_rows", …)`
#    就**再也打不着**（2026-09-30 实测：12 条判据当场红，症状是 `session=None` 一路传到真的查询里）。
def load_inv_rows(session, **kw):
    """⭐ 包间出口：库存单据行（`ACC-RPT-EXP-001` 表体的来源）。"""
    from app.mod06_proc import repository as R

    return R.load_inv_rows(session, **kw)


def load_mech(session, **kw):
    """包间出口：导入和手录共用的有效机械值。"""
    from app.mod06_proc import repository as R

    return R.load_mech(session, **kw)


def load_history(session, **kw):
    """⭐ 包间出口：历史段行。"""
    from app.mod06_proc import repository as R

    return R.load_history(session, **kw)


def load_cutoff(session, **kw):
    """⭐ 包间出口：某项目的截止核算月（§5.2.5）。"""
    from app.mod06_proc import repository as R

    return R.load_cutoff(session, **kw)


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
    """**过程资料页**的候选项目 = 库存单据里出现过的仓库名 ∪ 只有历史段快照的仓库名
    （**项目键 = 仓库名**，§2.7.4）。

    ⚠️ 与**导入页**的候选**刻意不同**（2026-09-27 用户裁定 · `TAIL-114`）：
       · **过程资料页**（本函数）＝ **只在有数据的那些项目里选**（用户原话：「过程资料**本身**可以
         只显示仓库有数据的项目没问题」）—— 页面上本来也只画得出有数据的项目；
       · **导入页**（`import_projects`）＝ **项目档案里的全部**（含归档）∪ 有数据的 —— 见下面那个函数的
         docstring（"导历史"这件事本身要能给**还没有任何数据**的项目做）。
       ⛔ 别再让两页"共用一份候选"：那正是 2026-09-27 之前的状态（导入页因此**自我锁死**）。
    """
    out = {str(r.get("warehouse") or "") for r in inv_rows if r.get("warehouse")}
    out |= {str(r.get("warehouse") or "") for r in history_rows if r.get("warehouse")}
    return sorted(out)


def import_projects(s: Session) -> list[str]:
    """**历史导入页**的候选项目 = **项目档案里所有有仓库名的项目（含归档）** ∪ 「有数据的那些」。

    ⭐⭐ 2026-09-27（用户裁定 · `TAIL-114`）：导入页的候选**不再只给"有数据的项目"** ——
      原口径（只有 `projects_of`）看的是「库存单据里出现过的仓库名 ∪ 已有历史段快照的仓库名」，
      而**"导历史资料"这件事本身**才是给项目造历史段的手段 ⇒
      **没有库存单据的项目永远进不了候选 ⇒ 它的历史资料永远导不进去**（自我锁死＝鸡生蛋；
      实测 17 个有仓库名的档案项目里 **8 个选不到**）—— 而这恰恰是"**系统刚启用、还没有正式段**"时
      最需要做的那件事。用户原话：「过程资料**导入**项目只显示仓库有数据的项目这个还是没改，改一下吧；
      过程资料**本身**可以只显示仓库有数据项目没问题」⇒ **两处口径就此分开**（见 `projects_of` 的注释）。

    ⚠️ 档案那一侧**复用唯一出口** `displays_by_key`（它自己走 `mod01_projects.domain.build_candidates`
      ⇒ 含归档、不含壳、键=仓库名）—— ⛔ 不在这里另立一套"从档案取候选"。
    ⚠️ 并集里**保留** i8 出现过、档案里没有的仓库名：m06 落库**不要求**档案行
      （`import_snapshot(project_id=None)` 照样写、页面按仓库名读）⇒ 那些项目也导得进去 ✓。
    """
    keys = set(projects_of(load_inv_rows(s), load_history(s) + load_mech(s)))
    keys |= set(displays_by_key(s))
    return sorted(k for k in keys if k)


def displays_by_key(s: Session) -> dict[str, str]:
    """**键（仓库名）→ 展示名**（§2.7.4）—— 唯一出口 = `mod01_projects.domain.build_candidates`
    （⛔ 不在这里另立一套"从档案里取展示名"）。

    ⭐ 用途：导出成品的**标题与文件名**一律用**展示名**（用户 2026-09-18 裁），
       且**页面清单预览**与**真实产物**必须同名（`ACC-RPT-EXP-001/001-01`）⇒ 两边共用本函数。
    """
    from sqlalchemy import select

    from app.mod01_projects import domain as PJ
    from app.mod01_projects.models import Project

    return {c.key: c.display
            for c in PJ.build_candidates(list(s.execute(select(Project)).scalars().all()))}


def build_import_data(s: Session, *, warehouse: str = "") -> dict:
    """导入项目候选、两类上次截止与批次；只读，不修改截止或数据。"""
    # ⭐ `TAIL-114`（2026-09-27 用户裁定）：导入页候选 = **档案里的全部**（含归档）∪ 有数据的
    #   —— 见 `import_projects` 的 docstring（"导历史"要能给还没数据的项目做）。
    #   ⚠️ **过程资料页**仍走 `projects_of`（用户确认：那里只显示有数据的项目没问题）。
    projects = import_projects(s)
    current = warehouse if warehouse in projects else (projects[0] if projects else "")
    return {
        "projects": projects,
        "warehouse": current,
        "cutoff_ym": load_cutoff(s, warehouse=current) if current else "",
        # ⭐ **每个项目的截止月表**（2026-09-26）：界面上「截止核算月」要**跟着所选项目换** ——
        #   上面那个 `cutoff_ym` 只是"当前项目"的那一格（读到的是候选人里的第一个），
        #   而用户会换项目 ⇒ 只给一格就会把 A 项目的分界写给 B（真缺陷，见 `load_cutoffs`）。
        #   ⚠️ 口径仍只有一处：本键由 `load_cutoffs` 给，与 `cutoff_ym` 同一张表。
        "cutoffs": load_cutoffs(s),
        "mechanical_cutoff_ym": load_mechanical_cutoffs(s).get(current, ""),
        "mechanical_cutoffs": load_mechanical_cutoffs(s),
        "batches": [b for b in load_batches(s) if not current or b.warehouse_name == current],
    }


def build_page_data(s: Session, state: dict | None = None) -> dict:
    st = dict(state or parse_state())
    inv_rows = load_inv_rows(s)
    mech_rows = load_mech(s)
    history_rows = load_history(s)                     # 历史段快照（只取未回滚批次）

    # 候选项目 = **库存单据里出现过的仓库名** ＋ **只有历史段的项目**（照原型；项目键 = 仓库名，§2.7.4）
    projects = projects_of(inv_rows, history_rows + mech_rows)
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
        "export": _export_data(st, projects=projects, warehouse=warehouse,
                               displays=displays_by_key(s)),
    }


def build_matrices(s: Session) -> dict:
    """壳与成品导出共用领域矩阵：所有有库存或有效历史的项目。"""
    inv, manual, history = load_inv_rows(s), load_mech(s), load_history(s)
    projects = projects_of(inv, history + manual)
    cutoffs = load_cutoffs(s)
    matrices = {}
    for warehouse in projects:
        tables = {name: D.build_matrix(inv_rows=inv, manual_rows=manual, history_rows=history,
                                       warehouse=warehouse, adjusted=adjusted,
                                       cutoff_ym=cutoffs.get(warehouse) or "")
                  for name, adjusted in (("raw", False), ("adjusted", True))}
        matrices[warehouse] = {**tables, "cutoff_ym": cutoffs.get(warehouse) or "",
                               "totals": {name: D.column_totals(rows) for name, rows in tables.items()},
                               "segments": {name: D.segment_totals(rows) for name, rows in tables.items()}}
    return {"projects": projects, "matrices": matrices}


def _export_data(state: dict, *, projects: list[str], warehouse: str,
                 displays: dict[str, str] | None = None) -> dict:
    """导出展开区的状态 ＋ 清单（§7.1 · `ACC-RPT-EXP-001`）。

    - **默认选中本页当前项目**（001-02）—— 只认「展开区没被提交过」这一次；
    - 全选 / 清空（`expset`）优先于逐项勾选；
    - ⚠️ 只认**真候选**（URL 里塞进来的陌生项目一律丢弃 ⇒ 不导出不存在的东西）；
    - 年月取**北京时间当月**（§7.1「文件名含日期」）；
    - ⭐ **清单里的文件名用「展示名」**（用户 2026-09-18 裁）——与真实产物同名（001-01）；
      取不到展示名（该项目还没建档）时回落成键，真实导出那一步会**拒做并给中文原因**。
    """
    from app.core.timing import today_cn, ym_of

    disp = dict(displays or {})
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
        **D.export_manifest([disp.get(p) or p for p in selected], tab=state.get("tab"), ym=ym),
        "projects": projects,
        "selected": selected,
        "open": bool(state.get("exp_open")),
    }


__all__ = ["parse_state", "build_page_data", "build_import_data", "projects_of", "displays_by_key"]
