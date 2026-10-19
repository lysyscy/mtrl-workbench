"""Validate real history against private SQLite memory tables; never acquire a live engine."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord, MechanicalWorkbenchPreview
from app.mod06_proc import workbench as W
from app.mod06_proc.workbench_history import load_history_payload, verify_source_hashes


def keep_existing(preview):
    resolutions = {}
    for project in preview['projects']:
        if project['before_history']:
            resolutions[project['warehouse'] + '|history'] = 'current'
        for monthly in project['months']:
            resolutions.update({conflict['id']: 'current' for conflict in monthly['conflicts']})
    return resolutions


def effective_values(s):
    return {(row.warehouse_name, row.ym): {f'mech_{i}': getattr(row, f'mech_{i}') for i in range(6)}
            for row in s.scalars(select(ProcMechManual))}


def validate():
    artifact_root = ROOT / '.artifacts/machinery-fee-workflow'
    initial = load_history_payload(artifact_root)
    source_count = verify_source_hashes(initial['source_hashes'])
    mappings = {item['report_project']: f'__history_validation_{item["source_index"]}__'
                for item in initial['unmapped']}
    payload = load_history_payload(artifact_root, mappings=mappings)
    assert not payload['unmapped']
    assert sum(len(batch['rows']) for batch in payload['detail_import']['batches']) == 1966
    snapshot = json.loads((artifact_root / 'technical-feasibility-20261017/history/system.json').read_text(encoding='utf-8'))
    engine = create_engine('sqlite:///:memory:')
    assert engine.url.get_backend_name() == 'sqlite' and engine.url.database == ':memory:'
    metadata = MetaData()
    for model in (Project, ProcMechManual, MechanicalWorkbenchRecord, MechanicalWorkbenchPreview):
        table = model.__table__.to_metadata(metadata)
        if model is ProcMechManual:
            table.c.source_batches.server_default = None
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        s.add_all(Project(id=p['id'], warehouse_name=p['warehouse_name'], disp=p['disp'],
                          status=p['status'], project_type=p['project_type']) for p in snapshot['projects'])
        s.flush()
        s.add_all(Project(warehouse_name=wh, disp=name, status='archived') for name, wh in mappings.items())
        for row in snapshot['effective']:
            s.add(ProcMechManual(id=row['id'], ym=row['ym'], project_id=row['project_id'],
                                warehouse_name=row['warehouse_name'], source_batches=row['source_batches'],
                                **{f'mech_{i}': Decimal(row[f'mech_{i}']) for i in range(6)}))
        s.commit()
        before = effective_values(s)
        history_preview = W.history_preview(s, payload['history_import'])
        conflict_count = sum(len(m['conflicts']) for p in history_preview['projects'] for m in p['months'])
        confirmed = W.history_confirm(s, {'preview_id': history_preview['preview_id'],
                                         'resolutions': keep_existing(history_preview)})
        assert W.history_confirm(s, {'preview_id': history_preview['preview_id']}) == confirmed
        for key, values in before.items():
            assert effective_values(s)[key] == values
        imported = W.import_preview(s, payload['detail_import'])
        assert not any(batch['conflicts'] for batch in imported['batches'])
        result = W.import_confirm(s, {'preview_id': imported['preview_id'], 'confirm_amounts': False})
        assert W.import_confirm(s, {'preview_id': imported['preview_id'], 'confirm_amounts': False}) == result
        s.commit()
        current = W.state(s)
        assert sum(len(detail['rows']) for detail in current['details']) == 1966
        assert len(current['histories']) == len(payload['history_import']['projects'])
        assert any('8月核实4,500' in matter['text'] and not matter['completed'] for matter in current['matters'])
        source_history = next(p['history'] for p in payload['history_import']['projects']
                              if p['history']['report_project'] == '晋江污泥项目')
        assert Decimal(source_history['original_months']['2026-02']['mech_2']) == 0
        assert Decimal(source_history['reference_months']['2026-02']['mech_2']) == 4850
        jinjiang = '晋江污泥处理项目'
        annual_base = Decimal(source_history['report_total']).quantize(Decimal('0.01'))
        assert Decimal(W.report_total(s, jinjiang)) == annual_base
        detail = current['details'][0]
        edits = deepcopy(detail['rows'])
        edits[0]['memo'] = '隔离人工修订，应由重导保护'
        W.save_details(s, {**detail, 'rows': edits})
        protected = '太康龙源热电联产升级改造项目仓库'
        W.repo.save_mech(s, ym='2026-09', warehouse=protected, values={'mech_1': Decimal('14001')})
        W.repo.save_mech(s, ym='2026-02', warehouse=jinjiang, values={'mech_2': Decimal('5000')})
        assert Decimal(W.report_total(s, jinjiang)) == annual_base + Decimal('150')
        retry_detail = deepcopy(payload['detail_import'])
        retry_detail['request_id'] += '-reimport'
        retried = W.import_preview(s, retry_detail)
        assert not any(batch['conflicts'] for batch in retried['batches'])
        W.import_confirm(s, {'preview_id': retried['preview_id'], 'confirm_amounts': False})
        retry_history = deepcopy(payload['history_import'])
        retry_history['request_id'] += '-reimport'
        retried_history = W.history_preview(s, retry_history)
        assert any(c['column'] == 'mech_1' and c['current'] == '14001.00'
                   for p in retried_history['projects'] if p['warehouse'] == protected
                   for m in p['months'] if m['ym'] == '2026-09' for c in m['conflicts'])
        W.history_confirm(s, {'preview_id': retried_history['preview_id'],
                              'resolutions': keep_existing(retried_history)})
        s.commit()
        final = W.state(s)
        assert sum(len(item['rows']) for item in final['details']) == 1966
        assert any(row.get('memo') == '隔离人工修订，应由重导保护'
                   for item in final['details'] for row in item['rows'])
        assert W.effective(s, protected, '2026-09')['values']['mech_1'] == '14001.00'
        for key, values in before.items():
            if key == (protected, '2026-09'):
                values = {**values, 'mech_1': Decimal('14001')}
            if key == (jinjiang, '2026-02'):
                values = {**values, 'mech_2': Decimal('5000')}
            assert effective_values(s)[key] == values
        summary = {'database': 'sqlite:///:memory:', 'business_connections': False,
                   'details': 1966, 'initial_effective_rows': len(before),
                   'history_projects': len(final['histories']), 'initial_conflicts_kept': conflict_count,
                   'unmapped_separate_validation_archives': len(mappings),
                   'unmapped_names': list(mappings), 'source_hashes_verified': source_count,
                   'source_hashes_reverified': verify_source_hashes(payload['source_hashes']),
                   'idempotent_confirmation': True, 'reimport_preserved_manual_details': True,
                   'reimport_preserved_effective_values': True,
                   'latest_annual_included_month_replaced_once': True,
                   'annual_rows': sum(len(h.get('annual_rows', [])) for h in final['histories']),
                   'matters': len(final['matters'])}
    engine.dispose()
    output = artifact_root / 'history-isolation-20261019.json'
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    validate()
