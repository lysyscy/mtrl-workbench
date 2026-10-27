"""CLI result/cleanup contract without opening a database or starting another pytest."""
from contextlib import contextmanager
import json
import subprocess
from types import SimpleNamespace
import pytest
from tools.dev import backend_verify as runner

DEV='postgresql+psycopg://source:private@127.0.0.1:1/business'
TEST='postgresql+psycopg://test:private@127.0.0.1:1/business_test'

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    for key in ('DATABASE_URL','TEST_DATABASE_URL','MTRL_TEST_SOURCE_ENV'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    tests=tmp_path/'backend/tests';tests.mkdir(parents=True);(tests/'test_example.py').write_text('',encoding='utf-8')
    source=tmp_path/'source.env';source.write_text(f'DATABASE_URL={DEV}\nTEST_DATABASE_URL={TEST}\n',encoding='utf-8')
    def output(kind):
        path=tmp_path/kind;path.mkdir(exist_ok=True);return path
    monkeypatch.setattr(runner,'output_dir',output)
    monkeypatch.setattr(runner,'close_runs',lambda:None)
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
        return SimpleNamespace(returncode=exit_code)
    monkeypatch.setattr(runner,'isolated_database',isolated);monkeypatch.setattr(runner.subprocess,'run',child)
    code,path=runner.verify(prepared,['tests/test_example.py'])
    report=json.loads(path.read_text(encoding='utf-8'))
    assert code==exit_code and report['pytest_returncode']==exit_code and report['cleanup_completed'] is True
    assert cleaned==[True] and DEV not in path.read_text(encoding='utf-8')

def test_empty_selection_rejected_before_database(prepared,monkeypatch):
    monkeypatch.setattr(runner,'isolated_database',lambda *a,**k:pytest.fail('No test selection must not create schema'))
    with pytest.raises(ValueError):runner.verify(prepared,[])

def test_setup_failure_is_nonzero_and_not_reported_as_pytest_success(prepared,monkeypatch):
    @contextmanager
    def failed(*args,**kwargs):
        raise subprocess.CalledProcessError(3,['alembic'])
        yield
    monkeypatch.setattr(runner,'isolated_database',failed)
    code,path=runner.verify(prepared,['tests/test_example.py'])
    report=json.loads(path.read_text(encoding='utf-8'))
    assert code==3 and report['pytest_returncode'] is None and report['cleanup_completed'] is None


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
