"""Read the workbench or record reviewed reports directly through its transaction service."""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

FIELDS = {'equipment': 'device', 'specification': 'spec', 'unit': 'unit',
          'quantity': 'qty', 'planned_months': 'plan', 'elapsed_months': 'used',
          'gross_amount': 'amount', 'lessor': 'vendor', 'reviewer': 'reviewer',
          'team': 'team', 'plate': 'plate', 'purpose': 'use', 'remarks': 'memo'}
EDITABLE = set(FIELDS.values()) | {'rate', 'date', 'tax', 'sourceNet', 'oil'}


def build(extraction, review, state):
    period = extraction['period']
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period) or review['period'] != period:
        raise ValueError('申报月份无效或不一致')
    records, sources = extraction['records'], extraction['sources']
    warehouses = {p if isinstance(p, str) else p['warehouse'] for p in state['projects']}
    decisions = review.get('rows', [])
    indices = [d['record'] for d in decisions]
    if any(type(i) is not int for i in indices) or sorted(indices) != list(range(len(records))):
        raise ValueError('每条提取明细必须恰好处置一次，不能静默漏行或重复')
    resolutions = review.get('issue_resolutions', [])
    issue_ids = [r['issue'] for r in resolutions]
    if (any(type(i) is not int for i in issue_ids) or sorted(issue_ids) != list(range(len(extraction['issues'])))
            or any(not str(r.get('reason', '')).strip() for r in resolutions)):
        raise ValueError('每个提取问题必须有明确处置依据')
    manifests = {}
    for source in sources:
        if source['sha256_before'] != source['sha256_after']:
            raise ValueError('来源读取前后发生变化')
        path = Path(source['path']).resolve(strict=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256_after']:
            raise ValueError('原报已更新，请重新提取和核对')
        manifests[(str(path), source['sheet'])] = source
    batches, evidence = defaultdict(list), defaultdict(list)
    for decision in decisions:
        record = records[decision['record']]
        if not str(decision.get('reason', '')).strip():
            raise ValueError('每条明细需要分类、关联或排除的核实依据')
        source = record['source']
        manifest = manifests[(str(Path(source['path']).resolve()), source['sheet'])]
        if record['period'] != period:
            raise ValueError('明细申报月份与批次不一致')
        if decision.get('exclude') is True:
            continue
        warehouse = review['projects'].get(record['project'])
        if warehouse not in warehouses:
            raise ValueError('项目须明确对应当前系统仓库档案')
        category = decision.get('category') or {'零租': 'zero', '包月': 'monthly'}.get(record['kind'])
        if category not in ('zero', 'monthly') or not str(decision.get('id', '')).strip():
            raise ValueError('明细须有明确零租/包月分类及稳定id')
        fields = record['fields']
        values = {target: item['value'] for field, target in FIELDS.items()
                  if (item := fields.get(field)) and item['value'] is not None}
        for field, target in [('original_unit_price' if category == 'zero' else 'monthly_unit_price', 'rate'),
                              ('rental_date' if category == 'zero' else 'entry_date', 'date'),
                              ('reported_net_amount', 'sourceNet')]:
            if fields.get(field, {}).get('value') is not None:
                values[target] = fields[field]['value']
        tax = record.get('tax', {})
        raw_tax = fields.get('tax_description', {}).get('value')
        values['tax'] = ('普票' if tax.get('invoice') == '普票' else
                         format(Decimal(tax['rate']) * 100, 'f') + '%专票'
                         if tax.get('invoice') == '专票' and tax.get('rate') is not None else str(raw_tax or ''))
        original, original_tax = values.get('amount'), values['tax']
        overrides = decision.get('values', {})
        if set(overrides) - EDITABLE:
            raise ValueError('修订包含不支持的明细字段')
        values.update(overrides)
        for name in ('amount', 'rate', 'sourceNet'):
            if values.get(name) is not None:
                number = Decimal(str(values[name]))
                if not number.is_finite() or number < 0:
                    raise ValueError('金额须为非负有限数值')
                values[name] = format(number, 'f')
        row = {'id': str(decision['id']), **values,
               'original': None if original is None else str(original), 'originalTax': original_tax,
               'source': {**deepcopy(source), 'sha256': manifest['sha256_after'],
                          'fields': deepcopy(fields), 'raw_cells': deepcopy(record.get('raw_cells', [])),
                          'review': deepcopy(decision)}}
        key = (warehouse, category)
        if any(r['id'] == row['id'] for r in batches[key]):
            raise ValueError('同批明细id重复')
        batches[key].append(row)
        if manifest not in evidence[key]:
            evidence[key].append(manifest)
    output = []
    for (warehouse, category), rows in batches.items():
        current = next((d for d in state.get('details', []) if d['warehouse'] == warehouse
                        and d['ym'] == period and d['category'] == category), {})
        removed = {r['id'] for r in current.get('baseline_rows', current.get('rows', []))} - {r['id'] for r in rows}
        approved = {r['id'] for r in review.get('removed_rows', [])
                    if r.get('warehouse') == warehouse and r.get('category') == category and r.get('reason')}
        if removed - approved:
            raise ValueError('系统已有行未对应：复用原id，或明确记录删行依据')
        output.append({'warehouse': warehouse, 'ym': period, 'category': category, 'rows': rows,
                       'revision': current.get('revision', 0),
                       'source': {'file': '；'.join(s['path'] for s in evidence[(warehouse, category)]),
                                  'sources': deepcopy(evidence[(warehouse, category)]), 'review': deepcopy(review)}})
    if not output:
        raise ValueError('没有可录入的外租明细')
    payload = {'batches': output}
    identity = {'batches': [{k: v for k, v in batch.items() if k != 'revision'} for batch in output]}
    signature = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {'request_id': 'mechanical-' + signature, **payload,
            'resolutions': deepcopy(review.get('conflict_resolutions', {}))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    read = commands.add_parser('state', help='只读当前项目与明细，供本批关联')
    read.add_argument('--output', type=Path, required=True)
    write = commands.add_parser('write', help='获准后直接录入明细并回读')
    for name in ('extraction', 'review', 'receipt'):
        write.add_argument('--' + name, type=Path, required=True)
    write.add_argument('--operator', required=True)
    args = parser.parse_args()
    target = (args.output if args.command == 'state' else args.receipt).resolve()
    if target.exists():
        raise FileExistsError('请选择新的输出路径：' + str(target))
    root = args.project_root.resolve(strict=True)
    if not (root / 'backend/app/mod06_proc/workbench.py').is_file():
        raise ValueError('请选择材料工作台维护项目根目录')
    sys.path.insert(0, str(root / 'backend'))
    from app.core.db import session_scope
    from app.mod06_proc import workbench
    if args.command == 'state':
        with session_scope() as session:
            result = workbench.state(session)
    else:
        load = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
        extraction = load(args.extraction)
        if any(target.is_relative_to(Path(s['path']).resolve().parent) for s in extraction['sources']):
            raise ValueError('录入回执须保存到原报目录之外')
        # Read current revisions, validate the source and write in one transaction.
        with session_scope() as session:
            payload = build(extraction, load(args.review), workbench.state(session))
            result = workbench.record_details(session, payload, args.operator)
        # A new transaction verifies persisted data, rather than echoing the write payload.
        with session_scope() as session:
            result['readback'] = [workbench.detail_view(session, *workbench.read(session,
                workbench.key('details', batch['warehouse'], batch['ym'], batch['category'])))
                for batch in payload['batches']]
            result['effective'] = [workbench.effective(session, batch['warehouse'], batch['ym'])
                                   for batch in payload['batches']]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'output': str(target), 'command': args.command,
                      'batches': len(result.get('batches', []))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
