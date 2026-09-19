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
from pydantic import BaseModel, Field

from app.core.db import session_scope
from app.mod11_jc import domain as D
from app.mod11_jc import fetch_service as FS
from app.mod11_jc import repository as R
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


# ============================================================ 写端点（`M5-4`）
# ⚠️ 本层**不写判定**：编排在 `service.act_*`（那里才调 `domain` 的校验 / 归一出口）。
# ⚠️ 回执形状与读端点不同：写动作回 `{"ok","kind","message",...}`（`data` 省略即可），
#    `ok=False` 时 `kind="err"` ⇒ 壳据 `ok` 决定 toast 的语气（⛔ 别只看 message 文案）。


class AddIn(BaseModel):
    """手工新增合同入参（判据 `001-13`）。

    ⚠️ 收的是 **`project_key`（= 仓库名）**，⛔ 不是 `project_id` —— 本仓前后端之间「项目」一律以
    **仓库名**为键（§2.7.4）；`/api/m11/list` 的 `projects` 也只给 `key`/`display`。翻译成 id 在服务端点内做。
    """

    project_key: str = ""
    contract_date: str = ""
    material_name: str = ""
    supplier: str = ""
    contract_amt: str = "0"
    trade_co: str | None = None
    trade_contract_amt: str | None = None
    tag: str = ""                     # 留空 ⇒ 服务层按「手工新增 = 纳入台账」填（判据 `001-07`）
    method: str = ""
    remark: str = ""


class FetchIn(BaseModel):
    """抓取入参 —— ⚠️ `confirm` **必须为真**（防静默抓取，`D9`；同 `m08` 的口径）。"""

    confirm: bool = False


class TagIn(BaseModel):
    """三态标记入参：给 `id` = 单条；给 `ids` = **批量**（判据 `001-03`）。"""

    id: int | None = None
    ids: list[int] = Field(default_factory=list)
    tag: str = ""


class FieldsIn(BaseModel):
    """主表可改列入参（判据 `001-12`）—— 白名单外一律忽略（见 `repository.EDITABLE_COLS`）。"""

    id: int
    fields: dict = Field(default_factory=dict)


class SubRowIn(BaseModel):
    """子表增删入参（发票 / 付款**同款**）—— 增行用 `id` ＋ `date`/`amount`，删行用 `row_id`。"""

    id: int = 0                       # 合同 id（增行用）
    row_id: int | None = None         # 子表行 id（删行用）
    kind: str = "supplier"            # `supplier` | `trade`（仅发票用）
    date: str = ""
    amount: str = "0"
    source: str = "manual"            # `manual` | `notice`（仅付款用）
    notice_id: int | None = None


@router.post("/api/m11/fetch")
def api_fetch(payload: FetchIn) -> dict:
    """抓采购合同（`API-04`）⇒ 回执（含**匹配预览**：匹配上 / 匹配不上的项目分布）。

    ⭐ 编排在 `fetch_service.run_fetch`：抓合同 → **先同步常用项目** → 再匹配 → 落库。
    ⚠️ 抓取**会顶号**（`D9`：登录 i8 会踢掉该账号其它在线会话）⇒ ⛔ 缺 `confirm` 一律拒（防静默抓取）。
    """
    if not payload.confirm:
        return {"ok": False, "kind": "err",
                "message": "抓取前必须二次确认（这一步会登录 i8，可能顶掉该账号的其它会话）"}
    with session_scope() as s:
        return FS.run_fetch(s, confirmed=True)


@router.post("/api/m11/add")
def api_add(payload: AddIn) -> dict:
    """手工新增合同 ⇒ **真的建档**（判据 `001-13`）；三态默认「纳入台账」（判据 `001-07`）。"""
    with session_scope() as s:
        pid = R.project_id_by_key(s, payload.project_key)
        if not pid:
            return {"ok": False, "kind": "err",
                    "message": f"找不到项目（仓库名）：{payload.project_key or '（空）'}"}
        return SV.act_add_contract(s, **payload.model_dump(exclude={"project_key"}))


@router.post("/api/m11/tag")
def api_tag(payload: TagIn) -> dict:
    """三态标记（判据 `001-03` / `001-05`）：给 `ids` ⇒ 批量（返回 `affected_ids` 供壳清空勾选）。"""
    with session_scope() as s:
        if payload.ids:
            return SV.act_batch_tag(s, contract_ids=payload.ids, tag=payload.tag)
        if payload.id is None:
            return {"ok": False, "kind": "err", "message": "要给 id（单条）或 ids（批量）"}
        return SV.act_set_tag(s, contract_id=int(payload.id), tag=payload.tag)


@router.post("/api/m11/fields")
def api_fields(payload: FieldsIn) -> dict:
    """主表可改列（备注 / 付款方式 / 收发登记三列 / 金额）—— 判据 `001-12`。"""
    with session_scope() as s:
        return SV.act_update_contract(s, contract_id=int(payload.id), **(payload.fields or {}))


@router.post("/api/m11/invoice/add")
def api_inv_add(payload: SubRowIn) -> dict:
    """发票子表增行 —— **日期必填**（判据 `001-05`，校验在域层）。"""
    with session_scope() as s:
        return SV.act_add_invoice(s, contract_id=int(payload.id), kind=payload.kind,
                                  date=payload.date, amount=payload.amount)


@router.post("/api/m11/invoice/del")
def api_inv_del(payload: SubRowIn) -> dict:
    """发票子表删行。"""
    with session_scope() as s:
        return SV.act_del_invoice(s, invoice_id=int(payload.row_id or 0))


@router.post("/api/m11/payment/add")
def api_pay_add(payload: SubRowIn) -> dict:
    """付款子表增行 —— 引用付款域时先过**全库去重**（§6.6.2）。"""
    with session_scope() as s:
        return SV.act_add_payment(s, contract_id=int(payload.id), date=payload.date,
                                  amount=payload.amount, source=payload.source,
                                  notice_id=payload.notice_id)


@router.post("/api/m11/payment/del")
def api_pay_del(payload: SubRowIn) -> dict:
    """付款子表删行。"""
    with session_scope() as s:
        return SV.act_del_payment(s, payment_id=int(payload.row_id or 0))


__all__ = ["router"]
