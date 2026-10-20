"""通知书抓取逐行忽略：真实写事务使用内存 SQLite，i8 取数隔离。"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import db
from app.mod01_projects.models import Project
from app.mod02_i8.models import RunRecord
from app.mod03_notice import notice_executors as ex, repository, router
from app.mod03_notice.models import ExcludeRuleRow, NoticeStatLog, PaymentNotice


@pytest.fixture
def case(monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool,
                           connect_args={'check_same_thread': False})
    for model in (Project, PaymentNotice, NoticeStatLog, ExcludeRuleRow, RunRecord):
        model.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, '_session_factory', factory)
    state = SimpleNamespace(rows=[], error=None, client_closed=False)

    class Client:
        def __init__(self, **kwargs): pass
        def close(self): state.client_closed = True

    class Fetcher:
        def __init__(self, client): pass
        def fetch_month(self, month):
            if state.error:
                raise state.error
            return state.rows

    monkeypatch.setattr(ex, 'I8Client', Client)
    monkeypatch.setattr(ex, 'NoticeFetcher', Fetcher)
    with db.session_scope() as s:
        s.add_all([Project(id=1, name_full='正常项目', warehouse_name='正常仓库'),
                   Project(id=2, project_type='shell', name_full='测试小微壳'),
                   Project(id=3, project_type='small', name_full='测试小微壳',
                           warehouse_name='甲仓库', parent_shell_id=2, match_keywords=['甲'])])
    app = FastAPI()
    app.include_router(router.router)
    with TestClient(app) as client:
        state.client = client
        yield state
    engine.dispose()


def row(identity, *, bad=False, **changes):
    return dict(ph_id=identity, bill_no=identity, project_name='测试小微壳' if bad else '正常项目',
                fields={'BillName': '未知项目材料款' if bad else '正常材料款'},
                doc_date='2026-10-01', amount_approved=100, **changes)


def fetch(case):
    response = case.client.post('/api/m03/notices/fetch', json={'year_month': '2026-10'})
    assert response.status_code == 200, response.text
    return response.json()


def test_valid_rows_commit_and_ignored_rows_report_reasons(case):
    case.rows = [row('GOOD'), row('BAD', bad=True), row('EXCLUDED', bad=True, biz_type='付劳务公司款')]
    result = fetch(case)
    assert (result['fetched'], result['upserted']) == (3, 2)
    assert len(result['ignored']) == 1
    item = result['ignored'][0]
    assert (item['bill_no'], item['project_name'], item['doc_name']) == ('BAD', '测试小微壳', '未知项目材料款')
    assert '未命中' in item['reason']
    with db.session_scope() as s:
        notices = list(s.scalars(select(PaymentNotice).order_by(PaymentNotice.id)))
        assert [(n.ph_id, n.excluded) for n in notices] == [('GOOD', False), ('EXCLUDED', True)]
        assert notices[0].ownership_id == 1 and notices[1].ownership_id is None
        run = s.scalar(select(RunRecord))
        assert (run.status, run.success_count, run.fail_count, run.total_count) == ('partial', 2, 1, 3)
        assert run.detail['unresolved'][0]['bill_no'] == 'BAD'
        assert repository.latest_unresolved(s)[0]['bill_no'] == 'BAD'


@pytest.mark.parametrize('kind', ['not_archived', 'needs_choice'])
def test_other_ownership_failures_only_skip_the_affected_row(case, monkeypatch, kind):
    bad = row('BAD', bad=True)
    if kind == 'not_archived':
        from app.mod01_projects import sync_service
        monkeypatch.setattr(sync_service, 'sync_and_archive', lambda *a, **kw: {'degraded': True})
        bad['project_name'] = '填错的未建档项目'
    else:
        with db.session_scope() as s:
            s.add(Project(project_type='small', name_full='测试小微壳', warehouse_name='另一甲仓',
                          parent_shell_id=2, match_keywords=['甲']))
        bad['fields'] = {'BillName': '甲项目材料款'}
    case.rows = [row('GOOD'), bad]
    result = fetch(case)
    assert result['upserted'] == 1
    assert len(result['ignored']) == 1 and result['ignored'][0]['kind'] == kind
    assert result['ignored'][0]['reason']


@pytest.mark.parametrize('replacement', [False, True])
def test_next_fetch_rechecks_corrected_or_replaced_source_without_duplicates(case, replacement):
    case.rows = [row('GOOD'), row('BAD', bad=True)]
    fetch(case)
    assert len(fetch(case)['ignored']) == 1
    corrected = row('NEW' if replacement else 'BAD')
    corrected.update(doc_date='2026-10-15', amount_approved=250,
                     fields={'BillName': '更正后的材料款'}, payee='更正收款单位')
    case.rows = [row('GOOD'), corrected]
    assert fetch(case)['ignored'] == []
    assert fetch(case)['upserted'] == 0
    with db.session_scope() as s:
        notices = list(s.scalars(select(PaymentNotice).order_by(PaymentNotice.id)))
        assert [n.ph_id for n in notices] == ['GOOD', 'NEW' if replacement else 'BAD']
        assert (notices[1].ownership_id, notices[1].amount_approved, notices[1].payee) == (1, 250, '更正收款单位')
        assert repository.latest_unresolved(s) == []


@pytest.mark.parametrize('bad_rows', [True, False])
def test_all_ignored_then_source_deleted_or_empty_month(case, bad_rows):
    case.rows = [row('BAD', bad=True)] if bad_rows else []
    result = fetch(case)
    assert result['upserted'] == 0 and len(result['ignored']) == int(bad_rows)
    case.rows = []
    assert fetch(case)['ignored'] == []
    with db.session_scope() as s:
        assert list(s.scalars(select(PaymentNotice))) == []
        assert repository.latest_unresolved(s) == []


def test_write_error_rolls_back_valid_rows_instead_of_ignoring(case, monkeypatch):
    case.rows = [row('GOOD'), row('BAD', bad=True), row('WRITE-ERROR')]
    apply = ex.apply_fetched_row

    def fail_on_second(session, source, **kwargs):
        if source['ph_id'] == 'WRITE-ERROR':
            raise RuntimeError('isolated write failure')
        return apply(session, source, **kwargs)

    monkeypatch.setattr(ex, 'apply_fetched_row', fail_on_second)
    with pytest.raises(RuntimeError, match='isolated write failure'):
        fetch(case)
    with db.session_scope() as s:
        assert list(s.scalars(select(PaymentNotice))) == []
        assert list(s.scalars(select(RunRecord))) == []


def test_fetch_error_is_not_turned_into_ignored_rows(case):
    case.error = RuntimeError('isolated fetch failure')
    with pytest.raises(RuntimeError, match='isolated fetch failure'):
        fetch(case)
    assert case.client_closed
    with db.session_scope() as s:
        run = s.scalar(select(RunRecord))
        assert run.status == 'failed' and run.detail['notice_fetch'] is True
        assert repository.latest_unresolved(s) == []
