"""守机械台账真实来源与大表合计首格：断线、错列、串项目及解除固定均应红。"""
from pathlib import Path
import subprocess
import sys
import shutil
from _isolated import isolated_backend
CASES = [('机械来源断线', 'app/mod05_flow/service.py', 'mech_settle_by_month=mech_settle if cat == CATEGORY_MECH else None', 'mech_settle_by_month={} if cat == CATEGORY_MECH else None', 'tests/test_tail273_ledger.py'), ('错取不含税列', 'app/mod05_flow/service.py', "[r.get('mech_2'), r.get('mech_3')]", "[r.get('mech_4'), r.get('mech_5')]", 'tests/test_tail273_ledger.py'), ('混入别项目', 'app/mod05_flow/service.py', "r.get('warehouse') == wh", 'True', 'tests/test_tail273_ledger.py')]
with isolated_backend('tail273-') as (base, env):
    shutil.copytree(Path(__file__).resolve().parents[2] / 'tools/audit', base.parent / 'tools/audit', ignore=shutil.ignore_patterns('__pycache__'))
    for name, rel, old, new, test in CASES:
        args = [sys.executable, '-X', 'utf8', '-m', 'pytest', test, '-q', '--tb=short']
        normal = subprocess.run(args, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=45)
        assert normal.returncode == 0, normal.stdout + normal.stderr
        p = base / rel
        raw = p.read_bytes()
        text = raw.decode('utf-8').replace('\r\n', '\n')
        assert text.count(old) == 1, (name, text.count(old))
        p.write_text(text.replace(old, new), encoding='utf-8')
        try:
            red = subprocess.run(args, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=45)
            assert red.returncode == 1 and 'FAILED' in red.stdout and ('ERROR' not in red.stdout), red.stdout + red.stderr
            print(name + ': 正常绿 / 指定缺陷红', flush=True)
        finally:
            p.write_bytes(raw)
print('4/4 反向灵敏度通过', flush=True)
