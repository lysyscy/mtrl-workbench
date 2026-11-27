"""Build and run the existing full application on an owned real database copy."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import uuid

from tools.dev.frontend_preview_runtime import (ALLOWED_PREVIEW_PORTS, DISPOSABLE_SCHEMA_PREFIX, ROOT,
    product_sources, read_json, reserve_preview, validate_port, verify_build, write_json)
from tools.audit.workspace_paths import owned_run as validate_run, owned_work, consume_run, attach_run


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env', type=Path)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--port', type=int, choices=ALLOWED_PREVIEW_PORTS)
    parser.add_argument('--copy-source', action='store_true')
    parser.add_argument('--existing', action='store_true')
    parser.add_argument('--upgrade-existing', action='store_true')
    parser.add_argument('--disposable', action='store_true')
    command = parser.add_mutually_exclusive_group()
    command.add_argument('--prepare-build', type=Path)
    command.add_argument('--stop', action='store_true')
    command.add_argument('--list', action='store_true')
    command.add_argument('--prune', action='store_true')
    parser.add_argument('--all', action='store_true', help='停止所有工作树的预览，需与 --stop 一起使用')
    parser.add_argument('--pg-bin', type=Path, help='既有匹配PostgreSQL工具目录，仅已有副本升级需要')
    parser.add_argument('--browser-notice-check', type=Path,
                        help='单独获批后使用：本run/work内的月份/站点/账号范围文件，仅新建disposable副本')
    args = parser.parse_args()
    if args.all and (not args.stop or args.port is not None):
        parser.error('--all 仅用于 --stop，且不能与 --port 一起使用')
    if args.port is not None and (args.list or args.prune):
        parser.error('--list 和 --prune 作用于全部端口，不能指定 --port')
    return args


def prepare_build(args):
    with consume_run(args.run, root=ROOT):
        return _prepare_build(args)


def _prepare_build(args):
    run = owned_run(args.run)
    build = owned_work(args.prepare_build, root=ROOT, writing=True)
    if not build.is_relative_to(run / 'work') or build.exists():
        raise RuntimeError('新构建必须位于本run/work且不能覆盖已有资源')
    before = product_sources(frontend_only=True)
    executable = shutil.which('corepack.cmd') or shutil.which('corepack')
    if not executable:
        raise RuntimeError('未找到Corepack，不能核验项目声明的pnpm')
    declaration = json.loads((ROOT / 'apps/frontend/package.json').read_text(encoding='utf-8'))['packageManager']
    if not declaration.startswith('pnpm@'):
        raise RuntimeError('前端packageManager须声明pnpm版本')
    expected = declaration.removeprefix('pnpm@').split('+', 1)[0]
    command = [executable, 'pnpm']
    probe = subprocess.run([*command, '--version'], cwd=ROOT / 'apps/frontend',
        capture_output=True, encoding='utf-8')
    version_log = run / 'logs/package-manager.log'
    version_log.parent.mkdir(parents=True, exist_ok=True)
    version_log.write_text(probe.stdout + probe.stderr, encoding='utf-8')
    probe.check_returncode()
    actual = probe.stdout.strip()
    if actual != expected:
        raise RuntimeError(f'pnpm版本不符：声明{expected}，实际{actual}')
    for invocation, name in [([*command, 'typecheck'], 'typecheck.log'),
                             ([*command, 'build', '--outDir', str(build)], 'build.log')]:
        log = run / 'logs' / name
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8') as stream:
            subprocess.run(invocation, cwd=ROOT / 'apps/frontend', stdout=stream, stderr=stream, check=True)
    if before != product_sources(frontend_only=True):
        raise RuntimeError('构建期间前端输入变化，不能登记为最新构建')
    files = {p.relative_to(build).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in build.rglob('*') if p.is_file()}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                              encoding='utf-8', check=True).stdout.strip()
    write_json(run / 'reports/version.json', dict(build_path=str(build), files=files,
        index_sha256=files['index.html'], frontend_sources=before, source_commit=revision,
        package_manager=dict(declaration=declaration, version=actual, corepack=executable),
        diagnostic_instrumentation=False, prepared_at=datetime.now(timezone.utc).isoformat()))


def owned_run(path):
    return validate_run(path, root=ROOT, writing=True)


def existing_environment(args, run, guard):
    from tools.dev.frontend_preview import migrate
    from tools.dev.frontend_preview_copy import schema_fingerprints, schema_columns
    from sqlalchemy import create_engine, text
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    owner = read_json(run / 'reports/real_owner.json')
    schema = owner['schema']
    if (not owner.get('preserve_schema_on_stop') or owner.get('read_only') is not False or owner['database'] != 'mtrl_workbench_test'
            or not schema.startswith('frontend_writable_') or not schema.replace('_', '').isalnum()):
        raise RuntimeError('该记录不是已登记的用户试用副本')
    env = os.environ.copy()
    env.update(DATABASE_URL=guard.test_url, TEST_DATABASE_URL=guard.test_url,
               PGOPTIONS=f'-c search_path={schema}', MTRL_PREVIEW_COPY_SOURCE='1')
    engine = create_engine(guard.test_url, connect_args={'options': env['PGOPTIONS']}, hide_parameters=True)
    try:
        with engine.connect() as connection:
            actual = connection.exec_driver_sql("SELECT current_database(),current_schema(),current_setting('search_path')").one()
            role = connection.execute(text('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=:s'), {'s':schema}).scalar_one()
            revision = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
            if tuple(actual) != ('mtrl_workbench_test', schema, schema) or role != owner['owner'] or revision != owner['revision']:
                raise RuntimeError('试用副本数据库、所有权或版本不符')
        config = Config(str(ROOT / 'backend/alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'backend/alembic'))
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        if revision != head:
            if not args.upgrade_existing or revision not in {node.revision for node in script.iterate_revisions(head, 'base')}:
                raise RuntimeError('副本须经明确目标升级；未知版本或迁移分叉拒绝')
            # A private schema-only dump protects trial edits. Never recopy production.
            executable = str(args.pg_bin / ('pg_dump.exe' if sys.platform == 'win32' else 'pg_dump')) if args.pg_bin else shutil.which('pg_dump')
            if not executable:
                raise RuntimeError('缺少已有pg_dump恢复能力，未迁移用户副本')
            from sqlalchemy.engine import make_url
            url = make_url(guard.test_url)
            recovery = run / 'recovery' / ('before-' + head + '.dump')
            recovery.parent.mkdir(parents=True, exist_ok=True)
            if recovery.exists():
                raise RuntimeError('升级恢复点已存在，先核原运行结果，不能覆盖')
            dump_env = os.environ.copy()
            dump_env['PGPASSWORD'] = url.password or ''
            subprocess.run([executable, '--no-password', '--host', url.host, '--port', str(url.port or 5432),
                '--username', url.username, '--dbname', url.database, '--schema', schema,
                '--format=custom', '--file', str(recovery)], env=dump_env, check=True, capture_output=True)
            restore = Path(executable).with_name('pg_restore.exe' if sys.platform == 'win32' else 'pg_restore')
            subprocess.run([str(restore), '--list', str(recovery)], check=True, capture_output=True)
            columns = schema_columns(guard.test_url, schema)
            before = schema_fingerprints(guard.test_url, schema, columns=columns)
            migrate(env, head)
            after = schema_fingerprints(guard.test_url, schema, tables=before.keys(), columns=columns)
            write_json(run / 'reports/target-upgrade.json', dict(from_revision=revision, to_revision=head,
                original_tables=before, preserved=before == after, recovery=str(recovery), recovery_sha256=hashlib.sha256(recovery.read_bytes()).hexdigest(), source_written=False))
            if before != after:
                raise RuntimeError('升级后已有业务数据变化，保留恢复点并停止开放')
            owner['revision'] = head
            write_json(run / 'reports/real_owner.json', owner)
        return env, owner
    finally:
        engine.dispose()


def application(args, run, env, owner, version, browser_notice_check=None):
    from app.core import config
    private = ROOT / 'var/state/react-writable-preview' / run.name
    private.mkdir(parents=True, exist_ok=True)
    config.ENV_FILE = private / 'runtime.env'
    config.ENV_FILE.touch(exist_ok=True)
    class PreviewSettings(config.Settings):
        @property
        def exports_path(self):
            return run / 'exports'
    secret = secrets.token_hex(32)
    @lru_cache
    def settings():
        values = PreviewSettings(_env_file=(args.source_env, config.ENV_FILE))
        updates = dict(database_url=env['DATABASE_URL'], test_database_url=env['TEST_DATABASE_URL'],
            session_secret=secret, app_env='dev', allowed_ip_cidrs='127.0.0.1/32,::1/128', cors_allow_origins='',
            frontend_preview_dir=version['build_path'], frontend_app_dir='', artifacts_dir=str(ROOT / 'var/data/react-writable-preview' / run.name),
            logs_dir=str(run / 'logs/app'), i8_user='', i8_password='', printer_ipp_url='')
        if browser_notice_check is not None:
            updates['i8_base_url'] = browser_notice_check.origin
        return values.model_copy(update=updates)
    config.get_settings = settings
    os.environ.update(env)
    from app.core import db, session
    from sqlalchemy import event
    engine = db.get_engine()
    @event.listens_for(engine, 'checkout')
    def verify(connection, record, proxy):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_schema(),current_setting('search_path'),current_setting('transaction_read_only')")
            if cursor.fetchone() != ('mtrl_workbench_test', owner['schema'], owner['schema'], 'off'):
                raise RuntimeError('预览运行连接越出已登记目标')
        connection.rollback()
    session.COOKIE_NAME = owner['cookie_name']
    if browser_notice_check is not None:
        from tools.dev.frontend_preview_browser_check import bind_preview_account, enforce_browser_transport
        bind_preview_account(engine, owner, browser_notice_check)
        enforce_browser_transport()
    from app.mod02_i8 import cookie_store, source_cache, wh_cache
    from app.mod03_notice import print_batch_store
    print_batch_store.STATE_DIR = private / 'print-batches'
    cookie_store.CACHE_DIR = private / 'i8_cookie'
    source_cache.DIR = settings().artifacts_path / 'i8_source'
    wh_cache.CACHE_DIR = settings().artifacts_path / 'i8_warehouse'
    from app.core import preview_store
    preview_store.PREVIEW_DIR = private / 'import_preview'
    from app.report_export import service as exports
    exports.EXPORT_ROOT = run / 'exports'
    from app.main import create_app
    app = create_app()
    if not owner.get('i8_enabled'):
        from tools.dev.frontend_preview_copy import restrict_copy_preview
        restrict_copy_preview(app, full_app=True, browser_notice_check=browser_notice_check,
                              preview_account=owner['preview_account'])
    @app.get('/visual-version')
    def visual_version():
        with engine.connect() as connection:
            if connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() != owner['revision']:
                raise RuntimeError('运行副本版本已变化，拒绝沿用登记身份')
        return {key: owner[key] for key in ['schema','revision','cookie_name','index_sha256','product_digest','synthetic']}
    return app


def run(args):
    from tools.dev.frontend_preview import verified_database_source
    run = owned_run(args.run)
    from tools.dev.frontend_preview_browser_check import load_check
    browser_notice_check = load_check(args, run)
    if args.source_env is None:
        raise RuntimeError('须明确只读来源配置 --source-env')
    _, guard = verified_database_source(args.source_env)
    if not args.existing and (not args.copy_source or not args.disposable):
        raise RuntimeError('新验证实例须显式 --copy-source --disposable，不能复用用户副本生命周期')
    port = validate_port(args.port if args.port is not None else ALLOWED_PREVIEW_PORTS[0])
    path = run / 'reports/real_owner.json'
    schema = read_json(path)['schema'] if args.existing else DISPOSABLE_SCHEMA_PREFIX + uuid.uuid4().hex
    stop = path.parent / 'stop-request.json'
    with reserve_preview(port, path, schema=schema, disposable=not args.existing) as reservation:
        attach_run(run, root=ROOT)
        version = read_json(run / 'reports/version.json')
        verify_build(version)
        os.environ.setdefault('MTRL_EFFORT', 'frontend-preview')
        owner = _serve(args, run, guard, version, browser_notice_check, reservation, path, stop)
        if owner is not None and read_json(path).get('process') == reservation['process']:
            owner.update(status='stopped-schema-preserved' if owner['preserve_schema_on_stop'] else 'stopped-disposable',
                         stopped_at=datetime.now(timezone.utc).isoformat())
            write_json(path, owner)


def _stop_requested(stop, process):
    try:
        return read_json(stop).get('process') == process
    except FileNotFoundError:
        return False


def _serve(args, run, guard, version, browser_notice_check, reservation, path, stop):
    from tools.dev.frontend_preview import isolated_database

    process = reservation['process']
    port = reservation['port']
    if _stop_requested(stop, process):
        return None
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', port))
        if args.existing:
            env, owner = existing_environment(args, run, guard)
            database = nullcontext(env)
        else:
            database = isolated_database(args.source_env, copy_source=True, preview_schema=reservation['schema'])
            owner = dict(owner='', database='mtrl_workbench_test', revision='', read_only=False,
                cookie_name='mw_real_preview_' + secrets.token_hex(8), preview_account='preview-admin',
                i8_enabled=False, preserve_schema_on_stop=False, disposable=True)
        with database as env:
            from sqlalchemy import create_engine
            schema = env['PGOPTIONS'].split('search_path=', 1)[1]
            if schema != reservation['schema']:
                raise RuntimeError('预览实际 schema 与登记不符')
            if _stop_requested(stop, process):
                return None
            engine = create_engine(env['DATABASE_URL'], connect_args={'options':env['PGOPTIONS']}, hide_parameters=True)
            try:
                with engine.connect() as connection:
                    revision = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
                    role = connection.exec_driver_sql('SELECT current_user').scalar_one()
            finally:
                engine.dispose()
            sources = product_sources()
            backend_commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,encoding='utf-8',check=True).stdout.strip()
            owner.update(status='ready', synthetic=False, host='127.0.0.1', port=port,
                schema=schema, revision=revision, owner=role, pid=process['pid'], process=process,
                source_root=str(ROOT), source_commit=version['source_commit'], backend_commit=backend_commit, product_sources=sources,
                product_digest=hashlib.sha256(__import__('json').dumps(sources, sort_keys=True).encode()).hexdigest(),
                index_sha256=version['index_sha256'], build_path=version['build_path'], started_at=reservation['started_at'])
            owner.pop('stopped_at', None)
            if browser_notice_check is not None:
                owner['browser_notice_check'] = browser_notice_check.receipt()
            app = application(args, run, env, owner, version, browser_notice_check)
            write_json(path, owner)
            import uvicorn
            server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
            finished = threading.Event()
            def watch():
                while not finished.wait(.2):
                    if _stop_requested(stop, process):
                        server.should_exit = True
                        return
            thread = threading.Thread(target=watch, daemon=True)
            thread.start()
            try:
                server.run(sockets=[listener])
            finally:
                finished.set()
                thread.join(timeout=2)
            return owner
