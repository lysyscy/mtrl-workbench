"""剔除单导入不阻断，但唯一可判归属仍持久化。"""
from contextlib import contextmanager
from sqlalchemy import select
from app.core.db import session_scope
from app.mod01_projects import repository as projects
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice import notice_executors as ex
from tests.acc_plugin import acc


@acc()
def test_import_excluded_ownership_is_nonblocking_and_preserves_existing(monkeypatch):
    with session_scope() as s:
        p = projects.create_project(s, project_type='normal',
            name_full='__自检_剔除归属__项目(TBLX999)', warehouse_name='__自检_剔除归属__仓')
        s.flush()
        rows = [dict(ph_id=f'__自检_剔除归属__{i}', project_name=name,
                     biz_type='付劳务公司款', fields={'BillName':'劳务款'},
                     doc_date='2026-07-01', bill_no=f'__自检_{i}')
                for i, name in enumerate(['__自检_剔除归属__项目', '__自检_无档案__'])]
        @contextmanager
        def scope():
            yield s
        class Client:
            def __init__(self, **kw): pass
            def close(self): pass
        class Fetcher:
            def __init__(self, client): pass
            def fetch_month(self, ym): return rows
        monkeypatch.setattr(ex, 'session_scope', scope)
        monkeypatch.setattr(ex, 'I8Client', Client)
        monkeypatch.setattr(ex, 'NoticeFetcher', Fetcher)
        assert ex.get_fetch_executor()('2026-07', False)[0] == 2
        got=list(s.scalars(select(PaymentNotice).where(PaymentNotice.ph_id.in_([r['ph_id'] for r in rows])).order_by(PaymentNotice.id)))
        assert got[0].ownership_id == p.id and got[1].ownership_id is None
        assert all(n.excluded and n.exclude_source=='rule' for n in got)
        got[1].ownership_id=p.id
        rows[1]['project_name']='__自检_另一个无档案__'
        ex.get_fetch_executor()('2026-07', False)
        assert got[1].ownership_id == p.id
        s.rollback()
