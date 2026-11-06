"""Offline Git fixtures: exit evidence must preserve unsaved state and fail visibly."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


spec = importlib.util.spec_from_file_location('worktree_check', Path(__file__).resolve().parents[2] / 'tools/audit/worktree_check.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def run(root, *args):
    result = subprocess.run(['git', '-c', 'core.longpaths=true', *args], cwd=root, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    return result.stdout


@pytest.fixture
def repo(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('wt')
    root = tmp_path / 'repo'
    root.mkdir()
    run(root, 'init', '-b', 'master')
    run(root, 'config', 'user.email', 'fixture@example.invalid')
    run(root, 'config', 'user.name', 'Fixture')
    (root / '.gitignore').write_text('cache/\n', encoding='utf-8')
    (root / 'source.txt').write_text('saved\n', encoding='utf-8')
    run(root, 'add', '.gitignore', 'source.txt')
    run(root, 'commit', '-m', 'fixture')
    tree = tmp_path / '任务 tree'
    run(root, 'worktree', 'add', '-b', 'task', str(tree))
    return root, tree


def test_merged_head_does_not_hide_unsaved_ignored_or_staged_state(repo, monkeypatch, capsys):
    root, tree = repo
    run(tree, 'mv', 'source.txt', '改名 source.txt')
    (tree / '改名 source.txt').write_text('unsaved\n', encoding='utf-8')
    (tree / 'new.txt').write_text('unique\n', encoding='utf-8')
    (tree / 'cache').mkdir()
    (tree / 'cache/private.txt').write_bytes(b'private original\n')
    git_dir = Path(checker.text(tree, 'rev-parse', '--absolute-git-dir'))
    before = {p: p.read_bytes() for p in [git_dir / 'index', tree / '改名 source.txt', tree / 'new.txt', tree / 'cache/private.txt']}
    monkeypatch.setattr(checker, 'process_references', lambda paths: {'checked': True, 'matches': []})
    assert checker.main(['--root', str(root), '--worktree', str(tree)]) == 0
    result = json.loads(capsys.readouterr().out)
    entry = result['worktrees'][0]
    assert entry['head_in_base'] is True
    assert {item['path'] for item in entry['changes']} == {'改名 source.txt', 'new.txt'}
    renamed = next(item for item in entry['changes'] if item['status'] == 'RM')
    assert renamed['source'] == 'source.txt'
    assert entry['ignored'][0]['files'] == 1
    assert entry['ignored'][0]['bytes'] == len(b'private original\n')
    assert result['base']['remote_verified'] is False
    assert before == {p: p.read_bytes() for p in before}


def test_unmerged_commit_and_active_consumer_remain_visible(repo, monkeypatch, capsys):
    root, tree = repo
    (tree / 'source.txt').write_text('new commit\n', encoding='utf-8')
    run(tree, 'add', 'source.txt')
    run(tree, 'commit', '-m', 'not integrated')
    monkeypatch.setattr(checker, 'process_references', lambda paths: {'checked': True, 'matches': [{'worktree': str(tree), 'pid': 123}]})
    pointer = root / 'var/state/react-writable-preview/current.json'
    pointer.parent.mkdir(parents=True)
    pointer.write_text(json.dumps({'owner_path': str(tree / 'owner.json')}), encoding='utf-8')
    assert checker.main(['--root', str(root)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['worktrees'][0]['head_in_base'] is False
    assert result['process_commands']['matches'][0]['pid'] == 123
    assert result['preview_registration']['present'] is True
    assert tree.is_dir()


def test_unavailable_process_scan_and_corrupt_preview_are_not_success(repo, monkeypatch, capsys):
    root, _ = repo
    pointer = root / 'var/state/react-writable-preview/current.json'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('broken', encoding='utf-8')
    monkeypatch.setattr(checker, 'process_references', lambda paths: {'checked': False, 'error': 'access denied'})
    assert checker.main(['--root', str(root)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert not result['scan_complete']
    assert 'error' in result['preview_registration']


def test_junction_inventory_does_not_traverse_shared_target(tmp_path):
    shared = tmp_path / 'shared'
    shared.mkdir()
    (shared / 'keep.txt').write_bytes(b'preserve')
    link = tmp_path / 'dependency'
    import os
    if os.name == 'nt':
        subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(shared)], check=True, capture_output=True)
    else:
        link.symlink_to(shared, target_is_directory=True)
    try:
        result = checker.inventory(link)
        assert result['files'] == 0
        assert len(result['links']) == 1
        assert (shared / 'keep.txt').read_bytes() == b'preserve'
    finally:
        if os.name == 'nt':
            link.rmdir()
        else:
            link.unlink()


def test_missing_inventory_and_unknown_or_primary_worktree_fail(repo, capsys):
    root, tree = repo
    assert checker.inventory(tree / 'missing')['errors']
    for target in [root, tree / 'not-a-worktree']:
        assert checker.main(['--root', str(root), '--worktree', str(target)]) == 2
        assert not json.loads(capsys.readouterr().out)['scan_complete']


def test_windows_reserved_filename_is_literal_file(tmp_path):
    import os
    path = tmp_path / 'nul'
    native = Path('\\\\?\\' + str(path)) if os.name == 'nt' else path
    native.write_bytes(b'not a device')
    try:
        result = checker.inventory(path)
        assert not result['errors']
        assert result['files'] == 1
        assert result['bytes'] == 12
    finally:
        native.unlink()


def test_assume_unchanged_does_not_look_like_unqualified_clean_state(repo, monkeypatch, capsys):
    root, tree = repo
    run(tree, 'update-index', '--assume-unchanged', 'source.txt')
    (tree / 'source.txt').write_bytes(b'local original')
    monkeypatch.setattr(checker, 'process_references', lambda paths: {'checked': True, 'matches': []})
    assert checker.main(['--root', str(root)]) == 0
    entry = json.loads(capsys.readouterr().out)['worktrees'][0]
    assert entry['hidden_index_flags'] == ['h source.txt']
    assert (tree / 'source.txt').read_bytes() == b'local original'
