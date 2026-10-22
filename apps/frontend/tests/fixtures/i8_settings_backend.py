"""Address-only test controls; all external I/O stays blocked by the i8 fixture."""
import asyncio
import json

from .i8_backend import create_app as create_i8_app


def create_app():
    app = create_i8_app()
    from app.core.db import session_scope
    from app.mod14_config.models import AppSetting, AppSettingLog
    from sqlalchemy import select
    release = asyncio.Event()
    flight = {'started': False, 'finished': False, 'status': None}

    @app.middleware('http')
    async def delay_owned_address(request, call_next):
        delayed = False
        if request.method == 'POST' and request.url.path == '/api/m14/settings':
            body = json.loads(await request.body())
            delayed = body.get('i8_base_url') == 'http://held-old-address.invalid'
        if delayed:
            flight.update(started=True, finished=False, status=None)
            await release.wait()
        response = await call_next(request)
        if delayed:
            flight.update(finished=True, status=response.status_code)
        return response

    @app.post('/__test__/address-reset')
    async def reset():
        assert not flight['started'] or flight['finished']
        release.clear()
        flight.update(started=False, finished=False, status=None)
        return {'ok': True}

    @app.get('/__test__/address-flight')
    async def pending():
        return flight

    @app.post('/__test__/address-release')
    async def finish():
        release.set()
        return {'ok': True}

    @app.post('/__test__/address-remove-row')
    def remove_row():
        from app.core.app_settings import invalidate
        with session_scope() as session:
            row = session.get(AppSetting, 'i8_base_url')
            if row:
                session.delete(row)
        invalidate()
        return {'ok': True}

    @app.get('/__test__/settings-state')
    def state():
        with session_scope() as session:
            row = session.get(AppSetting, 'i8_base_url')
            log = session.scalar(select(AppSettingLog).where(AppSettingLog.key == 'i8_base_url').order_by(AppSettingLog.id.desc()))
            return {'value': row.value if row else '', 'updated_by': row.updated_by if row else '',
                    'operator': log.operator if log else ''}
    return app
