"""Directory audit protection through the same CLI modes used in the workspace."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.audit import directory_audit as audit


def git(root, *args):
    subprocess.run(['git', '-c', 'core.autocrlf=false', *args], cwd=root, capture_output=True, check=True)


def rule(path, **fields):
    return dict(path=path, owner='fixture', git_policy='local', manager='none',
                retention='fixture', exit_condition='fixture', apply_eligible=False,
                **{'class': 'source', **fields})


def residue(path):
    return {**rule(path), 'owner': 'none', 'class': 'residue', 'apply_eligible': True}


def write_manifest(root, *rows):
    path = root / audit.MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'directories': [
        rule('.git'), rule('tools'), rule('tools/audit'), *rows,
    ]}), encoding='utf-8')


def file(root, name, content=b'fixture'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def record(root, name, data):
    return file(root, name, json.dumps(data).encode('utf-8'))


def test_staged_checks_only_added_paths_against_index_manifest(tmp_path, capsys):
    git(tmp_path, 'init', '-q')
    write_manifest(tmp_path, rule('登记目录'))
    file(tmp_path, '旧目录/drop.txt')
    git(tmp_path, 'add', '--', str(audit.MANIFEST), '旧目录/drop.txt')
    git(tmp_path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'core.hooksPath=.git/hooks', 'commit', '-qm', 'initial')
    git(tmp_path, 'rm', '--', '旧目录/drop.txt')

    file(tmp_path, 'root note.txt')
    file(tmp_path, '登记目录/中文 空格.txt')
    file(tmp_path, '未登记/untracked.txt')
    git(tmp_path, 'add', '--', 'root note.txt', '登记目录')
    assert audit.main(['--staged'], root=tmp_path) == 0

    file(tmp_path, '未知目录/staged.txt')
    git(tmp_path, 'add', '--', '未知目录')
    write_manifest(tmp_path, rule('登记目录'), rule('未知目录'))
    assert audit.main(['--staged'], root=tmp_path) == 1
    assert '未知目录 未登记' in capsys.readouterr().out

    git(tmp_path, 'add', '--', str(audit.MANIFEST))
    (tmp_path / audit.MANIFEST).write_text('not valid JSON', encoding='utf-8')
    assert audit.main(['--staged'], root=tmp_path) == 0


def test_shared_hook_can_check_a_worktree_before_manifest_adoption(tmp_path, capsys):
    canonical = tmp_path / 'main'
    write_manifest(canonical, rule('docs'))
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    git(legacy, 'init', '-q')
    file(legacy, 'docs/approved.md')
    git(legacy, 'add', '--', 'docs')
    args = ['--staged', '--worktree', str(legacy)]
    assert audit.main(args, root=canonical) == 0
    file(legacy, 'unknown/staged.txt')
    git(legacy, 'add', '--', 'unknown')
    assert audit.main(args, root=canonical) == 1
    assert 'ERROR unknown ' in capsys.readouterr().out


def test_default_audit_and_dry_run_report_drift_without_writing(tmp_path, capsys):
    write_manifest(
        tmp_path, rule('docs', check_children=True), rule('var'),
        rule('var/frontend'), {**rule('var/frontend/releases'), 'manager': 'owner release command'},
        rule('var/state'), rule('var/state/frontend-release'), rule('history', retention_groups=True),
        residue('retired'), residue('**/__pycache__'),
    )
    retired = tmp_path / 'retired'
    retired.mkdir()
    (tmp_path / 'unknown').mkdir()
    (tmp_path / 'docs/unregistered').mkdir(parents=True)
    expired = record(tmp_path, 'history/expired/retention.json', {'expires_on': '2000-01-01'})
    held = record(tmp_path, 'history/held/retention.json', {'expires_on': '2000-01-01', 'Hold': True})
    permanent = record(tmp_path, 'history/permanent/retention.json', {'expires_on': '2000-01-01', 'kind': 'permanent'})
    record(tmp_path, 'var/state/frontend-release/retention.json', {'releases': {'live': 'fixture'}})
    release = file(tmp_path, 'var/frontend/releases/orphan/index.html')
    live = file(tmp_path, 'var/frontend/releases/live/index.html')
    before = {path: path.read_bytes() for path in (expired, held, permanent, release, live)}

    assert audit.main([], root=tmp_path) == 1
    output = capsys.readouterr().out
    assert audit.main(['--dry-run'], root=tmp_path) == 1
    assert capsys.readouterr().out == output
    for rel in ('unknown', 'docs/unregistered', 'history/expired/retention.json', 'var/frontend/releases/orphan'):
        assert f'ERROR {rel} ' in output
    assert 'owner release command' in output
    assert 'RESIDUE retired ' in output
    assert all(path not in output for path in ('history/held', 'history/permanent', 'var/frontend/releases/live'))
    assert retired.is_dir()
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize('limit', ['files', 'size'])
def test_soft_threshold_is_advisory_and_protects_from_apply(tmp_path, capsys, limit):
    write_manifest(tmp_path, rule('runtime', soft_thresholds={
        'max_files': 1 if limit == 'files' else 10, 'max_mb': 0.001 if limit == 'size' else 1,
        'remediation_hint': 'Use the runtime owner',
    }), residue('runtime/empty'))
    (tmp_path / 'runtime/empty').mkdir(parents=True)
    first = file(tmp_path, 'runtime/one', b'x' * 1024)
    second = file(tmp_path, 'runtime/sub/two', b'x' * 1024)
    assert audit.main([], root=tmp_path) == 0
    assert audit.main(['--apply'], root=tmp_path) == 0
    output = capsys.readouterr().out
    assert output.count('WARN runtime ') == 2
    assert 'Use the runtime owner' in output
    assert first.exists() and second.exists() and (tmp_path / 'runtime/empty').is_dir()


def test_apply_removes_only_verified_unowned_residue(tmp_path, capsys):
    git(tmp_path, 'init', '-q')
    protected = ('data', 'exports', 'var/backups', '.artifacts/runs', 'var/frontend/releases',
                 'producer', 'held', 'permanent', 'retained-run')
    write_manifest(
        tmp_path, rule('src'), rule('var'), rule('var/frontend'), rule('.artifacts'),
        *(rule(name) if name != 'producer' else {**rule(name), 'manager': 'producer cleanup'} for name in protected),
        *(residue(f'{name}/empty') for name in protected),
        residue('retired'), residue('occupied'), residue('**/__pycache__'),
    )
    for name in (*protected, 'retired'):
        (tmp_path / (name + '/empty' if name in protected else name)).mkdir(parents=True)
    record(tmp_path, 'held/retention.json', {'hold': 'waiting', 'expires_on': '2000-01-01'})
    record(tmp_path, 'permanent/retention.json', {'permanent': True})
    record(tmp_path, 'retained-run/run.json', {'kind': 'permanent'})
    occupied = file(tmp_path, 'occupied/unique.md')
    dead = file(tmp_path, 'src/retired/__pycache__/old.cpython-314.pyc')
    live = file(tmp_path, 'src/live/__pycache__/live.cpython-314.pyc')
    file(tmp_path, 'src/live/live.py')
    tracked = file(tmp_path, 'src/tracked/__pycache__/old.cpython-314.pyc')
    git(tmp_path, 'add', '-f', '--', str(tracked.relative_to(tmp_path)))
    unknown = tmp_path / 'unknown'
    unknown.mkdir()

    assert audit.main(['--apply'], root=tmp_path) == 1
    output = capsys.readouterr().out
    assert 'REMOVED retired\n' in output
    assert 'REMOVED src/retired/__pycache__\n' in output
    assert 'Git 索引内容' in output
    assert not (tmp_path / 'retired').exists() and not dead.parent.exists()
    assert occupied.exists() and live.exists() and tracked.exists() and unknown.exists()
    assert all((tmp_path / name / 'empty').is_dir() for name in protected)
