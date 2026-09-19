"""`MOD-07` 路由汇总：收发结存与活动大表 —— **只剩 JSON API**（前端壳直接接数据，`D18`）。

⚠️ 2026-09-19（`TAIL-27` · `§19` **批 2**）：本模块的**服务端渲染页半边已整体删除**（授权 `D18`）——
   `GET /m07`（收发结存月报）· `GET /m07/extract`（焊材 / 气体提取）· `GET /m07/fetch-dialog`（抓取弹窗）·
   `GET /m07/zip-manifest`（产出物清单）· PRG `POST /m07/fetch` · `GET /m07/big`（活动大表）·
   `GET /m07/big/export`（按模板导出的清单预览）· PRG `POST /m07/big/{cell,pick,move}`
   ＋ `query_params` / `_safe_back` / `_redirect` / `FLASH_KINDS`
   ＋ **`view.py`（425 行）与 `big_view.py`（261 行）**。
   ⇒ 本模块从此**只有 JSON API 一条路**：读 `GET /api/m07/settlement` · `/api/m07/extract` · `/api/m07/big`；
   写 `POST /api/m07/fetch` · `/api/m07/big/cell` · `/api/m07/big/selection` · `/api/m07/extract/balance`；
   导出 `/api/m07/settlement/export` · `/api/m07/big/export`（壳在用 ✓，`test_wired_m07.py` 钉着）。
   ⛔ 别再往本文件加页面路由（要加能力 ⇒ 加 API ＋ 壳里接，同 `D18` 的口径）。
"""

from __future__ import annotations

from fastapi import APIRouter

# ⭐ 前端壳的 **JSON API**（原型直接接数据，`D18`）—— 独立路由件，由本文件汇总（`main.py` 不用改）
from app.mod07_setl.api import router as api_router

router = APIRouter(tags=["mod07"])
router.include_router(api_router)


__all__ = ["router"]
