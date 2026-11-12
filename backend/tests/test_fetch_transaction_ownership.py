"""Real root transactions and independent lock probes; no i8 or source database access."""
from hashlib import sha256
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import db, history
from app.core.history import OperationHistory, actor_key
from app.mod01_projects import repository as projects
from app.mod01_projects.models import TYPE_NORMAL
from app.mod02_i8.models import RunRecord


@pytest.fixture
def isolated_engine():
    assert os.environ.get('MTRL_TEST_SOURCE_ENV'), 'Use backend_verify with its explicit disposable schema'
    engine = db.get_engine()
    with engine.connect() as connection:
        database, schema = connection.execute(text('SELECT current_database(), current_schema()')).one()
        assert database.endswith('_test') and schema.startswith('backend_verify_'), 'Refuse shared/public schemas'
    return engine


@pytest.mark.parametrize('domain', ['setl', 'inv', 'jc'])
def test_fetch_releases_connection_and_actor_lock_until_atomic_apply(domain, monkeypatch, tmp_path, isolated_engine):
    # backend_verify supplies a fresh isolated schema. No rollback_db fixture:
    # its outer transaction would keep locks beyond application scope exit.
    engine = isolated_engine
    actor = '450-' + uuid4().hex
    key = int.from_bytes(sha256(actor.encode()).digest()[:4], 'big', signed=True)
    warehouse = '450-' + domain + '-' + uuid4().hex
    full_name = warehouse + '项目'
    with db.session_scope() as session:
        if domain != 'jc':
            projects.create_project(session, project_type=TYPE_NORMAL, name_full=full_name,
                                    warehouse_name=warehouse, phid='450')
        prior = OperationHistory(actor=actor_key(actor), label='prior', state='undone', changes=[])
        session.add(prior)
        session.flush()
        prior_id = prior.id

    calls = []

    def lock_available():
        with engine.connect() as connection:
            return connection.execute(text('SELECT pg_try_advisory_xact_lock(384,:key)'), {'key': key}).scalar_one()

    def external(stage, result=None):
        assert engine.pool.checkedout() == 0, f'{stage} still owns a database connection'
        assert lock_available(), f'{stage} still holds the account transaction lock'
        calls.append(stage)
        return result

    client = SimpleNamespace(close=lambda: external('close'))
    if domain == 'setl':
        from app.mod07_setl import fetch_service as fetch
        from app.mod07_setl.api import api_fetch, FetchRequest
        from tests.test_acc_setl_fetch import build_xlsx, _line, _values, _total_line
        content = build_xlsx([_line(_values(code='R450', warehouse=warehouse)), _total_line()])
        monkeypatch.setattr(fetch, '_load_wh_rows', lambda c: external('warehouse', []))
    elif domain == 'inv':
        from app.mod08_inv import fetch_service as fetch
        from app.mod08_inv.router import api_fetch, FetchRequest
        from tests.test_acc_inv_fetch import _xlsx, _row
        content = _xlsx([_row(doc_no='450-' + uuid4().hex, wh=warehouse)])
        monkeypatch.setattr(fetch, 'load_warehouse_rows', lambda c: external('warehouse', []))
        monkeypatch.setattr(fetch.source_cache, 'DIR', tmp_path / 'source')
    else:
        from app.mod11_jc import fetch_service as fetch
        from app.mod11_jc.api import api_fetch, FetchIn
        rows = [{'contract_no': '450-' + uuid4().hex, 'project_name': full_name,
                 'party_name': '450-party', 'supplier_name': '450-supplier', 'contract_amt': '10.00',
                 'sign_date': '2026-08-01', 'fields': {'PhId': '450', 'BillName': '450'}}]
        monkeypatch.setattr(fetch, 'ContractFetcher', lambda c: SimpleNamespace(
            fetch_in_locked_batch=lambda **kw: external('list', rows),
            fetch_item_name=lambda phid: external('detail', '材料')))

        def common():
            external('common')
            # Another actor archives the project while i8 is in flight. Apply
            # must use current local facts, not the pre-fetch project snapshot.
            with Session(engine) as session, session.begin():
                projects.create_project(session, project_type=TYPE_NORMAL, name_full=full_name,
                                        warehouse_name=warehouse, phid='450-new')
            return []

        monkeypatch.setattr(fetch, 'default_loaders', lambda c: (common, lambda: external('warehouse', [])))

    monkeypatch.setattr(fetch, 'open_i8_client', lambda **kw: external('factory', client))
    if domain != 'jc':
        monkeypatch.setattr(fetch.report_export, 'export', lambda *a, **kw: external('export', content))
    original_record = fetch.save_run_record

    def record(session, **kwargs):
        assert not lock_available(), 'apply lost the actor lock before its receipt'
        return original_record(session, **kwargs)

    monkeypatch.setattr(fetch, 'save_run_record', record)
    token, state = history.begin_request(actor, 'POST', '/api/450/fetch')
    try:
        result = api_fetch(FetchIn(confirm=True) if domain == 'jc' else FetchRequest(month='2026-08', confirm=True))
        assert result['ok'] is True
        assert result['matched'] == 1 if domain == 'jc' else result['rows'] == 1
        assert state.root is None and state.result == 'unsupported'
    finally:
        history.end_request(token)
    assert lock_available()
    assert set(calls) == ({'factory', 'list', 'detail', 'common', 'warehouse', 'close'} if domain == 'jc'
                          else {'factory', 'export', 'warehouse', 'close'})
    with db.session_scope() as session:
        assert session.get(RunRecord, result['run_record_id']) is not None
        operations = session.scalars(select(OperationHistory).where(OperationHistory.actor == actor_key(actor))).all()
        assert len(operations) == 2
        assert session.get(OperationHistory, prior_id).state == 'discarded'
        assert len([op for op in operations if op.state == 'barrier']) == 1


@pytest.mark.parametrize('initially_ignored', [False, True])
def test_jc_rejects_changed_ignore_scope_before_any_apply(initially_ignored, isolated_engine, monkeypatch):
    from sqlalchemy import func
    from app.core.errors import MustReportError
    from app.mod11_jc import fetch_service as fetch, repository as contracts

    actor='450-rule-'+uuid4().hex
    name='450-rule-project-'+uuid4().hex
    no='450-rule-contract-'+uuid4().hex
    with db.session_scope() as session:
        projects.create_project(session, project_type=TYPE_NORMAL, name_full=name, warehouse_name=name, phid='450-rule')
        rule=contracts.add_ignored(session,name_full=name) if initially_ignored else None
        before=session.scalar(select(func.count()).select_from(RunRecord))

    def change_rule():
        token,_=history.begin_request(actor,'POST','/api/m14/jc-ignore')
        try:
            with db.session_scope() as session:
                if rule:contracts.delete_ignored(session,ignore_id=rule['id'])
                else:contracts.add_ignored(session,name_full=name)
        finally:history.end_request(token)
        return []

    applied=[]
    monkeypatch.setattr(fetch,'sync_and_archive',lambda *a,**kw:applied.append(True) or {})
    token,_=history.begin_request(actor,'POST','/api/m11/fetch')
    try:
        with pytest.raises(MustReportError,match='剔除名单已变化'):
            fetch.run_fetch(confirmed=True,
                client_factory=lambda:SimpleNamespace(close=lambda:None),
                fetch=lambda client:[{'contract_no':no,'project_name':name,'contract_amt':'10.00'}],
                loaders=(change_rule,lambda:[]))
    finally:history.end_request(token)
    assert not applied
    with db.session_scope() as session:
        assert contracts.one_by_no(session,no) is None
        assert session.scalar(select(func.count()).select_from(RunRecord))==before
