"""`MOD-09` 的 **JSON API** —— 前端壳（= 原型直接接数据，`D18`）。

⚠️ 本层**不写任何判定**：组装调 `service.build_page_data`，四个写动作调 `service.act_*`
   （⚠️ 2026-09-19 `TAIL-27` · `§19` 批 2：旧 PRG 端点 `/m09/add` · `/m09/cell` **已随旧页删除**（`D18`）
   ⇒ 本 API 就是**唯一出口**）—— 同 `mod07_setl/api.py` 的做法。

⚠️ 出参 = **语义形状**；转成原型演示形状（`AWF[核算年月][项目键] = [[项名, 金额], …]`）
   是**壳适配层的职责**（同 `m03` / `m08` / `m07`：后端出语义、前端 `adapt*` 转形）。

⚠️ 金额**出字符串**（`numeric(18,2)` 精度保护）⇒ 壳适配层**必须**过 `N0()` 转数字：
   原型切片里写着 `r[1].toFixed(2)` —— 拿到字符串会**直接 TypeError 整页崩**（不报错地坏）。

⚠️ 「操作」列（`domain.PAGE_ONLY_KEYS` 的 `ops`）是**页面专用 HTML 占位** ⇒ `/api/*` 一律剔除。

⚠️ 写动作**恒 HTTP 200**，成败看 `ok` 标志（同 `mod03` / `mod07` 的约定）——
   「金额不合法」是 §5.5 规定的**可预期的拒绝**（要把那句话原样给用户看），
   不该被壳当成"请求失败"（那样只会看到一句 `HTTP 400`，原因丢了）。

⚠️ **本页不设单独的导出**（§5.5 / `domain.EXPORT_BOUNDARY`）⇒ 没有导出端点。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.query import flatten_query
from app.core.db import session_scope
from app.mod09_fee import domain as D
from app.mod09_fee import service as SV

router = APIRouter(tags=["mod09"])


# ============================================================ 读


def _s(x) -> object:
    """金额 → **字符串**（`numeric(18,2)` 精度保护）；`None` / 空 ⇒ `None`（不可得 ≠ 0）。"""
    return None if x is None or x == "" else str(x)


def _row(r: dict) -> dict:
    """一行 → JSON：**剔除页面专用列**（`ops`，`D.PAGE_ONLY_KEYS`），金额转字符串。"""
    out: dict = {}
    for k, v in (r or {}).items():
        if k in D.PAGE_ONLY_KEYS:
            continue
        out[k] = _s(v) if k == "amount" else v
    return out


def _payload(s, *, ym: str, pj: str) -> dict:
    """页面数据 → JSON（⛔ 组装与判定一律在 `service`，这里只做形状与转字符串）。"""
    data = SV.build_page_data(s, SV.parse_state({"ym": ym, "pj": pj}))
    return {
        "ym": data["ym"],
        "project": data["project"],
        "project_display": data["project_display"],
        # 候选 = **唯一出口** `mod01_projects.domain.build_candidates`（键 = 仓库名 · 显示 = 展示名）
        # ⇒ 与写路径 `repository.project_by_key` **同源**：选得到的就写得了（⛔ 别让前端自造候选）。
        "projects": [
            {
                "key": c.key,
                "display": c.display,
                "archived": bool(c.archived),
                "placeholder": bool(c.placeholder),
            }
            for c in (data["projects"] or [])
        ],
        "auto": _row(data["auto"]),
        "manuals": [_row(r) for r in (data["manuals"] or [])],
        "total": _s(data["total"]),
        "count": int(data["count"] or 0),
        "can_edit": bool(data["can_edit"]),
        "columns": [dict(c) for c in D.AWF_COLUMNS],
        "auto_name": D.AUTO_NAME,
    }


@router.get("/api/m09/fee")
def api_fee(request: Request) -> dict:
    """特殊费用月报表（**该核算年月 ＋ 该项目那一份**）。

    ⚠️ **自动项取数用「核算年月」**（`inv_detail.ym`）而**不是**单据日期前缀 ——
       原型演示数据没有核算月列、拿单据日期前缀代替（`domain` 顶部已注明口径）。
       ⇒ 接线后这一处与口径一致，**且是真数据**（原先壳里按单据日期算，属静默偏差）。
    """
    with session_scope() as s:
        p = flatten_query(request.query_params)
        return _payload(s, ym=str(p.get("ym") or ""), pj=str(p.get("pj") or ""))


# ============================================================ 写（四个动作 · 全部只落在「当前那份」上）


class ScopeRequest(BaseModel):
    """(核算年月, 项目) —— 写动作的作用域（§5.5：每个动作先解析出那一份，再按该份内下标取行）。"""

    ym: str = ""
    project: str = ""


class CellRequest(ScopeRequest):
    """该份内第 `index` 行的项名 / 金额。

    ⚠️ `value` 用 `Any`：壳送来的可能是字符串（用户敲的）也可能是数字（JSON 里没引号）
       ⇒ 判定出口 `domain.amount_problem` 本来就吃任意输入，⛔ 别在这里先转一道（那是第二份口径）。
    """

    index: Any = 0
    value: Any = ""


def _flash(f: dict) -> dict:
    """`service` 的回执 → JSON：`kind` 原样带上，另给壳一个好判的 `ok`。"""
    return {"ok": f.get("kind") == "ok", "kind": f.get("kind") or "err", "message": f.get("message") or ""}


@router.post("/api/m09/fee/add")
def api_add(req: ScopeRequest) -> dict:
    """「＋ 增加手填项」：在该 (月, 项目) 那一份末尾追加一行（初值 = 名称可改、金额 0）。"""
    with session_scope() as s:
        return _flash(SV.act_add(s, ym=req.ym, project_key=req.project))


@router.post("/api/m09/fee/name")
def api_rename(req: CellRequest) -> dict:
    """改项名（§5.5：手填项**项名也可改**；⛔ 不强制非空）。"""
    with session_scope() as s:
        return _flash(
            SV.act_rename(s, ym=req.ym, project_key=req.project, index=req.index, value=str(req.value or ""))
        )


@router.post("/api/m09/fee/amount")
def api_amount(req: CellRequest) -> dict:
    """改金额：**非法输入必须被拒绝且原值不变**（§5.5 只拦"非数字"，允许 0 与负数）。"""
    with session_scope() as s:
        return _flash(
            SV.act_set_amount(s, ym=req.ym, project_key=req.project, index=req.index, raw=req.value)
        )


@router.post("/api/m09/fee/delete")
def api_delete(req: CellRequest) -> dict:
    """删除手填项 —— 回执里**带「重算后的合计」**（设计规则 `R9`）。"""
    with session_scope() as s:
        return _flash(SV.act_delete(s, ym=req.ym, project_key=req.project, index=req.index))


class BatchMonth(BaseModel):
    """批量表里的**一行** = 一个核算月 ＋ 该行各列的原始输入（`{项名: 用户敲的串}`）。"""

    ym: str = ""
    values: dict[str, Any] = {}


class BatchRequest(BaseModel):
    """⭐ `TAIL-156` 月度批量录入：一次提交「N 个核算月 × M 个项」。

    ⚠️ `values` 用 `Any`：壳送来的是**用户敲的原样字符串**（可能带空格、可能不是数字）
       ⇒ 判定出口 `domain.amount_problem` 本来就吃任意输入，⛔ 别在这里先转一道（那是第二份口径）。
    """

    project: str = ""
    items: list[str] = []
    months: list[BatchMonth] = []


@router.post("/api/m09/fee/batch")
def api_batch(req: BatchRequest) -> dict:
    """⭐ 一次写「N 个核算月 × M 个项」—— **按 (月, 项目, 项名) 幂等**；**空格外整格跳过**；
    **一格非法 ⇒ 整批不写**（语义与回执见 `service.act_batch`）。"""
    with session_scope() as s:
        return _flash(SV.act_batch(
            s,
            project_key=req.project,
            items=list(req.items or []),
            months=[{"ym": m.ym, "values": dict(m.values or {})} for m in (req.months or [])],
        ))


__all__ = ["router"]
