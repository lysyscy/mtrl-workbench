"""Read the three observed mechanical lists through the existing i8 identity boundary."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.core.errors import MustReportError
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


def preview_payload(lists, projects):
    candidates = {}
    for project in projects:
        if project.get('phid') and project.get('warehouse'):
            candidates.setdefault(str(project['phid']), set()).add(project['warehouse'])
    mapping = {project_id: next(iter(warehouses)) for project_id, warehouses in candidates.items()
               if len(warehouses) == 1}
    groups = {}
    for kind, source in lists.items():
        for row in source['rows']:
            item = groups.setdefault(row['projectId'], {'projectId': row['projectId'],
                                     'projectName': row['projectName'], 'sources': {k: [] for k in SOURCES}})
            item['sources'][kind].append(row)
    # Complete permission-scoped lists can propose a missing old project as a
    # reduction; confirmation still requires explicit evidence before zeroing.
    if all(kind in lists and lists[kind]['total'] == len(lists[kind]['rows']) for kind in SOURCES):
        for project in projects:
            if project.get('has_i8_snapshot') and project.get('phid'):
                groups.setdefault(str(project['phid']), {'projectId': str(project['phid']),
                    'projectName': project.get('name', project['warehouse']), 'sources': {k: [] for k in SOURCES}})
    now = datetime.now(timezone.utc).isoformat()
    known, unmapped = [], []
    for project_id, item in groups.items():
        item.update(complete={k: True for k in SOURCES}, fetched_at=now,
                    scope='第四工程公司权限内全部项目；不按报表显示名单或月份筛选')
        if project_id in mapping:
            known.append({**item, 'warehouse': mapping[project_id]})
        else:
            item['candidate_warehouses'] = sorted(candidates.get(project_id, set()))
            unmapped.append(item)
    return {'projects': known, 'unmapped_projects': unmapped, 'full_scope': True,
            'scope': '第四工程公司权限内全部项目', 'counts': {k: v['total'] for k, v in lists.items()}}


def read_preview(projects):
    client = I8Client(allow_kick=False)
    try:
        return preview_payload(fetch_lists(client), projects)
    finally:
        client.close()
