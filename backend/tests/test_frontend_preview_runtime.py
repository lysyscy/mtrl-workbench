"""Lifecycle guards use real OS processes; no HTTP service or business data is created."""
from pathlib import Path
import os
import subprocess
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.dev import frontend_preview_runtime as runtime


def test_other_process_cannot_prepare_another_preview_and_crash_releases_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'state_dir', lambda: tmp_path)
    script = "from pathlib import Path; from tools.dev import frontend_preview_runtime as r; r.state_dir=lambda:Path(" + repr(str(tmp_path)) + "); " + "lock=r.exclusive_preview(); lock.__enter__(); print('locked',flush=True); input()"
    process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', script], cwd=runtime.ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        assert process.stdout.readline().strip() == 'locked'
        with pytest.raises(RuntimeError, match='占用唯一实例'):
            with runtime.exclusive_preview():
                (tmp_path / 'must-not-prepare-database').touch()
        assert not (tmp_path / 'must-not-prepare-database').exists()
    finally:
        process.kill()
        process.communicate(timeout=10)
    with runtime.exclusive_preview():
        pass


def test_alive_registered_process_blocks_even_when_not_holding_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'state_dir', lambda: tmp_path)
    owner = tmp_path / 'owner.json'
    runtime.write_json(owner, {'process':runtime.process_identity(os.getpid())})
    runtime.write_json(tmp_path / 'current.json', {'owner_path':str(owner)})
    with pytest.raises(RuntimeError, match='进程仍存活'):
        with runtime.exclusive_preview():
            pytest.fail('Must reject before any persistent preparation')
    data = runtime.read_json(owner)
    data['process']['created'] += '-stale'
    runtime.write_json(owner, data)
    with runtime.exclusive_preview():
        pass


def test_retired_uvicorn_factory_cannot_create_another_preview():
    import uvicorn
    with pytest.raises(SystemExit):
        uvicorn.Config('tools.dev.frontend_preview:create_preview_app',factory=True).load()


@pytest.mark.parametrize(('url','copy_source'),[
    ('postgresql+psycopg://unused@127.0.0.1:1/mtrl_workbench',False),
    ('postgresql+psycopg://unused@127.0.0.1:1/mtrl_workbench_test',True),
])
def test_direct_test_dsn_rejects_before_database_connection(url,copy_source):
    from tools.dev.frontend_preview import isolated_database
    with pytest.raises(RuntimeError,match='直接测试DSN'):
        with isolated_database(test_url=url,copy_source=copy_source):
            pytest.fail('Invalid test DSN reached database preparation')


def test_cached_disposable_permission_cannot_follow_changed_or_user_preview():
    original=dict(process={'pid':1,'created':'one','command':'preview'},schema='frontend_rewrite_397_owned',
        database='mtrl_workbench_test',revision='current',cookie_name='private',product_digest='source',
        index_sha256='build',disposable=True,preserve_schema_on_stop=False,synthetic=False)
    runtime.assert_same_preview(original,dict(original),disposable=True)
    replacement={**original,'process':{'pid':2,'created':'two','command':'preview'}}
    with pytest.raises(RuntimeError,match='实例已切换'):
        runtime.assert_same_preview(original,replacement,disposable=True)
    user_copy={**original,'disposable':False,'preserve_schema_on_stop':True}
    with pytest.raises(RuntimeError,match='用户试用数据'):
        runtime.assert_same_preview(original,user_copy,disposable=True)


def test_html_entry_is_a_build_input(tmp_path,monkeypatch):
    monkeypatch.setattr(runtime,'ROOT',tmp_path)
    html=tmp_path/'apps/frontend/index.html';html.parent.mkdir(parents=True);html.write_text('entry one',encoding='utf-8')
    before=runtime.product_sources(frontend_only=True)
    html.write_text('entry two',encoding='utf-8')
    assert before['apps/frontend/index.html']!=runtime.product_sources(frontend_only=True)['apps/frontend/index.html']


def test_stop_uses_verified_active_owner_even_with_pending_build(tmp_path,monkeypatch):
    owner={'process':{'pid':123,'created':'recorded','command':'preview'},'port':8065}
    path=tmp_path/'reports/real_owner.json'
    runtime.write_json(path,owner)
    runtime.write_json(path.parent/'version.json',{'pending_replacement':'different-build'})
    monkeypatch.setattr(runtime,'active_preview',lambda:(path,owner,'http://127.0.0.1:8065'))
    monkeypatch.setattr(runtime,'registered_preview',lambda **kwargs:(_ for _ in ()).throw(RuntimeError('Pending build differs')))
    monkeypatch.setattr(runtime,'live_process',lambda value:False)
    monkeypatch.setattr(runtime,'listening',lambda port:False)
    runtime.request_stop()
    assert runtime.read_json(path.parent/'stop-request.json')=={'process':owner['process']}
