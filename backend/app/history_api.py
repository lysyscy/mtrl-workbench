"""全局撤销入口；只返回动作摘要，历史值留在服务端。"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core import history, session as SESS
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.history_bindings import configure
from app.mod15_user.service import active_account

router = APIRouter(prefix='/api/history', tags=['history'])


def actor_for(request, session):
    identity = SESS.read(request.cookies.get(SESS.COOKIE_NAME))
    if not identity:
        raise HTTPException(401, '请先登录')
    if active_account(session, identity) is None:
        raise HTTPException(403, '账号不可用，请重新登录')
    return str(identity)


@router.get('/status')
def history_status(request: Request):
    with session_scope() as session:
        actor = actor_for(request, session)
        return JSONResponse(history.status(session, actor), headers={'Cache-Control': 'no-store'})


class ReplayIn(BaseModel):
    operation_id: int = Field(gt=0)


@router.post('/{direction}')
def history_replay(direction: Literal['undo', 'redo'], body: ReplayIn, request: Request):
    try:
        with session_scope() as session:
            actor = actor_for(request, session)
            result = history.replay(session, actor, direction, body.operation_id)
        return result
    except MustReportError as exc:
        return JSONResponse({'ok': False, 'message': exc.message}, status_code=409)
    except IntegrityError:
        return JSONResponse({'ok': False, 'message': '相关数据关系已经变化，本次未修改；请刷新后核对'}, status_code=409)


def install(app):
    configure()
    app.include_router(router)

    @app.middleware('http')
    async def history_context(request: Request, call_next):
        actor = SESS.read(request.cookies.get(SESS.COOKIE_NAME))
        token, state = history.begin_request(actor, request.method, request.url.path)
        try:
            response = await call_next(request)
            if state and state.result:
                response.headers['X-Operation-History'] = state.result
            return response
        finally:
            history.end_request(token)
