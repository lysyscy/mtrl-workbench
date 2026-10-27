"""测试数据库配置守卫：仅检查配置与已创建对象，不连接数据库。"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import re

from pydantic_settings.sources import DotEnvSettingsSource
from sqlalchemy.engine import URL, make_url


def database_identity(value: str | URL) -> tuple[str, int, str]:
    """只接受本项目可确认目的地址的 PostgreSQL TCP URL；凭据与驱动不构成隔离。"""
    try:
        url = make_url(value.strip() if isinstance(value, str) else value)
        host = (url.host or '').lower().rstrip('.')
        database = url.database or ''
        port = 5432 if url.port is None else url.port
        if (url.get_backend_name() != 'postgresql' or url.query or not host
                or not re.fullmatch(r'[a-z0-9_.:-]+', host)
                or not re.fullmatch(r'[a-zA-Z0-9_]+', database)
                or not 1 <= port <= 65535):
            raise ValueError
        try:
            host = str(ipaddress.ip_address(host))
        except ValueError:
            pass
        return host, port, database.casefold()
    except Exception:
        # 解析异常可能含原 URL，因此不传播原异常及凭据。
        raise RuntimeError('数据库目标无法确认：只接受无查询参数的 PostgreSQL TCP 配置') from None


@dataclass(frozen=True)
class TestDatabaseGuard:
    __test__ = False
    test_url: str = field(repr=False)

    @classmethod
    def from_sources(cls, original_urls: tuple[str, ...], test_url: str) -> TestDatabaseGuard:
        originals = tuple(value for value in original_urls if value)
        if not originals and not test_url:
            return cls('')
        if not originals or not test_url:
            raise RuntimeError('数据库配置不完整：必须同时提供原数据库目标与 TEST_DATABASE_URL')
        target = database_identity(test_url)
        if not target[2].endswith('_test'):
            raise RuntimeError('TEST_DATABASE_URL 必须指向名称以 _test 结尾的专用测试库')
        for original in originals:
            source = database_identity(original)
            # 不解析 DNS，也不把不同主机名/端口当作物理隔离证据。
            if source[2] == target[2]:
                raise RuntimeError('测试库必须与原数据库使用不同库名；同库或主机别名歧义已拒绝')
        return cls(test_url)

    def assert_runtime(self, *urls: str | URL) -> None:
        if not self.test_url:
            if any(urls):
                raise RuntimeError('数据库配置在守卫初始化后发生变化，无法确认测试目标')
            return
        target = database_identity(self.test_url)
        if any(not url or database_identity(url) != target for url in urls):
            raise RuntimeError('测试进程解析到的不是已确认的测试库（配置或缓存目标不符）')


def point_tests_at_test_db(settings_type, environ) -> TestDatabaseGuard:
    """使用应用自己的 Settings/env_file 规则，先保留原目标，再覆盖进程环境。"""
    try:
        original = settings_type()
        file_values = DotEnvSettingsSource(settings_type)()
    except Exception:
        raise RuntimeError('无法读取应用数据库配置；测试库守卫拒绝继续') from None
    if file_values.get('test_database_url') and not original.test_database_url:
        raise RuntimeError('数据库配置不完整：配置文件存在测试库来源，但有效 TEST_DATABASE_URL 为空')
    source_env = environ.get('MTRL_TEST_SOURCE_ENV')
    if source_env:
        # The runner starts with the test target already selected. Read source
        # identities separately; never make the source URL an application target.
        try:
            declared = DotEnvSettingsSource(settings_type, env_file=source_env)()
        except Exception:
            raise RuntimeError('无法读取隔离测试的明确来源配置') from None
        guard = TestDatabaseGuard.from_sources(
            (declared.get('database_url', ''), file_values.get('database_url', '')),
            declared.get('test_database_url', ''),
        )
        if not guard.test_url:
            raise RuntimeError('明确来源配置必须包含原库和专用测试库')
        guard.assert_runtime(original.database_url, original.test_database_url)
    else:
        guard = TestDatabaseGuard.from_sources(
            (original.database_url, file_values.get('database_url', '')),
            original.test_database_url,
        )
    if guard.test_url:
        environ['DATABASE_URL'] = guard.test_url
    return guard


def assert_application_targets(guard: TestDatabaseGuard, settings_type, get_settings, db_module) -> None:
    """核新配置、已有 Settings 缓存、引擎及 session 工厂；不创建或连接引擎。"""
    try:
        fresh, cached = settings_type(), get_settings()
    except Exception:
        raise RuntimeError('无法核对应用数据库配置；测试库守卫拒绝继续') from None
    guard.assert_runtime(fresh.database_url, fresh.test_database_url,
                         cached.database_url, cached.test_database_url)
    if db_module is None:
        return
    engine = db_module._engine
    if engine is not None:
        guard.assert_runtime(engine.url)
    factory = db_module._session_factory
    if factory is not None:
        bind = factory.kw.get('bind')
        engine = getattr(bind, 'engine', bind)
        guard.assert_runtime(getattr(engine, 'url', ''))
