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

    ⭐ **2026-09-20 接上登录态**（`MOD-15` 片 3）—— ⚠️ **只改本文件**，正是模块头那句承诺：
       `mod01` / `mod03` / `mod07` / `mod08` / `mod11` / `mod14` 那 13 处调用方**一行没动**。

    取值顺序（**第一个非空**为准）：
    ① **登录态**（`core/session.py` 由中间件从会话 cookie 解出的用户名）—— 正常路径；
    ② `.env` 的 `OPERATOR_NAME` —— ⚠️ **过渡期的兜底**（未登录 / 定时任务 / 测试进程仍要能留痕）；
    ③ 中性占位 `科室用户` —— ⛔ **绝不是人名**（见常量注释）。

    ⚠️ ⛔ **别把 ② 删掉**：本系统有大量**不带 cookie** 的路径（定时抓取 / 命令行脚本 /
       测试进程）—— 删了兜底，它们会把留痕写成占位。
    """
    from app.core.config import get_settings
    from app.core.session import current_name

    name = (current_name() or "").strip()          # ① 登录态
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
         未登录的路径（命令行脚本 / 测试进程）与"还没绑过 i8 的账号"都落这里，
         行为与接入本函数**之前完全一样**（零破坏）；
      ③ 两者皆空 ⇒ 返回空串，由 `http_login` 显式报「I8_USER 未配置」——
         ⛔ 不在这里抛：那会把"没配"伪装成一个身份层故障。

    ⚠️⚠️ **账号与密码必须同一个来源**（⛔ 不许"账号取用户行、密码回落 `.env`"这种混搭）：
       那会拿**甲**的账号配**乙**的密码去登录 ⇒ i8 侧只会说"账号或密码错"，
       而**没人看得出是混搭出来的** —— 这类"静默错配"正是本仓最贵的一类错。

    ⚠️ **DB 异常不吞**（⛔ 不用裸 `except`）：吞掉就会**悄悄拿 `.env` 的账号去登录**——
       那是"用错的人顶了号"，比直接报错坏得多。取不到绑定（查无此人）走 ② 是**正常路径**。
    """
    from app.core.config import get_settings
    from app.core.session import current_name

    who = (current_name() or "").strip()
    if who:
        from app.core.db import session_scope
        from app.mod15_user import repository as USR

        with session_scope() as s:
            row = USR.by_identity(s, who)
        if row is not None:
            bound = (row.i8_user or "").strip()
            if bound:
                return bound, (row.i8_password or "")     # ⚠️ 密码**不 strip**（前后空格也是密码的一部分）

    env = get_settings()
    return (env.i8_user or "").strip(), (env.i8_password or "")


__all__ = ["PLACEHOLDER_OPERATOR", "current_i8_credentials", "current_operator", "is_placeholder"]
