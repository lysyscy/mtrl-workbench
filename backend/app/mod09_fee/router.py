"""`MOD-09` 路由：特殊费用月报表页（`/m09`）＋ 三个写动作（PRG）。

- `GET  /m09`      —— 页面（核算年月 ＋ 项目两个筛选；**只开放按月**）
- `POST /m09/add`  —— 「＋ 增加手填项」
- `POST /m09/cell` —— 该份内某一行的「保存 / 删除」（靠 `op=save:<i>` / `op=del:<i>` 指明）

⚠️ **回跳只允许站内路径**（防开放重定向）；回执一律经 query 参数送回（`ok` / `err`）。
⚠️ 全部写动作都**只落在「当前所选核算年月 ＋ 当前所选项目」那一份上**（§5.5）。
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import session_scope
from app.mod09_fee import domain as D
from app.mod09_fee.service import (
    act_add, act_delete, act_rename, act_set_amount, build_page_data, parse_state,
)
from app.mod09_fee.view import render_fee_page

router = APIRouter(tags=["mod09"])


def _back(ym: str, pj: str) -> str:
    return "/m09?" + urlencode({"ym": ym, "pj": pj})


def _redirect(*, ym: str, pj: str, kind: str, message: str) -> RedirectResponse:
    key = "ok" if kind == "ok" else "err"
    return RedirectResponse(
        _back(ym, pj) + "&" + urlencode({key: message}), status_code=303
    )


@router.get("/m09", response_class=HTMLResponse)
def fee_page(request: Request, ym: str = "", pj: str = "", ok: str = "", err: str = ""):
    flash = ({"kind": "ok", "message": ok} if ok
             else ({"kind": "err", "message": err} if err else None))
    with session_scope() as s:
        data = build_page_data(s, parse_state(dict(request.query_params)))
    return HTMLResponse(render_fee_page(data, flash=flash))


@router.post("/m09/add")
async def fee_add(request: Request):
    form = await request.form()
    ym = str(form.get("ym") or "").strip()
    pj = str(form.get("pj") or "").strip()
    with session_scope() as s:
        flash = act_add(s, ym=parse_state({"ym": ym}).get("ym") or ym, project_key=pj)
    return _redirect(ym=ym, pj=pj, kind=flash["kind"], message=flash["message"])


@router.post("/m09/cell")
async def fee_cell(request: Request):
    """该份内某一行的保存 / 删除。

    ⚠️ 保存时**金额非法 ⇒ 整次不落**（项名与金额都不写）—— 一条明确规则，
       严格满足「非法输入被拒绝且原值不变」（001-07）；回执里说清。
    """
    form = await request.form()
    ym = str(form.get("ym") or "").strip()
    pj = str(form.get("pj") or "").strip()
    op = str(form.get("op") or "")
    action, _, idx = op.partition(":")

    with session_scope() as s:
        if action == "del":
            flash = act_delete(s, ym=ym, project_key=pj, index=idx)
        elif action == "save":
            problem = D.amount_problem(form.get(f"amount_{idx}"))
            if problem:
                flash = {"kind": "err", "message": problem}
            else:
                renamed = act_rename(s, ym=ym, project_key=pj, index=idx,
                                     value=str(form.get(f"name_{idx}") or ""))
                if renamed["kind"] != "ok":
                    flash = renamed
                else:
                    flash = act_set_amount(s, ym=ym, project_key=pj, index=idx,
                                           raw=form.get(f"amount_{idx}"))
        else:
            flash = {"kind": "err", "message": "未识别的动作 —— 请刷新页面后重试"}
    return _redirect(ym=ym, pj=pj, kind=flash["kind"], message=flash["message"])


# ⭐ 前端壳的 **JSON API**（原型直接接数据，`D18`）—— 独立路由件，由本文件汇总（`main.py` 不用改）
from app.mod09_fee.api import router as api_router      # noqa: E402

router.include_router(api_router)


__all__ = ["router"]
