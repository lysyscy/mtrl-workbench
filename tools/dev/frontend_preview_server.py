"""Build and run the existing full application on an owned real database copy."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading

from tools.dev.frontend_preview_runtime import (ROOT, product_sources, process_identity,
    read_json, write_json, state_dir, verify_build)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env', type=Path)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--port', type=int, default=8065)
    parser.add_argument('--copy-source', action='store_true')
    parser.add_argument('--existing', action='store_true')
    parser.add_argument('--upgrade-existing', action='store_true')
    parser.add_argument('--disposable', action='store_true')
    parser.add_argument('--prepare-build', type=Path)
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--pg-bin', type=Path, help='既有匹配PostgreSQL工具目录，仅已有副本升级需要')
    return parser.parse_args()


def prepare_build(args):
    run = owned_run(args.run)
    build = args.prepare_build.resolve()
    if not build.is_relative_to(run / 'work') or build.exists():
        raise RuntimeError('新构建必须位于本run/work且不能覆盖已有资源')
    before = product_sources(frontend_only=True)
    executable = shutil.which('pnpm.cmd') or shutil.which('pnpm')
    if not executable:
        raise RuntimeError('未找到项目pnpm')
    for command, name in [([executable, 'typecheck'], 'typecheck.log'),
                          ([executable, 'build', '--outDir', str(build)], 'build.log')]:
        log = run / 'logs' / name
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8') as stream:
            subprocess.run(command, cwd=ROOT / 'apps/frontend', stdout=stream, stderr=stream, check=True)
    if before != product_sources(frontend_only=True):
        raise RuntimeError('构建期间前端输入变化，不能登记为最新构建')
    files = {p.relative_to(build).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in build.rglob('*') if p.is_file()}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                              encoding='utf-8', check=True).stdout.strip()
    write_json(run / 'reports/version.json', dict(build_path=str(build), files=files,
        index_sha256=files['index.html'], frontend_sources=before, source_commit=revision,
        diagnostic_instrumentation=False, prepared_at=datetime.now(timezone.utc).isoformat()))


def owned_run(path):
    if path is None:
        raise RuntimeError('须指定已有运行归属 --run')
    run = path.resolve()
    if not run.is_relative_to(ROOT / '.artifacts/active'):
        raise RuntimeError('运行必须属于当前工作树的.artifacts/active')
    return run


def existing_environment(args, run, source, guard):
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


def application(args, run, env, owner, version, source, guard):
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
        return values.model_copy(update=dict(database_url=guard.test_url, test_database_url=guard.test_url,
            session_secret=secret, app_env='dev', allowed_ip_cidrs='127.0.0.1/32,::1/128', cors_allow_origins='',
            frontend_preview_dir=version['build_path'], frontend_app_dir='', artifacts_dir=str(ROOT / 'var/data/react-writable-preview' / run.name),
            logs_dir=str(run / 'logs/app'), i8_user='', i8_password='', printer_ipp_url='', printer_name=''))
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
    from app.mod02_i8 import cookie_store, source_cache, wh_cache
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
        restrict_copy_preview(app, full_app=True)
    @app.get('/visual-version')
    def visual_version():
        with engine.connect() as connection:
            if connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() != owner['revision']:
                raise RuntimeError('运行副本版本已变化，拒绝沿用登记身份')
        return {key: owner[key] for key in ['schema','revision','cookie_name','index_sha256','product_digest','synthetic']}
    return app


def run(args):
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard
    from tools.dev.frontend_preview import isolated_database
    run = owned_run(args.run)
    os.environ.update(MTRL_EFFORT=run.parent.name, MTRL_RUN_ID=run.name)
    if args.source_env is None:
        raise RuntimeError('须明确只读来源配置 --source-env')
    version = read_json(run / 'reports/version.json')
    verify_build(version)
    source = Settings(_env_file=args.source_env)
    guard = TestDatabaseGuard.from_sources((source.database_url,), source.test_database_url)
    if not args.existing and (not args.copy_source or not args.disposable):
        raise RuntimeError('新验证实例须显式 --copy-source --disposable，不能复用用户副本生命周期')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', args.port))
        if args.existing:
            env, owner = existing_environment(args, run, source, guard)
            database = nullcontext(env)
        else:
            database = isolated_database(args.source_env, copy_source=True)
            owner = dict(owner='', database='mtrl_workbench_test', revision='', read_only=False,
                cookie_name='mw_real_preview_' + secrets.token_hex(8), preview_account='preview-admin',
                i8_enabled=False, preserve_schema_on_stop=False, disposable=True)
        with database as env:
            from sqlalchemy import create_engine
            schema = env['PGOPTIONS'].split('search_path=', 1)[1]
            engine = create_engine(guard.test_url, connect_args={'options':env['PGOPTIONS']}, hide_parameters=True)
            try:
                with engine.connect() as connection:
                    revision = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
                    role = connection.exec_driver_sql('SELECT current_user').scalar_one()
            finally:
                engine.dispose()
            sources = product_sources()
            backend_commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,encoding='utf-8',check=True).stdout.strip()
            owner.update(status='ready', synthetic=False, host='127.0.0.1', port=args.port,
                schema=schema, revision=revision, owner=role, pid=os.getpid(), process=process_identity(os.getpid()),
                source_root=str(ROOT), source_commit=version['source_commit'], backend_commit=backend_commit, product_sources=sources,
                product_digest=hashlib.sha256(__import__('json').dumps(sources, sort_keys=True).encode()).hexdigest(),
                index_sha256=version['index_sha256'], build_path=version['build_path'], started_at=datetime.now(timezone.utc).isoformat())
            owner.pop('stopped_at', None)
            app = application(args, run, env, owner, version, source, guard)
            path = run / 'reports/real_owner.json'
            stop = run / 'reports/stop-request.json'
            if stop.exists():
                stop.unlink()
            write_json(path, owner)
            write_json(state_dir() / 'current.json', {'owner_path':str(path)})
            import uvicorn
            server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
            finished = threading.Event()
            def watch():
                while not finished.wait(.2):
                    if stop.exists() and read_json(stop).get('process') == owner['process']:
                        server.should_exit = True
                        return
            thread = threading.Thread(target=watch, daemon=True)
            thread.start()
            try:
                server.run(sockets=[listener])
            finally:
                finished.set()
                thread.join(timeout=2)
                owner.update(status='stopped-schema-preserved' if owner['preserve_schema_on_stop'] else 'stopped-disposable', stopped_at=datetime.now(timezone.utc).isoformat())
                write_json(path, owner)
