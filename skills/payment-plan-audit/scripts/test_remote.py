"""Portable-client contract checks; no database or production login."""
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.parse import parse_qs
from zipfile import ZipFile

import pytest

from remote import call, login, origin


@contextmanager
def server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((self.path, raw, self.headers.get('Cookie')))
            if self.path == '/m15/login':
                form = parse_qs(raw.decode())
                ok = form.get('account') == ['测试'] and form.get('password') == ['test-only']
                self.send_response(303 if ok else 200)
                if ok:
                    self.send_header('Set-Cookie', 'mw_session=test-cookie; HttpOnly; Path=/')
                    self.send_header('Location', '/app')
                self.end_headers()
                return
            self.do_GET()

        def do_GET(self):
            if self.headers.get('Cookie') != 'mw_session=test-cookie':
                self.send_response(401)
                self.end_headers()
                return
            if self.path == '/redirect':
                self.send_response(303)
                self.send_header('Location', 'http://127.0.0.1:1/never-send-cookie')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'schema': 1, 'ok': True}).encode())

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}', seen
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_login_reuses_cookie_without_password_and_rejects_redirect_or_wrong_server(tmp_path):
    profile = tmp_path/'session.json'
    with server() as (url, seen):
        login(url, '测试', 'test-only', profile)
        stored = profile.read_text()
        assert 'test-only' not in stored and 'cookie' in stored
        assert call('/snapshot', session_file=profile)['ok']
        assert call('/methods', session_file=profile, data={'preview_json': '中文'})['ok']
        assert json.loads(seen[-1][1]) == {'preview_json': '中文'}
        assert seen[-1][2] == 'mw_session=test-cookie'
        with pytest.raises(ValueError, match='未跟随跳转'):
            call('/redirect', session_file=profile)
        with pytest.raises(ValueError, match='另一个系统'):
            call('/snapshot', server='http://127.0.0.1:1', session_file=profile)
        with pytest.raises(ValueError, match='登录未成功'):
            login(url, '测试', 'wrong', profile)
        assert profile.read_text() == stored
        profile.write_text(json.dumps({'server': url, 'cookie': 'invalid'}))
        with pytest.raises(ValueError, match='登录已失效'):
            call('/snapshot', session_file=profile)


@pytest.mark.parametrize('url', ['ftp://host', 'http://user:pass@host', 'http://host/app', 'http://host/?password=secret'])
def test_server_address_rejects_credentials_and_wrong_paths(url):
    with pytest.raises(ValueError):
        origin(url)


def test_packaged_rules_match_canonical_and_run_without_repo_or_database(tmp_path):
    skill = Path(__file__).resolve().parents[1]
    repo = skill.parents[1]
    with ZipFile(skill/'resources/audit-runtime.zip') as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for path, digest in manifest.items():
            assert sha256((repo/'backend'/path).read_bytes()).hexdigest() == digest
        assert not any('db.py' in name or 'config.py' in name for name in archive.namelist())
    program = '''
import sys
sys.path.insert(0, sys.argv[1])
from snapshot import configure
configure()
from app.core.money import to_money
from app.mod04_plan.domain import audit_rows, NoticeAmounts
from decimal import Decimal
assert to_money('1.235') == Decimal('1.24')
assert audit_rows([dict(doc_no='A', flow_amount='100', planned_amount='10', year_month='2026-10')],
                  {'A': NoticeAmounts('A', Decimal('100'), Decimal('20'))}) == ['完全匹配']
assert 'sqlalchemy' not in sys.modules and 'app.core.config' not in sys.modules
'''
    subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', program, str(skill/'scripts')],
                   cwd=tmp_path, check=True, capture_output=True, text=True, encoding='utf-8')


def test_method_client_preserves_windows_preview_bytes_and_bound_receipt(tmp_path, monkeypatch):
    import methods
    source = tmp_path/'plan.xlsx'
    source.write_bytes(b'unchanged-source')
    preview = dict(schema=1, source=str(source), source_sha256=sha256(source.read_bytes()).hexdigest(),
                   changes=[dict(id=1, bill_no='A', ownership_id=1, source_row=4, old='', new='承兑',
                                 approved='100', paid='0', flow_amount='100', planned_amount='10')])
    file = tmp_path/'preview.json'
    file.write_bytes(json.dumps(preview, ensure_ascii=False, indent=2).replace('\n', '\r\n').encode())
    digest = sha256(file.read_bytes()).hexdigest()
    receipt = tmp_path/'receipt.json'

    def remote_call(path, **kwargs):
        assert path == '/api/m03/plan-audit/methods'
        data = kwargs['data']
        assert sha256(data['preview_json'].encode()).hexdigest() == data['approved_sha256'] == digest
        return dict(status='committed', count=1, preview_sha256=digest, source_sha256=preview['source_sha256'])

    monkeypatch.setattr(methods, 'call', remote_call)
    monkeypatch.setattr(sys, 'argv', ['methods.py', '--preview', str(file), '--approved-sha256', digest,
                                    '--receipt', str(receipt)])
    methods.main()
    assert json.loads(receipt.read_text(encoding='utf-8'))['status'] == 'committed'


def test_distributable_excludes_development_data_and_runs_unpacked(tmp_path, monkeypatch):
    import importlib.util
    import shutil

    skill = Path(__file__).resolve().parents[1]
    repo = skill.parents[1]
    spec = importlib.util.spec_from_file_location('plan_skill_builder', repo/'tools/oneoff/_build_plan_audit_runtime.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = tmp_path/'payment-plan-audit'
    shutil.copytree(skill, source, ignore=shutil.ignore_patterns('__pycache__'))
    (source/'.env').write_text('NO_REAL_CREDENTIALS')
    (source/'private-plan.xlsx').write_bytes(b'test-only workbook')
    package = tmp_path/'release/payment-plan-audit.skill'
    monkeypatch.setattr(builder, 'SKILL', source)
    monkeypatch.setattr(builder, 'PACKAGE', package)
    builder.build_package()
    payload = package.read_bytes()
    with ZipFile(package) as archive:
        expected = {'payment-plan-audit/'+name for name in (
            'SKILL.md', 'references/maintenance.md', 'references/payment-methods.md', 'resources/audit-runtime.zip',
            'scripts/annotate.py', 'scripts/audit.py', 'scripts/methods.py',
            'scripts/projects.py', 'scripts/remote.py', 'scripts/snapshot.py')}
        assert set(archive.namelist()) == expected
        assert all(archive.read(name) == (source/Path(name).relative_to('payment-plan-audit')).read_bytes()
                   for name in expected)
        archive.extractall(tmp_path/'unpacked')
    builder.build_package()
    assert package.read_bytes() == payload
    program = """
import sys
sys.path.insert(0, sys.argv[1])
from snapshot import configure
configure()
from app.core.money import to_money
from decimal import Decimal
assert to_money('1.235') == Decimal('1.24')
assert 'sqlalchemy' not in sys.modules and 'app.core.config' not in sys.modules
"""
    subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', program,
                    str(tmp_path/'unpacked/payment-plan-audit/scripts')],
                   cwd=tmp_path, check=True, capture_output=True, text=True, encoding='utf-8')
    (source/'SKILL.md').unlink()
    with pytest.raises(FileNotFoundError):
        builder.build_package()
    assert package.read_bytes() == payload
