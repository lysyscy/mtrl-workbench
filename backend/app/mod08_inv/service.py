"""`MOD-08` 页面数据组装（筛选状态解析 → 行 → 合计 → 值清单）。

⚠️ **本层不写判定**：一切筛选 / 合计 / 判据都调 `domain` 的出口（或全站共用件 `core.period`）。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.query import query_one

from app.core.period import default_period
from app.mod08_inv import domain as D

DEFAULT_TABLE = "inventory"          # 材料报表类 ⇒ 默认核算年月 = 北京时间**上月**（§9.2）


# ⭐ **包间出口**（`TAIL-218` 批 3）：`mod06_proc` 要库存单据明细 ⇒ **经本口取**，
#    ⛔ 别去 `import app.mod08_inv.repository`。计划 §2.3「包间只经 `service` 调用」；守卫 = 规则 C。
# ⚠️⚠️ **写成函数、且每次经 `repository` 模块取** —— ⛔ 别写成模块级别名（那会在 import 时把函数对象
#    **绑死**，测试里 monkeypatch 打不着；2026-09-30 实测 12 条判据当场红）。
# ⚠️ 本页自己取数也走它（⛔ 不留第二份"本包直连"的写法）。
def load_rows(session, **kw):
    """⭐ 包间出口：库存单据明细（**已叠加调整单**的规范行）。"""
    from app.mod08_inv import repository as R

    return R.load_rows(session, **kw)


def load_original_details(session, **kw):
    """包间只读出口：库存原单明细，不叠加人工调整金额。"""
    from app.mod08_inv import repository as R
    return R.list_details(session, **kw)


def load_original_inbound(session):
    """包间只读出口：原单入库的物料名、仓库、核算月及金额。"""
    from app.mod08_inv import repository as R
    return R.load_original_inbound(session)


def parse_state(params: dict | None = None) -> dict:
    """把扁平查询参数解析成**筛选状态**（视图与路由共用同一个出口，不在各处各解一遍）。"""
    p = params or {}

    def many(name: str) -> tuple[str, ...]:
        v = p.get(name, ())
        if isinstance(v, str):
            v = [v]
        return tuple(str(x).strip() for x in (v or ()) if str(x).strip())

    col_filters: dict[str, dict] = {}
    for key in D.filterable_keys():
        f: dict = {}
        q = query_one(p, f"f_{key}")
        if q:
            f["q"] = q
        lo, hi = query_one(p, f"f_{key}_min"), query_one(p, f"f_{key}_max")
        if lo:
            f["min"] = lo
        if hi:
            f["max"] = hi
        values = many(f"f_{key}_v")
        if values:
            f["v"] = list(values)
        if f:
            col_filters[key] = f

    return {
        "period": query_one(p, "period") or default_period(DEFAULT_TABLE),
        "projects": many("pj"),
        "direction": query_one(p, "dir") or D.DIRECTION_ALL,
        "only_adjusted": query_one(p, "only_adj") == "1",
        "col_filters": col_filters,
    }


def state_to_query(state: dict) -> str:
    """筛选状态 → 查询串（PRG 回跳 / 导出链接共用，避免各处手拼）。"""
    from urllib.parse import urlencode

    items: list[tuple[str, str]] = [("period", state.get("period") or "")]
    items += [("pj", p) for p in (state.get("projects") or ())]
    items.append(("dir", state.get("direction") or D.DIRECTION_ALL))
    if state.get("only_adjusted"):
        items.append(("only_adj", "1"))
    for key, f in (state.get("col_filters") or {}).items():
        if f.get("q"):
            items.append((f"f_{key}", str(f["q"])))
        if f.get("min") not in (None, ""):
            items.append((f"f_{key}_min", str(f["min"])))
        if f.get("max") not in (None, ""):
            items.append((f"f_{key}_max", str(f["max"])))
        for v in f.get("v") or ():
            items.append((f"f_{key}_v", str(v)))
    return urlencode(items)


def build_page_data(s: Session, state: dict | None = None) -> dict:
    """页面所需的一切（行 / 合计 / 值清单 / 抓取弹窗默认月 / 两种导出）。"""
    st = dict(state or parse_state())
    rows = load_rows(s, ym=None)          # ⚠️ 时间范围由 domain 的粗筛判（四种模式共用一套解析）

    view_rows = D.filter_rows(
        rows,
        ym=st["period"],
        projects=st["projects"],
        direction=st["direction"],
        only_adjusted=st["only_adjusted"],
        col_filters=st["col_filters"],
    )
    coarse = D.coarse_rows(
        rows,
        ym=st["period"],
        projects=st["projects"],
        direction=st["direction"],
        only_adjusted=st["only_adjusted"],
    )
    values = {
        key: sorted({D.cell_text(r, key) for r in coarse if D.cell_text(r, key) != ""})
        for key in D.filterable_keys()
    }
    return {
        "state": st,
        "rows": view_rows,
        "all_count": len(rows),
        "coarse_count": len(coarse),
        "sums": D.sum_cells(view_rows),
        "values": values,
        "active_columns": D.active_column_count(st["col_filters"]),
        "projects": sorted({str(r.get("warehouse") or "") for r in rows if r.get("warehouse")}),
        "fetch_default_month": D.fetch_dialog_default(st["period"]),
        "export_kinds": D.export_kinds(),
    }


__all__ = ["project_references", "DEFAULT_TABLE", "load_rows", "load_original_details", "load_original_inbound",
           "parse_state", "state_to_query", "build_page_data"]


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import InvDetail

    return read(session, ((InvDetail, '库存单据'),), project_id, warehouse, lock=lock)
