"""Manage full-app real-copy previews and prepare DB-only test schemas.

Source configuration is read only for explicit database targets. Browser tests attach
through the registered runtime and never create synthetic HTTP previews.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))


class IsolationInputError(RuntimeError):
    """An isolation preflight error with a message safe to display."""


def verified_database_source(source_env: Path):
    """Compare the file's database identities with effective settings before connecting."""
    from pydantic_settings.sources import DotEnvSettingsSource
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard, database_identity

    try:
        declared = DotEnvSettingsSource(Settings, env_file=source_env)()
        default = DotEnvSettingsSource(Settings)()
        effective = Settings(_env_file=source_env)
    except Exception:
        raise IsolationInputError('无法读取明确来源的数据库配置') from None

    source_url = declared.get('database_url', '')
    test_url = declared.get('test_database_url', '')
    if not source_url or not test_url:
        raise IsolationInputError('明确来源文件必须包含 DATABASE_URL 和 TEST_DATABASE_URL')
    try:
        TestDatabaseGuard.from_sources((source_url, default.get('database_url', '')), test_url)
        same_source = database_identity(source_url) == database_identity(effective.database_url)
        same_target = database_identity(test_url) == database_identity(effective.test_database_url)
    except RuntimeError as error:
        raise IsolationInputError(str(error)) from None
    if not same_source or not same_target:
        raise IsolationInputError('明确来源与有效数据库身份不符，请检查 DATABASE_URL 和 TEST_DATABASE_URL 环境覆盖')
    return effective.database_url, TestDatabaseGuard(effective.test_database_url)


@contextmanager
def isolated_database(source_env: Path | None = None, *, copy_source: bool = False, test_url: str = "",
                      preview: bool = True, log=None, preview_schema: str | None = None):
    from tests.db_guard import TestDatabaseGuard, database_identity
    from sqlalchemy import create_engine, text
    from tools.dev.frontend_preview_runtime import DISPOSABLE_SCHEMA_PREFIX

    if test_url:
        if copy_source or database_identity(test_url)[2] != 'mtrl_workbench_test':
            raise RuntimeError('直接测试DSN仅允许mtrl_workbench_test且不复制来源库')
        source_url = None
        guard = TestDatabaseGuard(test_url)
    else:
        if source_env is None:
            raise RuntimeError('缺少明确测试DSN或已批准来源配置')
        source_url, guard = verified_database_source(source_env)
    if not guard.test_url:
        raise RuntimeError('缺少可确认的专用测试库配置')
    revision = 'head'
    if copy_source:
        from tools.dev.frontend_preview_copy import source_revision
        revision = source_revision(source_url)
    if preview_schema is not None and (not preview or not re.fullmatch(DISPOSABLE_SCHEMA_PREFIX + '[0-9a-f]{32}', preview_schema)):
        raise RuntimeError('可丢弃预览 schema 名称不符')
    prefix = 'frontend_preview_test_' if preview else 'backend_verify_'
    schema = preview_schema or prefix + uuid.uuid4().hex
    engine = create_engine(guard.test_url)
    owned = False
    try:
        with engine.begin() as connection:
            guard.assert_runtime(engine.url)
            actual = connection.execute(text('SELECT current_database(), current_user')).one()
            if actual[0].casefold() != engine.url.database.casefold():
                raise RuntimeError('实际测试库身份不符')
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            owned = True
        from tools.audit.workspace_paths import output_dir
        export_dir = output_dir('exports')
        env = os.environ.copy()
        # No public fallback: missing tables fail instead of reaching shared test data.
        env.update(DATABASE_URL=guard.test_url, TEST_DATABASE_URL=guard.test_url,
                   PGOPTIONS=f'-c search_path={schema}', PGAPPNAME='frontend_preview_' + schema, SESSION_SECRET=secrets.token_hex(32),
                   APP_ENV='dev', ALLOWED_IP_CIDRS='127.0.0.1/32,::1/128',
                   CORS_ALLOW_ORIGINS='', I8_BASE_URL='', I8_USER='', I8_PASSWORD='',
                   PRINTER_IPP_URL='',
                   FRONTEND_PREVIEW_DIR=str(ROOT / 'apps/frontend/dist'), FRONTEND_APP_DIR='',
                   MTRL_PREVIEW_EXPORT_DIR=str(export_dir),
                   MTRL_PREVIEW_COPY_SOURCE='1' if copy_source else '0',
                   ARTIFACTS_DIR=str(output_dir('work') / schema),
                   LOGS_DIR=str(output_dir('logs') / schema),
                   PYTHONPATH=str(ROOT / 'backend'), PLAYWRIGHT_BROWSERS_PATH='C:/ProgramData/ms-playwright')
        if not preview:
            env['FRONTEND_PREVIEW_DIR'] = ''
            env['ALLOWED_IP_CIDRS'] = ''  # TestClient has an in-process host, no HTTP listener.
            env['PGAPPNAME'] = schema
        migrate(env, revision, log=log)
        if copy_source:
            from tools.dev.frontend_preview_copy import clone_from_source, schema_fingerprints, schema_columns
            clone_from_source(source_url, guard.test_url, schema)
            columns = schema_columns(guard.test_url, schema)
            before = schema_fingerprints(guard.test_url, schema, columns=columns)
            migrate(env, 'head', log=log)
            after = schema_fingerprints(guard.test_url, schema, tables=before.keys(), columns=columns)
            if before != after:
                raise RuntimeError('目标升级改变了已复制业务数据；保留失败证据')
        if preview:
            scoped = create_engine(guard.test_url, connect_args={'options': env['PGOPTIONS']})
            try:
                from app.mod15_user.models import UserAccount
                from app.mod01_projects.models import Project
                from sqlalchemy.orm import Session
                with scoped.begin() as connection:
                    if connection.execute(text('SELECT current_schema()')).scalar_one() != schema:
                        raise RuntimeError('schema隔离未生效')
                    # Initial migration seeds an admin; replace only inside our fresh schema.
                    if not copy_source:
                        connection.execute(UserAccount.__table__.delete())
                with Session(scoped) as session:
                    session.add_all([
                        UserAccount(account='preview-admin', name='预览管理员', role='admin', password=''),
                        UserAccount(account='preview-user', name='预览同事', role='user', password='', theme='深色', ui_scale='large'),
                    ])
                    if not copy_source:
                        session.add_all([
                            Project(project_type='normal', name_full='隔离验收项目', warehouse_name='隔离验收仓库', disp='隔离项目', ord=1),
                            Project(project_type='normal', name_full='隔离验收归档项目', warehouse_name='隔离归档仓库', disp='归档样例', status='archived', ord=2),
                            Project(project_type='normal', name_full='隔离验收长项目名称用于核对窄屏换行与横向滚动的可读性', warehouse_name='长名称验收仓库', disp='长项目名验收', ord=3),
                        ])
                        session.flush()
                        from app.mod05_flow.models import OpeningBalance
                        from app.mod03_notice.models import PaymentNotice
                        from sqlalchemy import select
                        project = session.scalar(select(Project).where(Project.disp == '隔离项目'))
                        other = session.scalar(select(Project).where(Project.disp == '长项目名验收'))
                        session.add_all([
                            OpeningBalance(project_id=project.id, category='material', entry_kind='manual',
                                           cutoff_ym='2025-10', settle_amount=1000, paid_amount=100, remark='合成历史行甲'),
                            OpeningBalance(project_id=project.id, category='material', entry_kind='manual',
                                           cutoff_ym='2025-11', settle_amount=500, paid_amount=50, remark='合成历史行乙'),
                            OpeningBalance(project_id=project.id, category='mechanical', entry_kind='month',
                                           cutoff_ym='2025-11', settle_amount=0, paid_amount=75, remark='合成机械付款'),
                            OpeningBalance(project_id=other.id, category='material', entry_kind='manual',
                                           cutoff_ym='2025-11', settle_amount=300, paid_amount=30, remark='另一项目测试行'),
                            PaymentNotice(ph_id='PREVIEW-HISTORY', bill_no='PREVIEW-HISTORY', project_name=project.name_full,
                                          ownership_id=project.id, category='material', doc_date='2025-09-01',
                                          stat_settle=200, stat_paid=20, amount_approved=200),
                            PaymentNotice(ph_id='PREVIEW-NORMAL', bill_no='PREVIEW-NORMAL', project_name=project.name_full,
                                          ownership_id=project.id, category='material', doc_date='2025-12-01',
                                          stat_settle=400, stat_paid=40, amount_approved=400),
                        ])
                    session.commit()
            finally:
                scoped.dispose()
        print(f'ISOLATION ready database={actual[0]} role={actual[1]} schema={schema}', flush=True, file=log)
        yield env
    finally:
        if owned:
            with engine.begin() as connection:
                owner = connection.execute(text('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=:schema'), {'schema': schema}).scalar_one_or_none()
                if owner != actual[1]:
                    raise RuntimeError('schema所有权变化，保留现场，拒绝自动清理')
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            print(f'ISOLATION cleaned schema={schema}', flush=True, file=log)
        engine.dispose()


def migrate(env, revision, *, log=None):
    subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'alembic', 'upgrade', revision],
                   cwd=ROOT / 'backend', env=env, check=True, stdout=log, stderr=log)


def prune(source_env, *, files_only=False):
    from tools.dev.frontend_preview_runtime import DISPOSABLE_SCHEMA_PREFIX, prune_preview_state

    default_env = ROOT / '.env'
    if files_only or (source_env is None and not default_env.is_file()):
        removed, _, runtime_dirs = prune_preview_state()
        return dict(removed_registrations=removed, removed_runtime_dirs=runtime_dirs, dropped_schemas=[],
                    schema_cleanup='files-only' if files_only else 'no-source-env')

    from sqlalchemy import create_engine, text

    _, guard = verified_database_source(source_env if source_env is not None else default_env)
    engine = create_engine(guard.test_url, hide_parameters=True)
    try:
        guard.assert_runtime(engine.url)
        if engine.url.database != 'mtrl_workbench_test':
            raise RuntimeError('仅能清理专用库 mtrl_workbench_test 中的可丢弃预览 schema')
        with engine.begin() as connection:
            identity = connection.exec_driver_sql('SELECT current_database(), current_user, session_user').one()
            if tuple(identity) != ('mtrl_workbench_test', engine.url.username, engine.url.username):
                raise RuntimeError('实际测试库或账号身份不符')
            candidates = connection.execute(text('''
                SELECT nspname FROM pg_namespace
                WHERE pg_get_userbyid(nspowner) = current_user
                  AND left(nspname, length(:prefix)) = :prefix
                  AND NOT EXISTS (
                      SELECT 1 FROM pg_stat_activity
                      WHERE datname = current_database()
                        AND application_name = left('frontend_preview_' || nspname, 63)
                  )
                ORDER BY nspname
            '''), {'prefix': DISPOSABLE_SCHEMA_PREFIX}).scalars().all()
            # New servers reserve their schema before creating it. Snapshot the
            # registry after discovering candidates, without holding it during DDL.
            removed, live, runtime_dirs = prune_preview_state()
            if any(not entry.owner.get('schema') for entry in live):
                raise RuntimeError('活动预览的 schema 无法确认，未执行数据库清理')
            protected = {entry.owner.get('schema') for entry in live}
            dropped = []
            for schema in candidates:
                if schema in protected or not re.fullmatch(DISPOSABLE_SCHEMA_PREFIX + r'[a-zA-Z0-9_]+', schema):
                    continue
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
                dropped.append(schema)
        return dict(removed_registrations=removed, removed_runtime_dirs=runtime_dirs, dropped_schemas=dropped)
    finally:
        engine.dispose()


def main() -> None:
    from tools.dev.frontend_preview_runtime import describe_preview, preview_inventory, request_stop
    from tools.dev.frontend_preview_server import run, arguments
    args = arguments()
    if args.list:
        live, stale = preview_inventory()
        print('活动预览：')
        print('\n'.join(map(describe_preview, live)) or '无')
        if stale:
            print('已退出的残留登记：')
            print('\n'.join(map(describe_preview, stale)))
        return
    if args.prune:
        import json
        print(json.dumps(prune(args.source_env, files_only=args.files_only), ensure_ascii=False))
        return
    if args.stop:
        if not args.all:
            request_stop(port=args.port)
            return
        live, _ = preview_inventory()
        failed = []
        for entry in live:
            try:
                request_stop(target=entry)
            except Exception as error:
                failed.append(f"端口 {entry.owner.get('port')}：{type(error).__name__}")
        if failed:
            raise RuntimeError('部分预览停止失败：' + '、'.join(failed))
        return
    if args.prepare_build:
        from tools.dev.frontend_preview_server import prepare_build
        prepare_build(args)
        return
    run(args)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, ValueError) as error:
        sys.exit(str(error))
