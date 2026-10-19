"""Read reviewed local history into the workbench preview contract; never connect or write."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re


COLUMNS = {'company': 'mech_0', 'internal': 'mech_1', 'zero': 'mech_2',
           'monthly': 'mech_3', 'zeroNet': 'mech_4', 'monthlyNet': 'mech_5'}
ANNUAL_CATEGORIES = {'当月零租费': 'zero', '当月包月费': 'monthly',
                     '当月周材费': 'weekly', '当月内租费': 'internal', '合计': 'total'}
DETAIL_MONEY = ('rate', 'amount', 'original', 'sourceNet')


def yuan(value):
    """Prototype money is cents, including fractional cents in saved Excel caches."""
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            raise InvalidOperation
        number = Decimal(str(value))
        if not number.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('历史金额无效') from exc
    return format(number / 100, 'f')


def exact_projects(system):
    """Only snapshot project names and explicitly maintained aliases establish identity."""
    names = {}
    valid = {p['warehouse_name'] for p in system['projects'] if p.get('warehouse_name')}
    for project in system['projects']:
        warehouse = project.get('warehouse_name')
        if warehouse:
            for name in (warehouse, project.get('disp')):
                if name:
                    names.setdefault(name, set()).add(warehouse)
    for rule in system['rules']:
        warehouse = rule['warehouse_name']
        if warehouse in valid:
            for alias in rule.get('aliases', []):
                names.setdefault(alias, set()).add(warehouse)
    return {name: next(iter(matches)) for name, matches in names.items() if len(matches) == 1}


def annual_rows(workbooks):
    """Retain cached numeric history and original formulas, without executing Excel."""
    result = {}
    for workbook in workbooks:
        sheet = next((s for s in workbook['sheets'] if s['name'] == '年度汇总'), None)
        if not sheet:
            continue
        rows = {}
        for cell in sheet['cells']:
            rows.setdefault(cell['row'], {})[re.sub(r'\d+', '', cell['cell'])] = cell
        for row_no, cells in rows.items():
            project = cells.get('A', {}).get('cache')
            label = cells.get('B', {}).get('cache')
            if not project or label not in ANNUAL_CATEGORIES:
                continue
            preserved = {col: deepcopy(cell) for col, cell in cells.items() if cell['col'] >= 3}
            item = {'category': ANNUAL_CATEGORIES[label], 'label': label,
                    'cells': {col: (str(cell['cache']) if isinstance(cell.get('cache'), (int, float))
                                    else cell.get('cache')) for col, cell in preserved.items()},
                    'source_cells': preserved,
                    'source': {'file': workbook['path'], 'sheet': sheet['name'], 'row': row_no}}
            result.setdefault(project, []).append(item)
    return result


def build_history_payload(seed, verification, system, workbooks, *, mappings=None):
    """Produce preview payloads and unmapped facts; caller must confirm every adoption."""
    data, names = seed['data'], seed['names']
    mapping = exact_projects(system)
    # Explicit mappings are for reviewed caller choices, including isolated validation archives.
    mapping.update(mappings or {})
    sources = {Path(path).name: {'file': path, 'sha256': item['before']}
               for path, item in verification['hashes'].items()}
    annual = annual_rows(workbooks)
    source_digest = hashlib.sha256(json.dumps([verification['hashes'], mapping], sort_keys=True).encode()).hexdigest()
    detail = {'request_id': 'history-details-' + source_digest, 'batches': []}
    history = {'request_id': 'history-months-' + source_digest, 'projects': []}
    unmapped = []
    for index, name in enumerate(names):
        warehouse = mapping.get(name)
        project_batches = []
        baseline_reference = data.get('referenceAt', {}).get(data['baseMonth'][index], data['latestMonthly'])
        original_months, reference_months, monthly = {}, {}, []
        for month in seed['months']:
            record = data['records'][f'{index}|{month}']
            values = {column: format(Decimal(yuan(record[field])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')
                      for field, column in COLUMNS.items()
                      if record.get(field) is not None}
            original_months[month] = {column: yuan(record.get(field)) for field, column in COLUMNS.items()}
            reference_months[month] = {column: yuan(baseline_reference.get(f'{index}|{month}|{field}'))
                                       for field, column in COLUMNS.items()
                                       if field in ('zero', 'monthly', 'internal')}
            reference_months[month]['mech_0'] = yuan(baseline_reference.get(
                f'{index}|{month}|company', record.get('company')))
            if values:
                monthly.append({'ym': month, 'values': values,
                                'source': {'report_project': name, 'reason': record.get('reason'),
                                           'reasons': deepcopy(record.get('reasons', {}))}})
        def facts(key):
            return [deepcopy(item) for item in data.get(key, []) if item['project'] == index]
        project_history = {
            'base_month': data['baseMonth'][index], 'report_total': yuan(data['feeBase'][index]),
            'i6': yuan(data['i8'][index].get('i6')), 'report_project': name,
            'fee_base_source': data['feeBaseSource'][index],
            'meta_at': {month: deepcopy(items[index]) for month, items in data.get('metaAt', {}).items()},
            'source': {'statement': data['feeBaseSource'][index],
                       'files': deepcopy(verification['hashes']), 'kind': 'reviewed-monthly-history'},
            'reference_months': reference_months, 'original_months': original_months,
            'reference_at': {report_month: {month: {
                column: yuan(references.get(f'{index}|{month}|{field}'))
                for field, column in COLUMNS.items() if field in ('zero', 'monthly', 'internal')} | {
                    'mech_0': yuan(references.get(f'{index}|{month}|company',
                                                 data['records'][f'{index}|{month}'].get('company')))}
                for month in seed['months']}
                for report_month, references in data.get('referenceAt', {}).items()},
            'cumulative_at': {month: {field: yuan(value) for field, value in
                                      data['cumulativeAt'][month][index].items()}
                              for month in seed['months']},
            'category_totals': {field: yuan(value) for field, value in data['latestCats'][index].items()},
            'quality': facts('quality'), 'month_conflicts': facts('monthConflicts'),
            'issues': facts('issues'), 'annual_rows': annual.get(name, []),
            'source_index': index, 'prototype_amount_unit': 'cent',
        }
        for key in ('quality', 'month_conflicts'):
            for item in project_history[key]:
                for field in ('detail', 'adopted', 'original_month_report', 'latest_annual_reference'):
                    if field in item:
                        item[field] = yuan(item[field])
        for item in project_history['issues']:
            if 'amount' in item:
                item['amount'] = yuan(item['amount'])
        matters = [{'id': f'history-{source_digest}-{index}-{item.get("id", n)}',
                    'text': item.get('note', ''), 'completed': item.get('status') == '已完成',
                    'metadata': deepcopy(item)} for n, item in enumerate(project_history['issues'])]
        project_payload = {'warehouse': warehouse, 'history': project_history, 'months': monthly,
                           'matters': matters}
        for month in seed['months']:
            for category in ('zero', 'monthly'):
                selected = [row for row in data['saved'] if row['project'] == index
                            and row['month'] == month and row['cat'] == category]
                if not selected:
                    continue
                rows = []
                batch_source = None
                for original in selected:
                    row = deepcopy(original)
                    row['source_project_index'] = row.pop('project')
                    for field in DETAIL_MONEY:
                        row[field] = yuan(row.get(field))
                    source = re.fullmatch(r'(.+) / (.+) / 第(\d+)行', row['source'])
                    if not source or source[1] not in sources:
                        raise ValueError('历史明细缺少可追溯源文件和行坐标')
                    row['source_evidence'] = {**sources[source[1]], 'sheet': source[2], 'row': int(source[3]),
                                              'raw_source': row['source']}
                    batch_source = sources[source[1]]
                    rows.append(row)
                project_batches.append({'warehouse': warehouse, 'ym': month, 'category': category,
                                        'rows': rows, 'source': batch_source})
        if warehouse:
            history['projects'].append(project_payload)
            detail['batches'].extend(project_batches)
        else:
            unmapped.append({'report_project': name, 'source_index': index,
                             'detail_count': sum(len(batch['rows']) for batch in project_batches),
                             'reason': '未取得唯一精确档案或已核别名',
                             'history_project': project_payload, 'detail_batches': project_batches})
    return {'detail_import': detail, 'history_import': history, 'unmapped': unmapped,
            'source_hashes': {path: item['before'] for path, item in verification['hashes'].items()},
            'system_effective': deepcopy(system['effective'])}


def load_history_payload(artifact_root, *, mappings=None):
    """Read local evidence only; hashes are checked separately to avoid hidden heavy I/O."""
    root = Path(artifact_root)
    def load(path):
        return json.loads((root / path).read_text(encoding='utf-8-sig'))
    return build_history_payload(load('prototype-20261017/jan-sep-seed.json'),
                                 load('prototype-20261017/jan-sep-source-verification.json'),
                                 load('technical-feasibility-20261017/history/system.json'),
                                 load('technical-feasibility-20261017/history/workbooks.json'),
                                 mappings=mappings)


def verify_source_hashes(source_hashes):
    for path, expected in source_hashes.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('来源文件已变化：' + path)
    return len(source_hashes)
