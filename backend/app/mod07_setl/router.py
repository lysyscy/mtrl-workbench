"""`MOD-07` 收发结存路由：月报页（`/m07`）＋ 抓取弹窗 ＋ 产出物清单 ＋ **按月抓取**（`API-02`）。

⚠️ 写操作一律 **PRG**（POST → 303 → GET），与全站一致。
⚠️ 判据走 `domain` 的出口（对平 / 合计 / 计数 / 清单），路由**不另写判定**。
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod02_i8.fetch_task import CONFIRM_TOKEN, KICK_WARNING
# ⚠️ `parse_state` 的**主人在 `big_service`**（不是 `big_domain`）—— 写错时**离线断言发现不了**
#    （直接调函数不走 router）；只有真机请求才 500（2026-09-17 实测踩到）⇒ 见测试里的「域出口存在性」断言。
from app.mod07_setl.big_service import parse_state as big_state
from app.mod07_setl import domain as D
from app.mod07_setl.big_view import render_big_page, render_export_page
from app.mod07_setl.repository import load_rows
from app.mod07_setl.service import (
    build_extract_data,
    build_page_data,
    parse_extract_state,
    parse_state,
)
from app.mod07_setl.view import (
    fetch_dialog_html,
    render_extract_page,
    render_setl_page,
    zip_dialog_html,
)

router = APIRouter(tags=["mod07"])

FLASH_KINDS = ("ok", "warn", "err")


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
    return b if b.startswith("/") and not b.startswith("//") else "/m07"


def _redirect(back: str, *, kind: str, message: str, period: str = "") -> RedirectResponse:
    """PRG 回执（三态：`ok` / `warn` / `err`）—— 一律**显式说明**，不静默。"""
    return RedirectResponse(
        f"{back}?{urlencode({'fetch': kind if kind in FLASH_KINDS else 'warn',
                             'msg': message, 'period': period})}",
        status_code=303,
    )


@router.get("/m07", response_class=HTMLResponse)
def setl_page(request: Request, fetch: str = "", msg: str = ""):
    flash = {"kind": fetch, "message": msg} if fetch else None
    with session_scope() as s:
        data = build_page_data(s, parse_state(query_params(request)))
    return HTMLResponse(render_setl_page(data, flash=flash))


@router.get("/m07/extract", response_class=HTMLResponse)
def extract_page(request: Request):
    """**焊材 / 气体提取**（§5.3.3 · 核对工具）—— 只读页，无写入口。"""
    with session_scope() as s:
        data = build_extract_data(s, parse_extract_state(query_params(request)))
    return HTMLResponse(render_extract_page(data))


@router.get("/m07/fetch-dialog", response_class=HTMLResponse)
def fetch_dialog(period: str = ""):
    """「按月抓取」弹窗（**默认月份 = 调用方当前所选核算年月**，001-06）。"""
    return HTMLResponse(fetch_dialog_html(D.fetch_dialog_default(period)))


@router.get("/m07/zip-manifest", response_class=HTMLResponse)
def zip_manifest(period: str = ""):
    """分仓库 zip 的**产出物清单**（份数随仓数实时算，001-08）。"""
    ym = D.fetch_dialog_default(period)
    with session_scope() as s:
        rows = D.warehouse_rows(load_rows(s), ym)
    return HTMLResponse(zip_dialog_html(D.zip_manifest(rows, ym), D.zip_name(ym)))


@router.post("/m07/fetch")
async def setl_fetch(request: Request):
    """**按月抓取**（`API-02`）—— 人工触发 ＋ **二次确认**（D9）⇒ 导出 → 解析 → **幂等落库**。

    回执三态：`ok`（成功，含条数与陌生仓库）/ `warn`（降级 / 空导出，**未改动数据**）
    / `err`（用法错误：非单月 · 未确认 · 无 phid · 报表登记不全 —— **不发请求、不写执行记录**）。
    """
    from app.mod01_projects.recovery import summary_text
    from app.mod07_setl import fetch_service as FS

    form = await request.form()
    month = str(form.get("month") or "").strip()
    confirmed = str(form.get("confirm") or "") == CONFIRM_TOKEN
    back = _safe_back(str(form.get("back") or "/m07"))

    try:
        with session_scope() as s:
            result = FS.run_fetch(s, year_month=month, confirmed=confirmed)
    except MustReportError as exc:                       # 用法错误（非单月 / 未确认 / 无 phid / 未定稿）
        return _redirect(back, kind="err", message=str(exc), period=month)

    if result["ok"]:
        st = result["stats"]
        msg = (f"抓取成功：{result['ym']} 共 {result['rows']} 行明细 —— 新增 {st['inserted']} · "
               f"更新 {st['updated']} · 删除 {st['deleted']} · 保留人工行 {st['kept_manual']}")
        # ⭐ 链路 B：陌生仓库**已自动建档 / 扶正**（`ACC-PRJ-AUTO-001`）—— 逐条说出来，禁静默
        auto = summary_text(result.get("recovery"))
        if auto:
            msg += "；" + auto
        return _redirect(back, kind="ok", message=msg, period=result["ym"])
    return _redirect(back, kind="warn", message=result["message"], period=result.get("ym") or month)


@router.get("/m07/big", response_class=HTMLResponse)
def big_page(request: Request, fetch: str = "", msg: str = ""):
    """**经济活动分析大表**（§5.7 —— 手填 6 列 ＋ 带入 ＋ 派生 ＋ 大表自己的顺序）。"""
    from app.mod07_setl.big_service import build_big_data

    flash = {"kind": fetch, "message": msg} if fetch else None
    with session_scope() as s:
        data = build_big_data(s, big_state(query_params(request)))
    return HTMLResponse(render_big_page(data, flash=flash))


@router.get("/m07/big/export", response_class=HTMLResponse)
def big_export(request: Request):
    """「按模板导出」的**清单预览**（与页面**同一份行装配** ⇒ 两处同序同值，§5.7.3）。

    ⚠️ 真实文件落盘 / 打包归切片 6（`ACC-X-EXP-001` · `TAIL-04`）。
    """
    from app.mod07_setl.big_service import build_big_data

    with session_scope() as s:
        data = build_big_data(s, big_state(query_params(request)))
    return HTMLResponse(render_export_page(data))


@router.post("/m07/big/cell")
async def big_cell(request: Request):
    """保存**一格**手填值 —— 非法输入**不写库**（原值不变）；PRG 回本页。
    ⛔ 手填值**不参与欠款计算**（§5.7.2）：本动作只写大表自己的表。
    """
    from app.mod07_setl.big_service import build_big_data, save_manual_cell

    form = await request.form()
    month = big_state({"period": str(form.get("period") or "")})["month"]
    with session_scope() as s:
        cands = build_big_data(s, {"month": month})["candidates"]
        res = save_manual_cell(s, month=month, warehouse=str(form.get("wh") or ""),
                               key=str(form.get("key") or ""), raw=form.get("value"),
                               cands=cands)
    return _redirect("/m07/big", kind="ok" if res["ok"] else "err",
                     message=res["message"], period=month)


@router.post("/m07/big/pick")
async def big_pick(request: Request):
    """保存选题（多选）—— 顺序 = 候选顺序（§5.7.3）。"""
    from app.mod07_setl.big_service import build_big_data, save_selection

    form = await request.form()
    month = big_state({"period": str(form.get("period") or "")})["month"]
    picked = [str(v) for v in form.getlist("pj")] if str(form.get("selnone") or "") == "" else []
    if str(form.get("selall") or ""):
        picked = None                                     # 全选 ⇒ 交给 `candidates` 顺序
    with session_scope() as s:
        cands = build_big_data(s, {"month": month})["candidates"]
        if picked is None:
            picked = [c["warehouse"] for c in cands]
        res = save_selection(s, picked, cands=cands)
    return _redirect("/m07/big", kind="ok", message=res["message"], period=month)


@router.post("/m07/big/move")
async def big_move(request: Request):
    """逐项**上移 / 下移**一格（§5.7.3）。"""
    from app.mod07_setl.big_service import build_big_data, move_project

    form = await request.form()
    month = big_state({"period": str(form.get("period") or "")})["month"]
    with session_scope() as s:
        cands = build_big_data(s, {"month": month})["candidates"]
        res = move_project(s, warehouse=str(form.get("wh") or ""),
                           direction=str(form.get("dir") or "up"), cands=cands)
    return _redirect("/m07/big", kind="ok", message=res["message"], period=month)


__all__ = ["router"]
