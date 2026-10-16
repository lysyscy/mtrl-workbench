"""选集CLI必须拒绝未知参数，避免误报自检已执行。"""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from tests.acc_plugin import acc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/oneoff'))
import _pytestscope as scope


@pytest.mark.parametrize('argv', [
    ['--selftest'], ['--expalin'], ['--cover'],
    ['--explain', '--cover-only'], ['unexpected.py'],
    ['--explain', 'test_pytestscope_cli.py'], ['--cover-only', '--', 'test_pytestscope_cli.py'],
])
@acc()
def test_invalid_arguments_fail_before_discovery(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, 'argv', ['_pytestscope.py', *argv])
    def unexpected(*args):
        pytest.fail('非法参数不应执行选集或覆盖检查')
    monkeypatch.setattr(scope, 'changed_paths', unexpected)
    monkeypatch.setattr(scope, 'report_cover', unexpected)
    with pytest.raises(SystemExit) as exc:
        scope.main()
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert 'error:' in output.err and 'pytest=' not in output.out


@pytest.mark.parametrize('argv,paths', [
    ([], ['discovered.py']), (['--explain'], ['discovered.py']),
    (['--explain', '--', 'a.py', 'b.py'], ['a.py', 'b.py']),
    (['--explain', '--'], []),
])
@acc()
def test_supported_modes_keep_selected_paths(monkeypatch, capsys, argv, paths):
    monkeypatch.setattr(sys, 'argv', ['_pytestscope.py', *argv])
    monkeypatch.setattr(scope, 'changed_paths', lambda: ['discovered.py'])
    seen = []
    def plan(selected):
        seen.append(selected)
        return SimpleNamespace(run=True, reason='case', files={'test_pytestscope_cli.py'},
                               argv=lambda: ['tests/test_pytestscope_cli.py'])
    monkeypatch.setattr(scope, 'plan', plan)
    assert scope.main() == 0 and seen == [paths]
    assert 'test_pytestscope_cli.py' in capsys.readouterr().out


@acc()
def test_cover_mode_preserves_failure_code(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['_pytestscope.py', '--cover-only'])
    monkeypatch.setattr(scope, 'report_cover', lambda: (1, 'gap'))
    assert scope.main() == 1


@acc()
def test_help_is_available_without_discovery(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['_pytestscope.py', '--help'])
    monkeypatch.setattr(scope, 'changed_paths', lambda: pytest.fail('帮助不应计算选集'))
    with pytest.raises(SystemExit) as exc:
        scope.main()
    assert exc.value.code == 0
    assert '--cover-only' in capsys.readouterr().out
