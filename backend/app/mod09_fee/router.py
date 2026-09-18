"""`MOD-09` 路由汇总：特殊费用月报表 —— **只剩 JSON API**（前端壳直接接数据，`D18`）。

⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：本模块的**服务端渲染页半边已整体删除**（授权 `D18`）——
   `GET /m09`（页面）· `POST /m09/add`（＋ 增加手填项）· `POST /m09/cell`（行内保存 / 删除）
   ＋ `_back`/`_redirect` ＋ `view.py`（`render_fee_page`：`_table_html` / `add_form` / `filter_form` …）。
   ⇒ 本表从此**只有 JSON API 一条路**：读 `GET /api/m09/fee`；写 `POST /api/m09/fee/add` ·
   `/fee/name` · `/fee/amount` · `/fee/delete`（壳的四个写动作全走它们 ✓，`test_wired_m09.py` 钉着）。
   ⛔ 别再往本文件加页面路由（要加能力 ⇒ 加 API ＋ 壳里接，同 `D18` 的口径）。
"""

from __future__ import annotations

from fastapi import APIRouter

# ⭐ 前端壳的 **JSON API**（原型直接接数据，`D18`）—— 独立路由件，由本文件汇总（`main.py` 不用改）
from app.mod09_fee.api import router as api_router

router = APIRouter(tags=["mod09"])
router.include_router(api_router)


__all__ = ["router"]
