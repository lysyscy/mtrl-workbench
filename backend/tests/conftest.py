"""pytest 装配：写入前确认专用测试库；普通 session_scope 写入由保存点回滚。"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

from app.core.config import Settings, get_settings
from tests.db_guard import assert_application_targets, point_tests_at_test_db

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR: Path = REPO_ROOT / "var/state/verification"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _point_tests_at_test_db():
    """在注册业务模块前保存原目标、验证隔离，再覆盖 DATABASE_URL。"""
    return point_tests_at_test_db(Settings, os.environ)


def _assert_test_db_isolated() -> None:
    assert_application_targets(_DB_GUARD, Settings, get_settings, sys.modules.get('app.core.db'))


def pytest_configure(config) -> None:  # noqa: ARG001
    _assert_test_db_isolated()


_DB_GUARD = _point_tests_at_test_db()
_assert_test_db_isolated()

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
    from sqlalchemy.orm import sessionmaker
    from app.core import db

    _assert_test_db_isolated()
    if not _DB_GUARD.test_url:
        raise RuntimeError('回滚夹具需要已确认的测试库配置')
    engine = db.get_engine()
    _DB_GUARD.assert_runtime(engine.url)
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
