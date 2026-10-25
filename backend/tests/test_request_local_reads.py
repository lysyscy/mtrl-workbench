"""请求内复用读取及抓取异常关闭的隔离回归。"""

from decimal import Decimal
from types import SimpleNamespace

from app.mod05_flow import service as M5
from app.mod05_flow.domain import OpeningView
from app.mod05_flow.models import CATEGORY_MATERIAL
from app.mod06_proc import service as M6
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
    monkeypatch.setattr(M5, "notice_debt_views", lambda _s: [])
    monkeypatch.setattr(M5.repo, 'list_openings', lambda _s, project_id=None: calls.append(project_id) or openings)
    monkeypatch.setattr(M5, "project_options", lambda _s: [])
    monkeypatch.setattr(M5.repo, "remarks_map", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.mod01_projects.service.all_projects", lambda _s: [])
    monkeypatch.setattr(M5, "mechanical_settlements", lambda _s: {})

    ledger = M5.build_ledger(None, project_id=7, end_ym="2026-02")

    assert calls == [7]
    material, mechanical = ledger["sides"]
    assert material['opening_id'] is None
    assert material['rows'][0]['record_id'] == 31
    assert material['rows'][0]['row_kind'] == 'manual'
    assert material["rows"][0]["other_expense"] == "9.00"
    assert material["rows"][0]["payment"] == "4.00"
    assert mechanical["opening_id"] is None


def test_m06_derives_both_mechanical_cutoff_keys_from_one_read(monkeypatch):
    calls = []
    monkeypatch.setattr(M6, "load_inv_rows", lambda _s: [{"warehouse": "A"}])
    monkeypatch.setattr(M6, "load_history", lambda _s: [])
    monkeypatch.setattr(M6, "load_mech", lambda _s: [])
    monkeypatch.setattr(M6, "displays_by_key", lambda _s: {})
    monkeypatch.setattr(M6, "load_cutoff", lambda _s, **kwargs: "")
    monkeypatch.setattr(M6, "load_cutoffs", lambda _s: {})
    monkeypatch.setattr(M6, "load_batches", lambda _s: [])
    monkeypatch.setattr(M6, "load_mechanical_cutoffs", lambda _s: calls.append(1) or {"A": "2026-09"})

    data = M6.build_import_data(None, warehouse="A")

    assert calls == [1]
    assert data["mechanical_cutoff_ym"] == "2026-09"
    assert data["mechanical_cutoffs"] == {"A": "2026-09"}


def test_m11_fetch_closes_client_when_fetch_fails(monkeypatch):
    closed = []
    client = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(M11, "ContractFetcher", lambda _client: SimpleNamespace(last_unapproved=0))
    monkeypatch.setattr(M11.fetch_task, "degrade_to_excel", lambda _exc: {"message": "降级"})
    monkeypatch.setattr(M11.fetch_task, "fetch_record_payload", lambda **kwargs: kwargs)
    monkeypatch.setattr(M11, "record_detail", lambda: {})
    monkeypatch.setattr(M11.R, "fetch_detail", lambda **kwargs: {})
    monkeypatch.setattr(M11, "save_run_record", lambda *args, **kwargs: SimpleNamespace(id=8))

    def fail(_client):
        raise RuntimeError("boom")

    result = M11.run_fetch(None, confirmed=True, operator="test",
                           client_factory=lambda: client, fetch=fail)

    assert result["ok"] is False
    assert closed == [True]
