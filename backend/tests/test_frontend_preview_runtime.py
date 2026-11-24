"""Lifecycle guards use real OS processes; no HTTP service or business data is created."""
from contextlib import ExitStack, nullcontext
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import pytest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.dev import frontend_preview_runtime as runtime
from tools.dev import frontend_preview_server as server


@pytest.fixture
def registry(tmp_path, monkeypatch):
    directory = tmp_path / 'registry'
    monkeypatch.setattr(runtime, 'state_dir', lambda root=None: directory)
    monkeypatch.setattr(runtime, 'ROOT', tmp_path / 'master')
    return directory


def identity(pid):
    return {'pid': pid, 'created': str(pid), 'command': 'fixture preview'}


def register(directory, root, port, pid, *, legacy=False, schema=None):
    path = root / '.artifacts/active/preview/run/worktree-run/reports/real_owner.json'
    owner = dict(process=identity(pid), source_root=str(root), port=port, schema=schema or f'frontend_rewrite_397_{pid}',
                 started_at='2026-11-24T00:00:00Z', status='ready', synthetic=False, host='127.0.0.1',
                 database='mtrl_workbench_test', revision='fixture', cookie_name='fixture', index_sha256='fixture',
                 product_digest='fixture', disposable=True, preserve_schema_on_stop=False)
    runtime.write_json(path, owner)
    slot = runtime.slot_key(root)
    pointer = directory / ('current.json' if legacy else f'instances/{slot}.json')
    record = {'owner_path': str(path), 'process': owner['process']}
    if not legacy:
        record.update(source_root=str(root), port=port, slot=slot)
    runtime.write_json(pointer, record)
    return pointer, path, owner


def test_other_process_cannot_prepare_another_preview_and_crash_releases_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'state_dir', lambda root=None: tmp_path)
    path = tmp_path / 'one/reports/real_owner.json'
    script = (
        'from pathlib import Path; from tools.dev import frontend_preview_runtime as r; '
        f'r.state_dir=lambda root=None: Path({str(tmp_path)!r}); '
        f'lock=r.reserve_preview(8065, Path({str(path)!r}), schema="fixture", disposable=True); '
        'lock.__enter__(); print("locked",flush=True); input()'
    )
    process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', script], cwd=runtime.ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        assert process.stdout.readline().strip() == 'locked'
        with pytest.raises(RuntimeError, match='预览锁已被占用'):
            with runtime.reserve_preview(8066, path, schema='fixture', disposable=True):
                (tmp_path / 'must-not-prepare-database').touch()
        assert not (tmp_path / 'must-not-prepare-database').exists()
        with runtime.reserve_preview(8066, tmp_path / 'two/reports/real_owner.json',
                                     root=tmp_path / 'other-tree', schema='other', disposable=True):
            assert len(runtime.preview_inventory()[0]) == 2
    finally:
        process.kill()
        process.communicate(timeout=10)
    _, stale = runtime.preview_inventory()
    assert len(stale) == 1
    with runtime.reserve_preview(8065, path, schema='new', disposable=True):
        assert not runtime.preview_inventory()[1]


def test_same_worktree_legacy_process_blocks_and_startup_leaves_dead_legacy_pointer(registry, monkeypatch):
    pointer, path, _ = register(registry, runtime.ROOT, 8065, 123, legacy=True)
    original = pointer.read_bytes()
    monkeypatch.setattr(runtime, 'live_process', lambda owner: owner['process']['pid'] == 123)
    monkeypatch.setattr(runtime, 'process_identity', identity)
    with pytest.raises(RuntimeError, match='进程仍存活'):
        with runtime.reserve_preview(8066, path, schema='fixture', disposable=True):
            pytest.fail('Must reject before any persistent preparation')
    monkeypatch.setattr(runtime, 'live_process', lambda owner: False)
    with runtime.reserve_preview(8066, path, schema='fixture', disposable=True):
        assert pointer.read_bytes() == original
    assert pointer.read_bytes() == original


def test_prune_preserves_process_whose_command_identity_cannot_be_confirmed(registry, monkeypatch):
    pointer, path, _ = register(registry, runtime.ROOT, 8065, 41, legacy=True)
    monkeypatch.setattr(runtime, 'process_identity', lambda pid: {**identity(pid), 'command': None})
    with pytest.raises(RuntimeError, match='命令身份'):
        runtime.prune_registrations()
    assert pointer.exists() and path.exists()


def test_inventory_deduplicates_legacy_and_slot_for_same_process(registry, monkeypatch):
    pointer, path, owner = register(registry, runtime.ROOT, 8065, 41)
    runtime.write_json(registry / 'current.json', {'owner_path': str(path), 'process': owner['process']})
    monkeypatch.setattr(runtime, 'process_identity', identity)
    live, stale = runtime.preview_inventory()
    assert [entry.pointer for entry in live] == [pointer]
    assert not stale


def test_distinct_worktree_reservations_share_cap_and_report_live_legacy(registry, tmp_path, monkeypatch, capsys):
    from tools.dev import frontend_preview as cli

    legacy, _, _ = register(registry, tmp_path / 'equipment', 8065, 41, legacy=True)
    legacy_bytes = legacy.read_bytes()
    legacy_lock = registry / 'instance.lock'
    legacy_lock.write_bytes(b'old lock')
    dead, stale_owner, _ = register(registry, tmp_path / 'crashed', 8066, 42)
    pids = iter((43, 44, 45, 46))
    monkeypatch.setattr(runtime, 'os', SimpleNamespace(getpid=lambda: next(pids)))
    monkeypatch.setattr(runtime, 'process_identity', identity)
    monkeypatch.setattr(runtime, 'live_process', lambda owner: owner['process']['pid'] != 42)
    with ExitStack() as stack:
        for root, port in ((runtime.ROOT, 8066), (tmp_path / 'ledger', 8067)):
            stack.enter_context(runtime.reserve_preview(port, root / 'run/reports/real_owner.json', root=root,
                                                        schema=f'frontend_rewrite_397_{port}', disposable=True))
        assert not dead.exists() and stale_owner.exists()
        monkeypatch.setattr(sys, 'argv', ['frontend_preview.py', '--list'])
        cli.main()
        listed = capsys.readouterr().out
        assert all(text in listed for text in ('PID=41', 'PID=43', 'PID=44', 'port=8065', 'port=8066', 'port=8067'))
        with pytest.raises(RuntimeError, match='3 个上限') as denied:
            with runtime.reserve_preview(8067, tmp_path / 'fourth/owner.json', root=tmp_path / 'fourth',
                                         schema='unused', disposable=True):
                pytest.fail('Fourth reservation succeeded')
        assert all(text in str(denied.value) for text in ('equipment', 'master', 'ledger', 'PID=41', 'run=', 'started_at='))
    assert legacy.read_bytes() == legacy_bytes
    assert legacy_lock.read_bytes() == b'old lock'


def test_port_validation_and_legacy_port_conflict(registry, tmp_path, monkeypatch):
    from tools.dev import frontend_preview as cli

    monkeypatch.setattr(sys, 'argv', ['frontend_preview.py', '--port', '8068'])
    with pytest.raises(SystemExit) as invalid:
        cli.main()
    assert invalid.value.code == 2
    register(registry, tmp_path / 'equipment', 8065, 41, legacy=True)
    monkeypatch.setattr(runtime, 'process_identity', identity)
    monkeypatch.setattr(runtime, 'live_process', lambda owner: True)
    with pytest.raises(RuntimeError, match='端口已被占用'):
        with runtime.reserve_preview(8065, tmp_path / 'owner.json', schema='unused', disposable=True):
            pytest.fail('Reused legacy port')


def test_active_preview_isolates_worktrees_and_registered_build_uses_selected_root(registry, tmp_path, monkeypatch):
    import httpx

    other = tmp_path / 'equipment'
    _, old_path, old = register(registry, other, 8065, 41, legacy=True)
    _, path, owner = register(registry, runtime.ROOT, 8066, 43)
    monkeypatch.setattr(runtime, 'live_process', lambda owner: True)
    html = b'fixture preview index'
    build = old_path.parent.parent / 'work/build-old'
    build.mkdir(parents=True)
    (build / 'index.html').write_bytes(html)
    runtime.write_json(old_path.parent / 'version.json', {'build_path': str(build),
                       'files': {'index.html': hashlib.sha256(html).hexdigest()}})

    def get(url, **kwargs):
        if url.endswith('/preview'):
            return httpx.Response(200, content=html, request=httpx.Request('GET', url))
        result = old if ':8065/' in url else owner
        return httpx.Response(200, json=result, request=httpx.Request('GET', url))

    monkeypatch.setattr(httpx, 'get', get)
    assert runtime.active_preview()[0] == path
    assert runtime.active_preview(root=other)[0] == old_path
    assert runtime.registered_preview(port=8065, require_latest=False)[0] == old_path
    with pytest.raises(RuntimeError, match='没有登记'):
        runtime.active_preview(root=tmp_path / 'absent')


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


def test_stop_uses_verified_active_owner_even_with_pending_build(registry, monkeypatch):
    _, path, owner = register(registry, runtime.ROOT, 8066, 43)
    runtime.write_json(path.parent / 'version.json', {'pending_replacement': 'different-build'})
    stop = path.parent / 'stop-request.json'
    monkeypatch.setattr(runtime, '_verify_active', lambda owner: 'verified')
    monkeypatch.setattr(runtime, 'live_process', lambda owner: not stop.exists())
    monkeypatch.setattr(runtime, 'listening', lambda port: False)
    runtime.request_stop()
    assert runtime.read_json(stop) == {'process': owner['process']}


@pytest.mark.parametrize(('flags', 'expected'), [([], {43}), (['--port', '8065'], {41}), (['--all'], {41, 43})])
def test_cli_stop_selects_current_worktree_port_or_all(registry, tmp_path, monkeypatch, flags, expected):
    from tools.dev import frontend_preview as cli

    _, legacy_path, _ = register(registry, tmp_path / 'equipment', 8065, 41, legacy=True)
    _, path, _ = register(registry, runtime.ROOT, 8066, 43)
    stop_paths = {41: legacy_path.parent / 'stop-request.json', 43: path.parent / 'stop-request.json'}
    monkeypatch.setattr(runtime, '_verify_active', lambda owner: 'verified')
    monkeypatch.setattr(runtime, 'live_process', lambda owner: not stop_paths[owner['process']['pid']].exists())
    monkeypatch.setattr(runtime, 'listening', lambda port: False)
    monkeypatch.setattr(sys, 'argv', ['frontend_preview.py', '--stop', *flags])
    cli.main()
    assert {pid for pid, marker in stop_paths.items() if marker.exists()} == expected


@pytest.mark.parametrize('replace', [False, True])
def test_reservation_exit_only_clears_its_registration_and_stop_request(registry, tmp_path, monkeypatch, replace):
    path = tmp_path / 'run/reports/real_owner.json'
    monkeypatch.setattr(runtime, 'process_identity', identity)
    with runtime.reserve_preview(8066, path, schema='frontend_writable_user', disposable=False) as saved:
        pointer = registry / 'instances' / f"{saved['slot']}.json"
        owner = {'process': saved['process'], 'schema': saved['schema'], 'status': 'stopped-schema-preserved'}
        if replace:
            owner['process'] = identity(41)
            runtime.write_json(pointer, {**saved, 'process': owner['process']})
        runtime.write_json(path, owner)
        stop = path.parent / 'stop-request.json'
        runtime.write_json(stop, {'process': owner['process']})
    assert runtime.read_json(path) == owner
    assert stop.exists() == pointer.exists() == replace


@pytest.mark.parametrize('legacy_alive', [False, True])
def test_prune_reaps_dead_entries_and_protects_active_and_unowned_schemas(registry, tmp_path, monkeypatch, capsys, legacy_alive):
    from sqlalchemy.engine import make_url
    import sqlalchemy
    from tests.db_guard import TestDatabaseGuard
    from tools.dev import frontend_preview as cli

    dead_legacy, old_owner, _ = register(registry, tmp_path / 'old', 8065, 40, legacy=True)
    dead, dead_owner, _ = register(registry, tmp_path / 'crashed', 8066, 42)
    live, _, _ = register(registry, tmp_path / 'running', 8067, 43)
    live_pids = {40, 43} if legacy_alive else {43}
    monkeypatch.setattr(runtime, 'live_process', lambda owner: owner['process']['pid'] in live_pids)
    url = 'postgresql+psycopg://tester@127.0.0.1:1/mtrl_workbench_test'
    source = tmp_path / '.env'
    source.touch()
    monkeypatch.setattr(cli, 'ROOT', tmp_path)

    def verify(path):
        assert path == source
        return None, TestDatabaseGuard(url)

    monkeypatch.setattr(cli, 'verified_database_source', verify)
    schemas = {'public': 'tester', 'frontend_writable_trial': 'tester', 'frontend_rewrite_397_43': 'tester',
               'frontend_rewrite_397_40': 'tester', 'frontend_rewrite_397_42': 'tester',
               'frontend_rewrite_397_foreign': 'foreign', 'frontend_rewrite_397_"invalid': 'tester'}
    drops = []

    class Connection:
        def execute(self, query, params):
            assert 'pg_get_userbyid(nspowner) = current_user' in str(query)
            candidates = [name for name, role in schemas.items() if role == 'tester' and name.startswith(params['prefix'])]
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: candidates))

        def exec_driver_sql(self, query):
            if query == 'SELECT current_database(), current_user, session_user':
                return SimpleNamespace(one=lambda: ('mtrl_workbench_test', 'tester', 'tester'))
            drops.append(query)

    engine = SimpleNamespace(url=make_url(url), begin=lambda: nullcontext(Connection()), dispose=lambda: None)
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *args, **kwargs: engine)
    monkeypatch.setattr(sys, 'argv', ['frontend_preview.py', '--prune'])
    cli.main()
    receipt = json.loads(capsys.readouterr().out)
    removed = {dead.name} if legacy_alive else {dead.name, dead_legacy.name}
    assert set(receipt['removed_registrations']) == removed
    expected = ['frontend_rewrite_397_42'] if legacy_alive else ['frontend_rewrite_397_40', 'frontend_rewrite_397_42']
    assert receipt['dropped_schemas'] == expected
    assert drops == [f'DROP SCHEMA "{name}" CASCADE' for name in receipt['dropped_schemas']]
    assert old_owner.exists() and dead_owner.exists() and live.exists()
    assert dead_legacy.exists() == legacy_alive and not dead.exists()


@pytest.mark.parametrize('actual',['12.15.0','11.25.0'])
def test_build_uses_corepack_and_rejects_wrong_package_manager(tmp_path,monkeypatch,actual):
    root=tmp_path/'带 空格的项目';front=root/'apps/frontend';front.mkdir(parents=True)
    (front/'package.json').write_text('{"packageManager":"pnpm@12.15.0"}',encoding='utf-8')
    run=root/'.artifacts/active/build/one';build=run/'work/build'
    monkeypatch.setattr(server,'ROOT',root)
    monkeypatch.setattr(server,'product_sources',lambda **kwargs:{'input':'stable'})
    monkeypatch.setattr(server.shutil,'which',lambda name:'corepack' if name.startswith('corepack') else pytest.fail('Direct pnpm fallback is forbidden'))
    commands=[]
    def child(command,**kwargs):
        commands.append(command)
        if command[0]=='git':return SimpleNamespace(stdout='fixture\n')
        assert command[:2]==['corepack','pnpm'] and kwargs['cwd']==front
        if command[2]=='--version':
            return subprocess.CompletedProcess(command,0,actual+'\n','')
        if command[2]=='build':
            build.mkdir(parents=True);(build/'index.html').write_text('complete',encoding='utf-8')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(server.subprocess,'run',child)
    args=SimpleNamespace(run=run,prepare_build=build)
    if actual!='12.15.0':
        with pytest.raises(RuntimeError,match='pnpm版本不符'):server.prepare_build(args)
        assert len(commands)==1 and not build.exists()
    else:
        server.prepare_build(args)
        assert [c[2] for c in commands if c[0]=='corepack']==['--version','typecheck','build']
        version=runtime.read_json(run/'reports/version.json')
        assert version['package_manager']['version']==actual


def test_missing_corepack_cannot_fall_back_to_path_pnpm(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path)
    monkeypatch.setattr(server,'product_sources',lambda **kwargs:{})
    monkeypatch.setattr(server.shutil,'which',lambda name:None if name.startswith('corepack') else 'wrong-pnpm')
    run=tmp_path/'.artifacts/active/build/one'
    with pytest.raises(RuntimeError,match='未找到Corepack'):
        server.prepare_build(SimpleNamespace(run=run,prepare_build=run/'work/build'))
