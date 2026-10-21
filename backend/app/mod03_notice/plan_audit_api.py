"""Authenticated plan-audit data and explicitly approved method updates."""
from hashlib import sha256
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core import history, session as SESS
from app.core.db import get_engine, session_scope
from app.mod15_user.service import active_account
from app.mod03_notice import plan_audit_data as DATA
from app.mod03_notice.plan_audit_methods import apply_changes, validate_changes

router = APIRouter(prefix='/api/m03/plan-audit', tags=['mod03-plan-audit'])


def audit_user(request: Request):
    identity = SESS.read(request.cookies.get(SESS.COOKIE_NAME))
    if not identity:
        raise HTTPException(401, '请先登录工作台')
    with session_scope() as session:
        if active_account(session, identity) is None:
            raise HTTPException(403, '账号不可用，请重新登录或联系管理员')
    return identity


@router.get('/snapshot')
def snapshot(response: Response, user=Depends(audit_user)):
    response.headers['Cache-Control'] = 'no-store'
    return DATA.capture()


class MethodRequest(BaseModel):
    preview_json: str
    approved_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.post('/methods')
def update_methods(req: MethodRequest, response: Response, user=Depends(audit_user)):
    response.headers['Cache-Control'] = 'no-store'
    if sha256(req.preview_json.encode('utf-8')).hexdigest() != req.approved_sha256:
        raise HTTPException(409, '预览与已确认版本不符，未写入')
    try:
        preview = json.loads(req.preview_json)
        validate_changes(preview)
        engine = get_engine()
        if (engine.dialect.name != 'postgresql'
                or DATA.database_fingerprint(engine) != preview['snapshot']['database_fingerprint']):
            raise ValueError('当前系统与核对快照不符，未写入')
        with session_scope() as session:
            history.lock_actor(session, str(user))
            conn = session.connection()
            conn.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
            apply_changes(conn, preview)
            history.record_barrier(session, str(user), '修改拟付款方式')
        response.headers['X-Operation-History'] = 'unsupported'
    except (ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            message = str(exc)
        else:
            message = '预览清单格式不正确，未写入'
        raise HTTPException(409, message) from None
    return {'status': 'committed', 'count': len(preview['changes']),
            'preview_sha256': req.approved_sha256, 'source_sha256': preview['source_sha256']}
