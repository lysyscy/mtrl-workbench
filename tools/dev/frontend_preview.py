"""TAIL-397 local preview: own schema, existing migrations, test accounts, cleanup.

Run with the worktree's Python; source-env is read only for database targets.
Tests may supply an explicit mtrl_workbench_test DSN without source configuration.
No credentials are printed or copied to the worktree .env.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))


@contextmanager
def isolated_database(source_env: Path | None = None, *, copy_source: bool = False, test_url: str = ""):
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard, database_identity
    from sqlalchemy import create_engine, text

    if test_url:
        if copy_source or database_identity(test_url)[2] != 'mtrl_workbench_test':
            raise RuntimeError('直接测试DSN仅允许mtrl_workbench_test且不复制来源库')
        source = None
        guard = TestDatabaseGuard(test_url)
    else:
        if source_env is None:
            raise RuntimeError('缺少明确测试DSN或已批准来源配置')
        source = Settings(_env_file=source_env)
        guard = TestDatabaseGuard.from_sources((source.database_url,), source.test_database_url)
    if not guard.test_url:
        raise RuntimeError('缺少可确认的专用测试库配置')
    engine = create_engine(guard.test_url)
    schema = 'frontend_rewrite_397_' + uuid.uuid4().hex
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
                   PRINTER_IPP_URL='', PRINTER_NAME='',
                   FRONTEND_PREVIEW_DIR=str(ROOT / 'apps/frontend/dist'),
                   MTRL_PREVIEW_EXPORT_DIR=str(export_dir),
                   MTRL_PREVIEW_COPY_SOURCE='1' if copy_source else '0',
                   ARTIFACTS_DIR=str(output_dir('work') / schema),
                   LOGS_DIR=str(output_dir('logs') / schema),
                   PYTHONPATH=str(ROOT / 'backend'), PLAYWRIGHT_BROWSERS_PATH='C:/ProgramData/ms-playwright')
        subprocess.run([sys.executable, '-X', 'utf8', '-m', 'alembic', 'upgrade', 'head'],
                       cwd=ROOT / 'backend', env=env, check=True)
        if copy_source:
            from tools.dev.frontend_preview_copy import clone_from_source
            clone_from_source(source.database_url, guard.test_url, schema)
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
        print(f'ISOLATION ready database={actual[0]} role={actual[1]} schema={schema}', flush=True)
        yield env
    finally:
        if owned:
            with engine.begin() as connection:
                owner = connection.execute(text('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=:schema'), {'schema': schema}).scalar_one_or_none()
                if owner != actual[1]:
                    raise RuntimeError('schema所有权变化，保留现场，拒绝自动清理')
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            print(f'ISOLATION cleaned schema={schema}', flush=True)
        engine.dispose()


def create_preview_app():
    # Cookies ignore ports: keep preview logins away from the normal workbench.
    from app.core import session
    session.COOKIE_NAME = 'mw_preview_397'
    from app.report_export import service as exports
    export_dir = Path(os.environ['MTRL_PREVIEW_EXPORT_DIR']).resolve()
    if not export_dir.is_relative_to(ROOT / '.artifacts/active'):
        raise RuntimeError('预览导出目录不在本轮隔离产物内')
    exports.EXPORT_ROOT = export_dir
    from app.main import create_app
    app = create_app()
    from app.core.db import get_engine
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    expected_schema = os.environ['PGOPTIONS'].split('search_path=', 1)[1]
    expected_database = make_url(os.environ['TEST_DATABASE_URL']).database
    with get_engine().connect() as connection:
        database, schema, search_path = connection.execute(text("SELECT current_database(),current_schema(),current_setting('search_path')")).one()
        if (database, schema, search_path) != (expected_database, expected_schema, expected_schema):
            raise RuntimeError('实际后端连接未限定本次测试schema')
    print(f'ISOLATION backend verified database={database} schema={schema}', flush=True)
    if os.environ.get('MTRL_PREVIEW_COPY_SOURCE') == '1':
        from tools.dev.frontend_preview_copy import restrict_copy_preview
        app = restrict_copy_preview(app)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8037)
    parser.add_argument('--copy-source', action='store_true', help='只读一致快照复制业务数据到本次测试schema')
    args = parser.parse_args()
    # Reserve/check before any DB mutation. Uvicorn owns this same socket.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', args.port))
        with isolated_database(args.source_env, copy_source=args.copy_source) as env:
            os.environ.update(env)
            from app.core.config import get_settings
            get_settings.cache_clear()
            import uvicorn
            app = create_preview_app()
            print(f'PREVIEW http://127.0.0.1:{args.port}/preview/projects', flush=True)
            uvicorn.Server(uvicorn.Config(app, log_level='warning')).run(sockets=[listener])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
