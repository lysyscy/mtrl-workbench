"""数据库引擎 / 会话 / 基类 / 金额列类型。

依据：
- 《技术栈选型分析》**§3.2**：短事务 + 连接池上限 + 「长任务不持写事务」
- 工程坑 1.2-5：**schema 变更的唯一入口 = 迁移**（Alembic），禁止用建表 API 改既有库
- 工程坑 1.4-14：测试库与开发库**物理隔离**，解析到开发库即熔断

⚠️ 引擎**懒加载**：不在 import 期连库（否则无 `.env` 时任何 import 都会炸）。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Numeric, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# 金额列类型：**全站唯一出口**（`numeric(18,2)`，元 / 2 位小数 —— 技术栈 §3.2）
# ⚠️ 任何模型都不得自写 Numeric / Float / Integer 来表达金额
MONEY = Numeric(18, 2)


class Base(DeclarativeBase):
    """ORM 基类（所有模型继承它）。"""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError("DATABASE_URL 未配置（见 .env.example）")
        _engine = create_engine(
            url,
            pool_size=5,          # 连接池上限（§3.2：防拖垮服务）
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """短事务：正常退出提交、异常回滚。

    ⚠️ 长耗时任务（抓取 / 渲染 / 打包）**先取完数据、关掉写事务再做**，不得持写事务。
    """
    session = get_session_factory()()
    tracker = None
    try:
        from app.core.history import track
        tracker = track(session)
        yield session
        if tracker is not None:
            tracker.prepare()
        session.commit()
        if tracker is not None:
            tracker.committed()
    except Exception:
        session.rollback()
        raise
    finally:
        if tracker is not None:
            tracker.close()
        session.close()


def dispose_engine() -> None:
    """释放连接池（测试 / 停机）。"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
