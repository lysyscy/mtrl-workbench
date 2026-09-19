"""`MOD-11` 的 **JSON API** —— 前端壳（= 原型直接接数据，`D18`）。

⚠️ 本层**不写任何判定**：读走 `service.build_list` / `build_detail`（组装与派生金额都在那边）。
⚠️ 出参 = **语义形状**；转成原型演示形状是**壳适配层**的职责（同 `m03` / `m07` / `m08` / `m09`）。
⚠️ 金额**出字符串**（`numeric(18,2)` 精度保护）⇒ 壳适配层**必须**过 `N0()` 转数字
   （原型切片里写着 `M(...)` / `toFixed` 那一族，拿到字符串会**直接 TypeError 整页崩**）。
⚠️ 「操作」列（`domain.PAGE_ONLY_KEYS` 的 `ops`）是**页面专用 HTML 占位** ⇒ `/api/*` 一律剔除。
⚠️ 筛选参数只认**语义**（三态 / 存档 / 供应商 / 项目键 = **仓库名**）；⛔ 不接受"按显示名查"。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.core.db import session_scope
from app.mod11_jc import domain as D
from app.mod11_jc import service as SV

router = APIRouter(tags=["mod11"])


def query_params(request: Request) -> dict:
    """查询参数 → 扁平 dict（同名单值给 `str`、多值给 `list`）—— 同 `mod09_fee/api.py` 的口径。"""
    out: dict = {}
    for key in request.query_params.keys():
        vals = request.query_params.getlist(key)
        out[key] = vals if len(vals) > 1 else (vals[0] if vals else "")
    return out


def _s(x) -> object:
    """金额 → **字符串**（精度保护）；`None` / 空 ⇒ `None`（"不可得" ≠ 0）。"""
    return None if x is None or x == "" else str(x)


def _row(r: dict) -> dict:
    """一行 → JSON：**剔除页面专用列**，金额列转字符串。"""
    out: dict = {}
    for k, v in (r or {}).items():
        if k in D.PAGE_ONLY_KEYS:
            continue
        out[k] = _s(v) if k in D.SUM_KEYS or k in D.DERIVED_MONEY_KEYS else v
    return out


def _tags(raw) -> list[str]:
    """三态筛选参数（可多值）⇒ 合法值列表（⛔ 认不出的丢掉，⛔ 不悄悄变成"全选"）。"""
    vals = raw if isinstance(raw, list) else ([raw] if raw else [])
    return [str(v).strip() for v in vals if str(v).strip() in D.TAGS]


@router.get("/api/m11/list")
def api_list(request: Request) -> dict:
    """集采台账主表（可按 三态 / 存档 / 供应商 / 项目 筛选）—— 判据 `ACC-JC-UI-001/001-02`。

    ⚠️ **不给任何筛选 = 全量**（判据「复位后回到全量」）；`project` 参数 = **仓库名**（§2.7.4）。
    """
    with session_scope() as s:
        p = query_params(request)
        data = SV.build_list(
            s,
            tags=_tags(p.get("tag")),
            arch=str(p.get("arch") or ""),
            supplier=str(p.get("supplier") or ""),
            project_key=str(p.get("project") or ""),
        )
    return {
        "rows": [_row(r) for r in data["rows"]],
        "count": int(data["count"]),
        "totals": {k: _s(v) for k, v in (data["totals"] or {}).items()},
        "columns": [dict(c) for c in data["columns"]],
        "projects": list(data["projects"] or []),
        # 三态取值域（壳的筛选下拉与批量标记按钮都用它 ⇒ ⛔ 别在壳里另抄一份）
        "tags": list(D.TAGS),
    }


@router.get("/api/m11/detail")
def api_detail(id: int) -> dict:
    """单个合同的明细（两张发票子表 ＋ 付款子表 ＋ 派生金额）—— 子表弹窗的数据源。"""
    with session_scope() as s:
        d = SV.build_detail(s, int(id))
    if d is None:
        return {"ok": False, "kind": "err", "message": f"找不到合同 {id}", "data": None}
    for key in ("supplier_invoices", "trade_invoices", "payments"):
        d[key] = [
            {**{k: (_s(v) if k == "amount" else v) for k, v in r.items()}}
            for r in (d.get(key) or [])
        ]
    d = {k: (v if k not in D.DERIVED_MONEY_KEYS and k not in D.SUM_KEYS else _s(v)) for k, v in d.items()}
    return {"ok": True, "kind": "ok", "message": "", "data": d}


__all__ = ["router"]
