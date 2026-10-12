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

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# `MOD-15` 落地前的中性占位 —— 不是任何人名（避免"写死一个真名"这种更难清理的形态）
PLACEHOLDER_OPERATOR = "科室用户"

#: ── 取数口（**装配层注入** · `TAIL-195` 批 1b）─────────────────────────────────
#: 实现 = `mod15_user.repository.by_identity`（数据主人那边那份，**唯一一份**）；
#: 装配 = `app/core_bindings.py::register_all()`。
#: ⛔ `core` 里别 import 业务包（计划 §2.3「依赖方向一律向外」；守卫 = `tests/test_layering.py` 规则 A）。
_BINDING_LOOKUP: Callable[..., object | None] | None = None


def bind_binding_lookup(fn: Callable[..., object | None]) -> None:
    """装配层接上「按身份取账号行」的实现（签名 `(session, 身份) → 行 | None`）。

    ⚠️ 接**转发**（每次经模块取属性）—— ⛔ 别接模块级别名（同 `TAIL-195` 批 2c 实测的坑）。
    """
    global _BINDING_LOOKUP
    _BINDING_LOOKUP = fn


def current_operator() -> str:
    """当前操作人（用于留痕 / 录入人）。

    ⭐ **2026-09-20 接上登录态**（`MOD-15` 片 3）—— ⚠️ **只改本文件**，正是模块头那句承诺：
       `mod01` / `mod03` / `mod07` / `mod08` / `mod11` / `mod14` 那 13 处调用方**一行没动**。

    取值顺序（**第一个非空**为准）：
    ① **登录态的账号行** → 姓名或账号（展示/留痕标签，⛔ 不写会话编码）—— 正常路径；
    ② `.env` 的 `OPERATOR_NAME` —— ⚠️ **过渡期的兜底**（未登录 / 定时任务 / 测试进程仍要能留痕）；
    ③ 中性占位 `科室用户` —— ⛔ **绝不是人名**（见常量注释）。

    ⚠️ ⛔ **别把 ② 删掉**：本系统有大量**不带 cookie** 的路径（定时抓取 / 命令行脚本 /
       测试进程）—— 删了兜底，它们会把留痕写成占位。
    """
    from app.core.config import get_settings
    from app.core.session import AccountIdentity, current_name

    who = current_name()
    name = (who or "").strip()
    if isinstance(who, AccountIdentity) and _BINDING_LOOKUP is not None:
        from app.core.db import session_scope

        with session_scope() as s:
            row = _BINDING_LOOKUP(s, who)
            if row is not None:
                name = (row.name or row.account or "").strip()
    if not name:
        try:
            name = str(get_settings().operator_name or "").strip()    # ② .env 兜底
        except Exception:  # noqa: BLE001 —— 配置异常不应让"取个名字"变成故障
            name = ""
    return name or PLACEHOLDER_OPERATOR            # ③ 中性占位


def is_placeholder() -> bool:
    """当前是否还在"占位"状态（界面上据此提示"录入人待登录体系接入"）。"""
    return current_operator() == PLACEHOLDER_OPERATOR


def current_i8_credentials() -> tuple[str, str]:
    """**当前登录用户绑定的 i8 账号 / 密码**（§7.8：「i8 的账号与密码…**绑定到本系统账号、每人一份**」）。

    ⭐ 与 `current_operator()` **同款三段式**（第一个非空为准）：
      ① **登录态** → 那个账号行上的 `i8_user` / `i8_password`（正常路径）；
      ② `.env` 的 `I8_USER` / `I8_PASSWORD` —— ⚠️ **过渡期兜底**：
         未登录 / **查无此人**（身份解析不到，与 `_me()` 同口径）的路径都落这里
         （命令行脚本 / 测试进程 / 真机自检都走这条）；
      ③ 两者皆空 ⇒ 返回空串，由 `http_login` 显式报「I8_USER 未配置」——
         ⛔ 不在这里抛：那会把"没配"伪装成一个身份层故障。

    ⚠️⚠️ **2026-09-30（`TAIL-202` · 用户「全部按推荐」）—— "有身份但没绑"这一档改成【拒绝】**：
      在账号表里**查得到这个人**、而他的 `i8_user` 是空的 ⇒ 抛 `MustReportError`（人话），⛔ **不回落**。
      理由 =《说明书》**§7.8** 原话「登录体系落地后每人都必须在自己的账号里填，**未填即拒绝抓取并提示、
      不回落** —— 回落等于用了别人的账号 ⇒ **留痕会记错人**」；而 i8 登录自带**强踢**
      ⇒ 拿 `.env` 那个共享账号去登录，代价是**把同事的在线会话顶掉**。
      ⛔ 「查无此人 / 未登录」**不算**"有身份"（查不到就是没有身份）⇒ 仍走 ②（否则命令行 / 测试
      / 真机自检那些**不带真人身份**的路径会成片崩）。

    ⚠️⚠️ **账号与密码必须同一个来源**（⛔ 不许"账号取用户行、密码回落 `.env`"这种混搭）：
       那会拿**甲**的账号配**乙**的密码去登录 ⇒ i8 侧只会说"账号或密码错"，
       而**没人看得出是混搭出来的** —— 这类"静默错配"正是本仓最贵的一类错。

    ⚠️ **DB 异常不吞**（⛔ 不用裸 `except`）：吞掉就会**悄悄拿 `.env` 的账号去登录**——
       那是"用错的人顶了号"，比直接报错坏得多。取不到绑定（查无此人）走 ② 是**正常路径**。
    """
    from app.core.config import get_settings
    from app.core.errors import MustReportError
    from app.core.session import current_name

    who = current_name()  # 保留新账号 / 旧标签格式，消歧由绑定的唯一身份出口负责。
    if who:
        from app.core.db import session_scope

        if _BINDING_LOOKUP is None:
            # ⛔ **不回落**（回落 = 拿 `.env` 那个共享账号去登录 ⇒ 顶掉同事的会话、留痕记错人）；
            #    口没接上属装配问题，只在真机/测试环境理论上可能 ⇒ **显式拒绝**，不静默降级。
            logger.error("身份取 i8 绑定的口没接上 —— 见 `app.core_bindings.register_all()`")
            raise MustReportError(
                f"暂时取不到「{who}」的 i8 绑定（身份服务没就绪）—— 请稍后重试；若一直如此，请找管理员。")

        with session_scope() as s:
            row = _BINDING_LOOKUP(s, who)
        if row is not None:
            bound = (row.i8_user or "").strip()
            if bound:
                return bound, (row.i8_password or "")     # ⚠️ 密码**不 strip**（前后空格也是密码的一部分）
            # ⭐⭐ 2026-09-30（`TAIL-202`）：**有身份但没绑 i8 ⇒ 拒绝**（见上方文档注释）。
            #   ⚠️ 消息**不写任何内部名**（守则 §3.1）：不提 `.env` / 变量名 / 文件名。
            raise MustReportError(
                f"「{who}」还没在自己账号里填 i8 账号 —— 抓取要用你自己的 i8 账号"
                "（用共享账号会顶掉同事的在线会话，执行记录也会记错人）。"
                "请到「用户管理」里给自己填上（那个弹窗叫「改密 / i8 绑定」）。")

    env = get_settings()
    return (env.i8_user or "").strip(), (env.i8_password or "")


__all__ = ["PLACEHOLDER_OPERATOR", "current_i8_credentials", "current_operator", "is_placeholder"]
