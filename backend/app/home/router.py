"""默认首页跳转与执行记录计数兼容端点；看板不再请求运行状态。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.core.db import session_scope
from app.home.service import run_counts

router = APIRouter(tags=["home"])


@router.get("/", include_in_schema=False)
def home_page() -> RedirectResponse:
    """默认落地页 = 看板 ⇒ 看板在壳里，跳到壳（`/app` 的初始视图就是 `home`）。

    ⚠️ **用 302、不用 301**：301 会被浏览器**长期缓存** ⇒ 将来这里若换回别的东西，
       老浏览器不会再来问（"改了不生效"的经典坑）。
    """
    return RedirectResponse(url="/app", status_code=302)


@router.get("/api/home/run-counts")
def run_counts_api() -> dict:
    """看板 ⑦⑬⑭ 的**唯一取数口**（全表 SQL；见 `service.run_counts` 的口径说明）。"""
    with session_scope() as s:
        return run_counts(s)


__all__ = ["router"]
