"""守实际付款金额、付款日期、撤销剔除与选桶合计；只变异有业务后果的出口。"""
from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('统计误用单据日期', 'app/mod05_flow/service.py',
     'str(f.pay_date or "")', 'n.doc_date'),
    ('欠款人工值污染付款统计', 'app/mod05_flow/service.py',
     'to_money(f.amount)', 'n.pay_stat'),
    ('撤销混入统计', 'app/mod05_flow/service.py',
     'f.status == FLOW_EFFECTIVE', 'f.status in (FLOW_EFFECTIVE, FLOW_REVOKED)'),
    ('剔除混入统计', 'app/mod05_flow/service.py',
     'if not n.excluded', 'if True'),
    ('选桶失效', 'app/web/shell/pages-a.js',
     'const picked=st.selected;', 'const picked=undefined;'),
    ('窗口误用全量', 'app/web/shell/pages-a.js',
     'total: N2(right.reduce((a,v)=>a+numOr0(v),0))', 'total: numOr0(st.total)'),
]

with isolated_backend('tail275-') as (base, env):
    for shell in (False, True):
        group = [c for c in CASES if c[1].startswith('app/web/') == shell]
        cwd = ROOT / 'backend' if shell else base
        runenv = dict(env)
        if shell:
            runenv['MTRL_UI_FIXTURE_WEB'] = str(base / 'app/web')
        args = [sys.executable, '-X', 'utf8', '-m', 'pytest',
                'tests/test_tail275_stats.py' if shell else 'tests/test_acc_flow_pst.py', '-q', '--tb=short']
        green = subprocess.run(args, cwd=cwd, env=runenv, capture_output=True,
                               text=True, encoding='utf-8', timeout=90)
        assert green.returncode == 0, green.stdout + green.stderr
        for name, rel, old, new in group:
            path = base / rel
            raw = path.read_bytes()
            body = raw.decode('utf-8')
            assert old in body, name
            path.write_bytes(body.replace(old, new).encode('utf-8'))
            try:
                red = subprocess.run(args, cwd=cwd, env=runenv, capture_output=True,
                                     text=True, encoding='utf-8', timeout=90)
                assert red.returncode == 1 and 'FAILED' in red.stdout and 'ERROR' not in red.stdout, red.stdout + red.stderr
                print(name + ': 正常绿 / 隔离缺陷红', flush=True)
            finally:
                path.write_bytes(raw)
print('6/6 反向灵敏度通过', flush=True)
