"""Build/publication path contracts; temporary files only, no service or database."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops import frontend_release as release
from tools.audit import workspace_paths as paths
from tools.dev import frontend_preview_runtime as runtime
from tools.dev import frontend_preview_server as server


class RunPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='frontend-run-paths-', dir=os.environ.get('MTRL_TEST_WORK'))
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.repo = base / 'repo'
        self.repo.mkdir()
        # Consume the project's fixed lifecycle runtime, independent of personal skills.
        self.lifecycle, _ = paths._lifecycle()
        self.managed = base / 'managed'
        self.lifecycle.enroll(self.managed)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(lambda: paths.close_runs(success=False))
        self.stack.enter_context(patch.dict(os.environ, {'MTRL_LIFECYCLE_ROOT': str(self.managed)}))
        for name in ('MTRL_RUN_ID', 'MTRL_LIFECYCLE_OUTPUT', 'MTRL_EFFORT'):
            self.stack.enter_context(patch.dict(os.environ))
            os.environ.pop(name, None)
        for module in (paths, runtime, server, release):
            self.stack.enter_context(patch.object(module, 'ROOT', self.repo))

    def register(self, name='test-run', root=None):
        return Path(self.lifecycle.register(root or self.managed, name, 'frontend-release', 'isolated path regression'))

    def version(self, run):
        build = run / 'work' / 'build'
        build.mkdir(parents=True)
        (build / 'index.html').write_text('verified entry', encoding='utf-8')
        return {'build_path': str(build), 'files': {'index.html': hashlib.sha256(b'verified entry').hexdigest()}}

    def test_registered_managed_run_and_build_are_accepted(self):
        run = self.register()
        self.assertEqual(server.owned_run(run), run)
        version = self.version(run)
        self.assertEqual(runtime.verify_build(version, check_sources=False), Path(version['build_path']))
        (Path(version['build_path']) / 'index.html').write_text('tampered', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, '散列'):
            runtime.verify_build(version, check_sources=False)

    def test_legacy_active_run_remains_accepted(self):
        run = self.repo / '.artifacts/active/release/old-run'
        self.assertEqual(server.owned_run(run), run)
        version = self.version(run)
        self.assertEqual(runtime.verify_build(version, check_sources=False), Path(version['build_path']))

    def test_registered_root_and_input_may_use_windows_short_and_long_names(self):
        # Windows TEMP commonly spells Administrator as ADMINI~1. The enrollment
        # must retain its own spelling while path containment uses canonical names.
        root = Path(self.temporary.name) / 'short-managed'
        self.lifecycle.enroll(root)
        run = self.register(root=root)
        with patch.dict(os.environ, {'MTRL_LIFECYCLE_ROOT': str(root)}):
            self.assertTrue(server.owned_run(run.resolve()).samefile(run))

    def test_unregistered_and_other_project_runs_are_rejected(self):
        self.register()  # The other project deliberately uses the same group ID.
        unknown = self.managed / 'groups/missing/files'
        other = self.managed.parent / 'other-project'
        self.lifecycle.enroll(other)
        for run in (unknown, self.register(root=other), self.managed.parent / 'arbitrary'):
            with self.subTest(run=str(run)), self.assertRaises((RuntimeError, ValueError)):
                server.owned_run(run)

    def test_held_and_closed_runs_cannot_prepare_new_writes(self):
        run = self.register()
        version = self.version(run)
        self.lifecycle.hold(self.managed, 'test-run', 'failed evidence', 'review before reuse')
        with self.assertRaises((RuntimeError, ValueError)):
            server.owned_run(run)
        self.assertEqual(runtime.verify_build(version, check_sources=False), Path(version['build_path']))
        self.lifecycle.release(self.managed, 'test-run')
        self.lifecycle.close(self.managed, 'test-run')
        with self.assertRaises((RuntimeError, ValueError)):
            server.owned_run(run)
        self.assertEqual(runtime.verify_build(version, check_sources=False), Path(version['build_path']))

    def test_mismatched_registration_and_parent_escape_are_rejected(self):
        run = self.register()
        record, _, data = self.lifecycle.load(self.managed, 'test-run')
        self.lifecycle.atomic(record, {**data, 'id': 'different-run'})
        with self.assertRaises((RuntimeError, ValueError)):
            server.owned_run(run)
        with self.assertRaises((RuntimeError, ValueError)):
            server.owned_run(self.repo / '.artifacts/active/../../outside')

    def test_link_is_rejected_before_resolving_to_valid_managed_run(self):
        run = self.register()
        alias = self.repo / '.artifacts/active/release/linked-run'
        alias.parent.mkdir(parents=True)
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(run)], check=True, capture_output=True)
            self.addCleanup(alias.rmdir)
        else:
            alias.symlink_to(run, target_is_directory=True)
            self.addCleanup(alias.unlink)
        with self.assertRaises((RuntimeError, ValueError)):
            server.owned_run(alias)

    def preflight(self, explicit):
        frontend = self.repo / 'apps/frontend'
        (frontend / 'src').mkdir(parents=True)
        (frontend / 'package.json').write_text(json.dumps({'packageManager': 'pnpm@12.15.0'}), encoding='utf-8')
        (frontend / 'index.html').write_text('source entry', encoding='utf-8')
        (frontend / 'src/main.ts').write_text('export {};', encoding='utf-8')
        for command in (['init', '-q'], ['add', '--', 'apps/frontend'],
                        ['-c', 'user.name=Isolated test', '-c', 'user.email=test@example.invalid', 'commit', '-q', '-m', 'fixture']):
            subprocess.run(['git', *command], cwd=self.repo, check=True, capture_output=True)
        real_run = subprocess.run
        builds = []

        def external(command, **kwargs):
            if command[0] == 'git':
                return real_run(command, **kwargs)
            if command[-1] == '--version':
                return subprocess.CompletedProcess(command, 0, '12.15.0\n', '')
            if '--outDir' in command:
                build = Path(command[command.index('--outDir') + 1])
                (build / 'assets').mkdir(parents=True)
                (build / 'index.html').write_text('<script src="/app/assets/app.js"></script>', encoding='utf-8')
                (build / 'assets/app.js').write_text('verified bundle', encoding='utf-8')
                builds.append(build)
            return subprocess.CompletedProcess(command, 0)

        class ReadOnlyHost:
            def __init__(self, *args):
                pass
            def validate(self):
                pass

        argv = ['frontend_release.py', 'publish', '--check-only']
        if explicit:
            argv += ['--run', str(self.register())]
        # Real allocation, prepare(), prepare_build(), path checks and sealing;
        # only host queries and external package-manager execution are replaced.
        with patch.object(release, 'output_dir', side_effect=lambda kind: paths.output_dir(kind, root=self.repo)), \
             patch.object(release, 'WindowsService', ReadOnlyHost), \
             patch.object(server, 'subprocess', SimpleNamespace(run=external)), \
             patch.object(server.shutil, 'which', return_value='corepack'), \
             patch.object(sys, 'argv', argv):
            self.assertEqual(release.main(), 0)
        self.assertEqual(len(builds), 1)
        run = builds[0].parent.parent
        self.assertTrue(run.is_relative_to(self.managed))
        self.assertEqual(json.loads((run / 'reports/preflight.json').read_text(encoding='utf-8'))['status'], 'checked')
        return run

    def test_default_publication_preflight_uses_and_closes_managed_run(self):
        run = self.preflight(explicit=False)
        _, _, record = self.lifecycle.load(self.managed, run.parent.name)
        self.assertEqual(record['state'], 'closed')
        self.assertFalse((run / 'work').exists())

    def test_explicit_managed_run_survives_publication_handoff(self):
        self.preflight(explicit=True)

    def test_project_layout_publication_preserves_binding_and_releases_candidate(self):
        self.managed = self.repo / '.artifacts/runs'
        self.lifecycle.enroll(self.managed, project=self.repo)
        with patch.dict(os.environ, {'MTRL_LIFECYCLE_ROOT': str(self.managed)}):
            run = self.preflight(explicit=False)
            _, _, record = self.lifecycle.load(self.managed, run.name)
            self.assertEqual(record['state'], 'closed')
            self.assertEqual(record['operation_result'], 'success')
            self.assertEqual(record['consumers'], [])
            self.assertFalse((run / 'work').exists())


if __name__ == '__main__':
    unittest.main()
