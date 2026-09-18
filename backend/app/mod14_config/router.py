"""`MOD-14` 系统设置的路由（`/m14/settings`）—— §7.8。

⚠️ 保存走 **PRG**（POST → 303 → GET），与全站一致；校验失败**不写库**、原地回显错误。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.app_settings import (
    SETTING_KEYS,
    SPECS,
    invalidate,
    validate,
)
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.identity import current_operator
from app.mod14_config.repository import recent_logs, save
from app.mod14_config.view import render_settings_page

router = APIRouter(tags=["mod14"])


def _env_values() -> dict[str, str]:
    """`.env` 侧的值（按 `SPECS.env_attr` 取；仅用于展示「回落值」）。"""
    st = get_settings()
    return {s.key: str(getattr(st, s.env_attr, "") or "") for s in SPECS}


@router.get("/m14/settings", response_class=HTMLResponse)
def settings_page(ok: str = "", err: str = ""):
    with session_scope() as s:
        logs = recent_logs(s)
    flash = "已保存（改动已留痕）" if ok == "1" else ""
    errors = [err] if err else []
    return HTMLResponse(render_settings_page(env_values=_env_values(), logs=logs,
                                             flash=flash, errors=errors))


@router.post("/m14/settings/save")
async def settings_save(request: Request):
    form = await request.form()
    values = {k: str(form.get(k) or "") for k in SETTING_KEYS}

    errors = [e for e in (validate(k, v) for k, v in values.items()) if e]
    if errors:
        with session_scope() as s:
            logs = recent_logs(s)
        return HTMLResponse(
            render_settings_page(env_values=_env_values(), logs=logs, errors=errors),
            status_code=400,
        )

    with session_scope() as s:
        save(s, values=values, operator=current_operator())
    invalidate()                      # ⭐ 清缓存 —— 否则页面改了不生效
    return RedirectResponse("/m14/settings?ok=1", status_code=303)


# ⭐ 前端壳的 **剔除规则 JSON API**（`TAIL-40`）—— 独立路由件，由本文件汇总（`main.py` 不用改）
#    ⚠️ 数据主人是**付款域**（`mod03_notice.rules_repository`）：§4.2.2 原文即「剔除规则本身属付款域」
#       ⇒ 依赖单向 `mod14_config → mod03_notice`，不成环。
from app.mod14_config.rules_api import router as rules_router      # noqa: E402

router.include_router(rules_router)


__all__ = ["router"]
