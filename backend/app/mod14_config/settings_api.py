"""`MOD-14` **系统设置的 JSON API**（前端壳专用）—— 口径主人 =《说明书》§7.8。

⚠️ **为什么有它**（`TAIL-27` · `§19` 四个暂留件收口）：设置页的能力原先**只有服务端渲染页**
   （`mod14_config/view.py` ＋ `router.py` 的 PRG）有 —— 壳里**零入口** ⇒ 那页删不得。
   本件把那页的能力原样搬成 JSON：**页面内容（设置项 / 提示 / 留痕）与保存都从这里出**，
   壳侧 `V.set` 渲染它 ⇒ 旧页可删。
⛔ **判定一行没变**：`SPECS`（设置项唯一清单）· `validate`（格式校验）· `repository.save`
   （**只写传入的 key** ＋ 逐项留痕）· `invalidate()`（清缓存）—— 全部是**既有出口**，
   本层只做「读出来 → 转成 JSON」。

⚠️ 口径三条（§7.8，⛔ 不许在壳里重写一份）：
  ① 取值优先级 **库（页面所设）→ `.env`**（清空输入框 = 回落 `.env`）；
  ② 每项改动**都留痕**（与「规则配置」的硬删不留痕**有意不同**）；
  ③ 空值**一律合法**（= 清除），非法格式 ⇒ **拒绝并原地回显原因，一个字都不写库**。
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.app_settings import (
    SETTING_KEYS,
    SPECS,
    effective,
    invalidate,
    stored_value,
    validate,
)
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.identity import current_operator
from app.mod14_config.repository import recent_logs, save

router = APIRouter(tags=["mod14-api"])

#: 口径说明（照抄 `§7.8` 那四条）—— 壳侧的折叠块直接渲染这四条，⛔ 不在壳里另写文案。
#: ⭐ 2026-09-27（`TAIL-127` · 用户裁定 **B**）：这些**连接参数**已从「系统设置」页**搬回它们起作用的地方**
#:   （用户原话：「连接参数这个板块说实话可以删掉，因为**不可能有变动**」）—— 第①条据此改写，
#:   ⛔ 别再写成"本页只放…"（那就成了假话：本页**已经没有**输入框了）。
TIPS: tuple[str, ...] = (
    "这些**连接参数**（i8 地址 / 两个打印版式 ID）**配一次能用很久** —— 改到**用它的那一页**去改："
    "i8 地址 → 「**i8 接入层**」页的「i8 连接设置」；打印版式 → 「**付款通知书**」页的「打印机设置」。",
    "取值优先级：**界面所设 → `.env`**（清空那一格并保存即回落到 `.env`）。",
    "⚠️ **i8 的账号与密码不在这里** —— 它绑定到**本系统的账号**、**每人一份**（在「用户管理」页）。",
    "⚠️ 这几项改动**都会留痕**（与「规则配置」的硬删不留痕有意不同 —— 配错会印错版式 / 抓错数据），"
    "记录见下方「变更留痕」。",
)


def _env_values() -> dict[str, str]:
    """`.env` 侧的值（按 `SPECS.env_attr` 取；仅用于展示「回落值」）。"""
    st = get_settings()
    return {s.key: str(getattr(st, s.env_attr, "") or "") for s in SPECS}


def items() -> list[dict]:
    """设置项（**页面渲染的唯一数据源**）—— 每项带：标签 / 提示 / 控件类型 / 已设值 / `.env` 值与当前生效值。

    ⚠️ `stored` 空 ⇒ 该行走 `.env`（壳侧据此显示「.env」徽标）；`stored` 非空 ⇒ 显示「本页所设」。
    """
    env = _env_values()
    out: list[dict] = []
    for spec in SPECS:
        stored = stored_value(spec.key)
        env_value = env.get(spec.key, "")
        out.append({
            "key": spec.key,
            "label": spec.label,
            "hint": spec.hint,          # ⭐ 反直觉提示就写在 hint 里（`001-04` 钉着它）
            "kind": spec.kind,
            "stored": stored,
            "env": env_value,
            "effective": effective(spec.key, env_value),
        })
    return out


def logs() -> list[dict]:
    """最近变更留痕（倒序）—— 改前 / 改后 / 改动人 / 时间。"""
    with session_scope() as s:
        rows = recent_logs(s)
    return [{"at": str(getattr(r, "at", ""))[:19], "key": str(getattr(r, "key", "")),
             "old": str(getattr(r, "old_value", "") or ""),
             "new": str(getattr(r, "new_value", "") or ""),
             "operator": str(getattr(r, "operator", "") or "")} for r in rows]


@router.get("/api/m14/settings")
def api_settings_get() -> dict:
    """设置页的整页数据（**壳里零本地拼装**：设置项 / 提示 / 留痕都在这里）。"""
    return {"ok": True, "items": items(), "logs": logs(), "tips": list(TIPS)}


@router.post("/api/m14/settings")
async def api_settings_save(request: Request) -> dict:
    """保存（**只处理传进来的 key**）→ 逐项校验；有错 ⇒ **一个字都不写库**，把原因原样交回。

    ⚠️ 恒 **HTTP 200**：非法格式是**可预期的拒绝**（§7.8 ③），壳侧据 `ok` 分流并**原样显示** `errors`。
    """
    form = await request.json()
    values = {k: str((form or {}).get(k) or "") for k in SETTING_KEYS}

    errors = [e for e in (validate(k, v) for k, v in values.items()) if e]
    if errors:
        return {"ok": False, "errors": errors, "items": items(), "logs": logs()}

    with session_scope() as s:
        save(s, values=values, operator=current_operator())
    invalidate()          # ⭐ 清缓存 —— 否则页面改了不生效（同 PRG 那条路）
    return {"ok": True, "message": "已保存（改动已留痕）", "items": items(), "logs": logs()}


__all__ = ["router", "TIPS", "items", "logs"]
