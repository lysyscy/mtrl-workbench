"""Real producer API against disposable, enrolled output roots; no database."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path.home() / '.skills-manager/skills/setup-solo-workflow/scripts/artifact_lifecycle.py'


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'managed'
        spec = importlib.util.spec_from_file_location('producer_test_engine', ENGINE)
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        self.engine.enroll(self.root)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('MTRL_')}
        self.env['MTRL_LIFECYCLE_ROOT'] = str(self.root)
        self.env['PYTHONPATH'] = str(ROOT)

    def run_code(self, code):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=ROOT,
                                env=self.env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def records(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in (self.root / 'groups').glob('*/record.json')]

    def test_explicit_completion_keeps_report_and_releases_work(self):
        self.run_code("from tools.audit.workspace_paths import output, close_runs; "
                      "output('test.txt',kind='work').write_text('temporary'); "
                      "output('result.json').write_text('{}'); close_runs()")
        record = self.records()[0]
        files = self.root / 'groups' / record['id'] / 'files'
        self.assertEqual(record['state'], 'closed')
        self.assertEqual(record['days'], 30)
        self.assertFalse((files / 'work').exists())
        self.assertTrue((files / 'reports/result.json').exists())

    def test_exit_without_completion_preserves_and_holds(self):
        self.run_code("from tools.audit.workspace_paths import output; output('result.json').write_text('{}')")
        record = self.records()[0]
        self.assertEqual(record['state'], 'active')
        self.assertIsNotNone(record['hold'])

    def test_failed_completion_preserves_work(self):
        self.run_code("from tools.audit.workspace_paths import output, close_runs; "
                      "output('test.txt',kind='work').write_text('failure'); close_runs(success=False)")
        record = self.records()[0]
        self.assertTrue((self.root / 'groups' / record['id'] / 'files/work/test.txt').exists())
        self.assertIsNotNone(record['hold'])

    def test_child_shares_run_without_owning_closure(self):
        self.run_code("import subprocess,sys; from tools.audit.workspace_paths import output, close_runs; "
                      "output('parent.txt').write_text('parent'); "
                      "subprocess.run([sys.executable,'-c',\"from tools.audit.workspace_paths import output; output('child.txt').write_text('child')\"],check=True); "
                      "close_runs()")
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['state'], 'closed')
        self.assertEqual(set(records[0]['inventory']), {'reports/parent.txt', 'reports/child.txt'})

    def test_second_run_after_close_gets_new_identity(self):
        self.run_code("from tools.audit.workspace_paths import output, close_runs; "
                      "output('one.txt').write_text('one'); close_runs(); "
                      "output('two.txt').write_text('two'); close_runs()")
        self.assertEqual(len(self.records()), 2)

    def test_cli_finish_preserves_exit_code_and_failure_evidence(self):
        self.run_code("from tools.audit.workspace_paths import output, finish_run; "
                      "output('failure.json').write_text('{}'); assert finish_run(2) == 2")
        self.assertIsNotNone(self.records()[0]['hold'])

    def test_active_producer_holds_the_cleanup_lease(self):
        self.run_code("import subprocess,sys,os; from pathlib import Path; "
                      "from tools.audit.workspace_paths import output,close_runs; "
                      "output('active.txt').write_text('active'); "
                      "engine=Path.home()/'.skills-manager/skills/setup-solo-workflow/scripts/artifact_lifecycle.py'; "
                      "p=subprocess.run([sys.executable,str(engine),'sweep','--root',os.environ['MTRL_LIFECYCLE_ROOT']],capture_output=True); "
                      "assert p.returncode != 0; close_runs()")


if __name__ == '__main__':
    unittest.main()
