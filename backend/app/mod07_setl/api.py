"""`MOD-07` 的 **JSON API** —— 前端壳（= 原型直接接数据，`D18`）。

⚠️ 本层**不写任何判定**：取数 / 对平 / 提取 / 大表装配 / 手填校验一律调**既有出口**
   （`service` · `big_service` · `fetch_service`，它们的下游是 `domain` / `extract` / `big_domain`）
   —— 与 `mod08_inv/router.py` 的 API 段同款。

⚠️ 出参 = **语义形状**；转成原型演示形状（`WHM` / `EXTM` / `BIGVAL`）是**壳适配层的职责**
   （同 `m03` / `m08`：后端出语义、前端 `adapt*` 转形）。

⚠️ 金额**出字符串**（`numeric(18,2)` 精度保护）⇒ 壳适配层**必须**过 `N0()` 转数字：
   不然壳里的求和会变成**字符串拼接**（`'100.00' + '1.00'`），而且**不报错**。

⚠️ `V.m07` 切片**一行不改** —— 原型的筛选 / 排序 / 合计 / 勾选逻辑由 `ui_parity` 的 `U1` 看管。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.identity import current_operator
from app.mod07_setl import big_domain as B
from app.mod07_setl import big_service as BS
from app.mod07_setl import extract as X
from app.mod07_setl import service as S
from app.mod07_setl.big_repository import load_manual
from app.mod07_setl.domain import AMOUNT_KEYS, ROWCOUNT_KEY, WAREHOUSE_KEY
from app.mod07_setl.repository import load_rows

router = APIRouter(tags=["mod07"])


def query_params(request: Request) -> dict:
    """查询参数 → 扁平 dict（同名单值给 `str`、多值给 `list`；`parse_state` 两者都吃）。"""
    out: dict = {}
    for key in request.query_params.keys():
        vals = request.query_params.getlist(key)
        out[key] = vals if len(vals) > 1 else (vals[0] if vals else "")
    return out


def _s(x) -> object:
    """金额 → **字符串**（`numeric(18,2)` 精度保护）；`None` / 空 ⇒ `None`（不可得 ≠ 0）。"""
    return None if x is None or x == "" else str(x)


def _i(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def _big_row(r: dict) -> dict:
    """大表一行 → JSON（金额一律转字符串，含手填值 / 自动列 / 派生列）。"""
    return {
        "seq": r.get("seq"),
        "warehouse": str(r.get("warehouse") or ""),
        "display": str(r.get("display") or ""),
        "carry_n": _i(r.get("carry_n")),
        "manual": {
            k: {"value": _s(c.get("value")), "from": str(c.get("from") or "")}
            for k, c in (r.get("manual") or {}).items()
        },
        "auto": {k: _s(v) for k, v in (r.get("auto") or {}).items()},
        "derived": {k: _s(v) for k, v in (r.get("derived") or {}).items()},
    }


# ============================================================ 读


@router.get("/api/m07/settlement")
def api_settlement(request: Request) -> dict:
    """**收发结存月报**（`API-02`）—— 按月取数 ＋ 按仓汇总（**唯一取数出口 = `domain.warehouse_rows`**）。

    - ⭐ **全量**返回、筛选由前端做（与 `/api/m03/notice-list` 同款）：原型的
      筛选 / 排序 / 合计逻辑**一行不改**（`D18`）。
    - `balance_ok` = 逐仓对平判定的汇总（口径 = §9.1 **容差 0**，判定在域内核，前端只显示）。
    """
    st = S.parse_state(query_params(request))
    with session_scope() as s:
        data = S.build_page_data(s, st)
    rows = [
        {
            "id": str(r.get(WAREHOUSE_KEY) or ""),
            "name": str(r.get(WAREHOUSE_KEY) or ""),
            "rows": _i(r.get(ROWCOUNT_KEY)),
            **{k: _s(r.get(k)) for k in AMOUNT_KEYS},
        }
        for r in data["rows"]
    ]
    return {
        "ym": data["ym"],
        "rows": rows,
        "counts": {k: _i(v) for k, v in (data["counts"] or {}).items()},
        "balance_ok": bool(data["balance_ok"]),
    }


@router.get("/api/m07/extract")
def api_extract() -> dict:
    """**焊材 / 气体提取**（§5.3.3）→ `{类别: {仓库: {核算月: 金额}}}`。

    ⭐ 口径（关键词 / 白名单 / 排除子串）**唯一出口 = `extract.extract_amounts`** ——
      壳里的「总金额（累计）」与「金额（按所选月份）」两列都从这一份取数派生（`D18`：不在前端重算规则）。
    """
    with session_scope() as s:
        amounts = X.extract_amounts(load_rows(s))
    out: dict[str, dict[str, dict[str, object]]] = {}
    for kind in X.KINDS:
        by_wh = (amounts or {}).get(kind) or {}
        out[kind] = {
            str(wh): {str(ym): _s(v) for ym, v in (months or {}).items()}
            for wh, months in by_wh.items()
        }
    return {"amounts": out, "kinds": list(X.KINDS)}


@router.get("/api/m07/big")
def api_big(request: Request) -> dict:
    """**经济活动分析大表**（§5.7）—— 行装配 ＋ 手填值 ＋ 候选 ＋ 选题顺序。

    - `selected` = **大表自己的顺序**（未选题时 = 全部候选，与原型同款）。
    - `manual` = `{核算月: {仓库: {列 key: 值}}}` —— ⚠️ **全量**（不只当月）：
      壳的「上次值带入」（`OPEN-05`）要**向更早月份取最近一次录入值**，只给当月就带不进来。
    - `manual_keys` / `manual_fmts` = 手填 6 列的**顺序与格式**（**唯一主人 = `big_domain.BIG_MANUAL`**）——
      壳适配层据它把对象转成与原型同序的数组（并据此判断哪几列是金额、要转数字），
      ⛔ 前端**不硬编码**列序或列型。
    - `mat_available` = 「主材累计（含税）」的取数口**是否已接入**（集采台账属 `M5`）——
      `False` 时该列给 `None`（**不可得，绝不写 0**，`TAIL-25`）。
    """
    st = BS.parse_state(query_params(request))
    with session_scope() as s:
        data = BS.build_big_data(s, st)
        manual = load_manual(s)
    return {
        "month": data["month"],
        "selected": list(data["selected"]),
        "candidates": [
            {"warehouse": str(c.get("warehouse") or ""), "display": str(c.get("display") or "")}
            for c in (data["candidates"] or [])
        ],
        "manual": {
            str(ym): {str(wh): {k: _s(v) for k, v in (keys or {}).items()}
                      for wh, keys in (by_wh or {}).items()}
            for ym, by_wh in (manual or {}).items()
        },
        "manual_keys": list(B.BIG_MANUAL_KEYS),
        "manual_fmts": [B.MANUAL_FMT[k] for k in B.BIG_MANUAL_KEYS],
        "rows": [_big_row(r) for r in (data["rows"] or [])],
        "mat_available": bool(data["mat_available"]),
    }


# ============================================================ 写


class CellRequest(BaseModel):
    """手填一格（`month` / `warehouse` / 列 `key` / 原始输入 `raw`）。"""

    month: str = ""
    warehouse: str = ""
    key: str = ""
    raw: object | None = None


class SelectionRequest(BaseModel):
    """选题（顺序 = 所设顺序）。"""

    selected: list[str] = []


class MoveRequest(BaseModel):
    """逐项上移 / 下移一格（`direction` ∈ `up` / `down`）。"""

    warehouse: str = ""
    direction: str = ""


class FetchRequest(BaseModel):
    """按月抓取 —— ⚠️ `confirm` 缺省为假（**防"直接打进来"的静默抓取，会顶号**）。"""

    month: str = ""
    confirm: bool = False


def _cands(s) -> list[dict]:
    """大表候选（在建 · 非壳）—— 唯一出口 = `big_domain.candidates`。"""
    from app.mod01_projects.repository import all_projects

    return B.candidates(all_projects(s))


@router.post("/api/m07/big/cell")
def api_big_cell(req: CellRequest) -> dict:
    """保存**一格**手填值 —— 校验（金额非负 / 开工时间 `YYYY-MM`）**唯一出口 = `big_service.save_manual_cell`**。

    失败**不写库、原值不变**，回执带原因（`ok=False` ＋ 中文 `message`）⇒ 壳里如实报出，不静默。
    """
    with session_scope() as s:
        return BS.save_manual_cell(
            s, month=req.month, warehouse=req.warehouse, key=req.key,
            raw=req.raw, cands=_cands(s),
        )


@router.post("/api/m07/big/selection")
def api_big_selection(req: SelectionRequest) -> dict:
    """保存**选题**（多选）—— 顺序即所设顺序；`normalize_selection` 在服务层（唯一出口）。"""
    with session_scope() as s:
        return BS.save_selection(s, req.selected, cands=_cands(s))


@router.post("/api/m07/big/move")
def api_big_move(req: MoveRequest) -> dict:
    """逐项**上移 / 下移**一格 ⇒ 立即落库（未选题时先实体化一次，见 `big_service.move_project`）。"""
    with session_scope() as s:
        return BS.move_project(
            s, warehouse=req.warehouse, direction=req.direction, cands=_cands(s)
        )


@router.post("/api/m07/fetch")
def api_fetch(req: FetchRequest) -> dict:
    """**按月抓取**收发结存（`API-02`）—— 人工触发。

    ⚠️ **会登录 i8 并强踢在线用户**（D9）：`confirm` 必须为真（= 用户已在壳的弹窗里确认过）。
    ⚠️ 失败**降级为手动 Excel 导入并显式说明**（§3.6），**绝不自动重试登录**（D9）。
    """
    from app.mod07_setl import fetch_service as FS

    with session_scope() as s:
        return FS.run_fetch(
            s, year_month=req.month, confirmed=req.confirm, operator=current_operator()
        )


__all__ = ["router", "MustReportError"]
