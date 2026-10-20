"""Engineering document paths remain real inputs of checks and test selection."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/audit'))
sys.path.insert(0, str(ROOT / 'tools/oneoff'))

import audit_common
import audit_drift

ENGINEERING_DOCS = {
    'docs/architecture.md', 'docs/architecture/modules.md',
    'docs/guides/deployment.md', 'docs/guides/document-governance.md',
    'docs/guides/implementation-constraints.md',
    'docs/guides/development-and-verification.md', 'docs/guides/frontend-design.md',
    'docs/reference/thresholds.md', 'docs/reference/i8-contract.md',
    'docs/reference/sticky-total-row.md', 'docs/reference/template-export.md',
    'docs/reference/legacy-materials.md', 'docs/reference/changelog.md',
}


def test_engineering_authorities_are_in_actual_scan():
    scanned = {rel.replace('\\', '/') for _, rel, *_ in audit_common.iter_docs()}
    assert ENGINEERING_DOCS <= scanned
    assert audit_common.REPO_ROOT / 'docs/reference/thresholds.md' == Path(audit_drift.REPO_ROOT) / audit_drift.THRESHOLD_DOC


def test_missing_new_reference_still_fails():
    def sample(path):
        return [('仓', 'docs/agents/workflow.md', ROOT / 'docs/agents/workflow.md',
                 [f'现行参考：`{path}`'], ['current'])]

    assert not audit_drift.check_paths(sample('docs/reference/thresholds.md'))
    missing = audit_drift.check_paths(sample('docs/reference/does-not-exist.md'))
    assert any(h['code'] == 'T3' and h['level'] == audit_common.RED for h in missing)






def test_closed_ticket_history_leaves_default_scan_but_active_unknown_stays(tmp_path, monkeypatch):
    tickets = tmp_path / '.scratch/tails/issues'
    tickets.mkdir(parents=True)
    for name, state in [('closed', 'done'), ('withdrawn', 'wontfix'),
                        ('active', 'ready-for-agent'), ('unknown', 'new-state')]:
        (tickets / f'{name}.md').write_text(f'**Status:** {state}\n`docs/missing.md`', encoding='utf-8')
    (tickets / 'missing-state.md').write_text('`docs/missing.md`', encoding='utf-8')
    monkeypatch.setattr(audit_common, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(audit_common, 'SCAN_GLOBS', ('.scratch/tails/issues/*.md',))
    monkeypatch.setattr(audit_common, 'delivery_root', lambda: None)
    scanned = {p.stem for _, _, p, *_ in audit_common.iter_docs()}
    assert scanned == {'active', 'unknown', 'missing-state'}


def test_current_owners_and_history_have_distinct_reading_paths():
    assert audit_common.LEDGER_REL == 'docs/status.md'
    assert audit_common.CLOSED_INDEX_REL == 'docs/archive/tickets/index.md'
    assert audit_common.delivery_root() == ROOT / 'docs/requirements'
    scanned = {p.relative_to(ROOT).as_posix() for _, _, p, *_ in audit_common.iter_docs()}
    assert {'docs/status.md', 'docs/requirements.md',
            'docs/requirements/材料科业务全流程说明书.md'} <= scanned
    assert not any(p.startswith('docs/archive/') for p in scanned)


def test_close_ticket_archives_schedule_and_rolls_back_on_history_failure(tmp_path, monkeypatch):
    import _tail_close
    import pytest

    plan = tmp_path / 'status.md'
    closed = tmp_path / 'closed.md'
    tickets = tmp_path / 'tickets'
    tickets.mkdir()
    plan.write_text('''活跃 1 · 已销号 0
## 14. 尾巴排期
### 14.3 逐条排期
| `TAIL-999` fixture | 随时 | fixture | None |
### 14.4 已办排期（历史）
## 15. 尾巴台账
活跃 **1** 条 · 已销号 **0** 条
### 一、A 类
| `TAIL-999` | fixture |
### 二、B 类
### 三、C 类
''', encoding='utf-8')
    closed.write_text('| # | 事项 | 销号依据 | 日期 |\n|---|---|---|---|\n'
                      '| `TAIL-999` | fixture | fixture evidence | 2099-01-01 |\n', encoding='utf-8')
    ticket = tickets / 'TAIL-999-fixture.md'
    ticket.write_text('**Status:** ready-for-agent\n', encoding='utf-8')
    paths = (plan, closed, ticket)
    before = {p: p.read_bytes() for p in paths}
    original_schedule = next(row for row in before[plan].splitlines(keepends=True)
                             if row.startswith(b'| `TAIL-999` fixture'))
    args = ['--id', '999', '--plan', str(plan), '--closed-index', str(closed), '--tickets', str(tickets)]
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


def test_retired_host_inputs_have_real_consumers_and_missing_references_fail():
    import audit_meta
    import audit_work

    assert not (ROOT / '.codebuddy').exists()
    assert audit_meta.TICKET_DIR_REL == '.scratch/tails/issues'
    assert audit_work.HEADER_ZONES == ('.scratch/legacy-active', 'docs/adr')
    assert not audit_common._is_lenient('docs/adr/0033-document-layout.md')
    assert ('AGENTS.md', ('.md',)) in audit_meta.LIVE_MACHINE_REQUIRED
    scanned = {rel.replace('\\', '/') for _, rel, *_ in audit_common.iter_docs()}
    assert 'docs/agents/project-rules.md' in scanned
    for ticket in (ROOT / '.scratch/tails/issues').glob('TAIL-*.md'):
        state = audit_meta.TICKET_STATE_RE.search(ticket.read_text(encoding='utf-8')).group(1)
        rel = ticket.relative_to(ROOT).as_posix()
        assert (rel in scanned) == (state not in ('done', 'wontfix'))
    for path in ('docs/adr/D999-missing.md', '.scratch/tails/issues/TAIL-999-missing.md'):
        doc = [('仓', 'AGENTS.md', ROOT / 'AGENTS.md', [f'现行入口：`{path}`'], ['current'])]
        assert any(h['level'] == audit_common.RED for h in audit_drift.check_paths(doc))


def test_host_lane_missing_or_wrong_suffix_still_fails(monkeypatch):
    import audit_meta

    lanes = audit_meta.LIVE_MACHINE_GLOBS
    assert not audit_meta.check_live_machine()
    for replacement in (None, ('AGENTS.md', '⑤ 宿主入口', ('.mdc',))):
        changed = tuple(lane for lane in lanes if lane[0] != 'AGENTS.md')
        if replacement:
            changed += (replacement,)
        monkeypatch.setattr(audit_meta, 'LIVE_MACHINE_GLOBS', changed)
        assert any(h['level'] == audit_common.RED and 'AGENTS.md' in h['what']
                   for h in audit_meta.check_live_machine())




def test_layout_checks_new_task_paths_and_root_rejects_retired_host(tmp_path, monkeypatch):
    import audit_meta

    monkeypatch.setattr(audit_meta, 'REPO_ROOT', tmp_path)
    for rel in ('.scratch/legacy-active/wrong.md', 'docs/adr/wrong.md'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# fixture', encoding='utf-8')
    assert {h['rel'] for h in audit_meta.check_doc_layout()} == {
        '.scratch/legacy-active/wrong.md', 'docs/adr/wrong.md'}
    (tmp_path / '.codebuddy').mkdir()
    assert any(h['rel'].rstrip('/') == '.codebuddy' and h['level'] == audit_common.RED
               for h in audit_meta.check_drop_zones())




def test_project_constraints_keep_line_budget_without_retired_host_byte_limit(tmp_path, monkeypatch):
    import audit_meta

    budget = next(row for row in audit_meta.DOC_BUDGETS if row[0] == 'docs/agents/project-rules.md')
    assert budget == ('docs/agents/project-rules.md', 200, 'must', None)
    monkeypatch.setattr(audit_meta, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(audit_meta, 'DOC_BUDGETS', (budget,))
    doc = tmp_path / budget[0]
    doc.parent.mkdir(parents=True)
    doc.write_text('line\n' * 201, encoding='utf-8')
    assert any('201 行' in h['what'] for h in audit_meta.check_doc_budgets())
    doc.write_text('测' * 5000, encoding='utf-8')
    assert not audit_meta.check_doc_budgets()


def test_legacy_decision_guard_does_not_apply_old_state_words_to_new_adrs(tmp_path, monkeypatch):
    import audit_work

    monkeypatch.setattr(audit_work, 'REPO_ROOT', tmp_path)
    adrs = tmp_path / 'docs/adr'
    adrs.mkdir(parents=True)
    head = '读者：fixture\n回答：fixture\n何时读：fixture\n状态：已办结\n'
    legacy = adrs / 'D9999-fixture.md'
    legacy.write_text(head, encoding='utf-8')
    (adrs / '0033-fixture.md').write_text(head, encoding='utf-8')
    hits = audit_work.check_artifacts_and_headers()
    assert hits and all(h['rel'] == 'docs/adr/D9999-fixture.md' for h in hits)
    legacy.write_text(head.replace('已办结', '已归档'), encoding='utf-8')
    assert not audit_work.check_artifacts_and_headers()
