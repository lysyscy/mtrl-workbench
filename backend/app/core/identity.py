"""当前操作人（**留痕与"录入人"的唯一出口**）。

依据：《说明书》§1.5.1（科室 2 个账号）· §4.2.6（手动新增行的**录入人 = 当前登录用户**）·
      §9.3（留痕三要素含"改动人"）。

⚠️ **本出口的存在是为了一件事**：现在还没有登录体系（用户管理属 `MOD-15`，M6 才做），
   但留痕与手动行的"录入人"从第一天起就要写对。**先立唯一出口、后接登录态** ——
   等 `MOD-15` 落地时**只改本文件**，不必去各模块翻"写死的名字"。

⚠️ **不得**在业务模块里写死人名（《说明书》§4.1 逐页清单第 ③ 条：
   原型里两处"写死的人名"已改为当前登录用户）。
"""

from __future__ import annotations

# `MOD-15` 落地前的中性占位 —— 不是任何人名（避免"写死一个真名"这种更难清理的形态）
PLACEHOLDER_OPERATOR = "科室用户"


def current_operator() -> str:
    """当前操作人（用于留痕 / 录入人）。

    - 登录体系（`MOD-15`）落地前：读 `.env` 的 `OPERATOR_NAME`，缺省返回中性占位；
    - 落地后：本函数改为返回登录态里的用户名 —— **调用方无需改动**。
    """
    from app.core.config import get_settings

    try:
        name = str(get_settings().operator_name or "").strip()
    except Exception:  # noqa: BLE001 —— 配置异常不应让"取个名字"变成故障
        name = ""
    return name or PLACEHOLDER_OPERATOR


def is_placeholder() -> bool:
    """当前是否还在"占位"状态（界面上据此提示"录入人待登录体系接入"）。"""
    return current_operator() == PLACEHOLDER_OPERATOR


__all__ = ["PLACEHOLDER_OPERATOR", "current_operator", "is_placeholder"]
