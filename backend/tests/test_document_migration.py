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


@acc()
def test_closed_ticket_history_leaves_default_scan_but_active_unknown_stays(tmp_path, monkeypatch):
    tickets = tmp_path / '.codebuddy/work/50-tickets'
    tickets.mkdir(parents=True)
    for name, state in [('closed', 'done'), ('withdrawn', 'wontfix'),
                        ('active', 'ready-for-agent'), ('unknown', 'new-state')]:
        (tickets / f'{name}.md').write_text(f'**Status:** {state}\n`docs/missing.md`', encoding='utf-8')
    (tickets / 'missing-state.md').write_text('`docs/missing.md`', encoding='utf-8')
    monkeypatch.setattr(audit_common, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(audit_common, 'SCAN_GLOBS', ('.codebuddy/work/50-tickets/*.md',))
    monkeypatch.setattr(audit_common, 'delivery_root', lambda: None)
    scanned = {p.stem for _, _, p, *_ in audit_common.iter_docs()}
    assert scanned == {'active', 'unknown', 'missing-state'}


@acc()
def test_current_owners_and_history_have_distinct_reading_paths():
    assert audit_common.LEDGER_REL == 'docs/status.md'
    assert audit_common.CLOSED_INDEX_REL == 'docs/archive/tickets/index.md'
    assert audit_common.delivery_root() == ROOT / 'docs/requirements'
    scanned = {p.relative_to(ROOT).as_posix() for _, _, p, *_ in audit_common.iter_docs()}
    assert {'docs/status.md', 'docs/requirements.md',
            'docs/requirements/材料科业务全流程说明书.md'} <= scanned
    assert not any(p.startswith('docs/archive/') for p in scanned)


@acc()
def test_close_ticket_archives_schedule_and_rolls_back_on_history_failure(tmp_path, monkeypatch):
    import _tail_close
    import pytest

    plan = tmp_path / 'status.md'
    closed = tmp_path / 'closed.md'
    tickets = tmp_path / 'tickets'
    tickets.mkdir()
    plan.write_bytes((ROOT / 'docs/status.md').read_bytes())
    closed_rows = (ROOT / 'docs/archive/tickets/index.md').read_bytes().splitlines(keepends=True)
    anchor = max(i for i, row in enumerate(closed_rows) if row.startswith(b'|'))
    closed_rows.insert(anchor + 1, '| `TAIL-284` | fixture | fixture evidence | 2099-01-01 |\r\n'.encode())
    closed.write_bytes(b''.join(closed_rows))
    original_ticket = next((ROOT / '.codebuddy/work/50-tickets').glob('TAIL-284-*.md'))
    ticket = tickets / original_ticket.name
    ticket.write_bytes(original_ticket.read_bytes())
    paths = (plan, closed, ticket)
    before = {p: p.read_bytes() for p in paths}
    original_schedule = next(row for row in before[plan].splitlines(keepends=True)
                             if row.startswith('| `TAIL-284` 项目'.encode()))
    args = ['--id', '284', '--plan', str(plan), '--closed-index', str(closed), '--tickets', str(tickets)]
    assert _tail_close.main(args) == 0
    assert all(p.read_bytes() == before[p] for p in paths)
    original_replace = Path.replace

    def reject_history(source, target):
        if Path(target) == closed:
            raise OSError('fixture history replacement rejected')
        return original_replace(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', reject_history)
        with pytest.raises(OSError, match='history replacement rejected'):
            _tail_close.main(args + ['--apply'])
    assert all(p.read_bytes() == before[p] for p in paths)
    assert not list(tmp_path.glob('~tailhistory-*'))
    assert _tail_close.main(args + ['--apply']) == 0
    assert original_schedule not in plan.read_bytes()
    assert b'> ' + original_schedule.rstrip(b'\r\n') in closed.read_bytes()
    assert '**Status:** done' in ticket.read_text(encoding='utf-8')
