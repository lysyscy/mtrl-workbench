"""本机备份发布前必须校验；失败或坏档不能冒充完整备份。"""
import importlib.util
from pathlib import Path

import pytest

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('database_backup', ROOT / 'ops/backup_databases.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
URLS = {'development': 'postgresql://fixture:dummy@127.0.0.1/dev',
        'test': 'postgresql://fixture:dummy@127.0.0.1/test'}


@acc()
def test_backup_publishes_only_verified_archives_and_detects_corruption(tmp_path, monkeypatch):
    def pg(exe, args, env=None):
        if exe.name == 'pg_dump.exe':
            assert env['PGPASSWORD'] == 'dummy' and all('dummy' not in arg for arg in args)
            Path(args[-1]).write_bytes(b'fixture archive ' + env['PGDATABASE'].encode())
            return b''
        return b'; archive header\n1; 1259 1 TABLE public fixture\n'

    monkeypatch.setattr(backup, '_run', pg)
    completed = backup.backup_databases(URLS, tmp_path, tmp_path / 'backups')
    assert not completed.name.startswith('.partial-')
    assert backup.verify_backup(completed, tmp_path)['files']['development.dump']['database'] == 'dev'
    (completed / 'test.dump').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        backup.verify_backup(completed, tmp_path)


@acc()
def test_failed_second_database_preserves_old_backup_and_never_publishes(tmp_path, monkeypatch):
    output = tmp_path / 'backups'
    previous = output / 'previous'
    previous.mkdir(parents=True)
    (previous / 'saved.dump').write_bytes(b'original')

    def fail(exe, args, env=None):
        if env['PGDATABASE'] == 'test':
            raise RuntimeError('fixture failure')
        Path(args[-1]).write_bytes(b'partial')

    monkeypatch.setattr(backup, '_run', fail)
    with pytest.raises(RuntimeError, match='fixture failure'):
        backup.backup_databases(URLS, tmp_path, output)
    assert (previous / 'saved.dump').read_bytes() == b'original'
    assert [p.name for p in output.iterdir() if not p.name.startswith('.partial-')] == ['previous']


@acc()
def test_backup_rejects_remote_or_identical_database_before_writing(tmp_path):
    for urls in ({**URLS, 'test': URLS['development']},
                 {**URLS, 'test': 'postgresql://fixture@remote.invalid/test'}):
        with pytest.raises(ValueError):
            backup.backup_databases(urls, tmp_path, tmp_path / 'backups')
        assert not (tmp_path / 'backups').exists()
