"""看板（`home`）—— ⚠️ **本模块不再有页面**（2026-09-21 `§19` 批 5）。

⭐ **看板已经进了新壳**（`V.home` · `backend/app/web/index.html`），`WIRED` 里有 `home`
   ⇒ 页面的**交互规格主人 = 原型 `V.home`**，数据由壳自己取。
   本模块只剩两件：

| 出口 | 作用 |
|---|---|
| `GET /` | ⭐ **默认落地页 = 看板**（`§3.1.3`/原型导读）—— 看板既已在壳里，这里就**跳到壳**（`/app` 的初始视图正是 `home`）⇒ 老书签/老习惯**照旧可用**，⛔ 不会 404 |
| `GET /api/home/run-counts` | 壳拿不到的**三个**（要跨全表执行记录）—— 口径在 `service.run_counts`，⛔ 本文件不另写判定 |

⚠️ **删掉的**（2026-09-21）：`home/view.py`（服务端渲染页）· `home/domain.py`（8 项待办的口径出口，
   现在归壳 `V.home`）· `service.gather` 的另外六项（壳自己按已加载行算，`V.home`）。
   ⇒ 依据 = 用户 2026-09-17 裁定 **D18**（前端换层：原型整体复制、只换数据源）
   ＋ 2026-09-20 「`MOD-12` 之后旧渲染层只剩 5 处」的收口序列（`§19`）。
"""

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
