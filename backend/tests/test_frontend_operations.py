"""Publication failures use private files and an isolated service boundary, never SCM."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops import frontend_release as release
from tools.dev import frontend_preview_runtime as runtime


def make_release(path, commit, content, *, base='/app/'):
    (path / 'assets').mkdir(parents=True)
    (path / 'index.html').write_text(f'<script src="{base}assets/app.js"></script>{content}', encoding='utf-8')
    (path / 'assets/app.js').write_text(content, encoding='utf-8')
    manifest = {'product_commit': commit, 'base': '/app/', 'frontend_sources': {'fixture': 'stable'},
                'files': {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in path.rglob('*') if p.is_file()}}
    (path / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return path


class IsolatedService:
    def __init__(self, root):
        self.root, self.state, self.pid = root, 'Running', 10
        self.calls, self.fail_starts, self.fail_stop = [], 0, False
        self.wrong_index, self.start_callback = False, None

    def info(self):
        return {'state': self.state, 'pid': self.pid, 'account': 'isolated-account'}

    validate = info

    def verify_listener(self, **kwargs):
        return {'owned': True, 'listener_pids': [self.pid]}

    def control(self, action):
        self.calls.append(action)
        if action == 'stop':
            self.state = 'Stopped'
            if self.fail_stop:
                self.fail_stop = False
                raise RuntimeError('stop returned failure after stopping')
        else:
            if self.start_callback:
                callback, self.start_callback = self.start_callback, None
                callback()
            if self.fail_starts:
                self.fail_starts -= 1
                raise RuntimeError('isolated startup failure')
            self.state = 'Running'; self.pid += 1

    def get(self, route):
        import httpx
        if self.state != 'Running':
            raise httpx.ConnectError('isolated service stopped')
        if route == '/healthz':
            return httpx.Response(200, content=b'healthy')
        selected = Path(release.FrontendPointer.value((self.root / '.env').read_bytes()))
        if route == '/app':
            body = (selected / 'index.html').read_bytes()
            if self.wrong_index and selected.name != 'previous':
                body = b'HTTP 200 from a different release'
            return httpx.Response(200, content=body)
        path = selected / route.removeprefix('/app/')
        return httpx.Response(200, content=path.read_bytes()) if path.is_file() else httpx.Response(404)


class ListenerOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = release.WindowsService(Path.cwd(), 'isolated-service', Path.cwd(), 1)

    def test_normal_listener_needs_no_http_fallback(self):
        with patch.object(release, 'powershell', return_value={'owned': True, 'listener_pids': [42]}):
            self.assertTrue(self.service.verify_listener()['owned'])

    def test_unknown_listener_state_uses_actual_http_connection(self):
        from types import SimpleNamespace
        stream = SimpleNamespace(get_extra_info=lambda key: {'client_addr': ('127.0.0.1', 32123), 'server_addr': ('127.0.0.1', 8000)}[key])
        response = SimpleNamespace(status_code=200, extensions={'network_stream': stream})
        with patch.object(release, 'powershell', side_effect=[{'owned': False, 'listener_pids': []}, {'owned': True, 'listener_pids': [42]}]) as query:
            result = self.service.verify_listener(get=lambda route: response)
        self.assertEqual(result['verification'], 'health-connection')
        self.assertIn('-RemotePort 32123', query.call_args.args[0])

    def test_healthy_connection_owned_by_another_process_is_rejected(self):
        from types import SimpleNamespace
        stream = SimpleNamespace(get_extra_info=lambda key: {'client_addr': ('127.0.0.1', 32123), 'server_addr': ('127.0.0.1', 8000)}[key])
        response = SimpleNamespace(status_code=200, extensions={'network_stream': stream})
        with patch.object(release, 'powershell', return_value={'owned': False, 'listener_pids': [99]}):
            with self.assertRaisesRegex(RuntimeError, '未归属'):
                self.service.verify_listener(get=lambda route: response)

    def test_health_without_transport_identity_is_rejected(self):
        from types import SimpleNamespace
        with patch.object(release, 'powershell', return_value={'owned': False, 'listener_pids': []}):
            with self.assertRaisesRegex(RuntimeError, '未归属'):
                self.service.verify_listener(get=lambda route: SimpleNamespace(status_code=200, extensions={}))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('MTRL_TEST_WORK')
        self.temporary = tempfile.TemporaryDirectory(prefix='release-', dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.old = make_release(self.root / 'var/frontend/releases/previous', 'a' * 40, 'previous saved release')
        self.candidate = make_release(self.root / '.artifacts/active/operation/run/work/build', 'b' * 40, 'new saved release')
        self.original = (f'TOKEN=private-before\r\nFRONTEND_APP_DIR="{self.old.as_posix()}"\r\nKEEP=保留\r\n').encode('utf-8')
        (self.root / '.env').write_bytes(self.original)
        self.service = IsolatedService(self.root)
        self.report = self.root / '.artifacts/active/operation/run/reports/deployment.json'

    def apply(self, candidate=True):
        return release.apply_release(self.root, self.service, self.service.get, self.report,
                                     candidate=self.candidate if candidate else None, wait=.01)

    def test_publish_checks_actual_resources_and_keeps_previous_release(self):
        result = self.apply()
        target = (self.root / 'var/frontend/releases' / ('b' * 12)).resolve()
        self.assertEqual(result['status'], 'loaded')
        self.assertEqual(result['assets_verified'], 1)
        self.assertEqual(self.service.calls, ['stop', 'start'])
        self.assertTrue(self.old.is_dir()); self.assertTrue(target.is_dir())
        actual = (self.root / '.env').read_bytes()
        self.assertEqual(release.POINTER.sub(b'FRONTEND_APP_DIR=', actual), release.POINTER.sub(b'FRONTEND_APP_DIR=', self.original))
        self.assertEqual(release.FrontendPointer.value(actual), target.as_posix())

    def test_restart_keeps_exact_configuration(self):
        self.assertEqual(self.apply(candidate=False)['status'], 'loaded')
        self.assertEqual((self.root / '.env').read_bytes(), self.original)

    def test_canonical_paths_keep_the_release_boundary(self):
        self.assertEqual(release.no_links(self.old, self.root.resolve()), self.old.resolve())
        with self.assertRaisesRegex(ValueError, '路径不属于指定目录'):
            release.no_links(self.candidate, self.root / 'var/frontend/releases')

    def test_corrupt_build_is_rejected_before_stopping(self):
        (self.candidate / 'assets/app.js').write_text('corrupted', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '散列'):
            self.apply()
        self.assertEqual(self.service.calls, [])
        self.assertEqual((self.root / '.env').read_bytes(), self.original)

    def test_preview_base_is_rejected_before_stopping(self):
        other = make_release(self.root / '.artifacts/active/preview/run/work/build', 'c' * 40, 'preview', base='/preview/')
        with self.assertRaisesRegex(ValueError, '基址'):
            release.apply_release(self.root, self.service, self.service.get, self.report, candidate=other)
        self.assertEqual(self.service.calls, [])

    def test_start_failure_restores_only_previous_frontend(self):
        self.service.fail_starts = 1
        with self.assertRaisesRegex(RuntimeError, 'startup failure'):
            self.apply()
        self.assertEqual((self.root / '.env').read_bytes(), self.original)
        self.assertEqual(self.service.state, 'Running')
        self.assertFalse((self.root / 'var/frontend/releases' / ('b' * 12)).exists())
        self.assertEqual(json.loads(self.report.read_text(encoding='utf-8'))['recovery'], 'previous-frontend-verified')

    def test_http_200_with_wrong_index_fails_and_restores(self):
        self.service.wrong_index = True
        with self.assertRaisesRegex(RuntimeError, '探活超时'):
            self.apply()
        self.assertEqual((self.root / '.env').read_bytes(), self.original)
        self.assertEqual(json.loads(self.report.read_text(encoding='utf-8'))['status'], 'failed')

    def test_partial_stop_failure_still_recovers_running_service(self):
        self.service.fail_stop = True
        with self.assertRaisesRegex(RuntimeError, 'after stopping'):
            self.apply()
        self.assertEqual(self.service.state, 'Running')
        self.assertEqual((self.root / '.env').read_bytes(), self.original)

    def test_recovery_preserves_an_unrelated_concurrent_edit(self):
        self.service.fail_starts = 1
        def change():
            path = self.root / '.env'
            path.write_bytes(path.read_bytes().replace(b'private-before', b'private-new'))
        self.service.start_callback = change
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual((self.root / '.env').read_bytes(), self.original.replace(b'private-before', b'private-new'))

    def test_existing_different_release_is_not_overwritten(self):
        existing = make_release(self.root / 'var/frontend/releases' / ('b' * 12), 'b' * 40, 'different content')
        with self.assertRaisesRegex(RuntimeError, '已有不同内容'):
            self.apply()
        self.assertEqual((existing / 'assets/app.js').read_text(encoding='utf-8'), 'different content')
        self.assertEqual(self.service.calls, [])

    def test_recovery_does_not_overwrite_another_frontend_selection(self):
        self.service.fail_starts = 1
        def change():
            path = self.root / '.env'
            raw = path.read_bytes()
            path.write_bytes(release.POINTER.sub(b'FRONTEND_APP_DIR=operator-selected', raw))
        self.service.start_callback = change
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(release.FrontendPointer.value((self.root / '.env').read_bytes()), 'operator-selected')
        self.assertEqual(json.loads(self.report.read_text(encoding='utf-8'))['recovery'], 'failed')

    def test_nssm_pipe_is_decoded_as_utf16_without_powershell_capture(self):
        expected = 'D:\\带空格 项目\\backend\\.venv\\Scripts\\python.exe'
        result = subprocess.CompletedProcess([], 0, (expected + '\r\n').encode('utf-16-le'), b'')
        host = release.WindowsService(self.root, 'isolated-service', self.root, 1)
        with patch.object(release.subprocess, 'run', return_value=result):
            self.assertEqual(host.setting('Application'), expected)


class BuilderReached(Exception):
    pass


class ProductInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='release-git-', dir=os.environ.get('MTRL_TEST_WORK'))
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'backend/app').mkdir(parents=True)
        (self.root / 'backend/app/kept.py').write_text('VALUE = 1\n', encoding='utf-8')
        (self.root / 'pnpm-lock.yaml').write_text('lockfileVersion: 9\n', encoding='utf-8')
        for command in [['init','-q'],['add','--','backend/app/kept.py','pnpm-lock.yaml'],['-c','user.name=Isolated test','-c','user.email=isolated@example.invalid','commit','-q','-m','fixture']]:
            subprocess.run(['git',*command],cwd=self.root,capture_output=True,encoding='utf-8',check=True)

    def prepare(self):
        with patch.object(release,'ROOT',self.root), patch.object(runtime,'ROOT',self.root), \
             patch('tools.dev.frontend_preview_server.prepare_build',side_effect=BuilderReached):
            release.prepare(self.root / '.artifacts/active/release/run')

    def test_untracked_product_input_stops_before_building(self):
        (self.root / 'backend/app/new.py').write_text('NEW = 1\n',encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError,'未提交'):
            self.prepare()

    def test_root_lock_edit_stops_before_building(self):
        (self.root / 'pnpm-lock.yaml').write_text('changed\n',encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError,'未提交'):
            self.prepare()

    def test_deleted_product_input_stops_before_building(self):
        (self.root / 'backend/app/kept.py').unlink()
        with self.assertRaisesRegex(RuntimeError,'未提交'):
            self.prepare()

    def test_staged_product_input_stops_before_building(self):
        (self.root / 'backend/app/kept.py').write_text('VALUE = 2\n',encoding='utf-8')
        subprocess.run(['git','add','--','backend/app/kept.py'],cwd=self.root,capture_output=True,encoding='utf-8',check=True)
        with self.assertRaisesRegex(RuntimeError,'未提交'):
            self.prepare()

    def test_unrelated_task_changes_do_not_block_product_preparation(self):
        (self.root / 'GLOSSARY.md').write_text('other task\n',encoding='utf-8')
        with self.assertRaises(BuilderReached):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
