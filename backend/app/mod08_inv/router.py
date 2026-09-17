"""`MOD-08` 路由：明细总表页（`/m08`）＋ 调整单（`/m08/adjust/{id}`）＋ 抓取弹窗（`/m08/fetch-dialog`）。

⚠️ 写操作一律 **PRG**（POST → 303 → GET），与全站一致；校验失败**不写库**、原地回显。
⚠️ 调整单的判据走 `domain.adjustment_problem`（唯一出口），路由**不另写判定**。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.core.money import to_money
from app.mod08_inv import domain as D
from app.mod08_inv.repository import (
    adjustments,
    clear_adjustment,
    list_details,
    load_rows,
    save_adjustment,
    to_row,
)
from app.mod08_inv.service import build_page_data, parse_state
# ⭐ 降级通道（§3.6）：手动 Excel 导入 —— 独立路由件，由本文件汇总（`main.py` 不用改）
from app.mod08_inv.import_router import router as import_router
from app.mod08_inv.view import fetch_dialog_html, render_adjust_page, render_inv_page

router = APIRouter(tags=["mod08"])
router.include_router(import_router)


def query_params(request: Request) -> dict:
    """查询参数 → 扁平 dict（同名单值给 `str`、多值给 `list`；`service.parse_state` 两者都吃）。"""
    out: dict = {}
    for key in request.query_params.keys():
        vals = request.query_params.getlist(key)
        out[key] = vals if len(vals) > 1 else (vals[0] if vals else "")
    return out


def _safe_back(back: str) -> str:
    """回跳地址只允许站内路径（防开放重定向）。"""
    b = str(back or "").strip()
    return b if b.startswith("/") and not b.startswith("//") else "/m08"


@router.get("/m08", response_class=HTMLResponse)
def inv_page(request: Request, fetch: str = "", ym: str = "", rows: str = "", ins: str = "",
             upd: str = "", deleted: str = "", kept: str = "", msg: str = "", auto: str = ""):
    flash = None
    if fetch == "ok":
        flash = {"kind": "ok", "ym": ym, "rows": rows,
                 "stats": {"inserted": ins, "updated": upd, "deleted": deleted,
                           "kept_with_adjustment": kept},
                 "auto": auto}
    elif fetch == "degraded":
        flash = {"kind": "degraded", "message": msg}
    elif fetch == "err":
        flash = {"kind": "err", "message": msg}
    with session_scope() as s:
        data = build_page_data(s, parse_state(query_params(request)))
    return HTMLResponse(render_inv_page(data, flash=flash))


@router.post("/m08/fetch")
async def inv_fetch(request: Request):
    """**按月抓取**（`API-03`）—— 人工触发 ＋ **二次确认**（D9）；失败**降级不静默**（§3.6）。"""
    from urllib.parse import urlencode

    from app.core.errors import MustReportError
    from app.core.identity import current_operator
    from app.mod01_projects.recovery import summary_text
    from app.mod08_inv import fetch_service as FS

    form = await request.form()
    month = str(form.get("month") or "").strip()
    confirmed = str(form.get("confirm") or "") == FS.CONFIRM_TOKEN
    back = _safe_back(str(form.get("back") or "/m08"))

    with session_scope() as s:
        try:
            result = FS.run_fetch(s, year_month=month, confirmed=confirmed,
                                  operator=current_operator())
        except MustReportError as exc:                     # 用法错误（非单月 / 未确认 / 无 phid）
            query = urlencode({"fetch": "err", "msg": str(exc), "period": month})
            return RedirectResponse(f"{back}?{query}", status_code=303)
    if result["ok"]:
        st = result["stats"]
        query = urlencode({"fetch": "ok", "ym": result["ym"], "rows": result["rows"],
                           "ins": st["inserted"], "upd": st["updated"],
                           "deleted": st["deleted"], "kept": st["kept_with_adjustment"],
                           "auto": summary_text(result.get("recovery")),
                           "period": result["ym"]})
    else:
        query = urlencode({"fetch": "degraded", "msg": result["message"], "period": result["ym"]})
    return RedirectResponse(f"{back}?{query}", status_code=303)


@router.get("/m08/fetch-dialog", response_class=HTMLResponse)
def fetch_dialog(period: str = ""):
    """「按月抓取」弹窗（**默认月份 = 调用方当前所选核算年月**，001-11）。"""
    return HTMLResponse(fetch_dialog_html(D.fetch_dialog_default(period)))


@router.get("/m08/adjust/{row_id}", response_class=HTMLResponse)
def adjust_page(row_id: int, back: str = "/m08"):
    with session_scope() as s:
        detail = next((d for d in list_details(s) if d.id == row_id), None)
        if detail is None:
            return HTMLResponse("<div class=\"wrap\">库存单据行不存在</div>", status_code=404)
        adj = adjustments(s).get(row_id)
        row = to_row(detail, adj)
        payload = None
        if adj is not None:
            payload = {"before": adj.before_amount, "after": adj.amount,
                       "remark": adj.remark, "operator": adj.operator,
                       "at": adj.changed_at.strftime("%Y-%m-%d %H:%M") if adj.changed_at else ""}
        return HTMLResponse(render_adjust_page(row=row, adj=payload, back=_safe_back(back)))


@router.post("/m08/adjust/{row_id}")
async def adjust_save(row_id: int, request: Request):
    form = await request.form()
    amount = str(form.get("amount") or "")
    remark = str(form.get("remark") or "")
    back = _safe_back(str(form.get("back") or "/m08"))

    problem = D.adjustment_problem(amount, remark)
    if problem:
        with session_scope() as s:
            detail = next((d for d in list_details(s) if d.id == row_id), None)
            if detail is None:
                return HTMLResponse("<div class=\"wrap\">库存单据行不存在</div>", status_code=404)
            row = to_row(detail, adjustments(s).get(row_id))
            return HTMLResponse(
                render_adjust_page(row=row, adj=None, errors=[problem], back=back),
                status_code=400,
            )

    with session_scope() as s:
        save_adjustment(s, row_id=row_id, new_amount=amount, remark=remark,
                        operator=current_operator())
    return RedirectResponse(back, status_code=303)


# ============================================================ JSON API（前端壳：原型直接接数据）
# ⚠️ 数据形状一律对齐**原型 `V.m08` 的字段名**（`docNo`/`amt`/`wh`…）由**壳的适配层**转 ——
#    后端这里只出**域内规范名**（`doc_no`/`amount`/`warehouse`…），与页面渲染同源。


class AdjustRequest(BaseModel):
    """打 / 改调整单（`ENT-04`）。`amount` 用 **str**（金额一律字符串进、判据自己解析）。"""

    row_id: int
    amount: str = ""
    remark: str = ""


class ClearAdjustRequest(BaseModel):
    row_id: int


class FetchRequest(BaseModel):
    """按月抓取（`API-03`）。

    ⚠️ `confirm` = **用户在壳的抓取弹窗里点过「按 X 抓取」**（D9 二次确认）。
    ⛔ 缺它一律拒（400）—— 防止任何"直接打进来"的静默抓取（**会顶号**）。
    """

    month: str = ""
    confirm: bool = False


def _money(x) -> float:
    """金额 → JSON 数字（2 位）。⚠️ 出 **number** 而不是字符串：壳里这些值直接参与求和。"""
    try:
        return round(float(to_money(x)), 2)
    except (TypeError, ValueError):
        return 0.0


@router.get("/api/m08/inventory")
def api_inventory() -> dict:
    """明细行（**全量**，已叠加调整后金额）＋ 调整单清单 —— 供前端壳。

    - ★ **全量**返回、筛选由前端做（与 `/api/m03/notice-list?period=` 同款）：原型的
      筛选 / 排序 / 合计 / 列筛选逻辑**一行不改**（`D18`）。
    - ⛔ 不含「操作」列（按钮 HTML 只在页面上成立 —— 全站同款，见 `PAGE_ONLY_KEYS`）。
    - `c5` = **材料 5 类别**（物料性质归集）—— 唯一出口 = `mod06_proc.domain.to_category`；
      壳里「过程资料」的入库 / 出库 5 列聚合直接吃它（⛔ 不在前端重写归集规则）。
    - `adjusted` = 这一行有没有调整单（壳里判 `adjOf` 用它，也用于「只看被调整行」筛选）。
    """
    from app.mod06_proc.domain import to_category          # 归集规则的**唯一出口**

    with session_scope() as s:
        rows = load_rows(s)                                 # 已叠加调整单
        adjs = adjustments(s)
        items = [
            {
                **r,
                "c5": to_category(r.get("material_property")) or "",
                "adjusted": r.get("adj_amount") is not None,
            }
            for r in rows
        ]
        payload = [
            {
                "id": a.id,
                "row_id": a.row_id,
                "before_amount": _money(a.before_amount),
                "amount": _money(a.amount),
                "remark": a.remark or "",
                "operator": a.operator or "",
                "changed_at": a.changed_at.strftime("%Y-%m-%d %H:%M") if a.changed_at else "",
            }
            for a in sorted(adjs.values(), key=lambda x: x.id)
        ]
        projects = sorted({str(r.get("warehouse") or "") for r in rows if r.get("warehouse")})
    return {"rows": items, "adjustments": payload, "count": len(items), "projects": projects}


@router.post("/api/m08/adjust")
def api_adjust(req: AdjustRequest) -> dict:
    """打 / 改调整单 —— **判据唯一出口 = `domain.adjustment_problem`**（金额 ≥ 0 · 备注必填）。

    失败 **抛 `MustReportError`** ⇒ 400 ＋ 原样原因（壳侧把原因给用户，不静默）。
    ⚠️ 原始数据**永不被改**：调整单独立存储（`inv_adjustment`），抓取只刷新 `inv_detail`。
    """
    problem = D.adjustment_problem(req.amount, req.remark)
    if problem:
        raise MustReportError(problem)
    try:
        with session_scope() as s:
            adj = save_adjustment(
                s, row_id=req.row_id, new_amount=req.amount,
                remark=req.remark, operator=current_operator(),
            )
            out = {
                "ok": True,
                "row_id": adj.row_id,
                "before_amount": _money(adj.before_amount),
                "amount": _money(adj.amount),
                "remark": adj.remark or "",
                "operator": adj.operator or "",
            }
    except ValueError as exc:                               # 行不存在 / 判据不过
        raise MustReportError(str(exc)) from exc
    return out


@router.post("/api/m08/adjust/clear")
def api_adjust_clear(req: ClearAdjustRequest) -> dict:
    """**撤销调整单** —— 回到 i8 原始金额（原始数据未受影响，两表物理分离）。

    依据：原型 `V.m08` 的调整单弹窗**有「撤销调整单」按钮**（**原型即交互规格**，`D18`）。
    """
    with session_scope() as s:
        clear_adjustment(s, row_id=req.row_id)
    return {"ok": True, "row_id": req.row_id}


@router.post("/api/m08/fetch")
def api_fetch(req: FetchRequest) -> dict:
    """**按月抓取**库存单据明细（`API-03`）—— 人工触发。

    ⚠️ **会登录 i8 并强踢在线用户**（D9）：`confirm` 必须为真（= 用户已在壳的弹窗里确认过）。
    ⚠️ 失败**降级为手动 Excel 导入并显式说明**（§3.6），**绝不自动重试登录**（D9）。
    """
    from app.mod08_inv import fetch_service as FS

    with session_scope() as s:
        return FS.run_fetch(
            s, year_month=req.month, confirmed=req.confirm, operator=current_operator()
        )


__all__ = ["router"]
