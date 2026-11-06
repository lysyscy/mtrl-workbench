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
ENGINE = ROOT / 'tools/_vendor/setup_solo_workflow/artifact_lifecycle.py'


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
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code], cwd=ROOT,
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
                      "engine=Path('tools/_vendor/setup_solo_workflow/artifact_lifecycle.py'); "
                      "p=subprocess.run([sys.executable,str(engine),'sweep','--root',os.environ['MTRL_LIFECYCLE_ROOT']],capture_output=True); "
                      "assert p.returncode != 0; close_runs()")


class ProjectProducerTests(unittest.TestCase):
    run_code = ProducerTests.run_code

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project-runs'
        spec = importlib.util.spec_from_file_location('project_producer_engine', ENGINE)
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        self.engine.enroll(self.root, project=ROOT)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('MTRL_')}
        self.env.update(MTRL_LIFECYCLE_ROOT=str(self.root), PYTHONPATH=str(ROOT))

    def records(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in self.root.glob('*/run.json')]

    def test_success_releases_work_and_preserves_evidence(self):
        self.run_code("from tools.audit.workspace_paths import development_run,output,finish_run; "
                      "development_run(); output('temporary.txt',kind='work').write_text('temporary'); "
                      "output('result.json').write_text('{}'); assert finish_run(0)==0")
        record = self.records()[0]
        self.assertEqual((record['state'], record['operation_result']), ('closed', 'success'))
        self.assertEqual(record['inventory'], {'reports/result.json': __import__('hashlib').sha256(b'{}').hexdigest()})
        self.assertFalse((self.root / record['id'] / 'work').exists())

    def test_declared_development_failure_has_finite_retention(self):
        self.run_code("from tools.audit.workspace_paths import development_run,output,finish_run; "
                      "development_run(); output('failure.txt',kind='work').write_text('failure'); "
                      "assert finish_run(7)==7")
        record = self.records()[0]
        self.assertEqual((record['state'], record['operation_result'], record['days']), ('closed', 'failure', 30))
        self.assertIsNone(record['hold'])
        self.assertTrue((self.root / record['id'] / 'work/failure.txt').exists())

    def test_undeclared_failure_and_explicit_recovery_protection_remain_held(self):
        for declaration in ('', "development_run(); protect_run('schema outcome unknown','verify schema exit'); "):
            self.run_code("from tools.audit.workspace_paths import development_run,protect_run,output,finish_run; "
                          + declaration + "output('recovery.txt',kind='work').write_text('recovery'); finish_run(1)")
        for record in self.records():
            self.assertEqual(record['state'], 'active')
            self.assertIsNotNone(record['hold'])
            self.assertTrue((self.root / record['id'] / 'work/recovery.txt').exists())

    def test_abrupt_exit_is_reconciled_after_process_really_exits(self):
        code = ("import os; from tools.audit.workspace_paths import development_run,output; "
                "development_run(abandonment_safe=True); output('failure.json').write_text('{}'); os._exit(7)")
        child = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, env=self.env,
                               capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(child.returncode, 7, child.stderr)
        record = self.records()[0]
        self.assertEqual(record['state'], 'active')
        self.assertEqual(self.engine.sweep(self.root, apply=True)[0]['status'], 'abandoned-closed')
        self.assertEqual(self.records()[0]['operation_result'], 'abandoned')

    def test_unverified_external_consumers_are_not_assumed_finished_at_exit(self):
        self.run_code("from tools.audit.workspace_paths import development_run,output; "
                      "development_run(); output('possible-child-output.json').write_text('{}')")
        record = self.records()[0]
        self.assertEqual(record['state'], 'active')
        self.assertIsNotNone(record['hold'])

    def test_real_child_joins_parent_run_and_does_not_own_closure(self):
        self.run_code("import subprocess,sys; from tools.audit.workspace_paths import development_run,output,finish_run; "
                      "development_run(); output('parent.txt').write_text('parent'); "
                      "subprocess.run([sys.executable,'-B','-c',\"from tools.audit.workspace_paths import output; output('child.txt').write_text('child')\"],check=True); "
                      "finish_run(0)")
        record = self.records()[0]
        self.assertEqual(record['state'], 'closed')
        self.assertEqual(record['consumers'], [])
        self.assertEqual(set(record['inventory']), {'reports/parent.txt', 'reports/child.txt'})

    def test_cleanup_error_does_not_replace_success_exit(self):
        output = self.run_code("from unittest.mock import patch; from tools.audit.workspace_paths import development_run,output,finish_run; "
                               "development_run(); output('occupied.txt',kind='work').write_text('occupied'); "
                               "patcher=patch('tools.audit.workspace_paths.shutil.rmtree',side_effect=PermissionError('occupied')); "
                               "patcher.start(); print(finish_run(0)); patcher.stop()")
        self.assertEqual(output.strip(), '0')
        record = self.records()[0]
        self.assertEqual(record['state'], 'active')
        warning = json.loads((self.root / record['id'] / 'reports/cleanup.json').read_text(encoding='utf-8'))
        self.assertFalse(warning['ok'])
        self.assertEqual(warning['error'], 'PermissionError')
        self.assertTrue((self.root / record['id'] / 'work/occupied.txt').exists())

    def test_different_workspace_cannot_allocate_into_this_project(self):
        other = Path(self.temp.name) / 'other-project'
        other.mkdir()
        code = ("from pathlib import Path; from tools.audit import workspace_paths as w; "
                f"w.ROOT=Path({str(other)!r}); "
                "w.output('must-not-exist.json',root=w.ROOT)")
        child = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, env=self.env,
                               capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(self.records(), [])


if __name__ == '__main__':
    unittest.main()
