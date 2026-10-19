"""Serve the real mechanical shell against a new owned SQLite fixture on localhost only."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import MetaData, UniqueConstraint, create_engine, inspect
from sqlalchemy.orm import sessionmaker
import uvicorn

from app.core import config, db
from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod03_notice.page import render_theme, DEFAULT_THEME
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc import workbench as W, workbench_api, workbench_i8
from app.mod06_proc.workbench_history import exact_projects, load_history_payload, verify_source_hashes
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord, MechanicalWorkbenchPreview
from app.export_bindings import register_all
from app.mod02_i8.client import I8Client
from app.mod02_i8.models import RunRecord
from validate_history import keep_existing

ARTIFACTS = ROOT / '.artifacts/machinery-fee-workflow'
OUTPUT = ARTIFACTS / 'implementation-20261019'
WEB = ROOT / 'backend/app/web'


def blocked(*args, **kwargs):
    raise RuntimeError('隔离现场禁止生产连接或i8请求')


def replay_lists():
    old_live = json.loads((ARTIFACTS / 'live-capture-20261017/i8-lists.json').read_text(encoding='utf-8'))
    lists = {kind: {'total': int(old_live['lists'][code]['total']),
                    'rows': deepcopy(old_live['lists'][code]['rows'])}
             for kind, code in [('usage', 'sbsy'), ('project', 'xmxhd'), ('team', 'jxxhd')]}
    return lists, old_live['capturedAt']


def validate_reuse(database, engine, metadata):
    database = database.resolve(strict=True)
    if database.parent != OUTPUT.resolve(strict=True) or database.name != 'ui.sqlite':
        raise ValueError('只能复用本任务目录内的ui.sqlite')
    receipt = json.loads((OUTPUT / 'ui-isolation.json').read_text(encoding='utf-8'))
    owner = 'current machinery-fee effort; stop this PID before deleting owned ui.sqlite'
    if (receipt.get('scope') != 'isolated-only' or receipt.get('cleanup_owner') != owner
            or Path(receipt.get('database', '')).resolve() != database):
        raise ValueError('无法确认SQLite副本属于本隔离脚本')
    schema = inspect(engine)
    actual_tables = set(schema.get_table_names())
    if actual_tables not in (set(metadata.tables), set(metadata.tables) - {RunRecord.__tablename__}):
        raise ValueError('隔离副本必须具有本脚本的业务表及可选旧版执行记录表')
    for name, table in metadata.tables.items():
        if name == RunRecord.__tablename__ and name not in actual_tables:
            continue
        reflected = {column['name']: column for column in schema.get_columns(name)}
        if set(reflected) != set(table.c.keys()):
            raise ValueError('隔离副本列结构不匹配：' + name)
        for column in table.c:
            actual = reflected[column.name]['type'].compile(dialect=engine.dialect)
            expected = column.type.compile(dialect=engine.dialect)
            if actual != expected:
                raise ValueError('隔离副本列类型不匹配：' + name + '.' + column.name)
        if set(schema.get_pk_constraint(name)['constrained_columns']) != {c.name for c in table.primary_key}:
            raise ValueError('隔离副本主键不匹配：' + name)
        actual_unique = {tuple(sorted(item['column_names'])) for item in schema.get_unique_constraints(name)}
        expected_unique = {tuple(sorted(column.name for column in item.columns))
                           for item in table.constraints if isinstance(item, UniqueConstraint)}
        if actual_unique != expected_unique:
            raise ValueError('隔离副本唯一约束不匹配：' + name)
    return receipt


def prepare(*, reuse=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    database = (OUTPUT / 'ui.sqlite').resolve()
    if database.parent != OUTPUT.resolve() or database.name != 'ui.sqlite':
        raise ValueError('隔离数据库真实路径超出本任务目录')
    # Exclusive creation makes ownership concrete and protects any earlier acceptance fixture.
    if reuse:
        if not database.is_file():
            raise ValueError('复用的隔离数据库不存在')
    else:
        with database.open('xb'):
            pass
    engine = create_engine('sqlite:///' + database.as_posix(), connect_args={'check_same_thread': False})
    assert Path(engine.url.database).resolve() == database.resolve()
    metadata = MetaData()
    for model in (Project, ProcMechManual, MechanicalWorkbenchRecord, MechanicalWorkbenchPreview, RunRecord):
        table = model.__table__.to_metadata(metadata)
        if model is ProcMechManual:
            table.c.source_batches.server_default = None
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    lists, captured_at = replay_lists()
    if reuse:
        receipt = validate_reuse(database, engine, metadata)
        metadata.tables[RunRecord.__tablename__].create(engine, checkfirst=True)
        receipt.update(pid=os.getpid(), reused=True)
        (OUTPUT / 'ui-isolation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
        return engine, factory, lists, captured_at
    metadata.create_all(engine)
    initial = load_history_payload(ARTIFACTS)
    verify_source_hashes(initial['source_hashes'])
    mappings = {item['report_project']: f'__history_validation_{item["source_index"]}__'
                for item in initial['unmapped']}
    payload = load_history_payload(ARTIFACTS, mappings=mappings)
    system = json.loads((ARTIFACTS / 'technical-feasibility-20261017/history/system.json').read_text(encoding='utf-8'))
    seed = json.loads((ARTIFACTS / 'prototype-20261017/jan-sep-seed.json').read_text(encoding='utf-8'))
    mapped = exact_projects(system)
    phids = {mapped[name]: seed['data']['i8'][index]['projectId']
             for index, name in enumerate(seed['names'])
             if name in mapped and seed['data']['i8'][index].get('projectId')}
    with factory() as s:
        s.add_all(Project(id=p['id'], warehouse_name=p['warehouse_name'], disp=p['disp'],
                          phid=p.get('phid') or phids.get(p['warehouse_name'], ''),
                          status=p['status'], project_type=p['project_type']) for p in system['projects'])
        s.flush()
        s.add_all(Project(warehouse_name=wh, disp=name, status='archived') for name, wh in mappings.items())
        for row in system['effective']:
            s.add(ProcMechManual(id=row['id'], ym=row['ym'], project_id=row['project_id'],
                                warehouse_name=row['warehouse_name'], source_batches=row['source_batches'],
                                **{f'mech_{i}': Decimal(row[f'mech_{i}']) for i in range(6)}))
        s.flush()
        history = W.history_preview(s, payload['history_import'])
        W.history_confirm(s, {'preview_id': history['preview_id'], 'resolutions': keep_existing(history)})
        details = W.import_preview(s, payload['detail_import'])
        assert not any(item['conflicts'] for item in details['batches'])
        W.import_confirm(s, {'preview_id': details['preview_id'], 'confirm_amounts': False})
        projects = W.state(s)['projects']
        incoming = workbench_i8.preview_payload(lists, projects)
        for item in incoming['projects'] + incoming['unmapped_projects']:
            item['fetched_at'] = captured_at
            item['scope'] = '隔离回放：2026-10-17旧快照；没有现场联网'
        incoming['request_id'] = 'isolated-old-snapshot-initial'
        preview = W.i8_preview(s, incoming)
        W.i8_confirm(s, {'preview_id': preview['preview_id'],
                         'warehouses': [item['warehouse'] for item in preview['projects'] if item['complete']]})
        shown = [mapped[seed['names'][index]] for index in seed['data']['selected'] if seed['names'][index] in mapped]
        W.action(s, 'settings', {'revision': W.settings(s)['revision'], 'shown_projects': shown,
                                'plate_keywords': W.DEFAULT_KEYWORDS})
        s.commit()
        current = W.state(s)
        assert sum(len(item['rows']) for item in current['details']) == 1966
        snapshot = W.snapshot(s, '2026-09', shown)
        (OUTPUT / 'ui-snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        receipt = {'pid': os.getpid(), 'database': str(database), 'scope': 'isolated-only',
                   'source_hashes_verified': verify_source_hashes(payload['source_hashes']),
                   'details': 1966, 'histories': len(current['histories']), 'shown_projects': shown,
                   'i8_snapshot_counts': incoming['counts'], 'i8_unmapped_projects': len(incoming['unmapped_projects']),
                   'phid_source': 'snapshot phid where present, otherwise reviewed historical seed mapping',
                   'cleanup_owner': 'current machinery-fee effort; stop this PID before deleting owned ui.sqlite'}
        (OUTPUT / 'ui-isolation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
    return engine, factory, lists, captured_at


def serve(*, reuse=False):
    engine, factory, lists, captured_at = prepare(reuse=reuse)

    @contextmanager
    def isolated_session():
        with factory() as s:
            try:
                yield s
                s.commit()
            except BaseException:
                s.rollback()
                raise

    def replay(projects):
        result = workbench_i8.preview_payload(deepcopy(lists), projects)
        for item in result['projects'] + result['unmapped_projects']:
            item['fetched_at'] = captured_at
            item['scope'] = '隔离回放：2026-10-17旧快照；没有现场联网'
        return result

    db.get_engine = blocked
    db.get_session_factory = blocked
    db.session_scope = isolated_session
    I8Client.request = blocked
    workbench_i8.read_preview = replay
    workbench_api.session_scope = isolated_session
    workbench_api.current_operator = lambda: '隔离验证用户'
    config.get_settings = lambda: SimpleNamespace(artifacts_path=OUTPUT, app_env='isolated')
    register_all()
    app = FastAPI(title='机械费隔离验收；没有生产连接', docs_url=None, redoc_url=None)

    @app.middleware('http')
    async def isolation_header(request, call_next):
        response = await call_next(request)
        response.headers['X-Isolated-Fixture'] = 'true'
        return response

    @app.exception_handler(MustReportError)
    async def business_error(request, exc):
        return JSONResponse({'ok': False, 'message': str(exc), 'isolation': True}, status_code=400)

    @app.get('/healthz')
    def health():
        return {'status': 'ok', 'isolation': True, 'pid': os.getpid(), 'i8': 'offline-old-snapshot-replay'}

    @app.get('/app')
    def shell():
        text = (WEB / 'index.html').read_text(encoding='utf-8')
        marker = '<script>boot();</script>'
        assert text.count(marker) == 1
        boot = "CUR={id:'isolated',acc:'isolated',name:'隔离验证用户',role:'user'};VIEW='m10';MW.month='2026-09';document.title='机械费隔离验证 · 旧快照回放';loadPaths(PAGE_LOAD.m10).then(()=>{BOOTING=false;render()});"
        text = text.replace(marker, '<script>' + boot + '</script>')
        text = text.replace('</body>', '<div style="position:fixed;bottom:0;left:0;z-index:99999;background:#fff4d5;color:#654b00;padding:3px 10px;font-size:12px">隔离验证 · SQLite副本 · 307/69/129旧快照回放 · 不联网</div></body>')
        return HTMLResponse(text)

    @app.get('/static/theme.css')
    def theme():
        return Response(render_theme(DEFAULT_THEME), media_type='text/css')

    @app.get('/api/m06/mech')
    def empty_mech():
        return {'ok': True, 'mech': {}, 'columns': [], 'isolation': True}

    @app.get('/api/m06/matrix')
    def empty_matrix():
        return {'ok': True, 'rows': [], 'projects': [], 'months': [], 'isolation': True}

    app.include_router(workbench_api.router)
    app.mount('/static', StaticFiles(directory=WEB), name='real-shell-static')

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def isolated_only(path):
        return JSONResponse({'ok': False, 'message': '隔离现场未开放此入口', 'isolation': True}, status_code=403)

    uvicorn.run(app, host='127.0.0.1', port=8777, log_level='warning')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse', action='store_true', help='核验本脚本副本后复用，兼容补建本任务执行记录表；保留现场操作')
    serve(reuse=parser.parse_args().reuse)
