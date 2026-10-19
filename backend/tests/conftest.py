"""pytest 全局夹具与守卫。

- 验收结果落盘路径统一到**工程根** `artifacts/`（不进版本控制）。
- **测试库熔断**：解析到开发库即失败（工程坑 1.4-14）—— 见 `_assert_test_db_isolated()`
  与下面的 ⚠️ 说明（**它此前只做了一半**）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR: Path = REPO_ROOT / "var/state/verification"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
# ⛔ **这里不再 `setdefault` `ACC_RESULTS_PATH`**（2026-09-23 改）：
#    原先那条 setdefault 让变量**永远有值** ⇒ `acc_plugin.pytest_configure` 的"没给变量就写**局部**文件"
#    那条默认分支**永远不触发** ⇒ 跑一支变异脚本（子集）照样把权威 `acc_results.json` 冲成十几条
#    （本仓反复踩过四次，本条正是**治本**的那一处）。
#    ⇒ 约定：**子集跑**默认写 `artifacts/_partial_acc_results.json`（插件内定）；
#      **要写权威文件必须显式给** `ACC_RESULTS_PATH`（全套跑法见 `细则.md` §十七）。


# ⚠️⚠️⚠️ **2026-09-20 修：pytest 此前根本没连测试库** ——
#
# 本文件原来的 `_assert_test_db_isolated()` 只检查「两个地址**不相同**」，
# 却**从来没有把库换过去** ⇒ `app.core.db.get_engine()` 读的是 `DATABASE_URL`（**开发库**）
# ⇒ **所有库级断言其实一直打在开发库上**。实测：pytest 里
# `get_engine().url == …/mtrl_workbench`（而不是 `…/mtrl_workbench_test`）。
#
# ⭐ 两个**旁证**此前都被我当成别的问题解释过去了，现在一对就明白：
#   ① **测试库落后开发库好几个迁移** —— 因为没人往它写，它的版本号停在很久以前；
#   ② 冒烟留下的自检行只在**开发库**里找得到。
#
# ⭐ 而本文件**文档头**写的正是「**测试库熔断：解析到开发库即失败**」——
#    ⇒ 代码从来没实现那句话（文档比代码承诺得多，是最容易骗过人的一种偏差）。
#
# ⛔ 这段**必须在任何 `app.core.config` 导入之前**执行（`get_settings()` 会缓存）⇒
#    放在 conftest 的**模块顶层**，而不是夹具里。
def _point_tests_at_test_db() -> None:
    """把 `DATABASE_URL` 指向**测试库**（没有测试库配置时**保持原样**并留给守卫报错）。

    ⚠️ 用**覆盖**语义（`os.environ[...] = ...`）而不是 `setdefault`：
       外部若已导出 `DATABASE_URL`（指向开发库），`setdefault` 会**默默保留它** ——
       那正是"看起来配了、其实没换"的老毛病。
    """
    test = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
    if test:
        os.environ["DATABASE_URL"] = test


def pytest_configure(config) -> None:  # noqa: ARG001
    """会话启动即做环境守卫（不连库，只比对配置）。"""
    _assert_test_db_isolated()


def _read_env_value(key: str) -> str:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return ""


def _assert_test_db_isolated() -> None:
    """**测试进程解析到的库，必须是测试库** —— 否则直接失败（工程坑 1.4-14）。

    ⚠️ 2026-09-20 改写。原来的实现只比对「`.env` 里两个地址**不相同**」就收工，
       **从没检查测试进程用哪个库** ⇒ 于是"两个地址当然不同"**恒成立**，
       而实际连的是**开发库** —— 一条**永远为真、因此永远不报**的守卫。
       ⭐ 那种守卫比没有更坏：它在文档头写着"解析到开发库即失败"，
         让人以为有防线（本仓最贵的一课）。

    现在的判据 = **拿"实际生效的地址"和"开发库"比**（而不是拿两个配置项互比）：
      ① 两个配置项相同 ⇒ 没有可用的测试库，报错；
      ② **实际生效的不是测试库** ⇒ 报错（这才是"解析到开发库即失败"的字面含义）。

    `.env` 未配置时**不报错**（M0 阶段尚未接库）——一旦配置就必须隔离。
    """
    dev = _read_env_value("DATABASE_URL")            # ⚠️ 直接读 .env：那才是"开发库"的本尊
    test = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
    live = os.environ.get("DATABASE_URL") or ""      # ⚠️ 实际生效的（已被上面换成测试库）
    if not dev or not test:
        return
    dev, test, live = dev.strip(), test.strip(), live.strip()
    if dev == test:
        raise RuntimeError(
            "TEST_DATABASE_URL 与 DATABASE_URL 相同 —— 测试库必须与开发库物理隔离（工程坑 1.4-14）")
    if live != test:
        raise RuntimeError(
            "测试进程**解析到的不是测试库** —— 「测试库熔断：解析到开发库即失败」（工程坑 1.4-14）\n"
            f"  实际生效：{live}\n  测试库应为：{test}\n"
            "  ⇒ 检查 `tests/conftest.py` 的 `_point_tests_at_test_db()` 有没有被绕过"
            "（例如某个 conftest / 插件在它之前就调用了 `get_settings()`）。")


# ⚠️ 调用点必须在**本文件末尾**（`_read_env_value` 得先定义好），
#    但仍**早于任何测试模块**被导入 ⇒ 也就早于 `app.core.config` 的首次调用 ✓
_point_tests_at_test_db()

# ⭐ 导出件注册（`TAIL-195` 批 2b · 与 `app/main.py` **同一个** `register_all()`）：
#    许多测试**直调**导出件（不经过 `app.main`）⇒ 这里也要填一次注册表。
#    ⚠️⚠️ **必须在上面那句之后** —— 它 import `app.report_export`，而那条链会碰 `app.core.config`；
#       先注册 = "在把 DATABASE_URL 换成测试库之前就把配置缓存了"（本文件开头那个坑，会静默打错库）。
from app.export_bindings import register_all as _register_exporters  # noqa: E402

_register_exporters()

# ⭐ `core` 取数口注册（`TAIL-195` 批 1b · 与 `app/main.py` **同一个** `register_all()`）：
#    许多测试**直调** `core`（不经过 `app.main`）⇒ 这里也要接一次。
#    ⚠️ 本件模块顶层**不 import 任何 app 件**（import 全在函数体里）⇒ 放这儿不会碰配置缓存（同上面那条注释）。
from app import core_bindings as _core_bindings  # noqa: E402

_core_bindings.register_all()


@pytest.fixture
def rollback_db(monkeypatch):
    """按需接管 session_scope；会话提交仅释放保存点，结束总是回滚外层事务。"""
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from app.core import db
    from app.core.config import get_settings

    engine = db.get_engine()
    test_url = get_settings().test_database_url
    assert test_url and engine.url == make_url(test_url), '回滚夹具只能连接已配置的测试库'
    with engine.connect() as connection, monkeypatch.context() as scoped:
        outer = connection.begin()
        factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False,
                               join_transaction_mode='create_savepoint')
        scoped.setattr(db, '_session_factory', factory)
        try:
            yield connection
        finally:
            try:
                assert outer.is_active, '测试不得提交外层事务'
            finally:
                outer.rollback()
