"""守卫反例仅使用假配置；无 .env、无数据库也必须可执行。"""

from functools import lru_cache
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from tests.db_guard import (
    TestDatabaseGuard, assert_application_targets, database_identity, point_tests_at_test_db,
)

DEV = 'postgresql+psycopg://developer:secret@localhost/mtrl'
TEST = 'postgresql+psycopg://tester:test_secret@localhost/mtrl_test'


@pytest.fixture
def settings_type(monkeypatch):
    # 不继承应用 Settings，避免任何真实 env_file 或凭据进入这些反例。
    for key in tuple(os.environ):
        if key.lower() in {'database_url', 'test_database_url', 'mtrl_test_source_env'}:
            monkeypatch.delenv(key)
    # 登记后移除，既让 dotenv 正常兜底，也让 helper 的直接覆盖在 teardown 恢复。
    for key in ('DATABASE_URL', 'TEST_DATABASE_URL'):
        monkeypatch.setenv(key, '')
        monkeypatch.delenv(key)

    class FakeSettings(BaseSettings):
        model_config = SettingsConfigDict(env_file=None, extra='ignore', case_sensitive=False)
        database_url: str = ''
        test_database_url: str = ''

    return FakeSettings


@pytest.mark.parametrize('original,test', [('', ''), (DEV, TEST)])
def test_absent_database_or_dedicated_test_target_is_allowed(original, test):
    guard = TestDatabaseGuard.from_sources((original,), test)
    guard.assert_runtime(test, test)


@pytest.mark.parametrize('original,test', [(DEV, ''), ('', TEST)])
def test_partial_database_configuration_fails_closed(original, test):
    with pytest.raises(RuntimeError, match='配置不完整'):
        TestDatabaseGuard.from_sources((original,), test)


@pytest.mark.parametrize('original', [
    'postgresql://another:password@LOCALHOST:5432/mtrl_test',
    'postgresql+psycopg://tester:new_password@localhost./mtrl_test',
    'postgresql+psycopg://tester:password@127.0.0.1/mtrl_test',
    'postgresql+psycopg://tester:password@db-alias:6543/mtrl_test',
    'postgresql+psycopg://tester:password@localhost/MTRL_TEST',
    'postgresql+psycopg://tester:password@localhost/mtrl%5ftest',
])
def test_same_database_name_is_rejected_even_with_host_or_credentials_changed(original):
    with pytest.raises(RuntimeError, match='同库或主机别名歧义'):
        TestDatabaseGuard.from_sources((original,), TEST)


@pytest.mark.parametrize('target', [
    'postgresql://tester:password@localhost/mtrl',
    'postgresql://tester:password@localhost/testing',
    'postgresql://tester:password@localhost/postgres',
])
def test_target_must_have_dedicated_test_name(target):
    with pytest.raises(RuntimeError, match='专用测试库'):
        TestDatabaseGuard.from_sources((DEV,), target)


@pytest.mark.parametrize('target', [
    'not a URL password', 'sqlite:///mtrl_test',
    'postgresql://tester:password@/mtrl_test',
    'postgresql://tester:password@localhost/mtrl_test?host=production',
    'postgresql://tester:password@localhost/mtrl_test?dbname=production',
    'postgresql://tester:password@localhost/mtrl_test?options=-csearch_path=public',
    'postgresql://tester:password@localhost:invalid/mtrl_test',
    'postgresql://tester:password@localhost:0/mtrl_test',
])
def test_ambiguous_database_routes_are_rejected_without_credentials(target):
    with pytest.raises(RuntimeError) as error:
        TestDatabaseGuard.from_sources((DEV,), target)
    assert 'password' not in str(error.value)
    assert target not in str(error.value)
    assert error.value.__suppress_context__


def test_normalization_ignores_driver_credentials_and_default_port():
    assert database_identity(TEST) == ('localhost', 5432, 'mtrl_test')
    guard = TestDatabaseGuard.from_sources((DEV,), TEST)
    guard.assert_runtime('postgresql://other:another_secret@LOCALHOST.:5432/mtrl_test')
    assert 'test_secret' not in repr(guard)


def test_settings_env_file_is_used(settings_type, monkeypatch, tmp_path):
    env_file = tmp_path / 'application.env'
    env_file.write_text(f'export DATABASE_URL="{DEV}"\nTEST_DATABASE_URL="{TEST}" # test\n', encoding='utf-8')
    settings_type.model_config['env_file'] = str(env_file)
    guard = point_tests_at_test_db(settings_type, os.environ)
    assert os.environ['DATABASE_URL'] == TEST
    assert_application_targets(guard, settings_type, settings_type, None)


def test_environment_original_cannot_be_lost_before_override(settings_type, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', TEST)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    with pytest.raises(RuntimeError, match='同库'):
        point_tests_at_test_db(settings_type, os.environ)
    assert os.environ['DATABASE_URL'] == TEST


def test_environment_only_configuration_is_switched(settings_type, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', DEV)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    guard = point_tests_at_test_db(settings_type, os.environ)
    assert os.environ['DATABASE_URL'] == TEST
    assert_application_targets(guard, settings_type, settings_type, None)


def test_dotenv_original_is_checked_even_if_environment_masks_it(settings_type, monkeypatch, tmp_path):
    env_file = tmp_path / 'application.env'
    env_file.write_text(f'DATABASE_URL={TEST}\n', encoding='utf-8')
    settings_type.model_config['env_file'] = str(env_file)
    monkeypatch.setenv('DATABASE_URL', DEV)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    with pytest.raises(RuntimeError, match='同库'):
        point_tests_at_test_db(settings_type, os.environ)
    assert os.environ['DATABASE_URL'] == DEV


def test_empty_environment_cannot_hide_a_database_source(settings_type, monkeypatch, tmp_path):
    env_file = tmp_path / 'application.env'
    env_file.write_text(f'TEST_DATABASE_URL={TEST}\n', encoding='utf-8')
    settings_type.model_config['env_file'] = str(env_file)
    monkeypatch.setenv('TEST_DATABASE_URL', '')
    with pytest.raises(RuntimeError, match='配置不完整'):
        point_tests_at_test_db(settings_type, os.environ)


def test_completely_unconfigured_settings_are_allowed(settings_type):
    guard = point_tests_at_test_db(settings_type, {})
    assert_application_targets(guard, settings_type, settings_type, None)
    with pytest.raises(RuntimeError, match='初始化后'):
        guard.assert_runtime(DEV)


@pytest.mark.parametrize('cache_kind', ['settings', 'engine', 'session_factory', 'unbound_factory'])
def test_cached_application_targets_are_checked_without_connecting(settings_type, monkeypatch, cache_kind):
    monkeypatch.setenv('DATABASE_URL', DEV)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    get_settings = lru_cache()(settings_type)
    if cache_kind == 'settings':
        get_settings()
    guard = point_tests_at_test_db(settings_type, os.environ)
    def forbidden_connect():
        pytest.fail('配置守卫不得连接数据库')
    engine = SimpleNamespace(url=make_url(DEV), connect=forbidden_connect)
    db = SimpleNamespace(_engine=None, _session_factory=None)
    if cache_kind == 'engine':
        db._engine = engine
    if cache_kind in {'session_factory', 'unbound_factory'}:
        db._session_factory = SimpleNamespace(kw={'bind': engine} if cache_kind == 'session_factory' else {})
    with pytest.raises(RuntimeError, match='配置或缓存目标不符') as error:
        assert_application_targets(guard, settings_type, get_settings, db)
    assert 'secret' not in str(error.value)


def test_changed_runtime_environment_is_rejected(settings_type, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', DEV)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    guard = point_tests_at_test_db(settings_type, os.environ)
    monkeypatch.setenv('DATABASE_URL', DEV)
    with pytest.raises(RuntimeError, match='解析到的不是'):
        assert_application_targets(guard, settings_type, settings_type, None)


def test_correct_cached_engine_and_connection_bind_are_allowed(settings_type, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', DEV)
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    guard = point_tests_at_test_db(settings_type, os.environ)
    engine = SimpleNamespace(url=make_url(TEST))
    factory = SimpleNamespace(kw={'bind': SimpleNamespace(engine=engine)})
    assert_application_targets(guard, settings_type, settings_type,
                               SimpleNamespace(_engine=engine, _session_factory=factory))


def test_settings_errors_do_not_reveal_validation_values():
    def invalid_settings():
        raise ValueError('postgresql://private_user:private_password@private_host/database')
    with pytest.raises(RuntimeError) as error:
        point_tests_at_test_db(invalid_settings, {})
    assert 'private_' not in str(error.value)
    assert error.value.__suppress_context__


def test_isolated_backend_preserves_original_target_for_child_guard(settings_type, monkeypatch, tmp_path):
    """实际隔离 recipe 传原目标，由子进程守卫切库；配置、复制源全为假件。"""
    recipe_path = Path(__file__).resolve().parents[2] / 'tools/mut/_isolated.py'
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, 'workspace_paths', SimpleNamespace(
        output=lambda *args: work, output_dir=lambda kind: work,
    ))
    spec = importlib.util.spec_from_file_location('_guard_test_isolated_recipe', recipe_path)
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    source = tmp_path / 'source'
    for name in ('app', 'tests'):
        (source / 'backend' / name).mkdir(parents=True)
    (source / 'backend/pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    monkeypatch.setattr(recipe, 'ROOT', source)
    monkeypatch.setitem(sys.modules, 'app.core.config', SimpleNamespace(
        get_settings=lambda: SimpleNamespace(database_url=DEV, test_database_url=TEST),
    ))
    with recipe.isolated_backend('guard-recipe-') as (base, env):
        assert env['DATABASE_URL'] == DEV
        assert env['TEST_DATABASE_URL'] == TEST
        assert not (base.parent / '.env').exists()
        monkeypatch.setenv('DATABASE_URL', env['DATABASE_URL'])
        monkeypatch.setenv('TEST_DATABASE_URL', env['TEST_DATABASE_URL'])
        guard = point_tests_at_test_db(settings_type, os.environ)
        assert os.environ['DATABASE_URL'] == TEST
        assert_application_targets(guard, settings_type, settings_type, None)
    assert not base.exists()


@pytest.mark.parametrize('scenario,passes', [
    ('no_config', True), ('valid', True), ('missing_test', False),
    ('same_database', False), ('cached_settings', False), ('cached_engine', False),
])
def test_conftest_checks_targets_before_loading_tests(tmp_path, scenario, passes):
    """启动真实 conftest 接线，但应用/配置全为临时假件，绝不加载真实 .env。"""
    tests = tmp_path / 'tests'
    core = tmp_path / 'app' / 'core'
    tests.mkdir()
    core.mkdir(parents=True)
    for path in (tests / '__init__.py', core / '__init__.py', core.parent / '__init__.py'):
        path.write_text('', encoding='utf-8')
    for name in ('conftest.py', 'db_guard.py'):
        shutil.copyfile(Path(__file__).with_name(name), tests / name)
    (tests / 'test_sample.py').write_text('def test_pure():\n    assert True\n', encoding='utf-8')
    config = '''from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(Path(__file__).parents[2] / '.env'))
    database_url: str = ''
    test_database_url: str = ''
@lru_cache
def get_settings():
    return Settings()
'''
    if scenario == 'cached_settings':
        config += 'get_settings()\n'
    if scenario == 'cached_engine':
        config += 'from app.core import db\n'
    (core / 'config.py').write_text(config, encoding='utf-8')
    (core / 'db.py').write_text(
        f'from types import SimpleNamespace\n_engine = SimpleNamespace(url={DEV!r})\n_session_factory = None\n',
        encoding='utf-8',
    )
    for module in ('export_bindings.py', 'core_bindings.py'):
        (core.parent / module).write_text('def register_all():\n    pass\n', encoding='utf-8')
    (tmp_path / 'pytest.ini').write_text('[pytest]\npythonpath = .\n', encoding='utf-8')
    env = {key: value for key, value in os.environ.items()
           if key.lower() not in {'database_url', 'test_database_url', 'pythonpath', 'mtrl_test_source_env'}}
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    if scenario != 'no_config':
        env['DATABASE_URL'] = TEST if scenario == 'same_database' else DEV
        if scenario != 'missing_test':
            env['TEST_DATABASE_URL'] = TEST
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', '-c', str(tmp_path / 'pytest.ini'), str(tests)],
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    if not passes:
        assert 'RuntimeError' in result.stderr


def test_explicit_source_identity_keeps_application_at_test_target(settings_type,monkeypatch,tmp_path):
    source=tmp_path/'source.env';source.write_text(f'DATABASE_URL={DEV}\nTEST_DATABASE_URL={TEST}\n',encoding='utf-8')
    monkeypatch.setenv('MTRL_TEST_SOURCE_ENV',str(source))
    monkeypatch.setenv('DATABASE_URL',TEST);monkeypatch.setenv('TEST_DATABASE_URL',TEST)
    guard=point_tests_at_test_db(settings_type,os.environ)
    assert settings_type().database_url==TEST and os.environ['DATABASE_URL']==TEST
    assert_application_targets(guard,settings_type,settings_type,None)


@pytest.mark.parametrize('declared_source,declared_test,actual',[(TEST,TEST,TEST),(DEV,TEST,DEV),(DEV,DEV,TEST)])
def test_explicit_source_rejects_same_or_wrong_target(settings_type,monkeypatch,tmp_path,declared_source,declared_test,actual):
    source=tmp_path/'source.env';source.write_text(f'DATABASE_URL={declared_source}\nTEST_DATABASE_URL={declared_test}\n',encoding='utf-8')
    monkeypatch.setenv('MTRL_TEST_SOURCE_ENV',str(source))
    monkeypatch.setenv('DATABASE_URL',actual);monkeypatch.setenv('TEST_DATABASE_URL',TEST)
    with pytest.raises(RuntimeError) as error:point_tests_at_test_db(settings_type,os.environ)
    assert 'secret' not in str(error.value)
