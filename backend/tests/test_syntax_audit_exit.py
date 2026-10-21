"""语法检查缺Node不冒充通过；实际源码错误优先返回失败。"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'audit'))
import syntax_audit as audit


@pytest.mark.parametrize('broken', [False, True])
def test_missing_node_keeps_other_checks_and_has_distinct_exit(tmp_path, monkeypatch, capsys, broken):
    source = tmp_path / 'sample.py'
    source.write_text('value = (' if broken else 'value = 1', encoding='utf-8')
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.setattr(audit, 'PY_ROOTS', [tmp_path])
    assert audit.main([]) == (1 if broken else 2)
    output = capsys.readouterr().out
    assert '跳过 Q2' in output and 'Q3' in output


def test_real_node_accepts_valid_and_rejects_invalid_script(tmp_path):
    source = tmp_path / 'sample.js'
    source.write_text('const value = 1;', encoding='utf-8')
    bad, note = audit.rule_q2(source)
    assert not note, 'Node未找到，无法验证JS解析'
    assert not bad
    source.write_text('const value = ;', encoding='utf-8')
    bad, note = audit.rule_q2(source)
    assert bad and not note
