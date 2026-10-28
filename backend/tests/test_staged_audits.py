"""暂存审计真实Git输入；stdlib unittest独立运行，不装配应用/数据库。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

AUDIT = Path(__file__).resolve().parents[2] / 'tools/audit'
sys.path.insert(0, str(AUDIT))
import syntax_audit as syntax
import bytes_guard as guard


class StagedAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mtrl_staged_audit_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        for p in [patch.object(syntax, 'ROOT', self.root), patch.object(guard, 'ROOT', self.root),
                  patch.object(syntax, 'PY_ROOTS', [self.root/'tools'])]:
            p.start(); self.addCleanup(p.stop)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def put(self, name, data, stage=True):
        path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        if stage:
            self.git('add', '--', name)
        return path

    def commit(self):
        self.git('-c', 'user.name=Audit Test', '-c', 'user.email=audit@example.invalid', 'commit', '-qm', 'fixture')

    def test_python_index_bad_worktree_good_and_reverse(self):
        path = self.put('tools/中文 空格.py', b'"""fixture"""\nvalue = (\n')
        path.write_bytes(b'"""fixture"""\nvalue = 1\n')
        self.assertEqual(syntax.main(['--staged']), 1)
        self.git('add', '--', 'tools/中文 空格.py')
        path.write_bytes(b'value = (\n')
        self.assertEqual(syntax.main(['--staged']), 0)

    def test_docstring_rule_uses_index_in_both_directions(self):
        path = self.put('tools/doc.py', b'value = 1\n')
        path.write_bytes(b'"""fixture"""\nvalue = 1\n')
        self.assertEqual(syntax.main(['--staged']), 1)
        self.git('add', '--', 'tools/doc.py'); path.write_bytes(b'value = 1\n')
        self.assertEqual(syntax.main(['--staged']), 0)

    def test_unmerged_index_cannot_be_reported_as_empty_success(self):
        path = self.put('tools/conflict.py', b'"""fixture"""\nvalue = 1\n')
        blob = self.git('rev-parse', ':tools/conflict.py').stdout.decode().strip()
        entries = f'0 {"0"*40}\ttools/conflict.py\n'
        entries += ''.join(f'100644 {blob} {stage}\ttools/conflict.py\n' for stage in (1, 2, 3))
        subprocess.run(['git', 'update-index', '--index-info'], input=entries.encode(), cwd=self.root, check=True, capture_output=True)
        self.assertEqual(syntax.main(['--staged']), 1)
        self.assertEqual(guard.main(['--staged']), 1)

    def test_text_and_tsx_use_index_bytes_even_when_worktree_missing(self):
        path = self.put('apps/frontend/src/中文 空格.tsx', b'\xff\n')
        path.write_bytes(b'const value = 1;\n')
        self.assertEqual(guard.main(['--staged']), 1)
        self.git('add', '--', 'apps/frontend/src/中文 空格.tsx')
        path.unlink()
        self.assertEqual(guard.main(['--staged']), 0)

    def test_rename_delete_and_exact_whitespace_names(self):
        self.put('old.py', b'"""fixture"""\nvalue = 1\n'); self.commit()
        self.git('mv', 'old.py', ' leading 中文 space .py')
        self.assertEqual(syntax.main(['--staged']), 0)
        self.assertEqual(guard.main(['--staged']), 0)
        renamed = self.put(' leading 中文 space .py', b'"""fixture"""\nvalue = (\n')
        renamed.write_bytes(b'"""fixture"""\nvalue = 1\n')
        self.assertEqual(syntax.main(['--staged']), 1)
        self.git('add', '--', ' leading 中文 space .py')
        self.commit()
        self.git('rm', '--', ' leading 中文 space .py')
        self.assertEqual(syntax.main(['--staged']), 0)
        self.assertEqual(guard.main(['--staged']), 0)

    def test_unrelated_text_does_not_compile_worktree_or_require_node(self):
        self.put('README.md', b'fixture\n')
        self.put('tools/broken.py', b'value = (\n', stage=False)
        with patch.object(syntax, 'iter_py', side_effect=AssertionError('must not full scan')):
            self.assertEqual(syntax.main(['--staged']), 0)
        self.assertEqual(guard.main(['--staged']), 0)

    def test_git_failure_is_nonzero_not_empty_success(self):
        with tempfile.TemporaryDirectory(prefix='mtrl_no_git_') as outside:
            with patch.object(syntax, 'ROOT', Path(outside)), patch.object(guard, 'ROOT', Path(outside)):
                self.assertEqual(syntax.main(['--staged']), 1)
                self.assertEqual(guard.main(['--staged']), 1)


if __name__ == '__main__':
    unittest.main()
