"""真实测试库验证：正常返回、显式提交与断言失败后都不遗留样例。"""
from contextlib import contextmanager, nullcontext
from uuid import uuid4

import pytest

from sqlalchemy import select

from app.core import db
from app.mod01_projects.models import Project
from tests.acc_plugin import acc
from tests.conftest import rollback_db


@pytest.mark.parametrize('end', ['normal', 'commit', 'assertion'])
@acc()
def test_session_scope_writes_are_rolled_back(monkeypatch, end):
    key = '__rollback_db_' + uuid4().hex
    original_factory = db.get_session_factory()
    expected = pytest.raises(AssertionError, match='模拟用例断言失败') if end == 'assertion' else nullcontext()
    with monkeypatch.context() as scoped:
        with expected:
            # 直接驱动yield夹具，验证它的teardown，而非在测试结束前手动回滚。
            with contextmanager(rollback_db.__wrapped__)(scoped) as connection:
                with db.session_scope() as s:
                    s.add(Project(warehouse_name=key, name_full=key))
                    s.flush()
                    if end == 'commit':
                        s.commit()
                assert connection.scalar(select(Project.id).where(Project.warehouse_name == key))
                if end == 'assertion':
                    raise AssertionError('模拟用例断言失败')
    assert db.get_session_factory() is original_factory
    with db.session_scope() as reader:
        assert reader.scalar(select(Project.id).where(Project.warehouse_name == key)) is None
