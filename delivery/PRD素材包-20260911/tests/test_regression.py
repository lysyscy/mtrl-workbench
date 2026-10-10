# -*- coding: utf-8 -*-
"""一键回归入口（S7-3）：子进程跑 verify_sfjc / verify_kcdj，以验收标准为唯一基准。

缺成品/验收基准时自动 skip（避免无数据环境误报）；有数据时则必须全绿。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _has_artifacts(table, y, m):
    month = '%04d-%02d' % (y, m)
    std = os.path.join(ROOT, '验收标准', table, month + '.json')
    if table == '收发结存':
        out = os.path.join(ROOT, 'output', '收发结存', '%d年%d月' % (y, m))
    else:
        out = os.path.join(ROOT, 'output', '库存单据明细表', '%d年%d月' % (y, m))
    return os.path.exists(std) and os.path.isdir(out)


def test_sfjc_regression_2026_08():
    if not _has_artifacts('收发结存', 2026, 8):
        import pytest
        pytest.skip('缺少 8月 收发结存成品/验收基准，跳过回归')
    p = subprocess.run([sys.executable,
                        os.path.join(ROOT, 'scripts', 'regression', 'verify_sfjc.py'),
                        'check', '2026', '8'],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_kcdj_regression_2026_08():
    if not _has_artifacts('库存单据', 2026, 8):
        import pytest
        pytest.skip('缺少 8月 库存单据成品/验收基准，跳过回归')
    p = subprocess.run([sys.executable,
                        os.path.join(ROOT, 'scripts', 'regression', 'verify_kcdj.py'),
                        'check', '2026', '8'],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
