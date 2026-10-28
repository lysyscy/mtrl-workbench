"""Mechanical routes on guarded PostgreSQL savepoints; no production/i8 reads."""
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core import db
from app.core.errors import AppError, MustReportError
from app.mod01_projects.models import Project
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord, MechanicalWorkbenchPreview
from app.mod06_proc import workbench, workbench_api as API, workbench_i8
from app.mod02_i8.models import RunRecord
from tests.test_mechanical_workbench import session


@pytest.fixture
def api(session, monkeypatch, tmp_path):
    factory = db.get_session_factory()
    with factory.begin() as session:
        for wh, phid in [('甲', 'i8-a'), ('乙', 'i8-b')]:
            session.scalar(select(Project).where(Project.warehouse_name == wh)).phid = phid

    tracker = {'active': 0, 'commits': 0, 'rollbacks': 0}

    @contextmanager
    def session_scope():
        with factory() as session:
            tracker['active'] += 1
            try:
                yield session
                session.commit()
                tracker['commits'] += 1
            except Exception:
                session.rollback()
                tracker['rollbacks'] += 1
                raise
            finally:
                tracker['active'] -= 1

    monkeypatch.setattr(API, 'session_scope', session_scope)
    monkeypatch.setattr(API, 'current_operator', lambda: 'isolated-test')
    from app.report_export import service as exports
    monkeypatch.setattr(exports, 'EXPORT_ROOT', tmp_path)

    captured = {'previews': [], 'exports': []}

    def preview(snapshot):
        assert tracker['active'] == 0
        captured['previews'].append(deepcopy(snapshot))
        return {'ok': True, 'snapshot': snapshot}

    def export(snapshot, output):
        assert tracker['active'] == 0
        captured['exports'].append(deepcopy(snapshot))
        output.mkdir(parents=True, exist_ok=True)
        path = output / f'isolated-{len(captured["exports"])}.xlsx'
        # The exporter is a sink here: route/snapshot isolation is under test,
        # while workbook formatting belongs to mechanical export tests.
        path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
        return path

    monkeypatch.setitem(API.export_registry._REG, 'mechanical', SimpleNamespace(preview=preview, export=export))
    app = FastAPI()

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(status_code=error.http_status, content={'ok': False, **error.to_payload()})

    app.include_router(API.router)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, factory=factory, tracker=tracker, captured=captured)


def draft(**changes):
    return {'warehouse': '甲', 'ym': '2026-09', 'category': 'zero', 'revision': 0,
            'rows': [{'id': 'row-a', 'device': '升降车', 'amount': '103.00', 'tax': '3%专',
                      'rate': '103.00', 'qty': '1', 'date': '1日至3日', 'plate': ''}], **changes}


def test_get_post_public_contract_and_persisted_confirmation(api):
    response = api.client.get('/api/m06/workbench', params={'ym': '2026-09'})
    assert response.status_code == 200
    initial = response.json()
    assert {p['warehouse'] for p in initial['projects']} == {'甲', '乙'}
    assert initial['details'] == []
    effective = next(r for r in initial['effective'] if r['warehouse'] == '甲')
    assert effective['values']['mech_2'] is None
    saved = api.client.post('/api/m06/workbench/details-save', json=draft())
    assert saved.status_code == 200
    assert saved.json()['totals'] == {'gross': '103.00', 'net': '100.00'}
    state = api.client.get('/api/m06/workbench', params={'ym': '2026-09'}).json()
    assert state['details'][0]['rows'][0]['date'] == '1日至3日'
    assert next(r for r in state['effective'] if r['warehouse'] == '甲')['values']['mech_2'] is None
    confirmed = api.client.post('/api/m06/workbench/amounts-confirm', json={
        'warehouse': '甲', 'ym': '2026-09', 'category': 'zero', 'revision': saved.json()['revision'],
        'effective_signature': effective['signature']})
    assert confirmed.status_code == 200
    assert confirmed.json()['values']['mech_2'] == '103.00'
    with api.factory() as session:
        assert str(session.scalar(select(ProcMechManual)).mech_4) == '100.00'


@pytest.mark.parametrize('name,payload', [('unsupported-action', {}), ('details-save', draft(warehouse='未知项目'))])
def test_illegal_action_and_unmapped_warehouse_do_not_write(api, name, payload):
    response = api.client.post('/api/m06/workbench/' + name, json=payload)
    assert response.status_code == 400
    assert response.json()['ok'] is False
    with api.factory() as session:
        assert list(session.scalars(select(MechanicalWorkbenchRecord))) == []
        assert list(session.scalars(select(ProcMechManual))) == []
    assert api.tracker['rollbacks'] == 1


def test_route_failure_rolls_back_already_flushed_changes(api, monkeypatch):
    original_action = workbench.action

    def fail_after_write(session, name, payload, operator=''):
        original_action(session, name, payload, operator)
        raise MustReportError('模拟确认失败，整次写入回滚')

    monkeypatch.setattr(workbench, 'action', fail_after_write)
    response = api.client.post('/api/m06/workbench/details-save', json=draft())
    assert response.status_code == 400
    assert api.tracker['rollbacks'] == 1
    with api.factory() as session:
        assert list(session.scalars(select(MechanicalWorkbenchRecord))) == []
    assert api.client.get('/api/m06/workbench').json()['details'] == []


def test_json_import_confirmation_failure_rolls_back_every_batch_and_can_retry(api, monkeypatch):
    from tests.test_mechanical_workbench import row

    batches = [{'warehouse': '甲', 'ym': '2026-09', 'category': category,
                'source': {'file': '合成原件'}, 'rows': [row(id=category)]}
               for category in ('zero', 'monthly')]
    response = api.client.post('/api/m06/workbench/import-preview',
                               json={'request_id': 'atomic-failure', 'batches': batches})
    assert response.status_code == 200
    preview_id = response.json()['preview_id']
    payload = {'preview_id': preview_id, 'confirm_amounts': True}
    original = workbench.confirm_amounts
    confirmed = []

    def fail_on_second_batch(session, data, operator=''):
        result = original(session, data, operator)
        confirmed.append(data['category'])
        if len(confirmed) == 2:
            raise MustReportError('第二类确认失败')
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(workbench, 'confirm_amounts', fail_on_second_batch)
        failed = api.client.post('/api/m06/workbench/import-confirm', json=payload)
    assert failed.status_code == 400 and confirmed == ['zero', 'monthly']
    with api.factory() as session:
        assert list(session.scalars(select(MechanicalWorkbenchRecord))) == []
        assert list(session.scalars(select(ProcMechManual))) == []
        assert session.get(MechanicalWorkbenchPreview, preview_id).result is None
    retried = api.client.post('/api/m06/workbench/import-confirm', json=payload)
    assert retried.status_code == 200
    with api.factory() as session:
        values = workbench.effective(session, '甲', '2026-09')['values']
        assert values['mech_2'] == values['mech_3'] == '103.00'
        assert values['mech_4'] == values['mech_5'] == '100.00'


def test_preview_export_read_only_saved_state_and_freeze_each_result(api):
    assert api.client.post('/api/m06/workbench/details-save', json=draft()).status_code == 200
    # An incoming GET query cannot insert a browser's unsaved draft into output.
    params = {'ym': '2026-09', 'projects': json.dumps(['甲']),
              'rows': json.dumps([{'id': 'unsaved', 'amount': '9999.00'}])}
    preview = api.client.get('/api/m06/workbench/preview', params=params)
    assert preview.status_code == 200
    snapshot = preview.json()['snapshot']
    assert snapshot['details'][0]['rows'][0]['amount'] == '103.00'
    assert snapshot['effective'][0]['values']['mech_2'] is None
    first = api.client.get('/api/m06/workbench/export', params=params)
    assert first.status_code == 200
    assert json.loads(first.content)['details'][0]['rows'][0]['amount'] == '103.00'
    changed = draft(revision=1)
    changed['rows'][0]['amount'] = '206.00'
    assert api.client.post('/api/m06/workbench/details-save', json=changed).status_code == 200
    second = api.client.get('/api/m06/workbench/export', params=params)
    assert json.loads(second.content)['details'][0]['rows'][0]['amount'] == '206.00'
    assert json.loads(first.content)['details'][0]['rows'][0]['amount'] == '103.00'
    assert api.captured['exports'][0]['details'][0]['rows'][0]['amount'] == '103.00'


@pytest.mark.parametrize('route', ['preview', 'export'])
def test_export_unknown_project_is_rejected_before_exporter(api, route):
    response = api.client.get('/api/m06/workbench/' + route,
                              params={'ym': '2026-09', 'projects': json.dumps(['甲', '不存在'])})
    assert response.status_code == 400
    assert '映射' in response.json()['message']
    assert not api.captured['previews'] and not api.captured['exports']


def test_i8_network_fetch_happens_outside_database_session(api, monkeypatch):
    from datetime import datetime
    calls = []
    fetched_at = []

    class Client:
        def __init__(self, *, allow_kick):
            assert allow_kick
            assert api.tracker['active'] == 0
            calls.append('create')

        def close(self):
            assert api.tracker['active'] == 0
            calls.append('close')

    def fetch_lists(client):
        assert isinstance(client, Client)
        assert api.tracker['active'] == 0
        calls.append('fetch')
        fetched_at.append(datetime.now())
        return {'usage': {'total': 1, 'rows': [{'id': 'u1', 'projectId': 'i8-a', 'projectName': '甲原项目',
                                               'amount': '100.00', 'approval': None}]},
                'project': {'total': 0, 'rows': []}, 'team': {'total': 0, 'rows': []}}

    monkeypatch.setattr(workbench_i8, 'I8Client', Client)
    monkeypatch.setattr(workbench_i8, 'fetch_lists', fetch_lists)
    response = api.client.post('/api/m06/workbench/i8-fetch', json={'request_id': 'network-boundary', 'allow_kick': True})
    assert response.status_code == 200
    body = response.json()
    assert body['counts'] == {'usage': 1, 'project': 0, 'team': 0}
    assert body['projects'][0]['warehouse'] == '甲'
    assert body['projects'][0]['totals']['usage'] == '100.00'
    with api.factory() as session:
        record = session.get(RunRecord, body['run_record_id'])
        assert record.status == 'success'
        assert record.triggered_by == 'isolated-test'
        assert record.total_count == record.success_count == 1
        assert record.started_at <= fetched_at[0] <= record.finished_at
        assert record.detail['counts'] == body['counts']
    assert calls == ['create', 'fetch', 'close']
    assert api.tracker['active'] == 0
    state = api.client.get('/api/m06/workbench').json()
    assert len(state['discoveries']) == 1
    assert state['i8'] == []  # Fetch is a preview until an explicit confirmation.


def test_i8_network_failure_does_not_open_write_session(api, monkeypatch):
    def fail_read(projects, previous, **kw):
        assert api.tracker['active'] == 0
        raise MustReportError('读取失败，旧值保持')

    monkeypatch.setattr(workbench_i8, 'read_preview', fail_read)
    response = api.client.post('/api/m06/workbench/i8-fetch', json={})
    assert response.status_code == 400
    assert api.tracker['commits'] == 2  # Project lookup and independent failure record.
    assert api.tracker['rollbacks'] == 0
    with api.factory() as session:
        assert list(session.scalars(select(MechanicalWorkbenchRecord))) == []
        assert list(session.scalars(select(MechanicalWorkbenchPreview))) == []
        record = session.scalar(select(RunRecord).where(RunRecord.target == '机械费三类来源（当前累计）')
                                .order_by(RunRecord.id.desc()))
        assert record.status == 'failed' and record.triggered_by == 'isolated-test'
        assert record.error_message == '读取失败，旧值保持'


def test_fetch_passes_shell_archive_and_keywords_without_holding_session(api, monkeypatch):
    from app.mod01_projects import service as projects_service
    from app.mod06_proc.workbench_i8 import normalize
    with api.factory.begin() as s:
        shell = Project(project_type='shell', name_full='小微壳', phid='shared-key')
        s.add(shell)
        s.flush()
        shell_id = shell.id
        for wh, keyword in [('甲', '大唐'), ('乙', '百利')]:
            row = s.scalar(select(Project).where(Project.warehouse_name == wh))
            row.phid, row.project_type, row.parent_shell_id, row.match_keywords = 'shared-key', 'small', shell_id, [keyword]
    original_all = projects_service.all_projects
    monkeypatch.setattr(projects_service, 'all_projects', lambda s: [*original_all(s), s.get(Project, shell_id)])

    class Client:
        def __init__(self, **kw):
            assert api.tracker['active'] == 0
            assert kw == {'allow_kick': False}
        def close(self):
            pass

    monkeypatch.setattr(workbench_i8, 'I8Client', Client)
    lists = {kind: {'total': 2, 'rows': [normalize({'phid': keyword + kind, 'phid_pc': 'shared-key',
              'bill_name': keyword, 'u_fyze': '10', 'u_bqjse': '10', 'u_bqspe': '10'}, kind)
              for keyword in ('大唐', '百利')]} for kind in ('usage', 'project', 'team')}
    monkeypatch.setattr(workbench_i8, 'fetch_lists', lambda client: deepcopy(lists))
    response = api.client.post('/api/m06/workbench/i8-fetch', json={'request_id': 'keywords'})
    assert response.status_code == 200
    preview = response.json()
    assert preview['unmapped_projects'] == []
    assert {p['warehouse'] for p in preview['projects']} == {'甲', '乙'}
    assert all(len(rows) == 1 for p in preview['projects'] for rows in p['sources'].values())
    assert api.client.post('/api/m06/workbench/i8-confirm', json={
        'preview_id': preview['preview_id'], 'warehouses': ['甲', '乙']}).status_code == 200


def test_i8_preview_failure_rolls_back_business_but_keeps_execution_record(api, monkeypatch):
    incoming = {'projects': [{'warehouse': '甲', 'projectId': 'i8-a',
        'sources': {'usage': [{'id': 'u', 'projectId': 'i8-a', 'amount': '1.00'}], 'project': [], 'team': []},
        'complete': {'usage': True, 'project': True, 'team': True}}], 'counts': {'usage': 1, 'project': 0, 'team': 0}}
    monkeypatch.setattr(workbench_i8, 'read_preview', lambda projects, previous, **kw: deepcopy(incoming))
    action = workbench.action

    def fail_after_preview(session, name, payload, operator=''):
        action(session, name, payload, operator)
        raise MustReportError('预览未保存')

    monkeypatch.setattr(workbench, 'action', fail_after_preview)
    response = api.client.post('/api/m06/workbench/i8-fetch', json={})
    assert response.status_code == 400
    with api.factory() as session:
        assert list(session.scalars(select(MechanicalWorkbenchRecord))) == []
        assert list(session.scalars(select(MechanicalWorkbenchPreview))) == []
        record = session.scalar(select(RunRecord).where(RunRecord.target == '机械费三类来源（当前累计）')
                                .order_by(RunRecord.id.desc()))
        assert record.status == 'failed' and record.error_message == '预览未保存'


def test_complete_empty_fetch_requires_evidence_before_zeroing_old_project(api, monkeypatch):
    first = {'projects': [{'warehouse': '甲', 'projectId': 'i8-a',
        'sources': {'usage': [{'id': 'u', 'projectId': 'i8-a', 'amount': '100.00'}], 'project': [], 'team': []},
        'complete': {'usage': True, 'project': True, 'team': True}}]}
    preview = api.client.post('/api/m06/workbench/i8-preview', json=first).json()
    assert api.client.post('/api/m06/workbench/i8-confirm', json={
        'preview_id': preview['preview_id'], 'warehouses': ['甲']}).status_code == 200

    class Client:
        def __init__(self, **kw):
            pass
        def close(self):
            pass

    monkeypatch.setattr(workbench_i8, 'I8Client', Client)
    monkeypatch.setattr(workbench_i8, 'fetch_lists', lambda client: {
        kind: {'total': 0, 'rows': []} for kind in ('usage', 'project', 'team')})
    reduced = api.client.post('/api/m06/workbench/i8-fetch', json={'request_id': 'all-empty'}).json()
    assert reduced['projects'][0]['warehouse'] == '甲'
    assert reduced['projects'][0]['reduction'] is True
    request = {'preview_id': reduced['preview_id'], 'warehouses': ['甲']}
    assert api.client.post('/api/m06/workbench/i8-confirm', json=request).status_code == 400
    state = api.client.get('/api/m06/workbench').json()
    assert state['i8'][0]['totals']['usage'] == '100.00'
    assert api.client.post('/api/m06/workbench/i8-confirm', json={**request,
        'allow_reduction': True, 'reduction_reason': '已核实查询权限与范围，全部作废'}).status_code == 200
    state = api.client.get('/api/m06/workbench').json()
    assert state['i8'][0]['totals']['usage'] == '0.00'
