"""Exercise comment checks with real files, Git index contents, and worktree diffs."""

from pathlib import Path
import subprocess
import sys

import pytest


CLI = Path(__file__).resolve().parents[2] / 'tools/audit/comment_guard.py'


def git(root, *args):
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


def run_guard(root, *args, expected=0):
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(CLI), *args],
                            cwd=root, capture_output=True, encoding='utf-8', check=False)
    assert result.returncode == expected, (result.stdout, result.stderr)
    return result.stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init')
    git(tmp_path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '--allow-empty', '-m', 'Initial')
    return tmp_path


def test_python_comments_and_directives(repo):
    path = repo / 'module.py'
    path.write_text(
        '#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n'
        '"""Public contract with # inline text."""\n'
        'url = "https://host/#fragment"\n'
        '# constraint: encoding belongs to the upstream compiler\n'
        '# NOTE(external): upstream identifiers are case-sensitive\n'
        '# type: ignore[unused-ignore]\n'
        'value = 42  # noqa: F841\n'
        '# Redundant comment\n',
        encoding='utf-8',
    )
    out = run_guard(repo, '--files', path.name, expected=1)
    assert out.splitlines()[:-1] == ['module.py:9: # Redundant comment']


def test_javascript_strings_regex_jsx_and_directives(repo):
    path = repo / 'page.tsx'
    source = (
        'const url = "https://example.test/path/*fragment*/";\n'
        "const raw = 'https://example.test/there';\n"
        'const template = ' + chr(96) + 'https://host/$' + '{url}' + chr(96) + ';\n'
        'const pattern = /[//]/;\n'
        '/// <reference types="vite/client" />\n'
        '// @vite-ignore\n'
        '/* eslint-disable example */\n'
        '// 外部约束: Preserve upstream keys\n'
        '/** Public contract. */\n'
        'const view = <><a href="https://host/">https://foo.test</a>{/* Explain the markup */}</>;\n'
        'const run = () => { /* Restate the callback */ return 1; };\n'
        'const extra = ' + chr(96) + 'https://host/$' + '{1 /* Template expression comment */}' + chr(96) + ';\n'
    )
    path.write_text(source, encoding='utf-8')
    out = run_guard(repo, '--files', path.name, expected=1)
    assert out.splitlines()[:-1] == [
        'page.tsx:10: /* Explain the markup */',
        'page.tsx:11: /* Restate the callback */',
        'page.tsx:12: /* Template expression comment */',
    ]


def test_index_and_diff_check_distinct_versions_and_only_added_lines(repo):
    path = repo / 'with space.ts'
    path.write_text('// Existing comment\nexport const yes = true;\n', encoding='utf-8')
    git(repo, 'add', '--', path.name)
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'Legacy source')
    path.write_text('// Existing comment\nexport const yes = false;\n// Only in index\n', encoding='utf-8')
    git(repo, 'add', '--', path.name)
    path.write_text('// Existing comment\nexport const yes = false;\n// Only in worktree\n', encoding='utf-8')
    (repo / 'new.py').write_text('"""A docstring"""\n# Untracked comment\n', encoding='utf-8')

    staged = run_guard(repo, '--staged', expected=1)
    assert staged.splitlines()[:-1] == ['with space.ts:3: // Only in index']

    diff = run_guard(repo, '--diff', expected=1)
    assert diff.splitlines()[:-1] == [
        'with space.ts:3: // Only in worktree',
        'new.py:2: # Untracked comment',
    ]


def test_diff_tracks_only_changed_lines_inside_multiline_comment(repo):
    path = repo / 'module.mjs'
    path.write_text('/* old header\n * old line\n */\nexport const yes = true;\n', encoding='utf-8')
    git(repo, 'add', '--', path.name)
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'Legacy comment')
    path.write_text('/* old header\n * new line\n */\nexport const yes = true;\n', encoding='utf-8')
    out = run_guard(repo, '--diff', expected=1)
    assert out.splitlines()[:-1] == ['module.mjs:2: * new line']
