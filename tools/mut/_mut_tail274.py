"""守期初两侧独立、统计口径与导出单次累计：隔离源码错取、断线、重复累计须红。"""
from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend
CASES = [('空日期付款丢失', 'app/mod05_flow/service.py', 'opening_auto=automatic if history_segment else None', 'opening_auto=Decimal("0") if history_segment else None'), ('手动付款混入自动', 'app/mod05_flow/domain.py', 'auto = to_money(opening_auto)', 'auto = to_money(opening_auto) + paid'), ('导出取内部三行重复累计', 'app/report_export/ledger_export.py', 'side.get("display_rows", side.get("rows"))', 'side.get("rows")'), ('编辑总额覆盖手动值', 'app/mod05_flow/service.py', 'paid = to_money(payment) - to_money(auto["payment"])', 'paid = to_money(payment)'), ('零付款历史段消失', 'app/mod05_flow/service.py', 'or bool(historical_notices)', 'or automatic != 0')]
with isolated_backend('tail274-') as (base, env):
    args = [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_tail274_ledger.py', '-q', '--tb=short']
    normal = subprocess.run(args, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert normal.returncode == 0, normal.stdout + normal.stderr
    for name, rel, old, new in CASES:
        path = base / rel
        raw = path.read_bytes()
        text = raw.decode('utf-8')
        assert old in text, name
        path.write_bytes(text.replace(old, new).encode('utf-8'))
        try:
            shell_case = rel.startswith('app/web/')
            test_args = args if not shell_case else [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_wired_m05.py', '-q', '--tb=short']
            if shell_case:
                import shutil
                shutil.copytree(Path(__file__).resolve().parents[2] / 'tools/audit', base.parent / 'tools/audit', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
                shutil.copytree(Path(__file__).resolve().parents[2] / 'tools/probe', base.parent / 'tools/probe', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
                path.write_bytes(raw)
                green = subprocess.run(test_args, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
                assert green.returncode == 0, green.stdout + green.stderr
                path.write_bytes(text.replace(old, new).encode('utf-8'))
            red = subprocess.run(test_args, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
            assert red.returncode == 1 and 'FAILED' in red.stdout and ('ERROR' not in red.stdout), red.stdout + red.stderr
            print(name + ': 正常绿 / 指定缺陷红', flush=True)
        finally:
            path.write_bytes(raw)
print('8/8 隔离反向灵敏度通过', flush=True)
