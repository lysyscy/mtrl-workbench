"""Manual i8 confirmation, safe reads and actual operator/timing regressions."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import app_settings, db, session
from app.core.errors import DataConflictError, MustReportError
from app.core.identity import require_expected_account
from app.mod02_i8 import client as clients, router, repository
from app.mod02_i8.login import LoginResult


def test_live_stored_config_is_used_without_login(rollback_db, monkeypatch):
    from app.mod14_config.models import AppSetting
    from app.core.config import get_settings, i8_base_of
    with db.session_scope() as s:
        item = s.get(AppSetting, 'i8_base_url')
        if item is None:
            s.add(AppSetting(key='i8_base_url', value='http://fixed-i8.invalid'))
        else:
            item.value = 'http://fixed-i8.invalid'
    monkeypatch.setattr(app_settings, '_CACHE', None)
    assert i8_base_of(get_settings()) == 'http://fixed-i8.invalid'


def test_read_routes_do_not_use_external_loaders(rollback_db, monkeypatch):
    import app.core.config as config
    import app.core.identity as identity
    def forbidden(*args, **kwargs):
        raise AssertionError('read route attempted external execution')
    monkeypatch.setattr(session, 'current_name', lambda: 'preview-admin')
    monkeypatch.setattr(identity, 'current_i8_credentials', lambda: ('synthetic-admin', 'synthetic-password'))
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(i8_base_url='http://fixed-i8.invalid'))
    monkeypatch.setattr(app_settings, '_CACHE', {})
    app = FastAPI()
    app.include_router(router.router)
    for dep in (router.get_notice_rows, router.get_common_project_rows, router.get_warehouse_rows):
        app.dependency_overrides[dep] = forbidden
    with TestClient(app) as client:
        value = client.get('/api/m02/config').json()
        assert value['ready'] and value['account'] == 'preview-admin'
        assert 'synthetic-password' not in str(value)
        assert client.get('/api/m02/fetch/plan?year_month=2026-02').json()['end_date'] == '2026-02-28'
        assert isinstance(client.get('/api/m02/fetch/records').json(), list)


def test_timing_and_operator_belong_to_real_action(rollback_db):
    from app.mod15_user.models import UserAccount
    with db.session_scope() as s:
        s.add(UserAccount(account='__run_record_operator__', name='执行记录测试人'))
    before = session.current_name()
    session.set_current_name(session.AccountIdentity('__run_record_operator__'))
    try:
        with db.session_scope() as s:
            start = datetime.now() - timedelta(seconds=4.25)
            row = repository.create_run_record(s, run_type='fetch', target='2026-01', started_at=start)
            repository.finish_run_record(s, row, status='success', success=1, fail=0, detail={})
            out = repository.run_record_out(row)
            assert out.triggered_by == '执行记录测试人' and out.duration_seconds >= 4.25
            second = repository.save_run_record(s, run_type='sync', target='仓库列表', status='success', started_at=start)
            assert second.triggered_by == '执行记录测试人'
    finally:
        session.set_current_name(before)


def test_stale_account_is_rejected_before_any_execution(monkeypatch):
    from app.mod03_notice.router import fetch_notices
    from app.mod03_notice.schemas import FetchRequest
    monkeypatch.setattr(session, 'current_name', lambda: 'new-account')
    def forbidden(*args, **kwargs):
        raise AssertionError('stale account reached external loader')
    with pytest.raises(DataConflictError):
        require_expected_account('old-account')
    with pytest.raises(DataConflictError):
        fetch_notices(FetchRequest(year_month='2026-01', expected_account='old-account'), executor=forbidden)
    with pytest.raises(DataConflictError):
        router.sync_warehouses(allow_kick=False, rows_loader=forbidden, expected_account='old-account')
    with pytest.raises(DataConflictError):
        router.sync_common_projects(allow_kick=False, rows_loader=forbidden, wh_loader=forbidden, expected_account='old-account')
    require_expected_account(None)
    with pytest.raises(MustReportError):
        fetch_notices(FetchRequest(year_month='2026'), executor=forbidden)


def test_online_conflict_never_kicks_without_explicit_confirmation(monkeypatch):
    calls, cookies = [], []
    monkeypatch.setattr(clients.I8Client, '_creds', lambda self: ('synthetic', 'synthetic-password'))
    def login(**kwargs):
        calls.append(kwargs['allow_kick'])
        return LoginResult(ok=kwargs['allow_kick'], conflict=True, cookie='fixed-cookie')
    monkeypatch.setattr(clients, 'http_login', login)
    monkeypatch.setattr(clients.cookie_store, 'save', lambda *args, **kwargs: cookies.append(args[0]))
    with pytest.raises(clients.I8OnlineConflictError) as failure:
        clients.I8Client()._login()
    assert failure.value.http_status == 409 and failure.value.code == 'i8_online_conflict'
    assert calls == [False] and cookies == []
    clients.I8Client(allow_kick=True)._login()
    assert calls == [False, True] and cookies == ['fixed-cookie']


def test_failed_zero_row_sync_is_not_recorded_as_success(rollback_db):
    from sqlalchemy import select
    from app.core.errors import ExternalServiceError
    from app.mod02_i8.models import RunRecord
    from app.mod02_i8.fetch_task import fetch_record_payload
    payload = fetch_record_payload(object_desc='仓库列表', success=0, fail=0, error_message='fixed failure')
    assert payload['status'] == 'failed'
    assert fetch_record_payload(object_desc='仓库列表', success=0, fail=0)['status'] == 'success'
    def unavailable(*args):
        raise ExternalServiceError('fixed failure')
    result = router.sync_warehouses(allow_kick=False, rows_loader=unavailable, expected_account=None)
    assert result.degraded is True
    with db.session_scope() as s:
        row = s.scalar(select(RunRecord).where(RunRecord.target == '仓库列表').order_by(RunRecord.id.desc()))
        assert row.status == 'failed' and row.success_count == 0
        assert row.error_message == 'fixed failure'


def test_empty_i8_password_is_configured_but_not_authenticated(monkeypatch):
    import app.core.config as config
    import app.core.identity as identity
    monkeypatch.setattr(session, 'current_name', lambda: 'preview-admin')
    monkeypatch.setattr(identity, 'current_i8_credentials', lambda: ('synthetic-admin', ''))
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(i8_base_url='http://fixed-i8.invalid'))
    monkeypatch.setattr(app_settings, '_CACHE', {})
    def forbidden(*args, **kwargs):
        raise AssertionError('configuration read attempted i8 authentication')
    monkeypatch.setattr(clients, 'http_login', forbidden)
    app = FastAPI()
    app.include_router(router.router)
    with TestClient(app) as client:
        value = client.get('/api/m02/config').json()
    assert value['ready'] and value['account'] == 'preview-admin'
    assert value['i8_user'] == 'synthetic-admin' and value['message'] == ''
    assert 'i8_password' not in value
