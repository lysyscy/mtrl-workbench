"""`MOD-07` 活动大表的**组装与写动作**。

⚠️ **本层不写判定**：列结构 / 带入 / 派生 / 解析一律调 `big_domain` 的出口；
   项目候选与顺序走 `MOD-01` 的出口（`build_candidates`）与 `big_repository`（大表自己的序）。
⚠️ **手填值不参与欠款计算**（§5.7.2）：本层**不调用**付款域的任何重算出口
   （欠款只认付款域口径，见 §4.5；判据 001-14 用 spy 钉住这一点）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod01_projects import service as P1S
from app.mod07_setl import big_domain as B
from app.mod07_setl import big_repository as R
from app.mod07_setl import extract as X
from app.mod07_setl import inventory_extract as I
from app.mod06_proc import service as P6S
from app.mod07_setl.repository import load_rows, load_balances

#: 主材累计取数口；显式None表示不可得，无纳入合同由owner返回0。
MAIN_MATERIAL_PORT: Callable[[Session, set[str]], dict[str, Decimal]] | None = None


def set_main_material_port(fn: Callable[[Session, set[str]], dict[str, Decimal]] | None) -> None:
    """注册同会话批量取数口；None退回不可得。"""
    global MAIN_MATERIAL_PORT
    MAIN_MATERIAL_PORT = fn


def _main_material_port(s: Session, warehouse_keys: set[str]) -> dict[str, Decimal]:
    """结算口径由MOD11持有；使用大表调用者的同一会话。"""
    from app.mod11_jc import service as M11

    return M11.settlement_totals_by_project(s, warehouse_keys)

set_main_material_port(_main_material_port)


def parse_state(params: dict | None = None) -> dict:
    """筛选状态 —— 本页**只有一个筛选**：核算年月（单月，§9.2 材料报表类）。

    ⚠️ 不给月份 ⇒ 用**本表默认年月**（北京时间上月）；「重置」= 回到不带参数的 `/m07/big`。
    """
    p = params or {}
    raw = p.get("period", "")
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ""
    v = str(raw if raw is not None else "").strip()
    return {"month": B.parse_month(v) or B.default_month(), "explicit": bool(v)}


def state_query(state: dict) -> str:
    from urllib.parse import urlencode

    return urlencode([("period", state.get("month") or "")])


# ============================================================ 自动列取数（§5.7.1）

def _extract_amounts(s: Session) -> dict:
    """焊材 / 三气：**库存入库提取**（§5.3.3）—— 当月走「金额」口径、累计走「总金额」口径。"""
    return I.load_amounts(s)


def _mech_amounts(s: Session) -> dict[str, dict[str, dict[str, object]]]:
    """机械：`{仓库: {月份: [6 列]}}`（过程资料机械 6 列的手录旁路表，§5.2.5）。"""
    out: dict[str, dict[str, list]] = {}
    for row in P6S.load_mech(s):
        wh = str(row.get("warehouse") or "")
        ym = str(row.get("ym") or "")
        if not wh or not ym:
            continue
        out.setdefault(wh, {})[ym] = [
            row.get(f"mech_{i}") for i in range(6)
        ]
    return out


def _m(d: dict, ym: str, idx: int):
    """机械 6 列某一格（缺省 0 —— 该月没录 = 0，**不是"不可得"**：这张表是手录旁路，空即无值）。"""
    return (d.get(ym) or [0] * 6)[idx] or 0


def _amounts(s: Session, warehouses, month: str) -> dict[str, dict]:
    """装配整表所需的**自动列取数**（唯一出口）—— 逐仓给 9 个键。

    口径（§5.7.1）：
    - 焊材 / 三气：**提取**（`extract`，当月 = 该核算月；累计复用历史列＋会议所属年12个月合计）
    - 外租机械 = **外租零租含税 ＋ 外租包月含税**（机械 6 列下标 2 / 3）
    - 设备租赁（含内租）= **内租设备**（下标 1）
    - 主材累计（含税）= 集采台账结算额 ⇒ **取数口未接入时给 `None`**（不可得，不写 0）
    """
    from app.core.money import sum_money

    ex = _extract_amounts(s)
    balances = load_balances(s)
    totals = {kind:{row['warehouse']:row['total'] for row in X.extract_template_grid(
        ex, kind, warehouses=warehouses, year=month[:4], balances=balances)['rows']}
        for kind in X.KINDS}
    mech = _mech_amounts(s)
    materials = MAIN_MATERIAL_PORT(s, set(warehouses or ())) if MAIN_MATERIAL_PORT else {}
    out: dict[str, dict] = {}
    for wh in warehouses or ():
        hw = ((ex.get("焊材") or {}).get(wh) or {})
        qt = ((ex.get("气体") or {}).get(wh) or {})
        m = mech.get(wh) or {}
        months = list(m)
        rent_cum = sum_money([_m(m, ym, 2) for ym in months] + [_m(m, ym, 3) for ym in months])
        lease_cum = sum_money([_m(m, ym, 1) for ym in months])
        out[wh] = {
            "hw_cum": totals['焊材'][wh],
            "hw_mon": hw.get(month) or 0,
            "qt_cum": totals['气体'][wh],
            "qt_mon": qt.get(month) or 0,
            "rent_cum": rent_cum,
            "rent_mon": sum_money([_m(m, month, 2), _m(m, month, 3)]),
            "lease_cum": lease_cum,
            "lease_mon": _m(m, month, 1),
            "mat_cum": materials.get(wh),
        }
    return out


# ============================================================ 页面数据

def require_month(month: str) -> str:
    if B.parse_month(month) != month:
        raise MustReportError("核算月要填 YYYY-MM；本次未保存")
    return month


def selection_data(s: Session, month: str) -> dict:
    projects = P1S.all_projects(s)
    selection = R.load_selection(s, month)
    active_keys = {c["warehouse"] for c in B.candidates(projects)}
    # 固定月保留自己已选的归档项目；继承月只取当前在建，且不追加新项目。
    cands = [c for c in B.candidates(projects, include_archived=True)
             if c["warehouse"] in active_keys or selection["fixed"] and c["warehouse"] in selection["order"]]
    order = B.resolve_order(selection["order"], cands, chosen=selection["source"] != "default")
    return {"selected": order, "candidates": cands,
            "selection": {"fixed": selection["fixed"], "source": selection["source"]}}


def materialize_selection(s: Session, month: str, data: dict | None = None) -> None:
    require_month(month)
    data = data if data is not None else selection_data(s, month)
    if not data["selection"]["fixed"]:
        R.save_order(s, month, data["selected"])


def build_big_data(s: Session, state: dict | None = None) -> dict:
    """页面 / 导出所需的一切（**同一份行装配** ⇒ 两处同序同值，§5.7.3）。"""
    st = dict(state or parse_state())
    month = st["month"]
    selected = selection_data(s, month)
    cands = selected["candidates"]
    by_key = {c["warehouse"]: c for c in cands}
    order = selected["selected"]
    projects = [by_key[w] for w in order if w in by_key]
    amounts = _amounts(s, [p["warehouse"] for p in projects], month)
    rows = B.assemble_rows(projects, amounts, R.load_manual(s), month=month)
    return {
        "state": st,
        "month": month,
        "candidates": cands,
        "selected": order,
        "selection": selected["selection"],
        "rows": rows,
        "totals": B.totals_row(rows),
        "carry_n": B.carry_count(rows),
        "counts": {"projects": len(rows), "candidates": len(cands), "carry": B.carry_count(rows)},
        "mat_available": MAIN_MATERIAL_PORT is not None,
        "save_query": state_query(st),
    }


# ============================================================ 写动作

def save_manual_cell(s: Session, *, month: str, warehouse: str, key: str, raw) -> dict:
    """保存**一格**手填值 → `{"ok", "message", "value"}`。

    ⛔ 非法输入（金额非数字 / 负数 · 开工时间不合 `YYYY-MM`）**一律不写库** ⇒ 原值不变（001-07/001-08）。
    ⭐ **只写这一格**：同行其它格保持原样（清空的行仍按带入显示，001-06）。
    """
    require_month(month)
    if key not in B.MANUAL_COLUMN:
        return {"ok": False, "message": B.MSG_NO_COLUMN, "value": None}
    data = selection_data(s, month)
    if warehouse not in data["selected"]:
        return {"ok": False, "message": B.MSG_NO_PROJECT, "value": None}
    parsed = B.parse_manual(raw, B.MANUAL_FMT[key])
    if not parsed["ok"]:
        return {"ok": False, "message": parsed["message"], "value": None}
    materialize_selection(s, month, data)
    R.save_cell(s, ym=month, warehouse=warehouse, key=key, value=parsed["value"])
    return {"ok": True,
            "message": B.MSG_SAVED if parsed["value"] is not None else B.MSG_CLEARED,
            "value": parsed["value"]}


def save_selection(s: Session, selected, *, month: str) -> dict:
    """保存选题（多选）结果 —— 顺序即所设顺序（§5.7.3）。"""
    require_month(month)
    keys = B.normalize_selection(selected, selection_data(s, month)["candidates"])
    R.save_order(s, month, keys)
    return {"ok": True, "selected": keys, "message": f"已保存选题：{len(keys)} 个项目"}


def move_project(s: Session, *, month: str, warehouse: str, direction: str) -> dict:
    """逐项**上移 / 下移**一格 ⇒ 立即落库（§5.7.3）。

    未固定月按当前继承结果移动并固定本月，不回写来源月或旧基线。
    """
    require_month(month)
    cur = selection_data(s, month)["selected"]
    if warehouse not in cur or direction not in ("up", "down"):
        return {"ok": False, "message": "项目或移动方向无效；本次未保存"}
    new = B.move_in_list(cur, warehouse, direction)
    R.save_order(s, month, new)
    moved = "已在首位，未移动" if new == cur else "已移动"
    return {"ok": True, "selected": new, "message": moved}


__all__ = ["parse_state", "state_query", "require_month", "selection_data", "materialize_selection", "build_big_data", "save_manual_cell",
           "save_selection", "move_project", "set_main_material_port", "MAIN_MATERIAL_PORT"]
