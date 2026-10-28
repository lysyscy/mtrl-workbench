"""Authenticated shell and external-agent entry points share one workbench contract."""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app import export_registry
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.mod06_proc import workbench
from app.mod06_proc.domain import normalize_ym
from app.mod02_i8 import service as i8_service
from app.mod01_projects import service as project_service

router = APIRouter(tags=['mechanical-workbench'])


@router.get('/api/m06/workbench')
def get_state(ym: str = ''):
    with session_scope() as session:
        return workbench.state(session, ym)


def report_snapshot(ym, projects):
    ym = normalize_ym(ym)
    if not ym:
        raise MustReportError('请选择有效报表月份')
    try:
        selected = json.loads(projects) if projects.startswith('[') else projects.split(',')
    except (ValueError, TypeError) as exc:
        raise MustReportError('项目选择无法识别，请重新选择') from exc
    if not isinstance(selected, list) or not selected or any(not isinstance(p, str) for p in selected):
        raise MustReportError('请至少选择一个项目')
    selected = list(dict.fromkeys(selected))
    with session_scope() as session:
        for warehouse in selected:
            workbench.warehouse(session, warehouse)
        data = workbench.snapshot(session, ym, selected)
    order = {warehouse: i for i, warehouse in enumerate(selected)}
    data['projects'].sort(key=lambda row: order[row['warehouse']])
    return data


@router.get('/api/m06/workbench/preview')
def preview_report(ym: str = '', projects: str = ''):
    data = report_snapshot(ym, projects)
    return {**export_registry.get('mechanical').preview(data), 'snapshot_token': workbench.digest(data)}


@router.get('/api/m06/workbench/export')
def export_report(ym: str = '', projects: str = '', snapshot_token: str = ''):
    output = export_registry.get('service').EXPORT_ROOT
    data = report_snapshot(ym, projects)
    if snapshot_token and snapshot_token != workbench.digest(data):
        raise MustReportError('预览后已保存内容有变化，请重新预览再导出')
    path = export_registry.get('mechanical').export(data, output)
    return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        filename=path.name, headers={'X-Export-Filename': quote(path.name)})


@router.post('/api/m06/workbench/{name}')
def perform_action(name: str, payload: dict, request: Request):
    if name == 'i8-fetch':
        from app.mod06_proc.workbench_i8 import read_preview
        allow_kick = payload.get('allow_kick', False)
        if not isinstance(allow_kick, bool):
            raise MustReportError('允许强踢须为布尔值')
        started, operator = datetime.now(), current_operator()
        try:
            with session_scope() as session:
                current = workbench.state(session)
                previous = {}
                for snapshot in current['i8']:
                    ids = ({snapshot['projectId']} if snapshot.get('projectId') else {
                        row['projectId'] for rows in snapshot.get('sources', {}).values()
                        for row in rows if row.get('projectId')})
                    previous[snapshot['warehouse']] = ids
                projects = project_service.all_projects(session)
            incoming = read_preview(projects, previous, allow_kick=allow_kick)
            incoming['request_id'] = payload.get('request_id', '')
            with session_scope() as session:
                result = workbench.action(session, 'i8-preview', incoming, operator)
                count = sum(incoming['counts'].values())
                run = i8_service.save_run_record(session, run_type='fetch', target='机械费三类来源（当前累计）',
                    status='success', total_count=count, success_count=count, operator=operator,
                    detail={'counts': incoming['counts'], 'preview_id': result['preview_id']}, started_at=started)
                run_id = run.id
            return {**result, 'counts': incoming['counts'], 'run_record_id': run_id}
        except Exception as exc:
            # A failed preview transaction must not erase its execution record.
            with session_scope() as session:
                i8_service.save_run_record(session, run_type='fetch', target='机械费三类来源（当前累计）',
                    status='failed', error_message=str(exc), operator=operator, started_at=started)
            raise
    with session_scope() as session:
        return workbench.action(session, name, payload, current_operator())
