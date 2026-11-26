"""批量关联的匹配依据、人工确认和应付完整性。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.db import session_scope
from app.core.errors import ExternalServiceError
from app.mod01_projects.models import Project
from app.mod02_i8.payable_source import fetch_payables
from app.mod03_notice.models import PaymentNotice
from app.mod11_jc import api, domain as D, repository as R, service as S
from app.mod11_jc.models import JcContract
from tests.test_acc_jc_pay_link import _contract, _notice, _project


def source(no="CGHT1", amount="100.01", supplier="甲", project="项目全名", code="CGYF1"):
    return dict(id=code, code=code, contract_no=no, project=project, supplier=supplier, amount=Decimal(amount))


def contract(s, project, no, *, supplier="甲", tag=D.TAG_IN, trade_co=""):
    item = _contract(s, project_id=project.id, supplier=supplier)
    item.contract_no = no
    item.tag = tag
    item.trade_co = trade_co
    return item


def notice(s, project, name, *, supplier="", title="", remark="", **fields):
    item = _notice(s, ph=name, approved="100.01")
    item.bill_no = name
    item.project_name = "项目全名"
    item.ownership_id = project.id
    item.jc_supplier = supplier
    item.approve_status = "已批"
    item.fields = {"BillName": title, "Remark": remark}
    for key, value in fields.items():
        setattr(item, key, value)
    return item


def selection(row, candidate=None):
    choice = candidate or row["target"]
    return {key: row[key] for key in ("notice_id", "expected_amount", "expected_jc_supplier", "expected_warehouse_key")} | {
        "contract_id": choice["contract_id"], "expected_contract_supplier": choice["supplier_name"],
    }


@pytest.fixture
def matching_api(monkeypatch):
    reads = {"sessions": 0, "payables": 0}

    @contextmanager
    def session(*args, **kwargs):
        reads["sessions"] += 1
        yield

    def read():
        reads["payables"] += 1
        return [source(), source(code="CGYF2")]

    monkeypatch.setattr(api, "unified_i8_session", session)
    monkeypatch.setattr(api, "_read_payables", read)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        yield client, reads


def test_preview_reads_payables_once_and_confirm_uses_local_facts_only(rollback_db, matching_api):
    client, reads = matching_api
    with session_scope() as s:
        project = _project(s, "__应付批量__")
        target = contract(s, project, "CGHT1")
        other = contract(s, project, "CGHT2", supplier="乙")
        items = [
            notice(s, project, "明确合同", remark="合同CGHT1"),
            notice(s, project, "同额应付", title="甲的钢材款"),
            notice(s, project, "人工选择", title="钢材款"),
            notice(s, project, "已关联", supplier="乙"),
            notice(s, project, "已剔除", excluded=True),
            notice(s, project, "未审批", approve_status="未批"),
            notice(s, project, "已撤回", i8_revoked=True),
            notice(s, project, "零金额", amount_approved=Decimal("0")),
            notice(s, project, "无归属", ownership_id=None),
        ]
        ids = [item.id for item in items]
        target_id, other_id = target.id, other.id
        S.act_link_notice(s, notice_id=ids[3], contract_id=other_id)

    def preview(ids_to_check, **session_fields):
        response = client.post("/api/m11/auto-link-preview", json={"notice_ids": ids_to_check, **session_fields})
        assert response.status_code == 200
        return response.json()

    assert preview([ids[0], *ids[3:]])["rows"][0]["rule_code"] == "explicit_contract"
    assert reads == {"sessions": 0, "payables": 0}
    assert preview(ids) == {"ok": True, "needs_payables": True}
    data = preview(ids, session_mode="browser", device_id="test")["rows"]
    assert reads == {"sessions": 1, "payables": 1}
    local, payable, review, *skipped = data
    assert local["target"]["contract_id"] == payable["target"]["contract_id"] == target_id
    assert payable["bucket"] == "auto_ready"
    assert payable["payable_codes"] == ["CGYF1", "CGYF2"]
    assert payable["expected_amount"] == "100.01"
    assert payable["expected_jc_supplier"] == ""
    assert payable["expected_warehouse_key"] == "__应付批量__"
    assert review["bucket"] == "needs_review"
    assert [row["bucket"] for row in skipped] == ["skipped"] * 6
    choice = next(c for c in review["candidates"] if c["contract_id"] == other_id)
    assert choice["selectable"]
    with session_scope() as s:
        assert R.payment_of_notice(s, ids[0]) is None

    selections = [selection(local), selection(payable), selection(review, choice)]
    response = client.post("/api/m11/auto-link", json={"selections": selections})
    assert response.status_code == 200
    assert response.json()["linked"] == 3
    replay = client.post("/api/m11/auto-link", json={"selections": selections}).json()
    assert replay["linked"] == 0
    assert all("已有合同关联" in row["reason"] for row in replay["rows"])
    assert reads == {"sessions": 1, "payables": 1}
    with session_scope() as s:
        assert R.links_by_notice(s, ids) == {ids[0]: [target_id], ids[1]: [target_id],
                                            ids[2]: [other_id], ids[3]: [other_id]}
        assert s.get(PaymentNotice, ids[1]).jc_supplier == "甲"
        assert s.get(PaymentNotice, ids[2]).jc_supplier == "乙"


@pytest.mark.parametrize("change, reason", [
    ("amount", "金额"), ("supplier", "供应商"), ("project", "项目"), ("tag", "不再纳入"),
    ("contract_supplier", "合同供应商"), ("contract_project", "已更换项目"),
    ("linked", "已有合同关联"), ("unbound", "手工解绑"),
])
def test_confirm_skips_preview_stale_local_facts(rollback_db, matching_api, change, reason):
    client, reads = matching_api
    with session_scope() as s:
        project = _project(s, "__关联并发__")
        other_project = _project(s, "__更改归属__")
        target = contract(s, project, "CGHT1")
        other = contract(s, project, "CGHT2")
        item = notice(s, project, "待核对", title="CGHT1材料款")
        nid, cid, other_cid, other_pid = item.id, target.id, other.id, other_project.id
    row = client.post("/api/m11/auto-link-preview", json={"notice_ids": [nid]}).json()["rows"][0]
    assert row["bucket"] == "auto_ready"
    with session_scope() as s:
        if change == "amount":
            s.get(PaymentNotice, nid).amount_approved = Decimal("101.01")
        elif change == "supplier":
            s.get(PaymentNotice, nid).jc_supplier = "乙"
        elif change == "project":
            s.get(PaymentNotice, nid).ownership_id = other_pid
        elif change == "tag":
            s.get(JcContract, cid).tag = D.TAG_OUT
        elif change == "contract_supplier":
            s.get(JcContract, cid).supplier = "乙"
        elif change == "contract_project":
            s.get(JcContract, cid).project_id = other_pid
        else:
            S.act_link_notice(s, notice_id=nid, contract_id=other_cid)
            if change == "unbound":
                S.act_unlink_notice(s, notice_id=nid)

    result = client.post("/api/m11/auto-link", json={"selections": [selection(row)]}).json()
    assert result["linked"] == 0 and reason in result["rows"][0]["reason"]
    assert reads == {"sessions": 0, "payables": 0}
    with session_scope() as s:
        assert R.links_by_notice(s, [nid]) == ({nid: [other_cid]} if change == "linked" else {})


def test_explicit_number_precedes_payable_and_protects_excluded_or_conflicting_contracts(rollback_db, matching_api):
    client, reads = matching_api
    with session_scope() as s:
        project = _project(s, "__明确合同号__")
        contract(s, project, "CGHT1")
        target = contract(s, project, "CGHTXX-20260101-2", supplier="乙")
        excluded = contract(s, project, "CGHT202507040001", tag=D.TAG_OUT)
        items = [
            notice(s, project, "备注提及", remark="合同cghtxx-20260101-2质保金"),
            notice(s, project, "含不纳入", supplier="甲", title="合同编号：202507040001 和 CGHT1"),
            notice(s, project, "供应商冲突", supplier="甲", title="CGHTXX-20260101-2"),
            notice(s, project, "提及多份", title="CGHT1 与 CGHTXX-20260101-2"),
        ]
        ids, cid, excluded_id = [item.id for item in items], target.id, excluded.id

    explicit, excluded_row, conflict, ambiguous = client.post(
        "/api/m11/auto-link-preview", json={"notice_ids": ids},
    ).json()["rows"]
    assert explicit["bucket"] == "auto_ready" and explicit["target"]["contract_id"] == cid
    assert explicit["payable_codes"] == []
    assert excluded_row["rule_code"] == "contract_excluded"
    excluded_candidate = next(c for c in excluded_row["candidates"] if c["contract_id"] == excluded_id)
    assert excluded_candidate["selectable"] is False
    assert conflict["rule_code"] == "supplier_conflict" and not conflict["candidates"][0]["selectable"]
    assert ambiguous["rule_code"] == "contract_ambiguous"
    assert reads == {"sessions": 0, "payables": 0}


@pytest.mark.parametrize("title, supplier, payable, expected", [
    ("甲方物资钢材", "", source(supplier="甲方物资有限公司"), "sole_supplier_contract"),
    ("甲方物资 乙方建材", "", source(supplier="甲方物资有限公司"), "supplier_unresolved"),
    ("钢材", "", source(supplier="甲方物资有限公司"), "supplier_unresolved"),
    ("乙方建材", "甲方物资有限公司", source(supplier="甲方物资有限公司"), "sole_supplier_contract"),
    ("甲方物资", "", source(supplier="甲方物资有限公司", project="其他项目"), "no_exact_payable"),
    ("甲方物资", "", source(supplier="乙方建材有限公司"), "no_exact_payable"),
    ("甲方物资", "", source(supplier="甲方物资有限公司", amount="110.01"), "no_exact_payable"),
])
def test_amount_match_uses_unique_supplier_project_and_exact_amount(rollback_db, title, supplier, payable, expected):
    with session_scope() as s:
        project = _project(s, "__付款应付范围__")
        first = contract(s, project, "CGHT1", supplier="甲方物资有限公司")
        contract(s, project, "CGHT2", supplier="乙方建材有限公司")
        item = notice(s, project, "供应商判断", title=title, supplier=supplier)
        row = S.auto_link_plan(s, [item.id], [payable])[0].as_row()
        assert row["rule_code"] == expected
        if expected == "sole_supplier_contract":
            assert row["target"]["contract_id"] == first.id
        else:
            assert row["bucket"] == "needs_review"
            assert row["candidates"]


@pytest.mark.parametrize("target_side, other_side, second_payable, expected", [
    ("trade", None, False, "unique_payment_invoice"),
    ("supplier", None, False, "insufficient_corroboration"),
    ("trade", "supplier", False, "insufficient_corroboration"),
    ("trade", None, True, "payable_contract_unresolved"),
])
def test_amount_match_checks_unique_payment_side_invoice_across_project(
    rollback_db, target_side, other_side, second_payable, expected,
):
    with session_scope() as s:
        project = _project(s, "__付款侧发票__")
        target = contract(s, project, "CGHT1", trade_co="贸易公司")
        contract(s, project, "CGHT2")
        competitor = contract(s, project, "CGHT3", supplier="乙")
        excluded = contract(s, project, "CGHT4", tag=D.TAG_OUT)
        item = notice(s, project, "付款侧发票校验", supplier="甲")
        invoice = R.insert_invoice(s, contract_id=target.id, kind=target_side, invoice_date="2026-09-18",
                                  amount=Decimal("100.01"))
        R.insert_invoice(s, contract_id=excluded.id, kind="supplier", invoice_date="2026-09-18",
                         amount=Decimal("100.01"))
        if other_side:
            R.insert_invoice(s, contract_id=competitor.id, kind=other_side, invoice_date="2026-09-18",
                             amount=Decimal("100.01"))
        payables = [source()]
        if second_payable:
            payables.append(source("CGHT2", code="CGYF2"))
        row = S.auto_link_plan(s, [item.id], payables)[0].as_row()
        assert row["rule_code"] == expected
        if expected == "unique_payment_invoice":
            assert row["target"]["contract_id"] == target.id
            assert row["target"]["invoice_ids"] == [invoice.id]
        else:
            evidence = next(c for c in row["candidates"] if c["contract_id"] == target.id)
            assert row["bucket"] == "needs_review"
            assert evidence["invoice_match"] == (target_side == "trade")
            assert evidence["invoice_side"] == "trade"


def test_manual_link_clears_unbind_protection(rollback_db, matching_api):
    client, reads = matching_api
    with session_scope() as s:
        project = _project(s, "__人工解绑保护__")
        target = contract(s, project, "CGHT1")
        item = notice(s, project, "绑定保护", title="CGHT1")
        nid, cid = item.id, target.id
    assert client.post("/api/m11/link", json={"notice_id": nid, "contract_id": cid}).json()["ok"]
    assert client.post("/api/m11/unlink", json={"notice_id": nid}).json()["ok"]
    preview = client.post("/api/m11/auto-link-preview", json={"notice_ids": [nid]}).json()
    assert preview["rows"][0]["rule_code"] == "manually_unlinked"
    with session_scope() as s:
        assert s.get(PaymentNotice, nid).jc_auto_link_blocked is True
        assert s.get(PaymentNotice, nid).jc_supplier == "甲"
        assert R.payment_of_notice(s, nid) is None
    assert client.post("/api/m11/link", json={"notice_id": nid, "contract_id": cid}).json()["ok"]
    with session_scope() as s:
        assert s.get(PaymentNotice, nid).jc_auto_link_blocked is False
        assert R.payment_of_notice(s, nid).contract_id == cid
    assert reads == {"sessions": 0, "payables": 0}


def test_concurrent_confirmations_link_the_notice_once(matching_api):
    client, reads = matching_api
    name = "lock-" + uuid4().hex
    with session_scope() as s:
        project = _project(s, name)
        target = contract(s, project, "CGHT1")
        item = notice(s, project, name, title="CGHT1")
        nid, cid, pid = item.id, target.id, project.id
    try:
        row = client.post("/api/m11/auto-link-preview", json={"notice_ids": [nid]}).json()["rows"][0]
        barrier = Barrier(2)

        def confirm():
            barrier.wait(10)
            return client.post("/api/m11/auto-link", json={"selections": [selection(row)]}).json()

        with ThreadPoolExecutor(2) as pool:
            attempts = [pool.submit(confirm) for _ in range(2)]
            outcomes = [attempt.result(timeout=10) for attempt in attempts]
        assert sorted(outcome["linked"] for outcome in outcomes) == [0, 1]
        assert reads == {"sessions": 0, "payables": 0}
        with session_scope() as s:
            assert R.links_by_notice(s, [nid]) == {nid: [cid]}
    finally:
        with session_scope() as s:
            s.execute(delete(PaymentNotice).where(PaymentNotice.id == nid))
            s.execute(delete(JcContract).where(JcContract.id == cid))
            s.execute(delete(Project).where(Project.id == pid))


def test_source_pagination_and_money():
    class Client:
        calls=[]
        def post_json(self,path,**kw):
            self.calls.append(kw['data'])
            start=int(kw['data']['start'])
            return {'Success':True,'totalRows':'202','Record':[
                dict(PhId=str(i), BillNo='CGYF'+str(i), AsrFlag=0 if i == 200 else 1,
                     WfFlag=6 if i == 201 else 2, PhidFcur_EXName='人民币', ExchRate=1, AppAmtVatFc='0.10')
                for i in range(start, min(start+200, 202))
            ]}
    client=Client(); rows=fetch_payables(client)
    assert len(rows)==201 and rows[0]['amount']==Decimal('0.10')
    assert rows[-1]['code'] == 'CGYF200'
    assert 'CGYF201' not in {r['code'] for r in rows}
    assert [r['start'] for r in client.calls]==['0','200']
    class Broken:
        def post_json(self,*a,**kw):return {'Success':True,'totalRows':'3','Record':[]}
    with pytest.raises(ExternalServiceError):fetch_payables(Broken())
