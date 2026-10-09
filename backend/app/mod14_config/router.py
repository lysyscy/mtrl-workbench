"""`MOD-14` 系统设置的路由 —— §7.8。

⚠️ 2026-09-21（`TAIL-27` · `§19` 四个暂留件收口）：**服务端渲染的设置页已删**
（`GET /m14/settings` ＋ PRG `POST /m14/settings/save` ＋ `view.py`）—— 能力**原样搬成 JSON API**
（`settings_api.py`，壳 `V.set` 在用）：设置项 / 提示 / 留痕 / 保存 / 校验全都在那边，
**判定一行没变**（`app_settings.SPECS` · `validate` · `repository.save` · `invalidate`）。
⚠️ 本文件此后只做**汇总**：剔除规则 API（`TAIL-40`）＋ 系统设置 API。
"""

from __future__ import annotations

from fastapi import APIRouter

# ⭐ 前端壳的 **系统设置 JSON API**（`§19` 四个暂留件收口）—— 独立路由件，由本文件汇总
from app.mod14_config.settings_api import router as settings_api_router

router = APIRouter(tags=["mod14"])
router.include_router(settings_api_router)


# ⭐ 前端壳的 **剔除规则 JSON API**（`TAIL-40`）—— 独立路由件，由本文件汇总（`main.py` 不用改）
#    ⚠️ 数据主人是**付款域**（`mod03_notice.rules_repository`）：§4.2.2 原文即「剔除规则本身属付款域」
#       ⇒ 依赖单向 `mod14_config → mod03_notice`，不成环。
from app.mod14_config.rules_api import router as rules_router      # noqa: E402

# ⭐ `TAIL-96` 集采项目**剔除名单**（页面在 M14、数据主人在集采域，与剔除规则**同构**）
from app.mod14_config.jc_ignore_api import router as jc_ignore_router  # noqa: E402

router.include_router(rules_router)
router.include_router(jc_ignore_router)      # ⭐ `TAIL-96` 集采剔除名单（与上面同构）

from app.mod14_config.mech_rules_api import router as mech_rules_router  # noqa: E402

router.include_router(mech_rules_router)


__all__ = ["router"]
