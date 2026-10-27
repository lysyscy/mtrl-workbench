"""Historical material edit, readback and workbook use the same stored value."""
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod06_proc import repository as R, service as M6
from app.mod06_proc.models import ProcHistoryBatch, ProcHistorySnapshot, ProcMaterialManual
from app.mod06_proc.router import MaterialSaveRequest, api_material_save
from app.report_export import service as EX


def test_save_readback_and_export(rollback_db, monkeypatch, tmp_path):
    ProcMaterialManual.__table__.create(rollback_db, checkfirst=True)
    wh = '__material_' + uuid4().hex
    batch = '__batch_' + uuid4().hex
    monkeypatch.setattr(R, 'load_inv_rows', lambda s: [])
    monkeypatch.setattr(R, 'load_mech', lambda s: [])
    monkeypatch.setattr(M6, 'load_cutoffs', lambda s: {})
    monkeypatch.setattr(M6, 'displays_by_key', lambda s: {wh: '测试项目'})
    monkeypatch.setattr(EX, 'EXPORT_ROOT', tmp_path)
    with session_scope() as s:
        s.add(ProcHistoryBatch(batch_no=batch, warehouse_name=wh, status='active'))
        s.add(ProcHistorySnapshot(batch_no=batch, warehouse_name=wh, ym='2025-11',
                                  in_0=100, in_1=20))
    req = MaterialSaveRequest(warehouse=wh, ym='2025-11', column='in_主辅材', value='-12.34', expected='100')
    assert api_material_save(req)['ok'] is True
    api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='out_工具', value='0', expected='0'))
    api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='in_主辅材', value='', expected='-12.34'))
    with session_scope() as s:
        row = M6.build_matrices(s, warehouses=[wh])['matrices'][wh]['raw'][0]
        assert row['in_主辅材'] is None and row['in_工具'] == Decimal('20')
    api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='in_主辅材', value='-12.34', expected=None))
    with session_scope() as s:
        matrix = M6.build_matrices(s, warehouses=[wh])['matrices'][wh]
        for kind in ('raw', 'adjusted'):
            row = matrix[kind][0]
            assert row['in_主辅材'] == Decimal('-12.34')
            assert row['in_工具'] == Decimal('20')
            assert row['out_工具'] == Decimal('0')
            assert matrix['totals'][kind]['in_主辅材'] == Decimal('-12.34')
        snapshot = s.scalar(select(ProcHistorySnapshot).where(ProcHistorySnapshot.batch_no == batch))
        assert snapshot.in_0 == Decimal('100')
        refs = M6.project_references(s, None, wh)
        assert next(group for group in refs if group['table'] == 'proc_material_manual')['count'] == 2
        paths = [EX.export_proc(s, [wh], tab, ym='2026-10') for tab in (0, 1)]
    for path in paths:
        book = openpyxl.load_workbook(path, data_only=True)
        try:
            sheet = book['汇总表']
            assert sheet['B4'].value == '2025-11'
            assert Decimal(str(sheet['C4'].value)) == Decimal('-12.34')
            assert Decimal(str(sheet['D4'].value)) == Decimal('20')
            assert Decimal(str(sheet['C5'].value)) == Decimal('-12.34')
        finally:
            book.close()
    with pytest.raises(MustReportError):
        api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-12', column='in_主辅材', value='1', expected=None))
    with pytest.raises(MustReportError):
        api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='mech_0', value='1', expected=None))
    with pytest.raises(MustReportError, match='其他操作修改'):
        api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='in_主辅材', value='55', expected='100'))
    monkeypatch.setattr(R, 'load_inv_rows', lambda s: [{'warehouse': wh, 'ym': '2025-11'}])
    with pytest.raises(MustReportError, match='库存'):
        api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-11', column='in_主辅材', value='55', expected='-12.34'))
    with session_scope() as s:
        assert s.scalar(select(ProcMaterialManual).where(ProcMaterialManual.warehouse_name == wh,
                        ProcMaterialManual.column_key == 'in_主辅材')).amount == Decimal('-12.34')


def test_manual_new_month_preserves_other_empty_cells():
    from app.mod06_proc import domain as D
    row = D.build_matrix(inv_rows=[], history_rows=[{'warehouse': 'A', 'ym': '2025-10',
        'material_manual': True, 'in_工具': Decimal('0')}], warehouse='A', adjusted=False)[0]
    assert row['in_工具'] == Decimal('0')
    assert row['in_主辅材'] is None
    assert row['material_editable'] is True


def test_history_material_create_update_undo(rollback_db, monkeypatch):
    from app.core import history
    from app.history_bindings import configure
    ProcMaterialManual.__table__.create(rollback_db, checkfirst=True)
    monkeypatch.setattr(R, 'load_inv_rows', lambda s: [])
    configure()
    actor, wh = '__material_actor_' + uuid4().hex, '__material_' + uuid4().hex
    def save(value, expected):
        token, state = history.begin_request(actor, 'POST', '/api/m06/material')
        try:
            api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-10', column='in_工具', value=value, expected=expected))
            assert state.result == 'recorded'
        finally:
            history.end_request(token)
    def replay(direction):
        with session_scope() as s:
            item = history.status(s, actor)[direction]
            return history.replay(s, actor, direction, item['id'])
    def value():
        with session_scope() as s:
            row = s.scalar(select(ProcMaterialManual).where(ProcMaterialManual.warehouse_name == wh))
            return row.amount if row else None
    save('1.25', None)
    save('2.50', '1.25')
    replay('undo')
    assert value() == Decimal('1.25')
    replay('undo')
    assert value() is None
    replay('redo')
    assert value() == Decimal('1.25')


def test_history_cannot_redo_after_project_deleted(rollback_db, monkeypatch):
    from app.core import history
    from app.history_bindings import configure
    from app.mod01_projects.models import Project
    ProcMaterialManual.__table__.create(rollback_db, checkfirst=True)
    monkeypatch.setattr(R, 'load_inv_rows', lambda s: [])
    configure()
    actor, wh = '__material_actor_' + uuid4().hex, '__material_' + uuid4().hex
    with session_scope() as s:
        project = Project(project_type='normal', name_full=wh, warehouse_name=wh, disp='测试')
        s.add(project); s.flush(); project_id = project.id
    token, state = history.begin_request(actor, 'POST', '/api/m06/material')
    try:
        api_material_save(MaterialSaveRequest(warehouse=wh, ym='2025-10', column='in_工具', value='1', expected=None))
        assert state.result == 'recorded'
    finally:
        history.end_request(token)
    with session_scope() as s:
        row = s.scalar(select(ProcMaterialManual).where(ProcMaterialManual.warehouse_name == wh))
        assert row.project_id == project_id
        history.replay(s, actor, 'undo', history.status(s, actor)['undo']['id'])
    with session_scope() as s:
        s.delete(s.get(Project, project_id))
    with pytest.raises(MustReportError, match='所属项目'):
        with session_scope() as s:
            history.replay(s, actor, 'redo', history.status(s, actor)['redo']['id'])


def test_http_save_and_matrix_readback(rollback_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core import session as SESS
    ProcMaterialManual.__table__.create(rollback_db, checkfirst=True)
    monkeypatch.setattr(SESS, 'secret', lambda: b'material-test-only')
    monkeypatch.setattr(R, 'load_inv_rows', lambda s: [])
    monkeypatch.setattr(R, 'load_mech', lambda s: [])
    monkeypatch.setattr(M6, 'load_cutoffs', lambda s: {})
    wh = '__material_http_' + uuid4().hex
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__material_actor__'))
        response = client.post('/api/m06/material', json={'warehouse': wh, 'ym': '2025-08',
                               'column': 'in_工具', 'value': '3.20', 'expected': None})
        assert response.status_code == 200 and response.json()['ok'] is True
        assert response.headers.get('X-Operation-History') == 'recorded'
        response = client.get('/api/m06/matrix')
        assert response.status_code == 200
        row = response.json()['matrices'][wh]['adjusted'][0]
        assert Decimal(str(row['in_工具'])) == Decimal('3.20')
        assert row['out_工具'] is None


def test_migration_creates_expected_table(rollback_db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text
    schema = 'material_check_' + uuid4().hex
    rollback_db.execute(text(f'CREATE SCHEMA "{schema}"'))
    rollback_db.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    rollback_db.execute(text('CREATE TABLE project (id INTEGER PRIMARY KEY)'))
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/pmat261027_process_material_manual.py'
    spec = importlib.util.spec_from_file_location('material_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(rollback_db)):
        migration.upgrade()
    cols = {column['name'] for column in inspect(rollback_db).get_columns('proc_material_manual', schema=schema)}
    assert cols == {'id', 'warehouse_name', 'project_id', 'ym', 'column_key', 'amount'}
