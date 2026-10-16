"""Archived dependency audit; historical evidence, not a current entry point."""
import ast
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from collections import defaultdict

out = defaultdict(list)
for root in ['backend/app', 'backend/tests', 'backend/alembic', 'tools', 'skills']:
    for p in Path(root).rglob('*.py'):
        if any(s in p.parts for s in ('.venv', '__pycache__')):
            continue
        try:
            tree = ast.parse(p.read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError):
            print('UNPARSED', p)
            continue
        for n in ast.walk(tree):
            mods = [a.name.split('.')[0] for a in n.names] if isinstance(n, ast.Import) else ([n.module.split('.')[0]] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else [])
            for m in mods:
                if m not in sys.stdlib_module_names:
                    out[m].append(str(p))
print('IMPORTS')
for k, v in sorted(out.items()):
    print(k, len(set(v)), ', '.join(sorted(set(v))[:6]))
lock = tomllib.loads(Path('backend/uv.lock').read_text(encoding='utf-8'))
print('LOCK', len(lock['package']))
for p in lock['package']:
    print(p['name'], '->', ','.join(d['name'] for d in p.get('dependencies', [])), 'OPTIONAL', str(p.get('optional-dependencies', {})))
commands = [
    ['uv', '--version'],
    ['backend/.venv/Scripts/python.exe', '-X', 'utf8', '-c', 'import importlib.metadata as m,json,sys; print(sys.version); print(json.dumps([{\'name\':d.metadata[\'Name\'],\'version\':d.version,\'requires\':d.requires} for d in m.distributions()]))'],
    ['rg', '-n', 'gmssl|Cryptodome|cryptodomex|xlsxwriter|loguru|requests|httpx|multipart|websocket|uvicorn|import_module|__import__', 'backend/app', 'tools', 'ops', 'skills'],
    ['rg', '-n', r'requirements\.(txt|in|lock)|pip install|pip compile|pip sync|pip.ini|uv sync|uv run', 'ops', 'tools', 'backend', 'README.md', 'docs/guides', '-g', '!uv.lock'],
]
for c in commands:
    r = subprocess.run(c, capture_output=True, encoding='utf-8')
    if r.returncode not in (0, 1) or (r.returncode == 1 and c[0] != 'rg'):
        raise RuntimeError((c, r.returncode, r.stderr))
    print('COMMAND', c, 'RC', r.returncode)
    print(r.stdout, r.stderr)
