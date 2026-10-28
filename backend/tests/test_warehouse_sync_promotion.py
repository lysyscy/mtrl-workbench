"""Warehouse sync promotes existing placeholders without replacing their identity."""
import pytest
from sqlalchemy import select

from app.core import db
from app.mod01_projects import repository as projects
from app.mod01_projects.models import Project
from app.mod02_i8 import router
from app.mod02_i8.models import RunRecord
from app.mod03_notice.models import PaymentNotice


def seed(s, name, warehouse, disp=''):
    return projects.create_project(s, project_type='normal', name_full=name,
                                   warehouse_name=warehouse, disp=disp, phid='isolated-' + name)


@pytest.mark.parametrize('custom_display', [False, True])
def test_sync_promotes_same_id_preserves_notices_and_is_idempotent(rollback_db, custom_display):
    with db.session_scope() as s:
        p = seed(s, '__同步扶正__', '未建仓-同步', '自定义展示' if custom_display else '')
        pid, phid = p.id, p.phid
        notice = PaymentNotice(ph_id='__同步关联__', doc_date='2026-10-28',
                               ownership_id=pid, project_name=p.name_full, fields={})
        s.add(notice); s.flush(); nid = notice.id
    rows = [{'warehouse_name': '同步真实仓', 'owner_full_name': '__同步扶正__(TBLX2026100007)'}]
    seen = []
    def load(allow):
        seen.append(allow)
        return rows
    first = router.sync_warehouses(allow_kick=True, rows_loader=load, expected_account=None)
    assert first.counts['promote'] == 1
    assert '未建仓-同步' in first.message and '同步真实仓' in first.message
    with db.session_scope() as s:
        p = s.get(Project, pid)
        assert (p.warehouse_name, p.phid) == ('同步真实仓', phid)
        assert p.disp == ('自定义展示' if custom_display else '同步真实仓')
        assert s.get(PaymentNotice, nid).ownership_id == pid
        rec = s.scalar(select(RunRecord).where(RunRecord.target == '仓库列表').order_by(RunRecord.id.desc()))
        assert rec.detail['warehouse_promotion']['promoted'][0]['project_id'] == pid
    second = router.sync_warehouses(allow_kick=True, rows_loader=load, expected_account=None)
    assert second.counts['promote'] == 0 and seen == [True, True]


def test_ambiguous_or_unowned_warehouses_are_reported_without_writes(rollback_db):
    with db.session_scope() as s:
        p = seed(s, '__多仓__', '未建仓-多仓'); pid = p.id
        seed(s, '__已有真实__', '原真实仓')
        seed(s, '__归属冲突甲__', '未建仓-甲')
        seed(s, '__归属冲突乙__', '未建仓-乙')
        seed(s, '__含已占用多仓__', '未建仓-含已占用')
        seed(s, '__别的项目__', '已占用仓')
        before = len(projects.all_projects(s))
    rows = [dict(warehouse_name=w, owner_full_name=n) for w, n in [
        ('候选甲', '__多仓__'), ('候选乙', '__多仓__'), ('陌生仓', '__未建档__'),
        ('另一个真实仓', '__已有真实__'), ('冲突仓', '__归属冲突甲__'), ('冲突仓', '__归属冲突乙__'),
        ('已占用仓', '__含已占用多仓__'), ('新候选仓', '__含已占用多仓__')]]
    result = router.sync_warehouses(allow_kick=False, rows_loader=lambda allow: rows, expected_account=None)
    assert result.counts['promote'] == 0 and result.counts['unresolved'] >= 4
    assert result.sample and all(r.get('reason') for r in result.sample)
    with db.session_scope() as s:
        assert s.get(Project, pid).warehouse_name == '未建仓-多仓'
        assert len(projects.all_projects(s)) == before


def test_write_failure_rolls_back_all_promotions_and_records_failure(rollback_db, monkeypatch):
    with db.session_scope() as s:
        ids = [seed(s, '__事务' + str(i), '未建仓-事务' + str(i)).id for i in range(2)]
    original = projects.promote_placeholder
    def fail_second(s, p, warehouse):
        original(s, p, warehouse)
        if p.id == ids[1]:
            raise RuntimeError('isolated promotion failure')
    monkeypatch.setattr(projects, 'promote_placeholder', fail_second)
    rows = [dict(warehouse_name='事务仓' + str(i), owner_full_name='__事务' + str(i)) for i in range(2)]
    result = router.sync_warehouses(allow_kick=False, rows_loader=lambda allow: rows, expected_account=None)
    assert result.degraded
    with db.session_scope() as s:
        assert [s.get(Project, pid).warehouse_name for pid in ids] == ['未建仓-事务0', '未建仓-事务1']
        rec = s.scalar(select(RunRecord).where(RunRecord.target == '仓库列表').order_by(RunRecord.id.desc()))
        assert rec.status == 'failed' and 'isolated promotion failure' in rec.error_message
