"""集采分笔展示、引用删除保护、撤销人工值回执与含撤销流水入口的隔离反例。"""
from pathlib import Path
import os
import subprocess
import sys
import shutil

from _isolated import isolated_backend


def main():
    with isolated_backend('tmp-tail281-') as (base, env):
        root = Path(__file__).resolve().parents[2]
        shutil.copytree(root / 'tools/audit', base.parent / 'tools/audit',
                        ignore=shutil.ignore_patterns('__pycache__'))
        env['PYTHONPATH'] = os.pathsep.join([str(base), str(base.parent), str(root), str(base.parent / 'tools/audit')])
        cases = [
            ('app/mod11_jc/service.py', 'if live and p["amount"] == sum_money(f.amount for f in live):',
             'if live:', 'test_display_and_revoke_receipt'),
            ('app/mod11_jc/service.py', 'row is not None and row.source == SRC_NOTICE',
             'False', 'test_display_and_revoke_receipt'),
            ('app/mod05_flow/router.py', '"protected": protected',
             '"protected": False', 'test_display_and_revoke_receipt'),
            ('app/mod03_notice/notice_api_router.py', '"has_any_flow": bool(row.flows)',
             '"has_any_flow": False', 'test_notice_only_revoked_flow'),
            ('app/web/shell/actions.js', "sum:(jcSubOn('pay',j.id)?jcSubRow():'')+sumRowOf",
             "sum:sumRowOf", None),
        ]

        def run(args):
            return subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', *args, '-q', '--tb=short'],
                                  cwd=base, env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)

        baseline = run(['tests/test_tail281_jc.py', '-k', 'not browser',
                        'tests/test_acc_jc_shell.py::test_子表草稿行列对齐且钉在合计行之前取消不入库'])
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr
        for name, old, new, test in cases:
            path = base / name
            source = path.read_text(encoding='utf-8')
            assert source.count(old) == 1, name
            try:
                path.write_text(source.replace(old, new), encoding='utf-8')
                target = ('tests/test_tail281_jc.py::' + test) if test else 'tests/test_acc_jc_shell.py::test_子表草稿行列对齐且钉在合计行之前取消不入库'
                red = run([target])
                assert red.returncode != 0 and 'FAILED ' in red.stdout, red.stdout + red.stderr
                print('PASS 隔离反例：', test or '草稿顺序', flush=True)
            finally:
                path.write_text(source, encoding='utf-8')
        print('PASS 正常绿、5项反例红；正式源码未变、测试事务回滚', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
