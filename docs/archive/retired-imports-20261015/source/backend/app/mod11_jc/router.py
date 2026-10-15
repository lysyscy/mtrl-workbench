"""`MOD-11` 路由汇总：集采台账 —— **只有 JSON API**（前端壳直接接数据，`D18`）。

⚠️ 本模块**从来没有过服务端渲染页**（`app/mod11_jc/` 在 2026-09-19 之前只有 `__init__.py`）
   ⇒ 从第一天起就走"新壳 ＋ JSON API"这条路，⛔ 别再补页面路由（同 `D18` 口径：
   要加能力 ⇒ 加 API ＋ 壳里接）。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.import_kit.api import build_router as build_imp_router

# ⭐ 前端壳的 **JSON API**（原型直接接数据，`D18`）—— 独立路由件，由本文件汇总
from app.mod11_jc import imp_spec
from app.mod11_jc.api import router as api_router

router = APIRouter(tags=["mod11"])
router.include_router(api_router)

# ⭐ `TAIL-75`（通用导入面）：**本域挂在 `import_kit` 的通用导入面**上（`/api/imp/m11_jc/*`）
#    —— 壳里的「数据导入」页走这套（列映射 ＋ 建议 ＋ 记忆 ＋ 预览 ＋ 确认）。
#    ⛔ 2026-09-23（`TAIL-75` 余项 · **用户裁定**）：原先「集采台账」页里那个**页内导入向导**
#       ＋ 它的两条端点（`/api/m11/import/parse|commit`）已**连件删除**（"导入只在启用初期用一次"）
#       ⇒ 现在**只有通用面这一条路**。
#    ⚠️ **匹配口径一直只有一份**：`import_service.match_and_apply`（`B5b` 拆出来的）——
#       通用面的域钩子调的也是它 ⇒ ⛔ 绝不是"两套匹配"，也⛔ 别把页内那条路加回来。
router.include_router(build_imp_router(imp_spec.SPEC, imp_spec.HOOKS))


__all__ = ["router"]
