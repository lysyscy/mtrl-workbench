"""检查工具承认已退役规格和样例配置，仍拒绝正常规格缺失。"""
import importlib.util
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]


@acc()
def test_retired_spec_and_missing_active_capability(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('face_probe_test', ROOT/'tools/probe/_audit_face.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    moddir = tmp_path/'PRD/02-功能规格'
    moddir.mkdir(parents=True)
    active = moddir/'MOD-01.md'
    active.write_text('## 二、能力清单\n| 1 | 档案 |\n', encoding='utf-8')
    (moddir/'MOD-04.md').write_text('原系统计划已退出。', encoding='utf-8')
    baseline = tmp_path/'baseline.json'
    baseline.write_text('{"cases":{}}', encoding='utf-8')
    empty = tmp_path/'empty.md'
    empty.write_text('', encoding='utf-8')
    for key, value in [('FACE', tmp_path), ('MOD_DIR', moddir), ('BASELINE', baseline),
                       ('INDEX', empty), ('DECOMP', empty)]:
        monkeypatch.setattr(module, key, value)
    assert module.main() == 0
    active.write_text('能力清单意外丢失', encoding='utf-8')
    assert module.main() == 1
    active.write_text('## 二、能力清单\n| 1 | `ACC-GHOST-001` |\n', encoding='utf-8')
    assert module.main() == 1


@acc()
def test_example_config_selects_settings_consumers():
    import sys
    sys.path.insert(0, str(ROOT/'tools/oneoff'))
    import _impactscope as impact
    import _run_rulers as rulers

    checks, tests, pending = impact.selection({'.env.example': (b'OLD=1', b'NEW=2')}, rulers.CMDS)
    assert not pending
    assert tests.run and 'test_config_env_example.py' in tests.files
    assert 'tools/audit/bytes_guard.py' in checks
