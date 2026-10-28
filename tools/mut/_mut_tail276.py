"""集采关联金额动态取统计付款且不回退审批额；日期适配只在隔离副本造错。"""
from pathlib import Path
import os
import subprocess
import sys
from _isolated import isolated_backend

def main():
    with isolated_backend('tmp-tail276-') as (base, env):
        env['PYTHONPATH'] = os.pathsep.join([str(base), str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / 'tools/audit')])
        cmd = [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_tail276_jc.py', '-q', '--tb=short']

        def run():
            return subprocess.run(cmd, cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)
        normal = run()
        assert normal.returncode == 0, normal.stdout + normal.stderr
        cases = [('app/mod11_jc/repository.py', 'Decimal(str(stat_paid or 0)) if linked else r.amount', 'r.amount'), ('app/mod11_jc/service.py', 'amount=0, source=SRC_NOTICE', 'amount=s.get(PaymentNotice, int(notice_id)).amount_approved, source=SRC_NOTICE')]
        for name, old, new in cases:
            path = base / name
            source = path.read_text(encoding='utf-8')
            assert source.count(old) == 1, name
            try:
                path.write_text(source.replace(old, new), encoding='utf-8')
                red = run()
                assert red.returncode and 'FAILED ' in red.stdout, red.stdout + red.stderr
                print('PASS 隔离反例：', name, flush=True)
            finally:
                path.write_text(source, encoding='utf-8')
        print('PASS 正常绿、3项反例红；测试库事务回滚')
    return 0
if __name__ == '__main__':
    sys.exit(main())
