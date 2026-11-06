"""Fingerprint and publication preflight without a build or service."""
from pathlib import Path

import pytest

from ops import frontend_release
from tools.dev import frontend_preview_runtime as runtime


WORKSPACE = 'apps/frontend/pnpm-workspace.yaml'
PATCH = 'apps/frontend/patches/grid.patch'
BROWSER_CHECK = 'tools/dev/frontend_preview_browser_check.py'


@pytest.mark.parametrize('name', [WORKSPACE, PATCH, BROWSER_CHECK])
def test_added_changed_and_deleted_inputs_invalidate_the_right_fingerprints(tmp_path, monkeypatch, name):
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    item = tmp_path / name
    item.parent.mkdir(parents=True)
    initial_frontend = runtime.product_sources(frontend_only=True)
    initial_product = runtime.product_sources()

    item.write_text('first input', encoding='utf-8')
    original_frontend = runtime.product_sources(frontend_only=True)
    original_product = runtime.product_sources()
    assert original_product.keys() - initial_product.keys() == {name}
    assert (original_frontend != initial_frontend) is (name != BROWSER_CHECK)

    item.write_text('changed input', encoding='utf-8')
    assert runtime.product_sources()[name] != original_product[name]
    assert (runtime.product_sources(frontend_only=True) != original_frontend) is (name != BROWSER_CHECK)

    item.unlink()
    assert runtime.product_sources() == initial_product
    assert runtime.product_sources(frontend_only=True) == initial_frontend


@pytest.mark.parametrize(('name', 'change'), [
    (WORKSPACE, 'modified'),
    (PATCH, 'added'),
    (BROWSER_CHECK, 'deleted'),
])
def test_release_preflight_refuses_uncommitted_declared_inputs(tmp_path, monkeypatch, name, change):
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    if change != 'deleted':
        item = tmp_path / name
        item.parent.mkdir(parents=True)
        item.write_text('uncommitted input', encoding='utf-8')

    def git(*args):
        pathspec = args[args.index('--') + 1:]
        declared = any(Path(name).is_relative_to(item) for item in pathspec)
        if not declared or change == 'added':
            return ''
        return name + '\0'

    monkeypatch.setattr(frontend_release, 'git', git)
    with pytest.raises(RuntimeError, match='尚未提交'):
        frontend_release.require_committed_product()
