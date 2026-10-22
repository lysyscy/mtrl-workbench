"""Local business snapshot for the owned frontend preview; never writes its source."""
from __future__ import annotations
import hashlib
import json
import re
from sqlalchemy import MetaData, Table, create_engine, inspect, literal, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

OMITTED = {'app_setting', 'app_setting_log', 'operation_history', 'run_record'}
LOCAL = {'localhost', '127.0.0.1', '::1'}


def identifier(value):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', value):
        raise ValueError('Unsupported database identifier')
    return '"' + value + '"'


def projection(table):
    columns = []
    for column in table.columns:
        if table.name == 'user_account' and column.name in {'password', 'i8_user', 'i8_password'}:
            columns.append(literal('').label(column.name))
        elif table.name == 'user_account' and column.name == 'account':
            columns.append((literal('preview-source-') + table.c.id.cast(column.type)).label(column.name))
        elif table.name == 'user_account' and column.name == 'status':
            columns.append(literal('已停用').label(column.name))
        else:
            columns.append(column)
    return select(*columns).order_by(*table.primary_key.columns)


def fingerprint(connection, statement):
    digest = hashlib.sha256(); count = 0
    for row in connection.execute(statement).mappings():
        digest.update(json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))
        digest.update(b'\n'); count += 1
    return count, digest.hexdigest()


def copy_snapshot(source, target, source_schema, target_schema):
    """Connections are caller-owned; source must already be a read-only RR snapshot."""
    if source.exec_driver_sql('SHOW transaction_read_only').scalar_one() != 'on':
        raise RuntimeError('Source transaction must be read only')
    if source.exec_driver_sql('SHOW transaction_isolation').scalar_one() not in {'repeatable read', 'serializable'}:
        raise RuntimeError('Source requires a consistent snapshot')
    if source is target or source_schema == target_schema:
        raise RuntimeError('Source and target must be isolated')
    si, ti = inspect(source), inspect(target)
    tables = set(si.get_table_names(schema=source_schema))
    if tables != set(ti.get_table_names(schema=target_schema)):
        raise RuntimeError('Source and preview table sets differ')
    revision = lambda c, schema: c.exec_driver_sql(f'SELECT version_num FROM {identifier(schema)}.alembic_version').scalars().all()
    if revision(source, source_schema) != revision(target, target_schema):
        raise RuntimeError('Source and preview migrations differ')
    ordered = si.get_sorted_table_and_fkc_names(schema=source_schema)
    if any(name is None and keys for name, keys in ordered):
        raise RuntimeError('Cyclic foreign keys need a dedicated copy procedure')
    retained = tables - OMITTED - {'alembic_version'}
    for name in tables:
        if si.get_pk_constraint(name, schema=source_schema)['constrained_columns'] != ti.get_pk_constraint(name, schema=target_schema)['constrained_columns']:
            raise RuntimeError('Primary keys differ')
        for method in ['get_unique_constraints', 'get_check_constraints']:
            if getattr(si, method)(name, schema=source_schema) != getattr(ti, method)(name, schema=target_schema):
                raise RuntimeError('Unique or check constraints differ')
        def foreign_keys(inspector, schema):
            return [{**fk, 'referred_schema': 'self' if fk['referred_schema'] in {None, schema} else fk['referred_schema']} for fk in inspector.get_foreign_keys(name, schema=schema)]
        if foreign_keys(si, source_schema) != foreign_keys(ti, target_schema):
            raise RuntimeError('Foreign keys differ')
    for name in retained:
        for fk in si.get_foreign_keys(name, schema=source_schema):
            if fk['referred_schema'] not in {None, source_schema} or fk['referred_table'] not in retained:
                raise RuntimeError('Copy would leave an external or omitted foreign key')
    names = ','.join(f'{identifier(target_schema)}.{identifier(name)}' for name in sorted(tables - {'alembic_version'}))
    target.exec_driver_sql('TRUNCATE TABLE ' + names + ' RESTART IDENTITY')
    receipt = {'tables': {}, 'omitted': sorted(OMITTED), 'sequences': 0}
    for name, _ in ordered:
        if name not in retained:
            continue
        st = Table(name, MetaData(), schema=source_schema, autoload_with=source, resolve_fks=False)
        tt = Table(name, MetaData(), schema=target_schema, autoload_with=target, resolve_fks=False)
        if list(st.columns.keys()) != list(tt.columns.keys()):
            raise RuntimeError('Copy column sets differ')
        statement = projection(st)
        rows = source.execute(statement).mappings()
        self_fks = [fk for fk in si.get_foreign_keys(name, schema=source_schema) if fk['referred_table'] == name]
        if self_fks:
            pending = [dict(row) for row in rows]; inserted = set()
            while pending:
                keys = {tuple(row[col] for col in fk['referred_columns']) for row in pending for fk in self_fks}
                ready = [row for row in pending if all(any(row[col] is None for col in fk['constrained_columns']) or tuple(row[col] for col in fk['constrained_columns']) not in keys or tuple(row[col] for col in fk['constrained_columns']) in inserted for fk in self_fks)]
                if not ready:
                    raise RuntimeError('Self-referential records cannot be safely ordered')
                target.execute(tt.insert(), ready)
                for row in ready:
                    for fk in self_fks: inserted.add(tuple(row[col] for col in fk['referred_columns']))
                ready_ids = {id(row) for row in ready}; pending = [row for row in pending if id(row) not in ready_ids]
        else:
            while batch := rows.fetchmany(500):
                target.execute(tt.insert(), [dict(row) for row in batch])
        expected = fingerprint(source, statement)
        actual = fingerprint(target, select(*(tt.c[c.name] for c in st.columns)).order_by(*(tt.c[c.name] for c in st.primary_key.columns)))
        if expected != actual:
            raise RuntimeError('Copied row count or content digest differs')
        receipt['tables'][name] = {'rows': actual[0], 'sha256': actual[1]}
    for sequence in si.get_sequence_names(schema=source_schema):
        if sequence not in ti.get_sequence_names(schema=target_schema):
            raise RuntimeError('Sequence missing from preview')
        value, called = source.exec_driver_sql(f'SELECT last_value,is_called FROM {identifier(source_schema)}.{identifier(sequence)}').one()
        target.execute(text('SELECT setval(CAST(:name AS regclass), :value, :called)'), {'name': f'{target_schema}.{sequence}', 'value': value, 'called': called})
        receipt['sequences'] += 1
    target.exec_driver_sql('SET CONSTRAINTS ALL IMMEDIATE')
    from app import core_bindings
    core_bindings.register_all()
    from app.mod05_flow.service import build_ledger
    with Session(bind=source, join_transaction_mode='rollback_only') as left, Session(bind=target, join_transaction_mode='rollback_only') as right:
        projects = source.exec_driver_sql(f"SELECT id FROM {identifier(source_schema)}.project WHERE project_type <> 'shell' ORDER BY id").scalars().all()
        digest = hashlib.sha256()
        for project in projects:
            before, after = build_ledger(left, project_id=project), build_ledger(right, project_id=project)
            if before != after:
                raise RuntimeError('Copied ledger rows or amounts differ')
            digest.update(json.dumps(before, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))
        receipt['ledger_projects_verified'] = len(projects)
        receipt['ledger_sha256'] = digest.hexdigest()
    return receipt


def clone_from_source(source_url, target_url, target_schema):
    origin, destination = make_url(source_url), make_url(target_url)
    if origin.host not in LOCAL or destination.host not in LOCAL or origin.database == destination.database:
        raise RuntimeError('Copy requires separate local source and test databases')
    source_engine = create_engine(source_url, isolation_level='REPEATABLE READ', hide_parameters=True)
    target_engine = create_engine(target_url, connect_args={'options': f'-c search_path={target_schema}'}, hide_parameters=True)
    try:
        with source_engine.connect() as source, source.begin(), target_engine.begin() as target:
            source.exec_driver_sql('SET TRANSACTION READ ONLY')
            if source.exec_driver_sql('SELECT current_database()').scalar_one() != origin.database or target.exec_driver_sql('SELECT current_database()').scalar_one() != destination.database:
                raise RuntimeError('Actual database identity differs')
            if target.exec_driver_sql('SHOW search_path').scalar_one() != target_schema:
                raise RuntimeError('Preview search path differs')
            receipt = copy_snapshot(source, target, 'public', target_schema)
        from tools.audit.workspace_paths import output
        output('preview-copy-verification.json', kind='logs').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(f"COPY verified tables={len(receipt['tables'])} sequences={receipt['sequences']} ledger_projects={receipt['ledger_projects_verified']}", flush=True)
    except Exception as error:
        detail = str(error) if type(error) is RuntimeError else type(error).__name__
        raise RuntimeError(f'隔离复制未完成：{detail}；源库未写入') from None
    finally:
        source_engine.dispose(); target_engine.dispose()


def restrict_copy_preview(app):
    from fastapi.responses import JSONResponse
    reads = {'/healthz', '/app', '/login', '/api/m15/users', '/api/m01/projects', '/api/history/status',
             '/api/m05/ledger', '/api/m05/ledger/export', '/api/m05/debt', '/api/m05/debt/export', '/api/m05/stats', '/api/m05/flows'}
    writes = {'/m15/login', '/api/m15/logout', '/api/m05/history/save', '/api/m05/history/delete', '/m05/ledger/remark', '/api/history/undo', '/api/history/redo'}
    @app.middleware('http')
    async def local_only(request, call_next):
        path = request.url.path
        allowed = request.method in {'GET', 'HEAD'} and (path in reads or path.startswith(('/preview/', '/static/')))
        allowed = allowed or request.method == 'POST' and path in writes
        if not allowed:
            return JSONResponse(status_code=403, content={'ok': False, 'message': '隔离预览仅开放台账本地操作。'})
        return await call_next(request)
    return app
