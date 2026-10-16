"""检查工具承认已退役规格和样例配置，仍拒绝正常规格缺失。"""
import importlib.util
import json
import shutil
import subprocess
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


@acc()
def test_asset_count_ignores_only_printer_runtime_config_and_cache(tmp_path):
    printer = tmp_path/'i8一键打印'
    (printer/'__pycache__').mkdir(parents=True)
    for relative in ('config.ini', 'source.py', '__pycache__/source.pyc'):
        (printer/relative).write_text('fixture', encoding='utf-8')
    (tmp_path/'other').mkdir()
    (tmp_path/'other/config.ini').write_text('source config', encoding='utf-8')
    source = (ROOT/'delivery/demo/_doccheck.js').read_text(encoding='utf-8')
    count = source[source.index('const countFilesOnDisk ='):source.index('/* ══ 事实登记表')]
    script = "const fs=require('fs'),path=require('path');const ROOT=" + json.dumps(str(tmp_path)) + ";const PACK='.';" + count
    result = subprocess.run([shutil.which('node'), '-e', script+'console.log(countFilesOnDisk(PACK));'],
                            encoding='utf-8', capture_output=True, check=True)
    assert result.stdout.strip() == '2'
