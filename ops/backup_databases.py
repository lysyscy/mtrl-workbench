"""用本机pg_dump备份两库，校验归档与摘要后发布；失败不覆盖既有备份。"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def _run(exe: Path, args: list[str], env: dict | None = None) -> bytes:
    result = subprocess.run([str(exe), *args], env=env, capture_output=True, timeout=600)
    if result.returncode:
        # 数据库口令只传子进程环境；错误不回显连接配置或原始参数。
        raise RuntimeError(f"{exe.name} failed: exit {result.returncode}")
    return result.stdout


def verify_backup(folder: Path, pg_bin: Path) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or set(manifest.get('files', {})) != {'development.dump', 'test.dump'}:
        raise ValueError('Invalid backup manifest')
    for name, item in manifest['files'].items():
        raw = (folder / name).read_bytes()
        if not raw or len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Backup checksum mismatch')
        toc = _run(pg_bin / 'pg_restore.exe', ['--list', str(folder / name)])
        if not any(line.strip() and not line.startswith(b';') for line in toc.splitlines()):
            raise ValueError('Empty archive table of contents')
    return manifest


def backup_databases(urls: dict[str, str], pg_bin: Path, output: Path) -> Path:
    parsed = {key: make_url(value) for key, value in urls.items()}
    if set(parsed) != {'development', 'test'}:
        raise ValueError('Both project databases are required')
    identities = {(u.host, u.port or 5432, u.database) for u in parsed.values()}
    if len(identities) != 2 or any(u.host not in {'localhost', '127.0.0.1', '::1'} for u in parsed.values()):
        raise ValueError('Expected two distinct local databases')
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone()
    name = stamp.strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8]
    pending = output / ('.partial-' + name)
    pending.mkdir()
    manifest = {'version': 1, 'created': stamp.isoformat(), 'files': {}}
    for key, url in parsed.items():
        env = {**os.environ, 'PGHOST': url.host, 'PGPORT': str(url.port or 5432),
               'PGUSER': url.username or '', 'PGPASSWORD': url.password or '',
               'PGDATABASE': url.database or '', 'PGCONNECT_TIMEOUT': '10'}
        file = pending / (key + '.dump')
        _run(pg_bin / 'pg_dump.exe', ['--no-password', '--format=custom', '--file', str(file)], env)
        raw = file.read_bytes()
        manifest['files'][file.name] = {'database': url.database, 'bytes': len(raw),
                                       'sha256': hashlib.sha256(raw).hexdigest()}
    (pending / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    verify_backup(pending, pg_bin)
    complete = output / name
    pending.rename(complete)
    return complete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'var/backups/databases')
    parser.add_argument('--verify', type=Path, help='只读核对一份已完成备份')
    args = parser.parse_args()
    try:
        if args.verify:
            verify_backup(args.verify, args.pg_bin)
            print('Backup archive and checksums verified')
        else:
            sys.path.insert(0, str(ROOT / 'backend'))
            from app.core.config import get_settings
            settings = get_settings()
            saved = backup_databases({'development': settings.database_url,
                                      'test': settings.test_database_url}, args.pg_bin, args.output)
            receipt = {'ok': True, 'backup': str(saved), 'checked': datetime.now().astimezone().isoformat()}
            print(saved)
    except Exception as error:
        print(f'Backup failed ({type(error).__name__}); previous backups retained', file=sys.stderr)
        if not args.verify:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / 'last-run.json').write_text(json.dumps({
                'ok': False, 'error': type(error).__name__,
                'checked': datetime.now().astimezone().isoformat()}), encoding='utf-8')
        return 1
    if not args.verify:
        pending_receipt = args.output / ('.receipt-' + uuid4().hex + '.json')
        pending_receipt.write_text(json.dumps(receipt), encoding='utf-8')
        pending_receipt.replace(args.output / 'last-run.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
