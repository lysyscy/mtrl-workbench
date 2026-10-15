"""`MOD-11` 路由汇总：集采台账 —— **只有 JSON API**（前端壳直接接数据，`D18`）。

⚠️ 本模块**从来没有过服务端渲染页**（`app/mod11_jc/` 在 2026-09-19 之前只有 `__init__.py`）
   ⇒ 从第一天起就走"新壳 ＋ JSON API"这条路，⛔ 别再补页面路由（同 `D18` 口径：
   要加能力 ⇒ 加 API ＋ 壳里接）。
"""

from __future__ import annotations

from fastapi import APIRouter


# ⭐ 前端壳的 **JSON API**（原型直接接数据，`D18`）—— 独立路由件，由本文件汇总
from app.mod11_jc.api import router as api_router

router = APIRouter(tags=["mod11"])
router.include_router(api_router)

# 集采Excel导入已归档：docs/archive/retired-imports-20261015/README.md。

__all__ = ["router"]
