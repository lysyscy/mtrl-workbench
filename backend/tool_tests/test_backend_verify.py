"""CLI result/cleanup contract without opening a database or starting another pytest."""
from contextlib import contextmanager
import json
import subprocess
from types import SimpleNamespace
import pytest
from tools.dev import backend_verify as runner
from tools.dev import frontend_preview, frontend_preview_copy, frontend_preview_server
from app.core.config import Settings

DEV='postgresql+psycopg://source:private@127.0.0.1:1/business'
TEST='postgresql+psycopg://test:private@127.0.0.1:1/business_test'

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    tmp_path=tmp_path/'带 空格的工作区';tmp_path.mkdir()
    for key in ('DATABASE_URL', 'TEST_DATABASE_URL', 'MTRL_TEST_SOURCE_ENV',
                'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
        monkeypatch.delenv(key,raising=False)
    for key in ('MTRL_EFFORT', 'MTRL_RUN_ID', 'MTRL_LIFECYCLE_OUTPUT'):
        monkeypatch.setenv(key, 'fixture')
    monkeypatch.setitem(Settings.model_config, 'env_file', tmp_path / 'default.env')
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    tests=tmp_path/'backend/tests';tests.mkdir(parents=True);(tests/'test_example.py').write_text('',encoding='utf-8')
    source=tmp_path/'source.env';source.write_text(f'DATABASE_URL={DEV}\nTEST_DATABASE_URL={TEST}\n',encoding='utf-8')
    def output(kind):
        path=tmp_path/kind;path.mkdir(exist_ok=True);return path
    monkeypatch.setattr(runner,'output_dir',output)
    monkeypatch.setattr(runner,'close_runs',lambda *,success:None)
    monkeypatch.setattr(runner,'development_run',lambda:None)
    monkeypatch.setattr(runner,'protect_run',lambda *args:None)
    monkeypatch.setattr(runner,'source_state',lambda:{'commit':'fixture','dirty':False})
    return source

@pytest.mark.parametrize('exit_code',[0,7])
def test_test_only_environment_and_exact_exit_after_cleanup(prepared,monkeypatch,exit_code):
    cleaned=[]
    @contextmanager
    def isolated(source_env,**kwargs):
        assert source_env==prepared and kwargs['preview'] is False
        try:yield {'DATABASE_URL':TEST,'TEST_DATABASE_URL':TEST,'PGOPTIONS':'-c search_path=backend_verify_fixture'}
        finally:cleaned.append(True)
    def child(command,**kwargs):
        env=kwargs['env'];assert env['DATABASE_URL']==env['TEST_DATABASE_URL']==TEST
        assert env['MTRL_TEST_SOURCE_ENV']==str(prepared)
        assert DEV not in env.values()
        temporary=runner.Path(command[command.index('--basetemp')+1])
        import tempfile
        assert temporary.is_absolute() and temporary.parent.samefile(tempfile.gettempdir())
        (temporary/'generated.txt').write_text('owned temporary output',encoding='utf-8')
        return SimpleNamespace(returncode=exit_code)
    monkeypatch.setattr(runner,'isolated_database',isolated);monkeypatch.setattr(runner.subprocess,'run',child)
    code,path=runner.verify(prepared,['tests/test_example.py'])
    report=json.loads(path.read_text(encoding='utf-8'))
    assert code==exit_code and report['pytest_returncode']==exit_code and report['cleanup_completed'] is True
    assert cleaned==[True] and DEV not in path.read_text(encoding='utf-8')
    assert report['temporary_cleanup_completed'] is True
    assert not runner.Path(report['pytest_basetemp']).exists()

def test_empty_selection_rejected_before_database(prepared,monkeypatch):
    monkeypatch.setattr(runner,'isolated_database',lambda *a,**k:pytest.fail('No test selection must not create schema'))
    with pytest.raises(ValueError):runner.verify(prepared,[])


def test_temporary_cleanup_failure_keeps_actual_test_result(prepared, monkeypatch):
    allocated = []
    real_temporary = runner.TemporaryDirectory
    def occupied(**kwargs):
        temporary = real_temporary(**kwargs)
        allocated.append(temporary)
        def fail_cleanup():
            raise PermissionError('synthetic occupied file')
        temporary.cleanup = fail_cleanup
        return temporary
    @contextmanager
    def isolated(*args, **kwargs):
        yield {'DATABASE_URL': TEST, 'PGOPTIONS': '-c search_path=backend_verify_fixture'}
    monkeypatch.setattr(runner, 'TemporaryDirectory', occupied)
    monkeypatch.setattr(runner, 'isolated_database', isolated)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    try:
        code, path = runner.verify(prepared, ['tests/test_example.py'])
        report = json.loads(path.read_text(encoding='utf-8'))
        assert code == report['pytest_returncode'] == 0
        assert report['cleanup_completed'] is True
        assert report['temporary_cleanup_completed'] is False
        assert report['temporary_cleanup_error'] == 'PermissionError'
    finally:
        for temporary in allocated:
            real_temporary.cleanup(temporary)

def test_setup_failure_is_nonzero_and_not_reported_as_pytest_success(prepared,monkeypatch):
    @contextmanager
    def failed(*args,**kwargs):
        raise subprocess.CalledProcessError(3,['alembic'])
        yield
    monkeypatch.setattr(runner,'isolated_database',failed)
    code,path=runner.verify(prepared,['tests/test_example.py'])
    report=json.loads(path.read_text(encoding='utf-8'))
    assert code==3 and report['pytest_returncode'] is None and report['cleanup_completed'] is None
    assert report['temporary_cleanup_completed'] is True


@pytest.mark.parametrize('error',[OSError('child failed'),KeyboardInterrupt()])
def test_child_failure_still_releases_owned_temporary_directory(prepared,monkeypatch,error):
    @contextmanager
    def isolated(*args,**kwargs):
        yield {'DATABASE_URL':TEST,'TEST_DATABASE_URL':TEST,'PGOPTIONS':'-c search_path=backend_verify_fixture'}
    def child(command,**kwargs):
        temporary=runner.Path(command[command.index('--basetemp')+1])
        (temporary/'partial.txt').write_text('partial',encoding='utf-8')
        raise error
    monkeypatch.setattr(runner,'isolated_database',isolated)
    monkeypatch.setattr(runner.subprocess,'run',child)
    code,path=runner.verify(prepared,['tests/test_example.py'])
    report=json.loads(path.read_text(encoding='utf-8'))
    assert code==(130 if isinstance(error,KeyboardInterrupt) else 1)
    assert report['pytest_returncode'] is None and report['temporary_cleanup_completed'] is True
    assert not runner.Path(report['pytest_basetemp']).exists()


@pytest.mark.parametrize('options',[['--maxfail','1'],['-k','fee']])
def test_option_values_are_not_test_nodes(prepared,monkeypatch,options):
    monkeypatch.setattr(runner,'isolated_database',lambda *a,**k:pytest.fail('Options alone must not create schema'))
    with pytest.raises(SystemExit) as error:
        runner.main(['--source-env',str(prepared),'--',*options])
    assert error.value.code==2


@pytest.mark.parametrize('options', [['.'], ['../../other/tests'], ['-o', 'addopts=.']])
def test_extra_collection_targets_rejected_before_database(prepared, monkeypatch, options):
    monkeypatch.setattr(runner, 'isolated_database', lambda *a, **k: pytest.fail('Invalid selection must not create schema'))
    with pytest.raises(ValueError):
        runner.verify(prepared, ['tests/test_example.py'], options)


def test_common_pytest_option_values_are_accepted():
    runner.validate_pytest_options(['-q', '-k', 'fee and not slow', '-m', 'not slow',
        '--maxfail', '1', '--tb=short', '-o', 'addopts=', '--durations=5'])


@pytest.mark.parametrize('key', ['DATABASE_URL', 'TEST_DATABASE_URL'])
def test_verify_rejects_conflicting_database_identity(prepared, monkeypatch, key):
    monkeypatch.setenv(key, 'postgresql+psycopg://other:never-echo@127.0.0.1:1/other_test')
    monkeypatch.setattr(runner, 'isolated_database', lambda *a, **k: pytest.fail('Database isolation started'))
    with pytest.raises(runner.IsolationInputError, match='身份不符') as error:
        runner.verify(prepared, ['tests/test_example.py'])
    assert 'never-echo' not in str(error.value)


def test_verify_rejects_test_database_missing_from_explicit_file(prepared, monkeypatch):
    prepared.write_text(f'DATABASE_URL={DEV}\n', encoding='utf-8')
    monkeypatch.setenv('TEST_DATABASE_URL', TEST)
    monkeypatch.setattr(runner, 'isolated_database', lambda *a, **k: pytest.fail('Database isolation started'))
    with pytest.raises(runner.IsolationInputError, match='来源文件必须包含'):
        runner.verify(prepared, ['tests/test_example.py'])


def test_verify_keeps_default_source_database_out_of_test_targets(prepared, monkeypatch):
    default = Settings.model_config['env_file']
    default.write_text(f'DATABASE_URL={TEST}\n', encoding='utf-8')
    monkeypatch.setattr(runner, 'isolated_database', lambda *a, **k: pytest.fail('Database isolation started'))
    with pytest.raises(runner.IsolationInputError, match='不同库名'):
        runner.verify(prepared, ['tests/test_example.py'])


def test_verified_database_source_preserves_credentials_for_matching_identity(prepared, monkeypatch):
    effective = TEST.replace('test:private', 'test:override')
    monkeypatch.setenv('TEST_DATABASE_URL', effective)
    source_url, guard = frontend_preview.verified_database_source(prepared)
    assert source_url == DEV
    assert guard.test_url == effective


@pytest.mark.parametrize(('key', 'value'), [
    ('PYTEST_ADDOPTS', '--noconftest tests/test_unselected.py'),
    ('PYTEST_PLUGINS', 'unexpected_plugin'),
])
def test_verify_explains_inherited_pytest_input_without_starting_isolation(prepared, monkeypatch, capsys, key, value):
    monkeypatch.setenv(key, value)
    monkeypatch.setattr(runner, 'isolated_database', lambda *a, **k: pytest.fail('Database isolation started'))
    assert runner.main(['--source-env', str(prepared), '--test', 'tests/test_example.py']) == 1
    stderr = capsys.readouterr().err
    assert key in stderr
    assert value not in stderr


@pytest.mark.parametrize('copy_source', [False, True])
def test_direct_isolation_rejects_conflict_before_database_or_copy(prepared, monkeypatch, copy_source):
    import sqlalchemy

    monkeypatch.setenv('TEST_DATABASE_URL', 'postgresql+psycopg://other:private@127.0.0.1:1/other_test')
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *a, **k: pytest.fail('Database engine created'))
    monkeypatch.setattr(frontend_preview_copy, 'source_revision', lambda *a: pytest.fail('Source accessed'))
    with pytest.raises(runner.IsolationInputError, match='身份不符'):
        with frontend_preview.isolated_database(prepared, copy_source=copy_source):
            pytest.fail('Database isolation opened')


@pytest.mark.parametrize('existing', [False, True])
def test_preview_refuses_conflicting_source_before_startup(prepared, monkeypatch, existing):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://other:private@127.0.0.1:1/other')
    monkeypatch.setattr(frontend_preview_server, 'owned_run', lambda path: path)
    monkeypatch.setattr(frontend_preview_server, 'read_json', lambda path: {})
    monkeypatch.setattr(frontend_preview_server, 'verify_build', lambda version: None)
    monkeypatch.setattr(frontend_preview_server.socket, 'socket', lambda: pytest.fail('Preview startup reached'))
    args = SimpleNamespace(run=prepared.parent, source_env=prepared, browser_notice_check=None,
                           existing=existing, copy_source=not existing, disposable=not existing)
    with pytest.raises(runner.IsolationInputError, match='身份不符'):
        frontend_preview_server.run(args)
