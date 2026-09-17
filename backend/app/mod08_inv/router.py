"""`MOD-08` 路由：明细总表页（`/m08`）＋ 调整单（`/m08/adjust/{id}`）＋ 抓取弹窗（`/m08/fetch-dialog`）。

⚠️ 写操作一律 **PRG**（POST → 303 → GET），与全站一致；校验失败**不写库**、原地回显。
⚠️ 调整单的判据走 `domain.adjustment_problem`（唯一出口），路由**不另写判定**。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import session_scope
from app.core.identity import current_operator
from app.mod08_inv import domain as D
from app.mod08_inv.repository import adjustments, list_details, save_adjustment, to_row
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
             upd: str = "", deleted: str = "", kept: str = "", msg: str = ""):
    flash = None
    if fetch == "ok":
        flash = {"kind": "ok", "ym": ym, "rows": rows,
                 "stats": {"inserted": ins, "updated": upd, "deleted": deleted,
                           "kept_with_adjustment": kept}}
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


__all__ = ["router"]
