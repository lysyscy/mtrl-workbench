"""`core` 取数口 ＋ 装配层接线（`TAIL-195` 批 1b）—— 四条：

① **三口必须都接上**（装配层漏接一件 ⇒ 红）；② 项目行口没接上 ⇒ **显式报错**；
③ 身份那处没接上 ⇒ **拒绝**；④ 接的必须是**转发**、不是模块级别名。

⚠️ 为什么值得单独立断言（两条都是**静默**故障，看着正常、结果不对）：
- ② 静默回空表 ⇒ 把"没装配"读成"库里一个项目都没有"；
- ③ 回落 `.env` ⇒ 拿**共享账号**去登录（《说明书》§7.8：会顶掉同事的在线会话、留痕记错人）；
- ④ 接成别名 ⇒ 测试的 `monkeypatch` 打不着（⭐ `TAIL-195` 批 **2c** 实测过：12 条判据当场红）。

反向灵敏度：`tools/mut/_mut_core_bindings.py`（三条各一靶 ⇒ 必红）。
"""

from __future__ import annotations

import pytest


from app import core_bindings
from app.core import app_settings as AS
from app.core import identity as ID
from app.core import projects as P1


# ------------------------------------------------------------------ ①② 装配齐全


def test_装配层把三个口都接上了():
    """⭐ 漏接一件 ⇒ 红（**静默**半边：设置那处会悄悄回落 `.env` ⇒「页面改了但没生效」）。"""
    core_bindings.register_all()
    assert AS._VALUES_LOADER is not None, "系统设置的取数口没接上"
    assert ID._BINDING_LOOKUP is not None, "身份取 i8 绑定的口没接上"
    assert P1._ROWS_LOADER is not None, "项目行的取数口没接上"


def test_接上之后项目索引照常_以id为键():
    """接上口以后，`project_index` 的口径（**键 = id**）不变。"""
    core_bindings.register_all()
    assert isinstance(P1.project_index(_EmptySession()), dict)


class _EmptySession:
    """只够 `select(Project)` 用（本断言不连库）。"""

    def execute(self, _stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return []

        return _R()


def test_注册是幂等的_重复接不会换掉已接上的实现():
    core_bindings.register_all()
    before = (AS._VALUES_LOADER, ID._BINDING_LOOKUP, P1._ROWS_LOADER)
    core_bindings.register_all()
    assert (AS._VALUES_LOADER, ID._BINDING_LOOKUP, P1._ROWS_LOADER) == before


# ------------------------------------------------------------------ ②③ 没接上时的态度


def test_项目行口没接上必须显式报错_不许静默回空表(monkeypatch):
    """⛔ 静默回空表 = 把"没装配"读成"库里一个项目都没有"。"""
    monkeypatch.setattr(P1, "_ROWS_LOADER", None)
    try:
        P1.project_index(object())
    except RuntimeError as exc:
        assert "取数口没接上" in str(exc), f"报错要说清是取数口没接上：{exc}"
    else:
        raise AssertionError("项目行口没接上时必须显式报错，⛔ 不许静默回空表")


def test_身份口没接上必须拒绝_不许回落共享账号(monkeypatch):
    """⛔ 回落 = 拿 `.env` 那个共享账号去登录（§7.8：顶掉同事会话、留痕记错人）。"""
    from app.core import session as SESS
    from app.core.errors import MustReportError

    monkeypatch.setattr(ID, "_BINDING_LOOKUP", None)
    monkeypatch.setattr(SESS, "current_name", lambda: "某人")     # 「有身份」这一档
    try:
        ID.current_i8_credentials()
    except MustReportError:
        pass
    else:
        raise AssertionError("身份口没接上时必须拒绝，⛔ 不许回落 .env 共享账号")


# ------------------------------------------------------------------ ④ 转发 ≠ 别名


class _Row:
    """项目行替身（只用到 `.id`）。"""

    def __init__(self, pid: int) -> None:
        self.id = pid


#: 「真实现」在 `_Session` 上会回这一行（id=99）—— 补丁回的是 id=7 那行 ⇒ **靠值区分**转发 / 别名。
_REAL_ROW = _Row(99)


class _Session:
    """只够 `select(Project)` 用（本断言不连库）。"""

    def execute(self, _stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return [_REAL_ROW]

        return _R()


def test_三个口都是转发_测试补丁必须看得见(monkeypatch):
    """⭐⭐ 批 **2c** 的坑（模块级别名把函数对象**绑死**）⇒ 这里钉住三个口都是**转发**。

    ⚠️ 断言用 `_Session`（**真实现**也能跑）⇒ 别名那条路**不会**撞 `AttributeError`，
       而是**回一个不同的值**（99 而不是 7）—— 这样"未命中"才是真的判据问题，不是异常串台。
    """
    from app.mod01_projects import repository as P1R
    from app.mod14_config import repository as C14R
    from app.mod15_user import repository as USR

    monkeypatch.setattr(C14R, "read_values", lambda: {"i8_base_url": "补丁"})
    monkeypatch.setattr(USR, "by_identity", lambda _s, who: f"补丁:{who}")
    monkeypatch.setattr(P1R, "all_projects", lambda _s: [_Row(7)])

    AS.invalidate()
    assert AS._values() == {"i8_base_url": "补丁"}, "设置的取数口没走转发"
    assert ID._BINDING_LOOKUP(object(), "甲") == "补丁:甲", "身份的取数口没走转发"
    assert list(P1.project_index(_Session())) == [7], "项目行的取数口接成别名了（补丁没生效）"


@pytest.fixture(autouse=True)
def _接好口():
    """每条断言前都确保接上；跑完**清掉设置缓存**。

    ⚠️⚠️ 那个 `AS.invalidate()` **不是摆设**：上面那条"补丁"断言会往 `app_settings._CACHE` 写进假值，
       不清就会**漏给别的测试件** —— 2026-09-30 实测症状：`test_i8_contract` 的
       「未配置时显式报错」静默变红（它只 `get_settings.cache_clear()`，**清不到**本模块的 `_CACHE`）。
    """
    core_bindings.register_all()
    yield
    core_bindings.register_all()
    AS.invalidate()
