"""探针只清理自己的记录：隔离测试库验证锁行保护，内存故障验证 finally。"""
from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.db import session_scope
from app.mod01_projects.models import Project, TYPE_NORMAL
from app.mod07_setl.models import WeldGasBalance
from app.mod08_inv.models import InvDetail, InvAdjustment
from app.mod09_fee.models import FeeManualItem

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M07 = _load("probe_m07_cleanup", "tools/probe/_e2e_m07bal.py")
M08 = _load("probe_m08_cleanup", "tools/probe/_e2e_m08_wired.py")
M09 = _load("probe_m09_cleanup", "tools/probe/_e2e_m09_wired.py")
OWN = _load("probe_own_cleanup", "tools/probe/_e2e_own_assign.py")


@pytest.fixture(autouse=True)
def reset_probe_results(monkeypatch):
    for module in (M08, M09, OWN):
        monkeypatch.setattr(module, "fails", [])
    monkeypatch.setattr(M07, "_ok", 0)
    monkeypatch.setattr(M07, "_bad", 0)


@pytest.fixture
def owned_rows(rollback_db):
    wh = "__自检仓_probe_" + uuid.uuid4().hex
    with session_scope() as s:
        project = Project(project_type=TYPE_NORMAL, name_full=wh, warehouse_name=wh)
        detail = InvDetail(ym="2026-08", warehouse_name=wh)
        balance = WeldGasBalance(kind="焊材", warehouse_name=wh, amount=Decimal("1234.56"))
        s.add_all([project, detail, balance])
        s.flush()
        adjustment = InvAdjustment(row_id=detail.id, before_amount=100, amount=Decimal("101.23"), remark=M08.REMARK)
        manual = FeeManualItem(ym="2026-08", project_id=project.id, item_name="油卡使用", amount=Decimal("-88.50"))
        s.add_all([adjustment, manual])
        s.flush()
        return wh, balance.id, detail.id, adjustment.id, manual.id


@pytest.mark.parametrize("conflict", [False, True])
def test_m07_atomic_owned_cleanup(owned_rows, conflict):
    wh, bid, _, _, _ = owned_rows
    if conflict:
        with session_scope() as s:
            s.get(WeldGasBalance, bid).amount = Decimal("9.99")
        with pytest.raises(RuntimeError, match="其他值"):
            M07.restore_balance_if_owned(kind="焊材", warehouse=wh, expected=Decimal("1234.56"))
        assert M07.balance_value("焊材", wh) == Decimal("9.99")
    else:
        assert M07.restore_balance_if_owned(kind="焊材", warehouse=wh, expected=Decimal("1234.56"))
        assert M07.balance_value("焊材", wh) is M07._MISSING
        assert not M07.restore_balance_if_owned(kind="焊材", warehouse=wh, expected=Decimal("1234.56"))


@pytest.mark.parametrize("conflict", [False, True])
def test_m08_atomic_owned_cleanup(owned_rows, conflict):
    _, _, rid, aid, _ = owned_rows
    if conflict:
        with session_scope() as s:
            s.get(InvAdjustment, aid).remark = "并发修改"
        with pytest.raises(RuntimeError, match="其他值"):
            M08.cleanup_adjustment(row_id=rid, before_amount=100, expected_amount=101.23)
        with session_scope() as s:
            assert s.get(InvAdjustment, aid).remark == "并发修改"
    else:
        assert M08.cleanup_adjustment(row_id=rid, before_amount=100, expected_amount=101.23)
        with session_scope() as s:
            assert s.get(InvAdjustment, aid) is None


@pytest.mark.parametrize("conflict", [False, True])
def test_m09_cleans_by_id_and_preserves_others(owned_rows, conflict):
    wh, _, _, _, mid = owned_rows
    with session_scope() as s:
        row = s.get(FeeManualItem, mid)
        other = FeeManualItem(ym=row.ym, project_id=row.project_id, item_name="其他记录", amount=0)
        s.add(other)
        s.flush()
        other_id = other.id
        if conflict:
            row.item_name = "并发修改"
    args = dict(ym="2026-08", project=wh, baseline={}, owned_id=mid,
                expected={"item": "油卡使用", "amount": "-88.50"})
    if conflict:
        with pytest.raises(RuntimeError, match="其他值"):
            M09.cleanup_manual(**args)
    else:
        assert M09.cleanup_manual(**args)
    with session_scope() as s:
        assert (s.get(FeeManualItem, mid) is not None) == conflict
        assert s.get(FeeManualItem, other_id).item_name == "其他记录"
    with pytest.raises(RuntimeError, match="稳定记录 id"):
        M09.cleanup_manual(**{**args, "owned_id": None})
    with pytest.raises(RuntimeError, match="基线"):
        M09.cleanup_manual(**{**args, "baseline": {mid: args["expected"]}})


def test_m09_real_api_zero_baseline_and_db_failure(owned_rows, monkeypatch):
    from fastapi import Request
    from urllib.parse import urlencode
    from app.mod09_fee import api

    wh, _, _, _, mid = owned_rows
    with session_scope() as s:
        s.get(FeeManualItem, mid).amount = Decimal("0.00")
    request = Request({"type": "http", "query_string": urlencode({"ym": "2026-08", "pj": wh}).encode()})
    baseline = M09.manual_snapshot(api.api_fee(request)["manuals"])
    assert M09.verify_db_baseline("2026-08", wh, baseline)[0]
    def fail(*args):
        raise RuntimeError("offline db")
    monkeypatch.setattr(M09, "db_manual_snapshot", fail)
    assert M09.verify_db_baseline("2026-08", wh, baseline)[0] is False


class _Response:
    status_code = 200
    text = "fake"

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def test_own_keywords_success_and_conflict(owned_rows):
    from sqlalchemy import select

    wh = owned_rows[0]
    with session_scope() as s:
        row = s.execute(select(Project).where(Project.warehouse_name == wh)).scalars().one()
        pid = row.id
        row.match_keywords = ["旧词", "新词"]
    assert OWN.restore_keywords_if_owned(pid, baseline=["旧词"], expected=["旧词", "新词"])
    assert OWN.keywords_of(pid) == ["旧词"]
    with session_scope() as s:
        s.get(Project, pid).match_keywords = ["并发词"]
    with pytest.raises(RuntimeError, match="其他值"):
        OWN.restore_keywords_if_owned(pid, baseline=["旧词"], expected=["旧词", "新词"])
    assert OWN.keywords_of(pid) == ["并发词"]


@pytest.mark.parametrize("existing", [Decimal("0"), Decimal("1234.56")])
def test_m07_main_refuses_existing_balance_before_any_write(monkeypatch, existing):
    monkeypatch.setattr(M07, "pick_sample", lambda: ("2026-08", "甲仓"))
    monkeypatch.setattr(M07, "balance_value", lambda *_: existing)
    monkeypatch.setattr(M07, "post_json", lambda *args: pytest.fail("已有结余不得写入"))
    monkeypatch.setattr(M07, "restore_balance_if_owned", lambda **kwargs: pytest.fail("已有结余不得清理"))
    assert M07.main() == 1


def test_m07_main_finally_cleans_after_write_then_read_failure(monkeypatch):
    state = {"value": M07._MISSING}
    monkeypatch.setattr(M07, "pick_sample", lambda: ("2026-08", "甲仓"))
    monkeypatch.setattr(M07, "balance_value", lambda kind, warehouse: state["value"])

    def post(_path, body):
        state["value"] = Decimal("1234.56")
        return {"ok": True, "value": "1234.56"}

    monkeypatch.setattr(M07, "post_json", post)
    monkeypatch.setattr(M07, "get_json", lambda _path: (_ for _ in ()).throw(RuntimeError("after write")))
    def restore(**kwargs):
        state["value"] = M07._MISSING
        return True
    monkeypatch.setattr(M07, "restore_balance_if_owned", restore)
    with pytest.raises(RuntimeError, match="after write"):
        M07.main()
    assert state["value"] is M07._MISSING


class _MainM08Client:
    def __init__(self):
        self.reads = 0
        self.adjustment = None

    def get(self, _path):
        self.reads += 1
        if self.reads == 3:
            raise RuntimeError("after create read")
        return _Response({
            "count": 1,
            "rows": [{"id": 7, "doc_no": "D1", "seq": "1", "direction": "入库",
                       "material": "焊条", "spec": "J422", "unit": "kg", "qty": "1",
                       "price_excl": "1", "price_incl": "1", "amount": "100.00",
                       "tax_total": "1", "biz_type": "采购", "vendor": "甲",
                       "doc_date": "2026-08-01", "audit_date": "2026-08-02",
                       "warehouse": "甲仓", "wbs_name": "W", "cbs_name": "C",
                       "c5": "主材", "adjusted": self.adjustment is not None,
                       "adj_amount": self.adjustment["amount"] if self.adjustment else None}],
            "adjustments": [self.adjustment] if self.adjustment else [],
        })

    def post(self, path, json):
        assert path == "/api/m08/adjust"
        self.adjustment = {"row_id": 7, "before_amount": 100.0,
                           "amount": 101.23, "remark": M08.REMARK,
                           "operator": "fake", "changed_at": "now"}
        return _Response({"ok": True, "before_amount": 100.0,
                          "amount": 101.23, "operator": "fake"})


@pytest.mark.parametrize("already_present, duplicate_failure, dirty", [
    (False, False, False), (True, False, False), (True, True, False), (True, False, True),
    (False, "first", False),
])
def test_own_main_restores_or_keeps_existing_word(monkeypatch, already_present, duplicate_failure, dirty):
    state = {"value": ["旧词", "甲单"] if already_present else ["旧词"]}
    if dirty:
        state["value"] += ["", "甲单"]
    before = list(state["value"])

    class Client:
        writes = 0

        def get(self, _path):
            return _Response({"items": [{"doc_name": "甲单据", "candidates": [{"id": 3, "disp": "甲仓"}]}]})

        def post(self, _path, json):
            if json["keyword"].startswith("__"):
                return _Response({"ok": False, "message": "拒绝"})
            self.writes += 1
            if duplicate_failure is True and self.writes == 2:
                return _Response({"ok": False, "message": "拒绝"})
            state["value"] = ["旧词", json["keyword"]]
            if duplicate_failure == "first" and self.writes == 1:
                return _Response({"ok": False, "message": "提交后回执失败"})
            return _Response({"ok": True, "message": "成功"})

    class Session:
        def get(self, model, project_id):
            return SimpleNamespace(match_keywords=list(state["value"]))

    @contextmanager
    def session_scope():
        yield Session()

    monkeypatch.setattr(OWN.httpx, "Client", lambda **kwargs: Client())
    monkeypatch.setattr(OWN, "session_scope", session_scope)
    def restore(project_id, *, baseline, expected):
        assert project_id == 3
        assert state["value"] == expected
        state["value"] = list(baseline)
        return expected != baseline

    monkeypatch.setattr(OWN, "restore_keywords_if_owned", restore)
    monkeypatch.setattr(OWN, "keywords_of", lambda project_id: list(state["value"]))
    original = OWN.keywords_of
    calls = {"n": 0}

    def fail_after_write(project_id):
        calls["n"] += 1
        if calls["n"] == 2 and not already_present:
            raise RuntimeError("after keyword write read")
        return original(project_id)

    monkeypatch.setattr(OWN, "keywords_of", fail_after_write)
    if dirty:
        assert OWN.main() == 1
        assert state["value"] == before
    elif already_present:
        assert OWN.main() == int(duplicate_failure)
        assert state["value"] == before
    else:
        with pytest.raises(RuntimeError, match="after keyword write read"):
            OWN.main()
        assert state["value"] == ["旧词"]


@pytest.mark.parametrize("lose_response", [False, True, "rejected"])
def test_m09_main_cleanup_needs_known_id(monkeypatch, lose_response):
    class Client:
        def __init__(self):
            self.rows = []
            self.param_reads = 0

        def get(self, _path, params=None):
            if params:
                self.param_reads += 1
            if self.param_reads == 3:
                raise RuntimeError("after fee create read")
            return _Response({
                "ym": "2026-08", "project": "甲仓", "project_display": "甲仓",
                "projects": [{"key": "甲仓"}], "auto": {},
                "manuals": [dict(row, index=i) for i, row in enumerate(self.rows)],
                "total": "0.00", "count": len(self.rows), "can_edit": True,
                "columns": [], "auto_name": "自动",
            })

        def post(self, path, json):
            if path.endswith("/fee/add"):
                self.rows.append({"id": 2, "item": "新项", "amount": "0.00"})
                if lose_response == "rejected":
                    return _Response({"ok": False, "message": "提交后回执失败"})
                if lose_response:
                    raise RuntimeError("after fee create response lost")
                return _Response({"ok": True})
            if path.endswith("/fee/name"):
                self.rows[0]["item"] = "油卡使用"
                return _Response({"ok": True})
            return _Response({"ok": True})

    client = Client()
    monkeypatch.setattr(M09.httpx, "Client", lambda **kwargs: client)
    def cleanup(**kwargs):
        if lose_response:
            assert kwargs["owned_id"] is None
            raise RuntimeError("未取得稳定记录 id，可能有残留")
        assert kwargs["owned_id"] == 2
        client.rows.clear()
        return True
    monkeypatch.setattr(M09, "cleanup_manual", cleanup)
    if lose_response == "rejected":
        assert M09.main() == 1
    else:
        with pytest.raises(RuntimeError, match="after fee create"):
            M09.main()
    assert bool(client.rows) == bool(lose_response)
    if lose_response:
        assert M09.fails  # 不能把无法认领的残留报告成通过。


@pytest.mark.parametrize("failure", ["read", "response_lost", "rejected"])
def test_m08_main_cleans_after_committed_write(monkeypatch, failure):
    client = _MainM08Client()
    original = client.post

    def post(path, json):
        response = original(path, json)
        if failure == "rejected":
            return _Response({"ok": False})
        if failure == "response_lost":
            raise RuntimeError("response lost")
        return response

    def cleanup(**kwargs):
        assert kwargs == {"row_id": 7, "before_amount": 100.0, "expected_amount": 101.23}
        assert client.adjustment is not None
        client.adjustment = None
        return True

    monkeypatch.setattr(client, "post", post)
    monkeypatch.setattr(M08.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(M08, "cleanup_adjustment", cleanup)
    with pytest.raises(RuntimeError, match="response lost|after create read"):
        M08.main()
    assert client.adjustment is None
