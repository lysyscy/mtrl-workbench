"""Complete React publication and verified service restart, called by server_ctl.ps1."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from types import SimpleNamespace

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit.workspace_paths import close_runs, output_dir
from tools.dev.frontend_preview_runtime import product_sources, read_json, write_json

POINTER = re.compile(rb'(?m)^(?:\xef\xbb\xbf)?FRONTEND_APP_DIR[ \t]*=[^\r\n]*')
OVERRIDES = {'DATABASE_URL', 'TEST_DATABASE_URL', 'PGOPTIONS', 'PYTHONPATH',
             'FRONTEND_APP_DIR', 'FRONTEND_PREVIEW_DIR'}


def powershell(script):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-EncodedCommand', encoded],
                            capture_output=True, check=False,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(f'系统查询或标准UAC失败，退出码{result.returncode}')
    try:
        message = result.stdout.decode('utf-8-sig')
    except UnicodeDecodeError:
        message = result.stdout.decode('mbcs')
    return json.loads(message) if message.strip() else None


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def git(*arguments):
    return subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True,
                          encoding='utf-8', check=True).stdout.strip()


def no_links(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    for item in [path, *path.parents]:
        if item.is_symlink() or item.is_junction():
            raise ValueError('发布路径含链接')
        if item == root:
            break
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('路径不属于指定目录')
    return resolved


def validate_release(directory):
    directory = Path(directory).resolve(strict=True)
    manifest = read_json(directory / 'release-manifest.json')
    if not isinstance(manifest, dict):
        raise ValueError('发布清单格式不完整')
    if manifest.get('base') != '/app/' or not re.fullmatch('[0-9a-f]{40}', manifest.get('product_commit', '')):
        raise ValueError('不是完整的/app正式发布清单')
    files = manifest.get('files')
    if not isinstance(files, dict) or 'index.html' not in files:
        raise ValueError('发布清单缺少完整文件集合')
    actual = set()
    for path in directory.rglob('*'):
        no_links(path, directory)
        if path.is_file() and path.relative_to(directory).as_posix() != 'release-manifest.json':
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(files):
        raise ValueError('发布目录与文件清单不一致')
    for name, digest in files.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name or '\\' in name:
            raise ValueError('发布文件路径越界')
        path = no_links(directory / name, directory)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('发布资源散列不符')
    html = (directory / 'index.html').read_text(encoding='utf-8')
    assets = re.findall(r'(?:src|href)=["\']([^"\']*/assets/[^"\']+)["\']', html)
    if not assets or any(not item.startswith('/app/assets/') or item.removeprefix('/app/') not in files for item in assets):
        raise ValueError('前端构建基址或入口资源不符')
    return manifest


class FrontendPointer:
    """Only the frontend setting is switched or restored; private values never enter reports."""
    def __init__(self, path):
        self.path = Path(path)
        self.original = self.path.read_bytes()
        matches = list(POINTER.finditer(self.original))
        if len(matches) != 1:
            raise ValueError('须在原.env中明确配置一次FRONTEND_APP_DIR')
        self.line = matches[0].group()
        self.previous = self.value(self.original)
        self.selected = None

    @staticmethod
    def value(raw):
        return dotenv_values(stream=io.StringIO(raw.decode('utf-8-sig'))).get('FRONTEND_APP_DIR') or ''

    def write(self, raw):
        descriptor, temporary = tempfile.mkstemp(prefix='.env-frontend-', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            shutil.copymode(self.path, temporary)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def switch(self, directory):
        if self.path.read_bytes() != self.original:
            raise RuntimeError('配置在发布前变化，已保留当前配置')
        self.selected = Path(directory).as_posix()
        prefix = b'\xef\xbb\xbf' if self.line.startswith(b'\xef\xbb\xbf') else b''
        replacement = prefix + b'FRONTEND_APP_DIR=' + self.selected.encode('utf-8')
        self.write(POINTER.sub(lambda match: replacement, self.original, count=1))

    def restore(self):
        raw = self.path.read_bytes()
        if self.value(raw) != self.selected or len(list(POINTER.finditer(raw))) != 1:
            raise RuntimeError('前端配置已由其他操作者改变，请人工核对；未覆盖当前配置')
        self.write(POINTER.sub(lambda match: self.line, raw, count=1))


class WindowsService:
    def __init__(self, root, name, run, wait):
        self.root, self.name, self.run, self.wait = Path(root), name, Path(run), wait
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
            raise ValueError('服务名无法识别')

    def setting(self, name):
        result = subprocess.run([str(self.root / 'ops/nssm/nssm.exe'), 'get', self.name, name], capture_output=True)
        if result.returncode:
            raise RuntimeError(f'无法读取服务设置{name}，未执行服务操作')
        # NSSM writes UTF-16 to a pipe; PowerShell's native capture can corrupt it.
        raw = result.stdout
        return raw.decode('utf-16-le' if b'\0' in raw[:64] else 'utf-8-sig').strip().strip('\x00').strip('"')

    def info(self):
        return powershell("$ErrorActionPreference='Stop';$s=Get-CimInstance Win32_Service -Filter "
            + ps_quote("Name='" + self.name + "'")
            + ";if(!$s){throw 'Service missing'};@{state=$s.State;pid=$s.ProcessId;account=$s.StartName}|ConvertTo-Json -Compress")

    def validate(self):
        app, directory, parameters = [self.setting(key) for key in ('Application', 'AppDirectory', 'AppParameters')]
        if (Path(app).resolve() != (self.root / 'backend/.venv/Scripts/python.exe').resolve()
                or Path(directory).resolve() != (self.root / 'backend').resolve()
                or ' '.join(parameters.split()) != '-m uvicorn app.main:app --host 0.0.0.0 --port 8000'):
            raise RuntimeError('服务注册与当前正式检出不符')
        keys = {line.split('=', 1)[0].upper() for line in self.setting('AppEnvironmentExtra').splitlines() if '=' in line}
        names = ','.join(ps_quote(key) for key in sorted(OVERRIDES))
        machine = powershell(f"@({names})|Where-Object {{[Environment]::GetEnvironmentVariable($_,'Machine')}}|ConvertTo-Json -Compress")
        if keys & OVERRIDES or machine:
            raise RuntimeError('服务或机器存在数据/前端配置覆盖，请先核对实际配置来源')
        return self.info()

    def control(self, action):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(self.root / 'ops/server_ctl.ps1'), '-Action', action, '-ServiceName', self.name,
            '-RepoRoot', str(self.root), '-WaitSec', str(self.wait)], capture_output=True)
        raw = result.stdout + result.stderr
        try:
            message = raw.decode('utf-8')
        except UnicodeDecodeError:
            message = raw.decode('mbcs')
        (self.run / 'logs' / f'service-{action}.log').write_text(message, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'服务{action}失败，详见本轮日志')
        expected = 'Stopped' if action == 'stop' else 'Running'
        if self.info()['state'] != expected:
            raise RuntimeError(f'服务未达到{expected}状态')

    def verify_listener(self, *, get=None):
        def owners(selection):
            return powershell("$ErrorActionPreference='Stop';$s=Get-CimInstance Win32_Service -Filter "
                + ps_quote("Name='" + self.name + "'")
                + ";$ids=@(" + selection + "|Select-Object -ExpandProperty OwningProcess -Unique);"
                + "$owned=$false;foreach($listener in $ids){$cursor=$listener;for($i=0;$i -lt 8 -and $cursor;$i++){"
                + "if($cursor -eq $s.ProcessId){$owned=$true;break};$p=Get-CimInstance Win32_Process -Filter \"ProcessId=$cursor\";$cursor=$p.ParentProcessId}};"
                + "@{owned=$owned;listener_pids=$ids}|ConvertTo-Json -Compress")
        result = owners('Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue')
        if result['owned']:
            return result
        # Some Windows CIM providers report a listening socket as unknown (0).
        # Prove ownership of the actual HTTP connection instead of accepting health alone.
        if get is not None:
            response = get('/healthz')
            stream = response.extensions.get('network_stream')
            if response.status_code == 200 and stream is not None:
                client, server = [stream.get_extra_info(key) for key in ('client_addr', 'server_addr')]
                if client and server and client[0] == server[0] == '127.0.0.1' and server[1] == 8000:
                    result = owners('Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 '
                        + '-RemoteAddress 127.0.0.1 -RemotePort ' + str(int(client[1])) + ' -ErrorAction SilentlyContinue')
                    if result['owned']:
                        return {**result, 'verification': 'health-connection'}
        raise RuntimeError('8000监听进程未归属本次正式服务，不能确认重启完成')


def verify_http(get, manifest, wait):
    deadline = time.monotonic() + wait
    last = '尚未收到健康响应'
    while True:
        try:
            health = get('/healthz')
            if health.status_code != 200:
                raise ValueError('健康检查未通过')
            if manifest:
                response = get('/app')
                if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != manifest['files']['index.html']:
                    raise ValueError('服务尚未加载目标索引')
            break
        except (httpx.HTTPError, ValueError) as exc:
            last = type(exc).__name__ + ': ' + str(exc)
            if time.monotonic() >= deadline:
                raise RuntimeError('探活超时：' + last) from None
            time.sleep(min(.2, wait))
    if not manifest:
        return {'health_status': 200}
    assets = {name: digest for name, digest in manifest['files'].items() if name.startswith('assets/')}
    for name, digest in assets.items():
        response = get('/app/' + name)
        if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != digest:
            raise RuntimeError('实际服务资源与发布清单不符')
    if get('/app/assets/missing-release-check.js').status_code != 404:
        raise RuntimeError('缺失构建资源没有返回404')
    return {'health_status': 200, 'index_sha256': manifest['files']['index.html'], 'assets_verified': len(assets)}


@contextmanager
def release_lock(root):
    directory = no_links(Path(root) / 'var/state/frontend-release', Path(root))
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'instance.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        import msvcrt
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('另一轮正式发布或重启正在运行') from None
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def apply_release(root, service, get, report_path, *, candidate=None, wait=20):
    """File and service boundary, also exercised against an isolated service double."""
    root, report_path = Path(root).resolve(), Path(report_path)
    report = {'action': 'publish' if candidate else 'restart', 'checkpoints': [], 'status': 'failed'}
    def checkpoint(name):
        report['checkpoints'].append(name); write_json(report_path, report)
    pointer = FrontendPointer(root / '.env')
    previous = Path(pointer.previous).absolute() if pointer.previous else None
    if previous:
        no_links(previous, root / 'var/frontend/releases')
    old_manifest = validate_release(previous) if previous else None
    before = service.validate()
    if before['state'] != 'Running':
        raise RuntimeError('原正式服务未在运行，请先诊断后再决定启动')
    report.update(previous_service=before, previous_release=str(previous) if previous else None)
    new_release, created, stopped, switched = previous, False, False, False
    try:
        manifest = old_manifest
        if candidate:
            candidate = no_links(Path(candidate).absolute(), root / '.artifacts/active')
            manifest = validate_release(candidate)
            new_release = no_links(root / 'var/frontend/releases' / manifest['product_commit'][:12], root)
            if new_release.exists():
                if validate_release(new_release) != manifest:
                    raise RuntimeError('同版本发布目录已有不同内容，未覆盖')
            else:
                new_release.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(candidate, new_release)
                created = True
            checkpoint('complete-release-verified')
        report.update(release=str(new_release) if new_release else None, product_commit=manifest.get('product_commit') if manifest else None)
        stopped = True
        service.control('stop')
        checkpoint('original-service-stopped')
        if candidate:
            pointer.switch(new_release); switched = True
            checkpoint('frontend-pointer-switched')
        service.control('start')
        checkpoint('service-started')
        report.update(verify_http(get, manifest, wait))
        current = (root / '.env').read_bytes()
        if POINTER.sub(b'FRONTEND_APP_DIR=', current) != POINTER.sub(b'FRONTEND_APP_DIR=', pointer.original):
            raise RuntimeError('其他配置在操作中发生变化，已停止验收并保留当前值')
        after = service.validate()
        if after['state'] != 'Running' or after['pid'] == before['pid'] or after['account'] != before['account']:
            raise RuntimeError('重启后的服务身份不符')
        report['listener'] = service.verify_listener(get=get)
        report.update(status='loaded', service=after, finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint('actual-version-verified')
        return report
    except BaseException as exc:
        report['error'] = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
        if stopped:
            try:
                if switched:
                    if service.info()['state'] == 'Running':
                        service.control('stop')
                    pointer.restore()
                if service.info()['state'] != 'Running':
                    service.control('start')
                verify_http(get, old_manifest, wait)
                report['recovery_listener'] = service.verify_listener(get=get)
                report['recovery'] = 'previous-frontend-verified'
            except BaseException as recovery:
                report['recovery'] = 'failed'; report['recovery_error'] = type(recovery).__name__
        if created and report.get('recovery') != 'failed' and FrontendPointer.value((root / '.env').read_bytes()) != new_release.as_posix():
            no_links(new_release, root / 'var/frontend/releases')
            shutil.rmtree(new_release)
        write_json(report_path, report)
        raise


def require_committed_product():
    from tools.dev.frontend_preview_runtime import product_inputs
    roots, files = product_inputs()
    tracked = set(git('ls-files', '-z', '--', *roots, *files).split('\0'))
    if (git('diff', 'HEAD', '--name-only', '-z', '--', *roots, *files)
            or set(product_sources()) - tracked):
        raise RuntimeError('产品源码尚未提交，先固定待发布版本')


def prepare(run):
    from tools.dev.frontend_preview_server import prepare_build
    require_committed_product()
    before = product_sources()
    build = run / 'work' / ('build-app-' + uuid.uuid4().hex[:12])
    original = os.environ.get('MTRL_FRONTEND_BASE')
    os.environ['MTRL_FRONTEND_BASE'] = '/app/'
    try:
        prepare_build(SimpleNamespace(run=run, prepare_build=build))
    finally:
        if original is None: os.environ.pop('MTRL_FRONTEND_BASE', None)
        else: os.environ['MTRL_FRONTEND_BASE'] = original
    if before != product_sources():
        raise RuntimeError('构建期间产品输入已变化')
    version = read_json(run / 'reports/version.json')
    manifest = {'product_commit': version['source_commit'], 'base': '/app/', 'files': version['files'],
                'frontend_sources': version['frontend_sources'], 'product_sources': before}
    write_json(build / 'release-manifest.json', manifest)
    validate_release(build)
    return build


def elevate(arguments):
    command = subprocess.list2cmdline([*arguments])
    script = ("$ErrorActionPreference='Stop';$p=Start-Process -FilePath " + ps_quote(sys.executable)
              + ' -ArgumentList ' + ps_quote(command) + ' -Verb RunAs -WindowStyle Hidden -Wait -PassThru;'
              + '@{returncode=$p.ExitCode}|ConvertTo-Json -Compress')
    return int(powershell(script)['returncode'])


def outcome(code, run, **details):
    close_runs()
    if not run.exists():
        run = ROOT / '.artifacts/archive' / run.relative_to(ROOT / '.artifacts/active')
    print(json.dumps({**details, 'run': str(run)}, ensure_ascii=False))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['publish', 'restart'])
    parser.add_argument('--service-name', default='mtrl-workbench-server')
    parser.add_argument('--wait-sec', type=int, default=20)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--run', type=Path)
    parser.add_argument('--candidate', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--elevated', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.wait_sec <= 120:
        parser.error('等待秒数须在1至120之间')
    os.environ.setdefault('MTRL_EFFORT', 'frontend-release')
    run = no_links(args.run, ROOT / '.artifacts/active') if args.run else output_dir('reports').parent
    for kind in ('logs', 'reports', 'work'): (run / kind).mkdir(parents=True, exist_ok=True)
    try:
        host = WindowsService(ROOT, args.service_name, run, args.wait_sec)
        host.validate()
        candidate = args.candidate or (prepare(run) if args.action == 'publish' else None)
        if not candidate:
            pointer = FrontendPointer(ROOT / '.env')
            if pointer.previous:
                directory = no_links(Path(pointer.previous), ROOT / 'var/frontend/releases')
                current = validate_release(directory)
                if current.get('frontend_sources') != product_sources(frontend_only=True):
                    raise RuntimeError('前端源码已变化，请使用publish构建并加载完整资源')
        if candidate:
            require_committed_product()
            manifest = validate_release(candidate)
            if manifest.get('product_sources') != product_sources() or manifest['product_commit'] != git('rev-parse', 'HEAD'):
                raise RuntimeError('待发布候选与当前固定产品输入不符')
        if args.check_only:
            write_json(run / 'reports/preflight.json', {'status': 'checked', 'action': args.action,
                'source_commit': git('rev-parse', 'HEAD'), 'candidate': str(candidate) if candidate else None})
            return outcome(0, run, status='checked')
        if not ctypes.windll.shell32.IsUserAnAdmin():
            if args.elevated: raise RuntimeError('未取得管理员权限，未执行服务操作')
            command = ['-B', '-X', 'utf8', str(Path(__file__).resolve()), args.action,
                       '--service-name', args.service_name, '--wait-sec', str(args.wait_sec), '--run', str(run), '--elevated']
            if candidate: command += ['--candidate', str(candidate)]
            code = elevate(command)
            if code == 0:
                report = read_json(run / 'reports/deployment.json')
                return outcome(0, run, status=report['status'], product_commit=report['product_commit'])
            return outcome(code, run, status='failed')
        with release_lock(ROOT), httpx.Client(base_url='http://127.0.0.1:8000', timeout=3) as client:
            report = apply_release(ROOT, host, client.get, run / 'reports/deployment.json', candidate=candidate, wait=args.wait_sec)
        return outcome(0, run, status=report['status'], product_commit=report['product_commit'])
    except Exception as exc:
        reason = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
        write_json(run / 'reports/failure.json', {'status': 'failed', 'reason': reason})
        return outcome(1, run, status='failed', reason=reason)


if __name__ == '__main__':
    raise SystemExit(main())
