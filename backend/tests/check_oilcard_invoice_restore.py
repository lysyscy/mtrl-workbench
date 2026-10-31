"""Explicit pg_dump/pg_restore drill; requires MTRL_PG_BIN and backend_verify."""
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import session as SESS
from app.core.db import get_engine, session_scope
from app.main import create_app
from app.mod01_projects.models import Project
from tests.oilcard_invoice_samples import invoice_pdf
from tests.test_oilcard_invoices import receive, setup_account
from tests.test_oilcard_invoice_adjustments import allocation, correct


def test_custom_dump_restore_recovers_original_and_accounting(monkeypatch, tmp_path, request):
    # This drill intentionally commits so an external pg_dump sees the bytes.
    # Refuse even the ordinary test schema: backend_verify owns final cleanup.
    schema = os.environ.get('PGOPTIONS', '').split('search_path=', 1)[-1]
    assert re.fullmatch(r'backend_verify_[0-9a-f]{32}', schema), '必须由backend_verify独占schema执行恢复演练'
    pg_bin = Path(os.environ['MTRL_PG_BIN']).resolve(strict=True)
    engine = get_engine()
    url = make_url(engine.url)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT current_schema()')) == schema
        version = connection.scalar(text('SHOW server_version_num'))
    env = os.environ.copy()
    env.update(PGHOST=url.host, PGPORT=str(url.port or 5432), PGUSER=url.username,
               PGPASSWORD=url.password or '', PGDATABASE=url.database)
    executable_version = subprocess.run([str(pg_bin / 'pg_dump.exe'), '--version'], check=True, capture_output=True, text=True, encoding='utf-8').stdout
    assert str(int(version) // 10000) in executable_version
    from app import history_api
    monkeypatch.setattr(SESS, 'secret', lambda: b'oilcard-restore-isolated-only')
    monkeypatch.setattr(history_api, 'active_account', lambda s, identity: object())
    with session_scope() as session:
        project = Project(project_type='normal', name_full='原件恢复合成项目', warehouse_name='__oilcard_restore__', disp='恢复测试')
        session.add(project); session.flush(); project_id = project.id
    def cleanup():
        # Own rows only; do not leave a committed example for later tests.
        with engine.begin() as connection:
            connection.execute(text('DELETE FROM oil_invoice_original WHERE invoice_id IN (SELECT invoice_id FROM oil_invoice_allocation WHERE project_id=:id)'), {'id': project_id})
            invoice_ids = list(connection.scalars(text('SELECT invoice_id FROM oil_invoice_allocation WHERE project_id=:id'), {'id': project_id}))
            connection.execute(text('DELETE FROM oil_invoice_allocation WHERE project_id=:id'), {'id': project_id})
            for invoice_id in invoice_ids:
                connection.execute(text('DELETE FROM oil_invoice_number WHERE invoice_id=:id'), {'id': invoice_id})
                connection.execute(text('DELETE FROM oil_invoice WHERE id=:id'), {'id': invoice_id})
            card_ids = list(connection.scalars(text('SELECT card_id FROM oil_account WHERE project_id=:id'), {'id': project_id}))
            connection.execute(text('DELETE FROM oil_account_assignment WHERE project_id=:id'), {'id': project_id})
            connection.execute(text('DELETE FROM oil_account WHERE project_id=:id'), {'id': project_id})
            for card_id in card_ids:
                connection.execute(text('DELETE FROM oil_card WHERE id=:id'), {'id': card_id})
            connection.execute(text('DELETE FROM project WHERE id=:id'), {'id': project_id})
    request.addfinalizer(cleanup)
    content = invoice_pdf()
    with TestClient(create_app()) as client:
        client.cookies.set(SESS.COOKIE_NAME, SESS.make('__oilcard_restore__'))
        account = setup_account(client, project_id)
        registered = receive(client, content)
        original_id = registered['original']['id']
        adjusted = correct(client, registered['item'], [allocation(account, '3000')], invoice_no='20261031000000000009')
        assert adjusted.status_code == 200, adjusted.text
        archive = tmp_path / 'invoice-originals.dump'
        def run(executable, *args):
            result = subprocess.run([str(pg_bin / executable), *args], env=env, check=True,
                capture_output=True, text=True, encoding='utf-8')
            return result.stdout
        run('pg_dump.exe', '--no-password', '--format=custom', '--no-owner', '--no-privileges',
            '--schema', schema, '--table', schema + '.oil_invoice*', '--file', str(archive))
        toc = run('pg_restore.exe', '--list', str(archive))
        assert 'TABLE DATA' in toc and 'oil_invoice_original' in toc and archive.stat().st_size > 0
        with engine.begin() as connection:
            connection.execute(text('TRUNCATE oil_invoice_allocation, oil_invoice_original, oil_invoice_number, oil_invoice RESTART IDENTITY'))
        assert client.get('/api/m13/invoices').json()['invoices'] == []
        run('pg_restore.exe', '--no-password', '--data-only', '--no-owner', '--no-privileges',
            '--exit-on-error', '--dbname', url.database, str(archive))
        recovered = client.get(f'/api/m13/invoices/originals/{original_id}')
        assert recovered.status_code == 200
        assert recovered.content == content
        assert sha256(recovered.content).hexdigest() == registered['original']['sha256']
        assert client.get('/api/m13/invoices').json()['total_amount'] == '3000.00'
        assert client.get('/api/m13/reconciliation').json()['invoiced_amount'] == '3000.00'
        historical = receive(client, invoice_pdf(variant='restored old number metadata'))
        corrected = receive(client, invoice_pdf(number='20261031000000000009'))
        assert historical['item']['id'] == corrected['item']['id'] == registered['item']['id']
        assert len(client.get('/api/m13/invoices').json()['invoices']) == 1
        assert client.get('/api/m13/invoices').json()['total_amount'] == '3000.00'
