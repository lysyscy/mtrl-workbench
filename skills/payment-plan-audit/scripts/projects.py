"""Give the Agent current project evidence; validate its recorded decisions."""
from collections import Counter
from hashlib import sha256
import json


def catalog_sha(projects):
    return sha256(json.dumps(sorted(projects, key=lambda p: p['id']), ensure_ascii=False,
                            sort_keys=True).encode('utf-8')).hexdigest()


def context(plan, snapshot):
    by_doc = {}
    for n in snapshot['notices']:
        by_doc.setdefault(n['bill_no'], []).append(n)
    groups = []
    for label in dict.fromkeys(r['project'] for r in plan['rows']):
        rows = [r for r in plan['rows'] if r['project'] == label]
        owners = Counter(n['ownership_id'] for r in rows for n in by_doc.get(r['doc_no'], [])
                         if len(by_doc.get(r['doc_no'], [])) == 1)
        groups.append({'source_project': label, 'title_cell': rows[0]['project_title_cell'],
                       'notice_owners': dict(owners)})
    return {'schema': 1, 'project_catalog_sha256': catalog_sha(snapshot['projects']),
            'projects': snapshot['projects'], 'plan_projects': groups,
            'instruction': '结合全名、仓库、展示名和单据归属判断；单据归属只作旁证，不能因为该单归到某项目就倒推该单归属正确。无法确定则project_id填null并说明。'}


def decisions(data, snapshot, plan):
    if data is None:
        return {}
    if data.get('schema') != 1 or data.get('project_catalog_sha256') != catalog_sha(snapshot['projects']):
        raise ValueError('当前项目清单已变化，请AI重新匹配，未标注原表')
    projects = {p['id']: p for p in snapshot['projects']}
    required = {r['project'] for r in plan['rows']}
    mapping = {}
    for d in data['decisions']:
        name, target = d['source_project'], d['project_id']
        if name not in required or name in mapping or not str(d.get('reason', '')).strip():
            raise ValueError('AI项目决策缺少依据、重复或不属于原表')
        if target is not None:
            if type(target) is not int:
                raise ValueError('AI项目ID必须是当前清单中的整数')
            p = projects.get(target)
            if not p or not p.get('warehouse_name') or p.get('project_type') == 'shell':
                raise ValueError('AI项目决策指向已不存在、壳或未确定的项目')
        mapping[name] = d
    if set(mapping) != required:
        raise ValueError('AI项目决策未覆盖原表各项目，请先补齐匹配')
    return mapping
