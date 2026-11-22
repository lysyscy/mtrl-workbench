"""请求内复用读取及抓取异常关闭的隔离回归。"""

from decimal import Decimal
from contextlib import nullcontext
from types import SimpleNamespace

from app.mod05_flow import service as M5
from app.mod05_flow.domain import OpeningView
from app.mod05_flow.models import CATEGORY_MATERIAL
from app.mod11_jc import fetch_service as M11


def test_m05_reuses_openings_and_keeps_ids_and_amounts(monkeypatch):
    openings = [OpeningView(CATEGORY_MATERIAL, 7, "2026-01", Decimal("9"), Decimal("4"), 31)]
    calls = []
    monkeypatch.setattr(M5, "notice_debt_views", lambda _s: [])
    monkeypatch.setattr(M5, "opening_views", lambda _s, project_id=None: calls.append(project_id) or openings)
    monkeypatch.setattr(M5, "project_index", lambda _s: {})

    debt = M5.build_debt(None)

    assert calls == [None]
    assert debt["openings"] == [{
        "id": 31, "category": CATEGORY_MATERIAL, "category_label": "辅材",
        "project_id": 7, "project_key": "", "project_label": "", "cutoff": "2026-01",
        "settle": "9.00", "paid": "4.00",
    }]


def test_m05_reads_ledger_openings_once_and_keeps_missing_side_none(monkeypatch):
    openings = [SimpleNamespace(category=CATEGORY_MATERIAL, project_id=7, cutoff_ym='2026-01', settle_amount=Decimal('9'), paid_amount=Decimal('4'), id=31, entry_kind='manual', remark='')]
    calls = []
    monkeypatch.setattr(M5, "notice_debt_views", lambda _s, *, project_id: [])
    monkeypatch.setattr(M5.repo, 'list_openings', lambda _s, project_id=None: calls.append(project_id) or openings)
    monkeypatch.setattr(M5, "project_index", lambda _s: {})
    monkeypatch.setattr(M5.repo, "remarks_map", lambda *args, **kwargs: {})

    ledger = M5.build_ledger(None, project_id=7, end_ym="2026-02")

    assert calls == [7]
    material, mechanical = ledger["sides"]
    assert material['opening_id'] is None
    assert material['rows'][0]['record_id'] == 31
    assert material['rows'][0]['row_kind'] == 'manual'
    assert material["rows"][0]["other_expense"] == "9.00"
    assert material["rows"][0]["payment"] == "4.00"
    assert mechanical["opening_id"] is None


def test_m11_fetch_closes_client_when_fetch_fails(monkeypatch):
    closed = []
    client = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(M11, 'session_scope', lambda: nullcontext(None))
    monkeypatch.setattr(M11, "ContractFetcher", lambda _client: SimpleNamespace())
    monkeypatch.setattr(M11.fetch_task, "degrade_to_excel", lambda _exc: {"message": "降级"})
    monkeypatch.setattr(M11.fetch_task, "fetch_record_payload", lambda **kwargs: kwargs)
    monkeypatch.setattr(M11, "record_detail", lambda: {})
    monkeypatch.setattr(M11.R, "fetch_detail", lambda **kwargs: {})
    monkeypatch.setattr(M11, "save_run_record", lambda *args, **kwargs: SimpleNamespace(id=8))

    def fail(_client):
        raise RuntimeError("boom")

    result = M11.run_fetch(confirmed=True, operator="test",
                           client_factory=lambda: client, fetch=fail)

    assert result["ok"] is False
    assert closed == [True]


def test_ledger_scopes_notice_ownership_and_mechanical_warehouse_independently(rollback_db):
    from app.core.db import session_scope
    from app.mod01_projects.models import Project
    from app.mod03_notice.models import PaymentNotice
    from app.mod06_proc.models import ProcMechManual
    from sqlalchemy import event

    with session_scope() as session:
        left = Project(warehouse_name="月账甲仓", name_full="甲")
        right = Project(warehouse_name="月账乙仓", name_full="乙")
        session.add_all([left, right])
        session.flush()
        session.add_all([
            PaymentNotice(ph_id="月账甲单", ownership_id=left.id, category="", doc_date="2025-03-11",
                          stat_settle=Decimal("23.51"), stat_paid=Decimal("1.34")),
            PaymentNotice(ph_id="月账乙单", ownership_id=right.id, category="material", doc_date="2025-03-12",
                          stat_settle=Decimal("72.80"), stat_paid=Decimal("6.75")),
            # Historical mechanical rows can have no project ID or an ID unrelated to their warehouse.
            ProcMechManual(warehouse_name=left.warehouse_name, project_id=right.id, ym="2025-03",
                           mech_0=Decimal("99"), mech_2=Decimal("13.27"), mech_3=Decimal("1.81")),
            ProcMechManual(warehouse_name=right.warehouse_name, ym="2025-03", mech_2=Decimal("5.00")),
        ])
        session.flush()
        for project, settle, paid, mechanical in [(left, "23.51", "1.34", "15.08"), (right, "72.80", "6.75", "5.00")]:
            statements = []
            def record(_conn, _cursor, sql, params, _context, _many):
                statements.append((" ".join(sql.lower().split()), params))

            conn = session.connection()
            event.listen(conn, "before_cursor_execute", record)
            try:
                ledger = M5.build_ledger(session, project_id=project.id, end_ym="2025-03")
            finally:
                event.remove(conn, "before_cursor_execute", record)
            for model, key, expected in [(PaymentNotice, "ownership_id", project.id),
                                         (ProcMechManual, "warehouse_name", project.warehouse_name)]:
                reads = [(sql, params) for sql, params in statements if f" from {model.__tablename__} " in sql]
                assert len(reads) == 1
                sql, params = reads[0]
                assert f"where {model.__tablename__}.{key} =" in sql and expected in params.values()
            material, machine = ledger["sides"]
            march = next(row for row in material["rows"] if row["month"] == "2025-03")
            assert (march["other_expense"], march["payment"]) == (settle, paid)
            assert next(row for row in machine["rows"] if row["month"] == "2025-03")["other_expense"] == mechanical
            assert {left.id, right.id} <= {option["id"] for option in ledger["project_options"]}


def test_debt_projection_keeps_all_facts_and_reads_fresh_values():
    from sqlalchemy import event, update
    from app.core.db import session_scope
    from app.mod03_notice.models import PaymentNotice
    from app.mod05_flow.domain import NoticeDebtView
    from app.core.money import to_money

    with session_scope() as session:
        notices = [PaymentNotice(ph_id=f"__440_{i}__", doc_date="2026-10-25",
                                 category=category, stat_settle=Decimal("12.34"),
                                 stat_paid=Decimal("0.00"), excluded=excluded,
                                 fields={"large": ["原始单据"] * 100})
                   for i, (category, excluded) in enumerate([("", False), ("材料", True)])]
        session.add_all(notices)
        session.flush()
        original = [NoticeDebtView(notice_id=int(n.id), doc_date=str(n.doc_date or ""),
                    category=str(n.category or "").strip() or CATEGORY_MATERIAL,
                    settle_stat=to_money(n.stat_settle), pay_stat=to_money(n.stat_paid),
                    excluded=bool(n.excluded), ownership_id=n.ownership_id)
                    for n in M5.repo.notice_rows(session)]
        statements = []
        conn = session.connection()
        def record(_conn, _cursor, stmt, _params, _context, _many):
            statements.append(stmt)
        event.listen(conn, "before_cursor_execute", record)
        try:
            assert M5.notice_debt_views(session) == original
        finally:
            event.remove(conn, "before_cursor_execute", record)
        assert len(statements) == 1 and "payment_notice.fields" not in statements[0]
        session.execute(update(PaymentNotice).where(PaymentNotice.id == notices[0].id)
                        .values(stat_paid=Decimal("3.21")),
                        execution_options={"synchronize_session": False})
        fresh = {n.notice_id: n for n in M5.notice_debt_views(session)}
        assert fresh[notices[0].id].pay_stat == Decimal("3.21")
        assert fresh[notices[1].id].excluded and fresh[notices[1].id].ownership_id is None
        session.rollback()
