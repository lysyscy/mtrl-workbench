"""A separately approved browser-only notice check on a fresh disposable preview.

The scope file describes the check; it is not an authorization credential.
Creating or using it requires the user's specific approval for the live check.
Ordinary previews retain their external-action block.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


_notice_request = ContextVar('preview_browser_notice_request', default=False)


@contextmanager
def approved_notice_context():
    token = _notice_request.set(True)
    try:
        yield
    finally:
        _notice_request.reset(token)


def browser_transport_allowed():
    return _notice_request.get()


@dataclass(frozen=True)
class BrowserNoticeCheck:
    year_month: str
    origin: str
    i8_user: str

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict) or set(data) != {'year_month', 'origin', 'i8_user'}:
            raise ValueError('浏览器验证范围只接受月份、站点原点和已核i8账号。')
        month, origin, user = (data[key] for key in ('year_month', 'origin', 'i8_user'))
        if not isinstance(month, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
            raise ValueError('须明确一个有效的通知书月份。')
        if not isinstance(origin, str):
            raise ValueError('须明确已批准的i8站点原点。')
        try:
            parsed = urlsplit(origin)
            valid = (parsed.scheme in {'http', 'https'} and parsed.hostname and
                     not parsed.username and not parsed.password and parsed.path in {'', '/'} and
                     not parsed.query and not parsed.fragment and
                     (parsed.port is None or 0 < parsed.port < 65536))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('i8验证目标必须是无凭据、路径和查询参数的站点原点。')
        if not isinstance(user, str) or not user.strip() or user != user.strip() or any(ord(c) < 32 for c in user):
            raise ValueError('须填写已核对的i8账号，不能包含控制字符或首尾空白。')
        return cls(month, origin.rstrip('/'), user)

    def receipt(self):
        return {'year_month': self.year_month, 'origin': self.origin,
                'i8_user_sha256': hashlib.sha256(self.i8_user.encode('utf-8')).hexdigest(),
                'mode': 'browser', 'default_external_guard_preserved': True}

    async def allows(self, request, *, preview_account):
        path, method = request.url.path, request.method
        if method == 'GET' and path == '/api/m02/browser/pending':
            return bool(request.query_params.get('device_id'))
        if method == 'POST' and path in {'/api/m02/browser/disconnect', '/api/m02/browser/complete'}:
            # The original authenticated broker checks owner, device, ticket and generation.
            return True
        if method != 'POST' or path not in {'/api/m02/browser/connect', '/api/m03/notices/fetch'}:
            return False
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return False
        if not isinstance(body, dict):
            return False
        if path == '/api/m02/browser/connect':
            # The approved i8 username is bound on the server by bind_preview_account.
            return body.get('i8_origin') == self.origin and bool(body.get('device_id'))
        return (body.get('session_mode') == 'browser' and body.get('year_month') == self.year_month
                and body.get('expected_account') == preview_account and bool(body.get('device_id'))
                and body.get('allow_kick', False) is False)


def load_check(args, run: Path):
    path = getattr(args, 'browser_notice_check', None)
    if path is None:
        return None
    if not args.copy_source or not args.disposable or args.existing:
        raise RuntimeError('浏览器通知书验证只可用于新建的真实可丢弃副本。')
    from tools.audit.workspace_paths import owned_work
    scope = owned_work(path, writing=False)
    if not scope.is_relative_to(run / 'work'):
        raise RuntimeError('验证范围文件必须属于本次登记运行的work目录。')
    return BrowserNoticeCheck.parse(json.loads(scope.read_text(encoding='utf-8')))


def bind_preview_account(engine, owner, check):
    """Bind only the generated preview account; no i8 password is read or copied."""
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session
    from app.mod15_user.models import UserAccount
    if not owner.get('disposable') or owner.get('preserve_schema_on_stop'):
        raise RuntimeError('拒绝在保留用途的副本绑定验证身份。')
    with Session(engine) as session:
        if session.execute(text('SELECT current_schema()')).scalar_one() != owner['schema']:
            raise RuntimeError('验证账号绑定越出登记schema。')
        user = session.execute(select(UserAccount).where(UserAccount.account == owner['preview_account'])).scalar_one()
        user.i8_user, user.i8_password = check.i8_user, ''
        session.commit()


def enforce_browser_transport():
    """Process-local fail-safe: even a missed route scope cannot open an HTTP session."""
    from app.core.errors import MustReportError
    from app.mod02_i8.client import I8Client
    from app.mod02_i8.browser_session import I8BrowserSessionClient
    from app.mod02_i8.browser_relay import BrowserRelayTransport
    strict_session = I8BrowserSessionClient._ensure_session

    def blocked(*args, **kwargs):
        raise MustReportError('此验证副本只授权浏览器中转，禁止HTTP登录或直连。')

    def browser_session(client):
        if not browser_transport_allowed() or not isinstance(client._reused.transport, BrowserRelayTransport):
            return blocked()
        return strict_session(client)

    I8Client._ensure_session = blocked
    I8Client._login = blocked
    I8BrowserSessionClient._ensure_session = browser_session
