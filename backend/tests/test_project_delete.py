"""空档案可删，任何关联和查询失败均拒删；只使用回滚测试库。"""
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text

from app.core.db import Base, session_scope
from app.core.errors import MustReportError
from app.mod01_projects import deletion as D
from app.mod01_projects.models import Project


def project(s, **kw):
    name = '__delete_' + uuid4().hex
    p = Project(name_full=name, warehouse_name=name, disp=name, **kw)
    s.add(p)
    s.flush()
    return p


def test_empty_delete_only_selected_and_tables_match_actual_schema(rollback_db):
    with session_scope() as s:
        p, other = project(s), project(s)
        preview = D.impact(s, p.id)
        assert preview['can_delete'] and all(g['count'] == 0 for g in preview['groups'])
        assert '不可撤销' in preview['message']
        covered = {g['table'] for g in preview['groups']}
        actual = inspect(s.connection())
        expected = set()
        for name in actual.get_table_names():
            keys = {c['name'] for c in actual.get_columns(name)}
            fks = actual.get_foreign_keys(name)
            if keys & {'warehouse_name', 'project_key'} or any(fk['referred_table'] == 'project' for fk in fks):
                expected.add(name)
        assert expected <= covered, expected - covered
        assert D.delete_project(s, p.id)['ok']
        assert s.get(Project, p.id) is None and s.get(Project, other.id) is other
        locked = set(s.execute(text("SELECT relation::regclass::text FROM pg_locks WHERE pid=pg_backend_pid() AND mode='ShareRowExclusiveLock'" )).scalars())
        assert covered <= locked


REFERENCES = [
    ('project_field_log', 'project_id'), ('payment_notice', 'ownership_id'),
    ('plan_row', 'project_id'), ('payment_flow', 'project_id'),
    ('opening_balance', 'project_id'), ('ledger_remark', 'project_id'),
    ('proc_mech_match_rule', 'warehouse_name'), ('proc_mech_manual', 'warehouse_name'),
    ('proc_history_batch', 'warehouse_name'), ('proc_history_snapshot', 'warehouse_name'),
    ('proc_cutoff', 'warehouse_name'), ('proc_mech_import_change', 'warehouse_name'),
    ('setl_detail', 'warehouse_name'), ('weldgas_balance', 'warehouse_name'),
    ('analysis_big_project', 'warehouse_name'), ('analysis_big_manual', 'warehouse_name'),
    ('inv_detail', 'warehouse_name'), ('fee_manual_item', 'project_id'),
    ('jc_contract', 'project_id'), ('jc_import_batch', 'project_key'),
]


@pytest.mark.parametrize('table,key', REFERENCES)
def test_each_reference_refuses_without_loss(rollback_db, table, key):
    with session_scope() as s:
        p = project(s, status='archived')
        model = next(m.class_ for m in Base.registry.mappers if m.local_table.name == table)
        values = {key: p.id if key.endswith('_id') else p.warehouse_name}
        # Fill only mandatory non-default fields; the real model keeps its own defaults.
        for c in model.__table__.columns:
            if c.name in values or c.nullable or c.default is not None or c.server_default is not None or c.autoincrement is True:
                continue
            if c.primary_key:
                continue
            t = c.type.python_type
            values[c.name] = ({str: '__del', int: 0, list: [], dict: {}}.get(t, 0))
        row = model(**values)
        s.add(row)
        s.flush()
        result = D.impact(s, p.id)
        group = next(g for g in result['groups'] if g['table'] == table)
        assert not result['can_delete'] and group['count'] == 1 and len(group['rows']) == 1
        with pytest.raises(MustReportError, match='不能删除'):
            D.delete_project(s, p.id)
        assert s.get(Project, p.id) is p
        assert s.execute(select(model)).scalars().all().count(row) == 1


def test_hierarchy_recheck_and_read_failure(rollback_db, monkeypatch):
    from app.mod07_setl import service
    from app.mod09_fee.models import FeeManualItem

    with session_scope() as s:
        p = project(s, project_type='shell')
        child = project(s, project_type='small', parent_shell_id=p.id)
        assert not D.impact(s, p.id)['can_delete']
        assert not D.impact(s, child.id)['can_delete']
        empty = project(s)
        assert D.impact(s, empty.id)['can_delete']
        row = FeeManualItem(project_id=empty.id, ym='2026-10', item_name='new reference', amount=1)
        s.add(row)
        s.flush()
        with pytest.raises(MustReportError, match='特殊费用'):
            D.delete_project(s, empty.id)
        def fail(*args, **kw):
            raise RuntimeError('isolated read failure')
        monkeypatch.setattr(service, 'project_references', fail)
        with pytest.raises(RuntimeError, match='isolated read failure'):
            D.delete_project(s, empty.id)
        assert s.get(Project, empty.id) is empty


def test_text_key_insert_cannot_race_delete_check(rollback_db):
    from sqlalchemy import insert
    from sqlalchemy.exc import OperationalError
    from app.core.db import get_engine
    from app.mod07_setl.models import WeldGasBalance

    with session_scope() as s:
        p = project(s)
        assert D.impact(s, p.id, lock=True)['can_delete']
        with get_engine().connect() as other:
            other.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(OperationalError, match='lock timeout'):
                other.execute(insert(WeldGasBalance).values(kind='weld', warehouse_name=p.warehouse_name, amount=1))
            other.rollback()
        assert D.delete_project(s, p.id)['ok']


def test_empty_shell_without_warehouse_can_delete(rollback_db):
    with session_scope() as s:
        p = Project(name_full='__empty_shell_' + uuid4().hex, project_type='shell', warehouse_name=None)
        s.add(p)
        s.flush()
        assert D.impact(s, p.id)['can_delete']
        assert D.delete_project(s, p.id)['ok']
        assert s.get(Project, p.id) is None


def test_delete_api_requires_confirmation(rollback_db):
    from app.mod01_projects.router import delete_project

    with pytest.raises(MustReportError, match='确认删除'):
        delete_project(1, confirmed=False)
