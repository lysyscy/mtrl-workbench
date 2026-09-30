"""`core` 取数口的**装配层**（`TAIL-195` 批 1b）—— `core` 定义**口**，本件把实现接上。

## 为什么有这件

`core` 是**公共底座**（全站都 import 它）⇒ 它一旦 import 业务包，改一侧就牵动另一侧
（计划 **§2.3**「依赖方向一律向外」）。而 `core` 里确实有**三处要读库**的地方：系统设置 /
身份 → i8 绑定 / 全部项目行。⇒ 办法：**口留在 `core`（函数可注入），取数实现留在数据主人的包里**，
两边由**本件**接上。

| 口（在 `core/`） | 实现（数据主人那份，**唯一一份**） |
|---|---|
| `app_settings.bind_values_loader` | `mod14_config.repository.read_values` |
| `identity.bind_binding_lookup` | `mod15_user.repository.by_identity` |
| `projects.bind_rows_loader` | `mod01_projects.repository.all_projects` |

⚠️⚠️ **接的必须是「转发」，⛔ 不是模块级别名**（`_project_rows` 那几个小函数就是干这个的）——
   模块级别名会在接的那一刻把函数对象**绑死**，测试里的 `monkeypatch` 就再也打不着
   （`TAIL-195` 批 **2c** 实测过：症状是 **12 条判据当场红**）。
⚠️⭐ **本件是唯一可以直接接 `repository` 的地方** —— 它在**接线**，不在取数；⛔ 业务包仍不许
   （跨包取数经对方 `service` 包间出口：规则 C / D）。
⚠️ 未接上的后果（各口自己定，都写在 `core` 那边）：设置 = 回落 `.env` ＋ warning（沿用"库不可用"那条
   已认可的降级）；项目行 / 身份 = **显式报错**（⛔ 不静默 —— 静默会把"没装配"读成"库里没有"，
   而身份那处还会**回落去用共享账号**，代价是顶掉同事的会话）。

反向灵敏度：`tools/mut/_mut_core_bindings.py`（接成别名 / 静默回空表 ⇒ 必红）。
"""

from __future__ import annotations


def _settings_values():
    """取数口 · 系统设置（**转发** ⇒ 测试的 monkeypatch 仍然生效）。"""
    from app.mod14_config import repository as C14R

    return C14R.read_values()


def _i8_binding(session, who):
    """取数口 · 身份 → i8 绑定（**转发**）。"""
    from app.mod15_user import repository as USR

    return USR.by_identity(session, who)


def _project_rows(session):
    """取数口 · 全部项目行（**转发**）。"""
    from app.mod01_projects import repository as P1R

    return P1R.all_projects(session)


def register_all() -> None:
    """接上 `core` 的三个取数口（幂等）。

    ⚠️ 调用点两处、**都要在模块顶层**（⛔ 别塞进 `create_app()`）：`app/main.py`（进程一起就接）
       与 `backend/tests/conftest.py`（许多测试**直调** `core`，不经过 `app.main`）。
    """
    from app.core import app_settings as AS
    from app.core import identity as ID
    from app.core import projects as PJ

    AS.bind_values_loader(_settings_values)
    ID.bind_binding_lookup(_i8_binding)
    PJ.bind_rows_loader(_project_rows)


__all__ = ["register_all"]
