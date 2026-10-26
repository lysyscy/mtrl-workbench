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
from pydantic import BaseModel, Field

from app.core.query import flatten_query
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod07_setl import big_domain as B
from app.mod07_setl import big_service as BS
from app.mod07_setl import extract as X
from app.mod07_setl import inventory_extract as I
from app.mod07_setl import service as S
from app.mod07_setl.big_repository import load_manual
from app.mod07_setl.domain import AMOUNT_KEYS, ROWCOUNT_KEY, WAREHOUSE_KEY, default_month
from app.mod07_setl.repository import load_balances, load_rows

router = APIRouter(tags=["mod07"])


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
    st = S.parse_state(flatten_query(request.query_params))
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
def api_extract(year: str = "", status: str = "全部") -> dict:
    """**焊材 / 气体提取**（§5.3.3）→ `{类别: {仓库: {核算月: 金额}}}` ＋ 「结余」录入值。

    ⭐ 口径（关键词 / 白名单 / 排除子串）**唯一出口 = `extract.extract_amounts`** ——
      壳里的「总金额（累计）」与「金额（按所选月份）」两列都从这一份取数派生（`D18`：不在前端重算规则）。
    ⭐ `balances` = 「结余」手工录入值（**唯一取数出口 = `repository.load_balances`**，
      粒度 = 类别 × 仓库 · 不按月）；**未录入的键不出现**（≠ 0 —— 0 是合法录入值）。
    """
    with session_scope() as s:
        amounts = I.load_amounts(s)
        balances = load_balances(s)
        annual = S.annual_grids(s, amounts, S.parse_extract_state({"ext_period":year, "status":status}))
    out: dict[str, dict[str, dict[str, object]]] = {}
    for kind in X.KINDS:
        by_wh = (amounts or {}).get(kind) or {}
        out[kind] = {
            str(wh): {str(ym): _s(v) for ym, v in (months or {}).items()}
            for wh, months in by_wh.items()
        }
    return {
        "amounts": out,
        "annual": {kind:{**grid, "rows":[{**row, "prior":_s(row['prior']), "balance":_s(row['balance']),
                    "cells":[_s(value) for value in row['cells']], "total":_s(row['total'])}
                    for row in grid['rows']], "sum_row":[_s(value) for value in grid['sum_row']]}
                    for kind,grid in annual.items()},
        "annual_totals": S.extract_year_totals(amounts, balances),
        "kinds": list(X.KINDS),
        "balances": {
            str(kind): {str(wh): _s(v) for wh, v in ((balances or {}).get(kind) or {}).items()}
            for kind in X.KINDS
        },
    }


@router.get("/api/m07/big/export")
def api_big_export(period: str = ""):
    return _big_export(period, fix_selection=False)


@router.post("/api/m07/big/export")
def api_big_export_save(period: str):
    return _big_export(period, fix_selection=True)


def _big_export(period: str, *, fix_selection: bool):
    """导出**活动大表成品**（`TAIL-04` 路径① **片 4b**）—— **一份**（全项目一张表 · ⛔ 无 zip）。

    ⚠️ 失败（**一行都没有** · 模板缺失/损坏 · **显示区对账不过**）⇒
       **JSON 200 ＋ `ok:false` ＋ 中文原因**，壳侧据 `content-type` 分流（同另五条导出）。
    ⚠️ 月份**原样带给后端**（`period`；空 = 本表默认年月 = 材料报表类上月，§9.2）—— ⛔ 前端不另算。
    """
    from urllib.parse import quote

    from fastapi.responses import FileResponse, JSONResponse

    from app import export_registry as EXP
    EX = EXP.get("service")

    try:
        if fix_selection:
            month = BS.require_month(period)
            with session_scope() as s:
                data = BS.build_big_data(s, {"month": month})
            path = EX.export_big_data(data, isolated=True)
            with session_scope() as s:
                current = BS.selection_data(s, month)
                if current["selected"] != data["selected"]:
                    raise MustReportError("大表项目或顺序已变化，请重读后重新导出；本次未固定")
                BS.materialize_selection(s, month, current)
        else:
            with session_scope() as s:
                path = EX.export_big(s, str(period or ""))
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name, headers={"X-Export-Filename": quote(path.name)})


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
    - `empty_text` = 大表**空态**那句「为什么是空的」（主人 = `big_domain.empty_text`）——
      ⚠️ 壳的空态行**直接用这一句**，⛔ 壳里不许自己编第二份（那是第二份口径）。
      ⭐ `A5`（2026-09-29 逐页）：这条此前是**死代码**（全仓没人调用），而壳那边 `rows` 为 0 时
      只 `return ''` ⇒ 用户看到的是一张**只剩三级表头的大空表**（且当天正值"空态"这条主线）。
    """
    st = BS.parse_state(flatten_query(request.query_params))
    with session_scope() as s:
        data = BS.build_big_data(s, st)
        manual = load_manual(s)
    return {
        "month": data["month"],
        "selected": list(data["selected"]),
        "selection": data["selection"],
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
        "totals": {k: _s(v) for k, v in data["totals"].items()},
        "mat_available": bool(data["mat_available"]),
        # ⭐ `A5`（2026-09-29）：大表空态文案随包给出（主人 = `big_domain.empty_text`）。
        "empty_text": B.empty_text(data["month"]),
    }


# ============================================================ 写


class CellRequest(BaseModel):
    """手填一格（`month` / `warehouse` / 列 `key` / 原始输入 `raw`）。"""

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    warehouse: str = ""
    key: str = ""
    raw: object | None = None


class SelectionRequest(BaseModel):
    """选题（顺序 = 所设顺序）。"""

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    selected: list[str] = []


class MoveRequest(BaseModel):
    """逐项上移 / 下移一格（`direction` ∈ `up` / `down`）。"""

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    warehouse: str = ""
    direction: str = ""


class FetchRequest(BaseModel):
    """按月抓取 —— ⚠️ `confirm` 缺省为假（**防"直接打进来"的静默抓取，会顶号**）。"""

    month: str = ""
    confirm: bool = False


@router.post("/api/m07/big/cell")
def api_big_cell(req: CellRequest) -> dict:
    """保存**一格**手填值 —— 校验（金额非负 / 开工时间 `YYYY-MM`）**唯一出口 = `big_service.save_manual_cell`**。

    失败**不写库、原值不变**，回执带原因（`ok=False` ＋ 中文 `message`）⇒ 壳里如实报出，不静默。
    """
    with session_scope() as s:
        return BS.save_manual_cell(
            s, month=req.month, warehouse=req.warehouse, key=req.key,
            raw=req.raw,
        )


class BalanceRequest(BaseModel):
    """「结余」一格（`kind` / `warehouse` / 原始输入 `raw`）。

    ⚠️ `raw` 一律**原样**传（**不预先转数字**）：格式判定是域内核的职责
       （空 ⇒ 清空；非数字 / 负数 ⇒ 拒）；前端先转会把非法输入变成 `NaN` 而**看不出错**。
    """

    kind: str = ""
    warehouse: str = ""
    raw: object | None = None


@router.post("/api/m07/extract/balance")
def api_extract_balance(req: BalanceRequest) -> dict:
    """保存提取页**「结余」一格**（历史结余 · 手工录入 · 2026-09-18 用户裁定）。

    - 判定与落库**唯一出口 = `service.save_balance_cell`**（其下游 = `extract.parse_balance`）；
    - 失败**不写库、原值不变**，回执带中文原因（`ok=False` ＋ `message`）⇒ 壳里如实报出，不静默；
    - ⚠️ 出参 `value`：**已录入给数字串**、**清空给 `None`** —— 两者**语义不同**，壳侧要分开处理。
    """
    with session_scope() as s:
        return S.save_balance_cell(
            s, kind=req.kind, warehouse=req.warehouse, raw=req.raw
        )


@router.post("/api/m07/big/selection")
def api_big_selection(req: SelectionRequest) -> dict:
    """保存**选题**（多选）—— 顺序即所设顺序；`normalize_selection` 在服务层（唯一出口）。"""
    with session_scope() as s:
        return BS.save_selection(s, req.selected, month=req.month)


@router.post("/api/m07/big/move")
def api_big_move(req: MoveRequest) -> dict:
    """逐项**上移 / 下移**一格 ⇒ 立即落库（未选题时先实体化一次，见 `big_service.move_project`）。"""
    with session_scope() as s:
        return BS.move_project(
            s, month=req.month, warehouse=req.warehouse, direction=req.direction
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


@router.get("/api/m07/settlement/export")
def api_export_settlement(request: Request):
    """导出收发结存**成品 zip**（分仓库 xlsx ＋ 总表）—— 浏览器直接下载（`TAIL-04`）。

    口径 = **模板法**：以「用户手作成品 xlsx」为基底做 `zip` 字节替换
    （`docs/reference/template-export.md`）；金额按 2 位小数对平、**容差 0**。

    ⚠️ 三种失败（模板缺失/损坏 · 该月没有明细 · **缓存级对账不过**）⇒ **不产出文件**，
       改成 **JSON 200 ＋ `ok:false` ＋ 中文原因** ——
       壳侧据 `content-type` 分流：`application/json` ⇒ 弹原因；否则当文件下载。
       （⛔ 不回 4xx：那样用户只看到一句 `HTTP 400`，而"该月没有数据"这种话必须给人看。）
    """
    from fastapi.responses import FileResponse, JSONResponse
    from urllib.parse import quote

    from app import export_registry as EXP
    EX = EXP.get("service")

    period = str(request.query_params.get("period") or "").strip() or default_month()
    try:
        with session_scope() as s:
            path = EX.export_settlement(s, period)
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    # ⚠️ 文件名**由后端带出**（`X-Export-Filename`，UTF-8 percent-encoded）——
    #    ⛔ 不让壳自己拼：命名规则一旦两处各写一份，改一处就会静默走形。
    return FileResponse(
        path,
        media_type="application/zip",
        filename=path.name,
        headers={"X-Export-Filename": quote(path.name)},
    )


@router.get("/api/m07/extract/export")
def api_export_extract(request: Request):
    """导出**焊材 / 气体提取**成品 xlsx（`TAIL-04` **路径① = 模板填充**）—— 浏览器直接下载。

    口径 = **模板填充**：以交付面 `docs/requirements/report-templates.md` 登记的 `模板-焊材气体.xlsx` 为基底，
    认标记文字 `DATA_START` 定位数据区、**尾块随行数派生**（《说明书》§7.1）。

    ⚠️ 三个筛选参数与页面**同名同义**（⛔ 不在前端另筛一遍）：
      `status` = 项目状态（缺省「在建」）；`period` = 金额月份（**缺省上月**；**显式传空串 = 全部**）。
    ⚠️ 失败（模板缺失/损坏 · 拿不到报告月 · **显示区对账不过**）⇒ **JSON 200 ＋ `ok:false` ＋ 中文原因**，
       壳侧据 `content-type` 分流（同另两条导出）。
    """
    from fastapi.responses import FileResponse, JSONResponse
    from urllib.parse import quote

    from app import export_registry as EXP
    EX = EXP.get("service")

    q = flatten_query(request.query_params)
    period = q.get("period")
    if isinstance(period, list):
        period = period[0] if period else ""
    try:
        with session_scope() as s:
            path = EX.export_extract(s, period, str(q.get("status") or ""))
    except MustReportError as exc:
        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
        headers={"X-Export-Filename": quote(path.name)},
    )


__all__ = ["router", "MustReportError"]
