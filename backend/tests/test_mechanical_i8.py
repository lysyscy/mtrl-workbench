"""Protect complete i8 reads, unique project ownership and explicit reductions."""

import pytest
import httpx

from app.core.errors import MustReportError
from app.mod02_i8.client import I8Client
from app.mod01_projects.models import Project
from app.mod06_proc.workbench_i8 import fetch_lists, preview_payload


def test_custom_form_expired_session_is_recognized():
    response = httpx.Response(200, json={'status': 'error', 'msg': 'No SessionInfo found', 'data': None})
    assert I8Client._is_session_invalid(response)


def raw(document_id, project_id='p1', **extra):
    return {'phid': document_id, 'phid_pc': project_id, 'phid_pc_EXName': '项目',
            'u_fyze': '12.34', 'u_bqjse': '20.00', 'u_bqspe': '22.00', **extra}


def project(id, warehouse, project_type='normal', **extra):
    return Project(id=id, warehouse_name=warehouse, project_type=project_type, name_full=warehouse or '小微壳',
                   phid=extra.pop('phid', 'p1'), match_keywords=extra.pop('match_keywords', []), **extra)


class Client:
    def __init__(self, broken=False):
        self.calls = []
        self.broken = broken

    def post_json(self, path, *, data):
        self.calls.append((path, data))
        start = data['start']
        return {'total': '3', 'data': [raw(str(i)) for i in (range(2) if self.broken else range(start, min(start + 2, 3)))]}


def test_full_pagination_and_original_approval_amounts():
    client = Client()
    lists = fetch_lists(client, page_size=2)
    assert [lists[k]['total'] for k in ('usage', 'project', 'team')] == [3, 3, 3]
    assert len(client.calls) == 6
    assert lists['team']['rows'][0]['amount'] == '20.00'
    assert lists['team']['rows'][0]['approval'] == '22.00'
    assert lists['usage']['rows'][0]['periodKey'] == ''
    payload = preview_payload(lists, [project(1, '已配项目')])
    assert payload['projects'][0]['warehouse'] == '已配项目'
    assert payload['full_scope'] is True
    assert payload['unmapped_projects'] == []
    unmatched = preview_payload(lists, [])
    assert len(unmatched['unmapped_projects']) == 1
    assert unmatched['projects'] == []


def test_repeated_page_is_rejected():
    with pytest.raises(MustReportError, match='重复'):
        fetch_lists(Client(broken=True), page_size=2)


def test_shared_project_key_never_chooses_one_small_warehouse():
    lists = fetch_lists(Client(), page_size=2)
    projects = [project(1, '甲'), project(2, '乙')]
    first = preview_payload(lists, projects)
    second = preview_payload(lists, list(reversed(projects)))
    assert first['projects'] == second['projects'] == []
    assert len(first['unmapped_projects']) == len(second['unmapped_projects']) == 1
    assert first['unmapped_projects'][0]['candidate_warehouses'] == ['乙', '甲']


def test_complete_empty_lists_keep_old_project_in_reduction_preview():
    empty = {kind: {'total': 0, 'rows': []} for kind in ('usage', 'project', 'team')}
    result = preview_payload(empty, [project(1, '甲', phid='old-id'), project(2, '乙', phid='new-id')],
                             {'甲': {'old-id'}})
    assert len(result['projects']) == 1
    item = result['projects'][0]
    assert item['warehouse'] == '甲'
    assert item['sources'] == {'usage': [], 'project': [], 'team': []}
    assert all(item['complete'].values())


def small_family():
    return [project(1, None, 'shell'),
            project(2, '大唐', 'small', parent_shell_id=1, match_keywords=['大唐', '大唐雷州']),
            project(3, '佰利', 'small', parent_shell_id=1, match_keywords=['佰利', '百利'], status='archived'),
            project(4, None, 'shell', phid='other-shell'),
            project(5, '其他壳下大唐', 'small', phid='other-shell', parent_shell_id=4, match_keywords=['大唐'])]


def test_shared_shell_splits_each_source_by_existing_small_keywords():
    from app.mod06_proc.workbench_i8 import normalize
    lists = {kind: {'total': 2, 'rows': [normalize(raw('dt-' + kind, bill_name='四分大唐雷州项目'), kind),
                                       normalize(raw('bl-' + kind, bill_name='四分百利项目'), kind)]}
             for kind in ('usage', 'project', 'team')}
    result = preview_payload(lists, small_family())
    assert result['unmapped_projects'] == []
    assert {p['warehouse'] for p in result['projects']} == {'大唐', '佰利'}
    for item in result['projects']:
        assert all(item['complete'].values())
        prefix = 'dt-' if item['warehouse'] == '大唐' else 'bl-'
        assert all(rows[0]['id'] == prefix + kind and len(rows) == 1 for kind, rows in item['sources'].items())
    assert sum(len(rows) for p in result['projects'] for rows in p['sources'].values()) == 6


@pytest.mark.parametrize('title', ['', '未知项目', '大唐百利共同费用'])
def test_unmatched_or_multiple_small_keywords_preserve_facts_and_block_partial_adoption(title):
    from app.mod06_proc.workbench_i8 import normalize
    lists = {kind: {'total': 1, 'rows': [normalize(raw(kind, bill_name='大唐'), kind)]}
             for kind in ('usage', 'project', 'team')}
    lists['usage']['rows'].append(normalize(raw('uncertain', bill_name=title), 'usage'))
    lists['usage']['total'] = 2
    result = preview_payload(lists, small_family(), {'大唐': {'p1'}, '佰利': {'p1'}})
    assert len(result['unmapped_projects']) == 1
    assert result['unmapped_projects'][0]['sources']['usage'][0]['id'] == 'uncertain'
    assert all(not any(p['complete'].values()) for p in result['projects'])
    assert sum(len(rows) for p in result['projects'] + result['unmapped_projects']
               for rows in p['sources'].values()) == 4


def test_only_small_child_still_needs_keyword_and_orphan_child_never_takes_whole_shell():
    lists = fetch_lists(Client(), page_size=2)
    family = small_family()[:2]
    assert preview_payload(lists, family)['projects'] == []
    lists['usage']['rows'][0]['title'] = '大唐'
    assert preview_payload(lists, family[1:])['projects'] == []


def test_empty_complete_shell_sources_offer_separate_old_small_project_reductions():
    lists = {kind: {'total': 0, 'rows': []} for kind in ('usage', 'project', 'team')}
    result = preview_payload(lists, small_family(), {'大唐': {'p1'}, '佰利': {'p1'}})
    assert result['unmapped_projects'] == []
    assert {p['warehouse'] for p in result['projects']} == {'大唐', '佰利'}
    assert all(all(p['complete'].values()) for p in result['projects'])
