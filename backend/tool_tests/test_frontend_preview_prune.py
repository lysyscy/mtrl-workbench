"""File-only frontend preview cleanup with active and stale registrations."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dev import frontend_preview as cli
from tools.dev import frontend_preview_runtime as runtime


def test_prune_files_only_preserves_live_runs_and_registry_skeleton(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    state = runtime.private_state_dir()
    monkeypatch.setattr(runtime, 'state_dir', lambda root=None: state)

    def identity(pid):
        return {'pid': pid, 'created': str(pid), 'command': 'fixture preview'}

    monkeypatch.setattr(runtime, 'process_identity', lambda pid: identity(pid) if pid == 41 else None)

    def register(name, run, pid):
        owner = tmp_path / '.artifacts/runs' / run / 'reports/real_owner.json'
        runtime.write_json(owner, {'process': identity(pid)})
        runtime.write_json(state / 'instances' / f'{name}.json',
                           {'owner_path': str(owner), 'process': identity(pid)})

    register('active', 'live', 41)
    register('alias', 'also-live', 41)
    register('dead', 'old', 42)
    for name in ('old', 'unregistered', 'live', 'also-live', 'files', 'trial', 'held'):
        env = state / name / 'runtime.env'
        env.parent.mkdir(parents=True, exist_ok=True)
        env.write_bytes(b'fixture=1' if name == 'trial' else b'')
    runtime.write_json(state / 'held/retention.json', {'hold': True})
    (state / 'slots').mkdir()
    (state / 'slots/slot.lock').touch()
    (state / 'instance.lock').touch()

    def reject_db(*_):
        raise AssertionError('file-only cleanup must not read database configuration')

    monkeypatch.setattr(cli, 'verified_database_source', reject_db)
    monkeypatch.setattr(sys, 'argv', ['frontend_preview.py', '--prune', '--files-only'])
    cli.main()
    report = json.loads(capsys.readouterr().out)
    assert report == {
        'removed_registrations': ['dead.json'],
        'removed_runtime_dirs': ['old', 'unregistered'],
        'dropped_schemas': [],
        'schema_cleanup': 'files-only',
    }
    assert set(path.name for path in state.iterdir()) == {
        'live', 'also-live', 'files', 'trial', 'held', 'instances', 'slots', 'instance.lock', 'registry.lock',
    }
    assert (state / 'instances/active.json').is_file() and (state / 'instances/alias.json').is_file()
    assert (state / 'slots/slot.lock').is_file()
    assert (state / 'trial/runtime.env').read_bytes() == b'fixture=1'

    cli.main()
    assert not json.loads(capsys.readouterr().out)['removed_runtime_dirs']
