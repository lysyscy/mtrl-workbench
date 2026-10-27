"""Run explicit backend pytest nodes in a disposable migrated test schema."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
from tools.dev.frontend_preview import isolated_database
from tools.audit.workspace_paths import output_dir, close_runs


def source_state():
    def git(*args):
        return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
            capture_output=True, text=True, encoding='utf-8').stdout.strip()
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}


def validate_pytest_options(options: list[str]) -> None:
    """Keep collection targets explicit; accept the common local tuning options."""
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument('-q', '--quiet', action='count')
    parser.add_argument('-v', '--verbose', action='count')
    parser.add_argument('-x', '--exitfirst', action='store_true')
    parser.add_argument('-k')
    parser.add_argument('-m')
    parser.add_argument('--maxfail', type=int)
    parser.add_argument('--tb', choices=['auto', 'long', 'short', 'line', 'native', 'no'])
    parser.add_argument('--durations', type=int)
    parser.add_argument('--disable-warnings', action='store_true')
    parser.add_argument('-o', '--override-ini', action='append', default=[])
    try:
        parsed, unknown = parser.parse_known_args(options)
    except argparse.ArgumentError as exc:
        raise ValueError('pytest选项无效') from exc
    if unknown or any(value != 'addopts=' for value in parsed.override_ini):
        raise ValueError('仅支持常用pytest调节选项；所有收集目标须通过--test指定，-o仅可清空addopts')


def verify(source_env: Path, nodes: list[str], pytest_options: list[str] | None = None) -> tuple[int, Path]:
    if not nodes:
        raise ValueError('请明确提供后端测试文件或节点，不默认运行全仓')
    backend = (ROOT / 'backend').resolve()
    for node in nodes:
        path = (backend / node.split('::', 1)[0]).resolve(strict=True)
        if node.startswith('-') or not path.is_relative_to(backend):
            raise ValueError('测试节点必须位于本项目backend内')
    validate_pytest_options(pytest_options or [])
    pytest_args = [*nodes, *(pytest_options or [])]
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard, database_identity
    source_env = source_env.resolve(strict=True)
    source = Settings(_env_file=source_env)
    guard = TestDatabaseGuard.from_sources((source.database_url,), source.test_database_url)
    if not guard.test_url:
        raise ValueError('缺少明确的测试库配置')
    os.environ.setdefault('MTRL_EFFORT', 'backend-verify')
    log_path = output_dir('logs') / 'backend-verify.log'
    report_path = output_dir('reports') / 'backend-verify.json'
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'source': source_state(),
              'pytest_args': pytest_args, 'database': database_identity(guard.test_url)[2],
              'schema': None, 'pytest_returncode': None, 'cleanup_completed': None}
    code = 1
    try:
        with log_path.open('w', encoding='utf-8') as log:
            with isolated_database(source_env, preview=False, log=log) as env:
                report['schema'] = env['PGOPTIONS'].split('search_path=', 1)[1]
                # DATABASE_URL and TEST_DATABASE_URL stay at the test target from
                # process startup. Only the guard reads source identities separately.
                env['MTRL_TEST_SOURCE_ENV'] = str(source_env)
                env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ROOT / 'backend')))
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'pytest',
                    *pytest_args], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log)
                code = report['pytest_returncode'] = result.returncode
            report['cleanup_completed'] = True
    except KeyboardInterrupt:
        code = 130
        report['error'] = 'KeyboardInterrupt'
    except Exception as exc:
        code = getattr(exc, 'returncode', 1) or 1
        report['error'] = type(exc).__name__
    finally:
        report['returncode'] = code
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        close_runs()
    if not report_path.exists():
        report_path = ROOT / '.artifacts/archive' / log_path.parents[2].name / log_path.parents[1].name / 'reports/backend-verify.json'
    return code, report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env', type=Path, required=True)
    parser.add_argument('--test', dest='nodes', action='append', required=True, help='backend内测试文件/目录/节点；可重复')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    tests = args.pytest_args[1:] if args.pytest_args[:1] == ['--'] else args.pytest_args
    try:
        code, report = verify(args.source_env, args.nodes, tests)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'后端隔离验证未开始：{type(exc).__name__}', file=sys.stderr)
        return 1
    print(json.dumps({'returncode': code, 'report': str(report)}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
