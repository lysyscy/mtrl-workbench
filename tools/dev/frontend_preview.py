"""TAIL-397 local preview: own schema, existing migrations, test accounts, cleanup.

Run with the worktree's Python; source-env is read only for database targets.
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


@contextmanager
def isolated_database(source_env: Path):
    from app.core.config import Settings
    from tests.db_guard import TestDatabaseGuard
    from sqlalchemy import create_engine, text

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
        env = os.environ.copy()
        # No public fallback: missing tables fail instead of reaching shared test data.
        env.update(DATABASE_URL=guard.test_url, TEST_DATABASE_URL=guard.test_url,
                   PGOPTIONS=f'-c search_path={schema}', SESSION_SECRET=secrets.token_hex(32),
                   APP_ENV='dev', ALLOWED_IP_CIDRS='127.0.0.1/32,::1/128',
                   CORS_ALLOW_ORIGINS='', I8_BASE_URL='', I8_USER='', I8_PASSWORD='',
                   PRINTER_IPP_URL='', PRINTER_NAME='',
                   FRONTEND_PREVIEW_DIR=str(ROOT / 'apps/frontend/dist'),
                   ARTIFACTS_DIR='var/tmp/frontend-397', LOGS_DIR='var/log/frontend-397',
                   PYTHONPATH=str(ROOT / 'backend'), PLAYWRIGHT_BROWSERS_PATH='C:/ProgramData/ms-playwright')
        subprocess.run([sys.executable, '-X', 'utf8', '-m', 'alembic', 'upgrade', 'head'],
                       cwd=ROOT / 'backend', env=env, check=True)
        scoped = create_engine(guard.test_url, connect_args={'options': env['PGOPTIONS']})
        try:
            from app.mod15_user.models import UserAccount
            from app.mod01_projects.models import Project
            from sqlalchemy.orm import Session
            with scoped.begin() as connection:
                if connection.execute(text('SELECT current_schema()')).scalar_one() != schema:
                    raise RuntimeError('schema隔离未生效')
                # Initial migration seeds an admin; replace only inside our fresh schema.
                connection.execute(UserAccount.__table__.delete())
            with Session(scoped) as session:
                session.add_all([
                    UserAccount(account='preview-admin', name='预览管理员', role='admin', password=''),
                    UserAccount(account='preview-user', name='预览同事', role='user', password='', theme='深色', ui_scale='large'),
                    Project(project_type='normal', name_full='隔离验收项目', warehouse_name='隔离验收仓库', disp='隔离项目', ord=1),
                    Project(project_type='normal', name_full='隔离验收归档项目', warehouse_name='隔离归档仓库', disp='归档样例', status='archived', ord=2),
                    Project(project_type='normal', name_full='隔离验收长项目名称用于核对窄屏换行与横向滚动的可读性', warehouse_name='长名称验收仓库', disp='长项目名验收', ord=3),
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
    from app.main import create_app
    return create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8037)
    args = parser.parse_args()
    # Reserve/check before any DB mutation. Uvicorn owns this same socket.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', args.port))
        with isolated_database(args.source_env) as env:
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
