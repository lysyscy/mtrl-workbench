"""Protect complete i8 reads, unique project ownership and explicit reductions."""

from tests.acc_plugin import acc
import pytest
import httpx

from app.core.errors import MustReportError
from app.mod02_i8.client import I8Client
from app.mod06_proc.workbench_i8 import fetch_lists, preview_payload


@acc("ACC-RPT-MECH-001", "001-07")
def test_custom_form_expired_session_is_recognized():
    response = httpx.Response(200, json={'status': 'error', 'msg': 'No SessionInfo found', 'data': None})
    assert I8Client._is_session_invalid(response)


def raw(document_id, project_id='p1', **extra):
    return {'phid': document_id, 'phid_pc': project_id, 'phid_pc_EXName': '项目',
            'u_fyze': '12.34', 'u_bqjse': '20.00', 'u_bqspe': '22.00', **extra}


class Client:
    def __init__(self, broken=False):
        self.calls = []
        self.broken = broken

    def post_json(self, path, *, data):
        self.calls.append((path, data))
        start = data['start']
        return {'total': '3', 'data': [raw(str(i)) for i in (range(2) if self.broken else range(start, min(start + 2, 3)))]}


@acc("ACC-RPT-MECH-001", "001-07")
@acc("ACC-RPT-MECH-001", "001-09")
def test_full_pagination_and_original_approval_amounts():
    client = Client()
    lists = fetch_lists(client, page_size=2)
    assert [lists[k]['total'] for k in ('usage', 'project', 'team')] == [3, 3, 3]
    assert len(client.calls) == 6
    assert lists['team']['rows'][0]['amount'] == '20.00'
    assert lists['team']['rows'][0]['approval'] == '22.00'
    assert lists['usage']['rows'][0]['periodKey'] == ''
    payload = preview_payload(lists, [{'phid': 'p1', 'warehouse': '已配项目'}])
    assert payload['projects'][0]['warehouse'] == '已配项目'
    assert payload['full_scope'] is True
    assert payload['unmapped_projects'] == []
    unmatched = preview_payload(lists, [])
    assert len(unmatched['unmapped_projects']) == 1
    assert unmatched['projects'] == []


@acc("ACC-RPT-MECH-001", "001-07")
def test_repeated_page_is_rejected():
    with pytest.raises(MustReportError, match='重复'):
        fetch_lists(Client(broken=True), page_size=2)


@acc("ACC-RPT-MECH-001", "001-07")
def test_shared_project_key_never_chooses_one_small_warehouse():
    lists = fetch_lists(Client(), page_size=2)
    projects = [{'phid': 'p1', 'warehouse': '甲'}, {'phid': 'p1', 'warehouse': '乙'}]
    first = preview_payload(lists, projects)
    second = preview_payload(lists, list(reversed(projects)))
    assert first['projects'] == second['projects'] == []
    assert len(first['unmapped_projects']) == len(second['unmapped_projects']) == 1
    assert first['unmapped_projects'][0]['candidate_warehouses'] == ['乙', '甲']


@acc("ACC-RPT-MECH-001", "001-08")
def test_complete_empty_lists_keep_old_project_in_reduction_preview():
    empty = {kind: {'total': 0, 'rows': []} for kind in ('usage', 'project', 'team')}
    result = preview_payload(empty, [{'phid': 'old-id', 'warehouse': '甲', 'has_i8_snapshot': True},
                                     {'phid': 'new-id', 'warehouse': '乙'}])
    assert len(result['projects']) == 1
    project = result['projects'][0]
    assert project['warehouse'] == '甲'
    assert project['sources'] == {'usage': [], 'project': [], 'team': []}
    assert all(project['complete'].values())
