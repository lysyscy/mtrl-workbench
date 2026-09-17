"""看板（默认落地页 `GET /`）—— 把 9 项待办汇总出来（`ACC-HOME-TODO-001`）。

⚠️ **不占模块号**（原型导读）⇒ 本路由挂在根路径，不是 `/mNN`。
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.db import session_scope
from app.home import domain as D
from app.home.service import gather
from app.home.view import render_home

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home_page() -> str:
    """看板 = 默认落地页：9 项待办（数字取自各域出口；未实现域记 0 并标注）。"""
    with session_scope() as s:
        out = gather(s)
    return render_home(D.dashboard(out["counts"]), errors=out["errors"])


__all__ = ["router"]
