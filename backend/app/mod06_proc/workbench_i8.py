"""Read the three observed mechanical lists through the existing i8 identity boundary."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.core.errors import MustReportError
from app.mod01_projects.domain import resolve_ownership
from app.mod01_projects.models import TYPE_NORMAL, TYPE_SHELL
from app.mod02_i8.client import I8Client, serialize_fetch

# Observed on all three Fourth Engineering Company list pages on 2026-10-19.
# These are query scopes, not credentials; never substitute an empty/all-organizations filter.
CLIENT_FILTER = 'e48f570da0f71818a59e798cfa48fa57bc388a6b8519dc9d0f237f397f1fdf63f4b6f41b8fbed0c7a9520cd37c2e728810b59c1f0f0f253c'
QUERY_FILTER = '5e3410ab22038162'
LIST_PATH = '/sup/customServer/getList'
SOURCES = {'usage': ('sbsy', 'u_fyze', 'u_orkcycle'),
           'project': ('xmxhd', 'u_bqjse', 'u_workcycle'),
           'team': ('jxxhd', 'u_bqjse', 'u_workcycle')}


def number(value):
    if value in (None, ''):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise InvalidOperation
    except (ValueError, InvalidOperation) as exc:
        raise MustReportError('i8返回的金额无法识别，旧值未改动') from exc
    return format(amount, 'f')


def normalize(row, kind):
    bus_code, amount_field, period_field = SOURCES[kind]
    document_id, project_id = str(row.get('phid') or ''), str(row.get('phid_pc') or '')
    if not document_id or not project_id:
        raise MustReportError('i8返回记录缺少单据或项目标识，旧值未改动')
    return {'id': document_id, 'projectId': project_id, 'projectName': row.get('phid_pc_EXName', ''),
            'bill': row.get('bill_no', ''), 'title': row.get('bill_name', ''),
            'periodKey': str(row.get(period_field) or ''), 'periodName': row.get(period_field + '_EXName', ''),
            'amount': number(row.get(amount_field)), 'approval': number(row.get('u_bqspe')) if kind == 'team' else None,
            'status': row.get('app_status'), 'workflow': row.get('wf_flag'),
            'version': row.get('ng_record_ver'), 'updatedAt': row.get('ng_update_dt'),
            'source': bus_code}


def fetch_lists(client, *, page_size=410):
    result = {}
    with serialize_fetch('mechanical-workbench'):
        for kind, (code, _, _) in SOURCES.items():
            rows, ids, expected = [], set(), None
            for page in range(1000):
                body = client.post_json(LIST_PATH, data={
                    'page': page, 'start': page * page_size, 'limit': page_size,
                    'customBusCode': code, 'containerId': f'p_form_{code}_m_list',
                    'clientfilter': CLIENT_FILTER, 'queryfilter': QUERY_FILTER})
                if not isinstance(body, dict) or not isinstance(body.get('data'), list):
                    raise MustReportError('i8列表返回不完整，旧值未改动')
                try:
                    count = int(body['total'])
                except (KeyError, ValueError, TypeError) as exc:
                    raise MustReportError('i8未返回完整条数，旧值未改动') from exc
                if count < 0 or (expected is not None and count != expected):
                    raise MustReportError('i8列表读取期间条数变化，请重新抓取')
                expected = count
                for raw in body['data']:
                    row = normalize(raw, kind)
                    if row['id'] in ids:
                        raise MustReportError('i8分页出现重复单据，请重新抓取')
                    ids.add(row['id'])
                    rows.append(row)
                if len(rows) == expected:
                    break
                if not body['data'] or len(rows) > expected:
                    raise MustReportError('i8分页未完整取得，旧值未改动')
            else:
                raise MustReportError('i8列表超过本次读取上限，旧值未改动')
            result[kind] = {'total': expected, 'rows': rows}
    return result


def preview_payload(lists, projects, previous=None):
    by_id, candidates = {}, {}
    for project in projects:
        if project.phid:
            by_id.setdefault(str(project.phid), []).append(project)
            if project.warehouse_name:
                candidates.setdefault(str(project.phid), set()).add(project.warehouse_name)
    groups, unresolved = {}, {}

    def new_group(project_id, project_name):
        return {'projectId': project_id, 'projectName': project_name, 'sources': {k: [] for k in SOURCES}}

    for kind, source in lists.items():
        for row in source['rows']:
            project_id = row['projectId']
            archives = by_id.get(project_id, [])
            shells = [p for p in archives if p.project_type == TYPE_SHELL]
            owner = None
            if len(shells) == 1:
                shell = shells[0]
                family = [shell, *(p for p in projects if p.parent_shell_id == shell.id)]
                decision = resolve_ownership(name_full=shell.name_full,
                                             doc_name=row.get('title', ''), projects=family)
                if decision.settled:
                    owner = next((p for p in family if p.id == decision.target_id), None)
            elif not shells:
                normals = [p for p in archives if p.project_type == TYPE_NORMAL and p.warehouse_name]
                if len(normals) == 1 and len(archives) == 1:
                    owner = normals[0]
            if owner and owner.warehouse_name:
                item = groups.setdefault((project_id, owner.warehouse_name), new_group(project_id, row['projectName']))
                item['warehouse'] = owner.warehouse_name
            else:
                item = unresolved.setdefault(project_id, new_group(project_id, row['projectName']))
            item['sources'][kind].append(row)
    # Complete permission-scoped lists can propose a missing old project as a
    # reduction; confirmation still requires explicit evidence before zeroing.
    if all(kind in lists and lists[kind]['total'] == len(lists[kind]['rows']) for kind in SOURCES):
        for project in projects:
            project_id = str(project.phid or '')
            if project.warehouse_name and project_id and (previous or {}).get(project.warehouse_name) == {project_id}:
                item = groups.setdefault((project_id, project.warehouse_name), new_group(project_id, project.name_full))
                item['warehouse'] = project.warehouse_name
    now = datetime.now(timezone.utc).isoformat()
    known, unmapped = [], []
    for item in [*groups.values(), *unresolved.values()]:
        project_id = item['projectId']
        item.update(complete={k: k in lists and lists[k]['total'] == len(lists[k]['rows'])
                              and (not item.get('warehouse') or project_id not in unresolved) for k in SOURCES}, fetched_at=now,
                    scope='第四工程公司权限内全部项目；不按报表显示名单或月份筛选')
        if item.get('warehouse'):
            known.append(item)
        else:
            item['candidate_warehouses'] = sorted(candidates.get(project_id, set()))
            unmapped.append(item)
    return {'projects': known, 'unmapped_projects': unmapped, 'full_scope': True,
            'scope': '第四工程公司权限内全部项目', 'counts': {k: v['total'] for k, v in lists.items()}}


def read_preview(projects, previous=None, *, allow_kick=False):
    client = I8Client(allow_kick=allow_kick)
    try:
        return preview_payload(fetch_lists(client), projects, previous)
    finally:
        client.close()
