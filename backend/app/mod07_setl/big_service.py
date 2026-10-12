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

def build_big_data(s: Session, state: dict | None = None) -> dict:
    """页面 / 导出所需的一切（**同一份行装配** ⇒ 两处同序同值，§5.7.3）。"""
    st = dict(state or parse_state())
    month = st["month"]
    cands = B.candidates(P1S.all_projects(s))
    by_key = {c["warehouse"]: c for c in cands}
    order = B.resolve_order(R.load_order(s), cands, chosen=R.has_choice(s))
    projects = [by_key[w] for w in order if w in by_key]
    amounts = _amounts(s, [p["warehouse"] for p in projects], month)
    rows = B.assemble_rows(projects, amounts, R.load_manual(s), month=month)
    return {
        "state": st,
        "month": month,
        "candidates": cands,
        "selected": order,
        "rows": rows,
        "totals": B.totals_row(rows),
        "carry_n": B.carry_count(rows),
        "counts": {"projects": len(rows), "candidates": len(cands), "carry": B.carry_count(rows)},
        "mat_available": MAIN_MATERIAL_PORT is not None,
        "save_query": state_query(st),
    }


# ============================================================ 写动作

def save_manual_cell(s: Session, *, month: str, warehouse: str, key: str, raw,
                     cands=None) -> dict:
    """保存**一格**手填值 → `{"ok", "message", "value"}`。

    ⛔ 非法输入（金额非数字 / 负数 · 开工时间不合 `YYYY-MM`）**一律不写库** ⇒ 原值不变（001-07/001-08）。
    ⭐ **只写这一格**：同行其它格保持原样（清空的行仍按带入显示，001-06）。
    """
    if key not in B.MANUAL_COLUMN:
        return {"ok": False, "message": B.MSG_NO_COLUMN, "value": None}
    keys = {c["warehouse"] for c in (cands or ())} if cands is not None else None
    if keys is not None and warehouse not in keys:
        return {"ok": False, "message": B.MSG_NO_PROJECT, "value": None}
    parsed = B.parse_manual(raw, B.MANUAL_FMT[key])
    if not parsed["ok"]:
        return {"ok": False, "message": parsed["message"], "value": None}
    R.save_cell(s, ym=month, warehouse=warehouse, key=key, value=parsed["value"])
    return {"ok": True,
            "message": B.MSG_SAVED if parsed["value"] is not None else B.MSG_CLEARED,
            "value": parsed["value"]}


def save_selection(s: Session, selected, *, cands=None) -> dict:
    """保存选题（多选）结果 —— 顺序即所设顺序（§5.7.3）。"""
    keys = B.normalize_selection(selected, cands if cands is not None else [])
    R.save_order(s, keys)
    return {"ok": True, "selected": keys, "message": f"已保存选题：{len(keys)} 个项目"}


def move_project(s: Session, *, warehouse: str, direction: str, cands=None) -> dict:
    """逐项**上移 / 下移**一格 ⇒ 立即落库（§5.7.3）。

    ⚠️ **从未选题**时数据库里没有顺序行 ⇒ 先按「默认 = 全部候选」**实体化**一次，再移动
       （否则动的是幽灵顺序，下次打开又回默认）。
    """
    cands = cands if cands is not None else []
    cur = B.resolve_order(R.load_order(s), cands, chosen=R.has_choice(s))
    new = B.move_in_list(cur, warehouse, direction)
    R.save_order(s, new)
    moved = "已在首位，未移动" if new == cur else "已移动"
    return {"ok": True, "selected": new, "message": moved}


__all__ = ["parse_state", "state_query", "build_big_data", "save_manual_cell",
           "save_selection", "move_project", "set_main_material_port", "MAIN_MATERIAL_PORT"]
