"""Engineering document paths remain real inputs of checks and test selection."""
from pathlib import Path
import sys

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/audit'))
sys.path.insert(0, str(ROOT / 'tools/oneoff'))

import audit_common
import audit_drift
import _gatescope
import _pytestscope

ENGINEERING_DOCS = {
    'docs/architecture.md', 'docs/architecture/modules.md',
    'docs/guides/deployment.md', 'docs/guides/document-governance.md',
    'docs/guides/implementation-constraints.md',
    'docs/guides/development-and-verification.md', 'docs/guides/frontend-design.md',
    'docs/reference/thresholds.md', 'docs/reference/i8-contract.md',
    'docs/reference/sticky-total-row.md', 'docs/reference/template-export.md',
    'docs/reference/legacy-materials.md', 'docs/reference/changelog.md',
}


@acc()
def test_engineering_authorities_are_in_actual_scan():
    scanned = {rel.replace('\\', '/') for _, rel, *_ in audit_common.iter_docs()}
    assert ENGINEERING_DOCS <= scanned
    assert audit_common.REPO_ROOT / 'docs/reference/thresholds.md' == Path(audit_drift.REPO_ROOT) / audit_drift.THRESHOLD_DOC


@acc()
def test_missing_new_reference_still_fails():
    def sample(path):
        return [('仓', 'docs/agents/workflow.md', ROOT / 'docs/agents/workflow.md',
                 [f'现行参考：`{path}`'], ['current'])]

    assert not audit_drift.check_paths(sample('docs/reference/thresholds.md'))
    missing = audit_drift.check_paths(sample('docs/reference/does-not-exist.md'))
    assert any(h['code'] == 'T3' and h['level'] == audit_common.RED for h in missing)


@acc()
def test_new_document_changes_invalidate_code_check_receipts():
    before = {'repo/docs/reference/thresholds.md': 'before'}
    after = {'repo/docs/reference/thresholds.md': 'after'}
    for tool in _gatescope.CODE_ONLY:
        assert _gatescope.input_signature(tool, [], before, 'ctx') != _gatescope.input_signature(tool, [], after, 'ctx')


@acc()
def test_selection_finds_actual_new_document_readers():
    assert 'docs/' in {prefix for prefix, _ in _pytestscope.OUTSIDE_PREFIXES}
    readers = _pytestscope.outside_readers()
    expected = {'test_design_rules.py', 'test_ux_colors.py', 'test_shell_part_routes.py'}
    assert expected <= {name for name, prefixes in readers.items() if 'docs/' in prefixes}
    plan = _pytestscope.plan(['docs/guides/frontend-design.md'])
    assert plan.run and (plan.run_all or expected <= set(plan.files))
