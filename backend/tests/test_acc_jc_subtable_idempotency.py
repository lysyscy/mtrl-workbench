"""集采子表**可靠保存 / 恢复**（可选 `request_id` 幂等 ＋ 回执读取）＋ 主表默认行序。

守的是用户口径（2026-11-03 已确认）：
- 默认行序 = **合同日期从早到晚、同一天按录入先后、无日期放最后**（与项目内动态序号同一口径）；
- 带 `request_id` 的**同一操作**重复提交 ⇒ ⛔ 不重复产生 / 删除事实，回放原成功回执；
- 同一标识换动作 / 换参数 ⇒ **明确拒绝**（⛔ 不拿"日期金额相同"当同一笔）；
- 回执只回**当前账号自己**；未登录 / 别人的 / 没这条 ⇒ 一律 `not_found`；
- 回执与业务变更**同事务** ⇒ 事务失败⛔ 不留"成功回执"；删行之后重放仍可靠（回执只增不删）；
- 回执**不进**撤销白名单 ⇒ 既有真实撤销通道不受影响。

⚠️ 库级断言**一律非破坏**：每个用例都用 `rollback_db`（提交只释放保存点、结束回滚外层事务）。
"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy import func, select

from app.core.db import session_scope
from app.core import history
from app.history_bindings import configure
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod03_notice import models as _m03  # noqa: F401  触库前必须注册 payment_notice
from app.mod11_jc import domain as D
from app.mod11_jc import repository as R
from app.mod11_jc import service as SV
from app.mod11_jc.models import (
    SUBOP_INVOICE_ADD,
    SUBOP_INVOICE_DEL,
    SUBOP_PAYMENT_ADD,
    TAG_IN,
    JcContract,
    JcInvoice,
    JcPayment,
    JcSubtableOperation,
)


@pytest.fixture(autouse=True)
def account(monkeypatch):
    """给每个用例一个确定的登录账号（回执按它隔离）；结束还原，⛔ 不污染其他用例。"""
    from app.core import session as SESS

    before = SESS.current_name()
    SESS.set_current_name("__acc_default__")
    try:
        yield SESS
    finally:
        SESS.set_current_name(before)


def _warehouse() -> str:
    """每个用例一个**独占仓库名**（= 项目筛选键）⇒ 断言不会被别的用例的行干扰。"""
    return f"__自检仓_子表回执_{uuid.uuid4().hex[:8]}__"


def _project(s, wh: str):
    row = pj_repo.create_project(
        s, project_type=TYPE_NORMAL, name_full=f"{wh}项目", warehouse_name=wh, phid="")
    s.flush()
    return row


def _contract(s, *, project_id: int, date: str = "2026-09-18", supplier: str = "自检供应商",
              amount: str = "1000", tag: str = TAG_IN) -> JcContract:
    row = JcContract(project_id=int(project_id), contract_date=date, material_name="自检材料",
                     supplier=supplier, contract_amt=Decimal(amount), tag=tag)
    s.add(row)
    s.flush()
    return row


def _n(s, model) -> int:
    """独立复算行数（⛔ 不靠接口自证）。"""
    return int(s.execute(select(func.count()).select_from(model)).scalar_one())


def _facts(s, *, contract_id: int) -> dict[str, int]:
    """该合同下的**事实行数**（发票 / 付款）—— 判据「重复请求只一条事实」看它。"""
    inv = s.execute(select(func.count()).select_from(JcInvoice)
                    .where(JcInvoice.contract_id == int(contract_id))).scalar_one()
    pay = s.execute(select(func.count()).select_from(JcPayment)
                    .where(JcPayment.contract_id == int(contract_id))).scalar_one()
    return {"invoice": int(inv), "payment": int(pay)}


# ======================================================== ① 默认行序（日期 / 同日 / 无日期）

def test_默认行序是合同日期升序_同日按录入先后_无日期排最后(rollback_db):
    """用户口径：日期从早到晚、同一天按录入先后、无日期放最后；与项目内动态号同一口径。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        late = _contract(s, project_id=project.id, date="2026-09-20")
        # 同一天两张：先录入的 id 更小 ⇒ 排在前面
        same_first = _contract(s, project_id=project.id, date="2026-09-18")
        same_second = _contract(s, project_id=project.id, date="2026-09-18")
        blank = _contract(s, project_id=project.id, date="")

        rows = R.list_contracts(s, project_key=wh)
        assert [r["id"] for r in rows] == [same_first.id, same_second.id, late.id, blank.id]

        # 动态序号与行序**同一口径**（筛选不改号 ⇒ 这里按全量算）
        sequences = D.project_sequences(rows)
        assert [sequences[r["id"]] for r in rows] == [1, 2, 3, 4]
        s.rollback()


def test_合同日期列不可为空所以无日期是空串不是NULL(rollback_db):
    """⚠️ 判据里的「无日期放最后」在库里**没有 NULL 可排**：`contract_date` 是 NOT NULL。

    ⇒ 排序靠"空串排最后"，⛔ 不能写 `NULLS LAST`（那种写法在这里永远不生效，还会骗人以为已覆盖）。
    """
    from sqlalchemy import inspect

    with session_scope() as s:
        column = {c["name"]: c for c in inspect(s.get_bind()).get_columns("jc_contract")}["contract_date"]
        assert column["nullable"] is False
        s.rollback()


def test_筛选后的行序仍按同一口径且不改动态号(rollback_db):
    """筛选只影响"看哪几行"，⛔ 不改行序口径、⛔ 不改项目内序号（判据：筛选不改变号）。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        a = _contract(s, project_id=project.id, date="2026-09-18")
        b = _contract(s, project_id=project.id, date="2026-09-20")
        c = _contract(s, project_id=project.id, date="")

        full = R.list_contracts(s, project_key=wh)
        sequences = D.project_sequences(full)
        filtered = R.list_contracts(s, project_key=wh, supplier="自检供应商")
        assert [r["id"] for r in filtered] == [r["id"] for r in full] == [a.id, b.id, c.id]
        assert [sequences[r["id"]] for r in filtered] == [1, 2, 3]
        s.rollback()


# ======================================================== ② 带标识的重复请求只产生一条事实

def test_发票增行重复提交只留一条事实且回放原回执(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"inv-add-{uuid.uuid4().hex}"

        first = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                   date="2026-09-18", amount="1000", request_id=rid)
        assert first["ok"] is True and first["id"]
        again = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                   date="2026-09-18", amount="1000", request_id=rid)
        # 回放 = **原样**的成功回执（同一个 id），⛔ 不是"再插一条"
        assert again == first
        assert _facts(s, contract_id=contract.id) == {"invoice": 1, "payment": 0}
        assert s.get(JcInvoice, int(first["id"])) is not None
        s.rollback()


def test_付款增行重复提交只留一条事实(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"pay-add-{uuid.uuid4().hex}"

        first = SV.act_add_payment(s, contract_id=contract.id, date="2026-10-05",
                                   amount="123", request_id=rid)
        again = SV.act_add_payment(s, contract_id=contract.id, date="2026-10-05",
                                   amount="123", request_id=rid)
        assert again == first and first["ok"] is True
        assert _facts(s, contract_id=contract.id) == {"invoice": 0, "payment": 1}
        s.rollback()


def test_删行重复提交仍然可靠_删后重放回原回执(rollback_db):
    """删成功之后再重放：⛔ 不能回"找不到" —— 回执只增不删，删行不会把它带走。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        added = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                   date="2026-09-18", amount="500")
        rid = f"inv-del-{uuid.uuid4().hex}"

        first = SV.act_del_invoice(s, invoice_id=int(added["id"]), request_id=rid)
        assert first["ok"] is True
        again = SV.act_del_invoice(s, invoice_id=int(added["id"]), request_id=rid)
        assert again == first                       # ⛔ 不是 {"ok": False, "找不到发票行"}
        assert _facts(s, contract_id=contract.id) == {"invoice": 0, "payment": 0}

        # 回执读取：跑成功过 ⇒ completed ＋ 原成功回执
        seen = SV.subtable_operation(s, request_id=rid)
        assert seen == {"ok": True, "status": "completed", "result": first}
        # 回执要能说清"删的是哪份合同的子表行"（删之前读出的，⛔ 行没了不影响）
        row = R.subtable_operation_by_request(s, rid)
        assert (row.action, row.contract_id, row.row_id) == (SUBOP_INVOICE_DEL,
                                                             contract.id, int(added["id"]))
        s.rollback()


def test_付款删行重放同样不回找不到(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        added = SV.act_add_payment(s, contract_id=contract.id, date="2026-10-05", amount="77")
        rid = f"pay-del-{uuid.uuid4().hex}"

        first = SV.act_del_payment(s, payment_id=int(added["id"]), request_id=rid)
        again = SV.act_del_payment(s, payment_id=int(added["id"]), request_id=rid)
        assert first["ok"] is True and again == first
        assert _facts(s, contract_id=contract.id) == {"invoice": 0, "payment": 0}
        s.rollback()


def test_不带标识的老调用行为一字不变(rollback_db):
    """迁移前的前端没带 `request_id` ⇒ 每次都是新操作（同日期同金额也不去重）。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        a = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                               date="2026-09-18", amount="1000")
        b = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                               date="2026-09-18", amount="1000")
        assert a["id"] != b["id"]
        assert _facts(s, contract_id=contract.id) == {"invoice": 2, "payment": 0}
        assert _n(s, JcSubtableOperation) == 0      # ⛔ 老调用不留回执
        s.rollback()


# ======================================================== ③ 同键不同内容 ⇒ 明确拒绝

def test_同标识换参数被明确拒绝且不再落事实(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"inv-add-{uuid.uuid4().hex}"

        assert SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                  date="2026-09-18", amount="1000", request_id=rid)["ok"] is True
        clash = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                   date="2026-09-18", amount="1001", request_id=rid)
        assert clash["ok"] is False and clash["kind"] == "err"
        assert clash["message"] == D.MSG_REQUEST_TAKEN
        assert _facts(s, contract_id=contract.id)["invoice"] == 1
        s.rollback()


def test_同标识换动作被明确拒绝(rollback_db):
    """同一个标识先用于"增"，再想用于"删" ⇒ 拒绝（⛔ 不能悄悄执行另一件事）。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"mixed-{uuid.uuid4().hex}"

        added = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                   date="2026-09-18", amount="1000", request_id=rid)
        assert added["ok"] is True
        clash = SV.act_del_invoice(s, invoice_id=int(added["id"]), request_id=rid)
        assert clash["ok"] is False and clash["message"] == D.MSG_REQUEST_TAKEN
        assert _facts(s, contract_id=contract.id)["invoice"] == 1
        s.rollback()


def test_不以日期金额相同判重_两个不同标识就是两笔(rollback_db):
    """⭐ 判重只认标识：**同日期同金额**但标识不同 ⇒ 两笔各落一条（那是两次真实录入）。"""
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        a = SV.act_add_payment(s, contract_id=contract.id, date="2026-10-05", amount="123",
                               request_id=f"pay-{uuid.uuid4().hex}")
        b = SV.act_add_payment(s, contract_id=contract.id, date="2026-10-05", amount="123",
                               request_id=f"pay-{uuid.uuid4().hex}")
        assert a["id"] != b["id"]
        assert _facts(s, contract_id=contract.id)["payment"] == 2
        s.rollback()


def test_不合法标识被拒且不落事实(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        bad = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                 date="2026-09-18", amount="1000", request_id="含 空格 与/斜杠")
        assert bad["ok"] is False and bad["message"] == D.MSG_REQUEST_BAD
        assert _facts(s, contract_id=contract.id)["invoice"] == 0
        assert _n(s, JcSubtableOperation) == 0
        s.rollback()


# ======================================================== ④ 回执只回当前账号自己

def test_回执只对写入它的账号可见(rollback_db, account):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"inv-add-{uuid.uuid4().hex}"
        account.set_current_name("__acc_a__")
        done = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                  date="2026-09-18", amount="1000", request_id=rid)
        assert done["ok"] is True

        # 同一个会话里换账号：读不到别人的回执，⛔ 也读不到"存在但没权限"的区别
        account.set_current_name("__acc_b__")
        assert SV.subtable_operation(s, request_id=rid) == {"ok": True, "status": "not_found"}
        # 而且⛔ 不能拿别人的标识继续做"自己的"操作
        stolen = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                    date="2026-09-18", amount="1000", request_id=rid)
        assert stolen["ok"] is False and stolen["message"] == D.MSG_REQUEST_TAKEN

        # 原账号照常读得到
        account.set_current_name("__acc_a__")
        assert SV.subtable_operation(s, request_id=rid)["status"] == "completed"
        s.rollback()


def test_未登录与没这条都回not_found(rollback_db, account):
    with session_scope() as s:
        account.set_current_name("")
        assert SV.subtable_operation(s, request_id=f"nobody-{uuid.uuid4().hex}") == {
            "ok": True, "status": "not_found"}
        account.set_current_name("__acc_a__")
        assert SV.subtable_operation(s, request_id=f"missing-{uuid.uuid4().hex}") == {
            "ok": True, "status": "not_found"}
        assert SV.subtable_operation(s, request_id="") == {"ok": True, "status": "not_found"}
        assert SV.subtable_operation(s, request_id="不合法 标识") == {"ok": True, "status": "not_found"}
        s.rollback()


def test_http读回执按当前登录账号隔离(rollback_db):
    """走真 HTTP：A 写、A 读到 completed；B 读同一标识只有 not_found。"""
    from app.core import session as SESS
    from app.main import create_app
    from tests._auth import TestClient

    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        cid = contract.id

    app = create_app()
    rid = f"http-{uuid.uuid4().hex}"
    client_a = TestClient(app)
    client_a.cookies.set(SESS.COOKIE_NAME, SESS.make("__acc_a__"))
    body = {"id": cid, "kind": "supplier", "date": "2026-09-18",
            "amount": "1000", "request_id": rid}
    first = client_a.post("/api/m11/invoice/add", json=body)
    assert first.status_code == 200 and first.json()["ok"] is True
    again = client_a.post("/api/m11/invoice/add", json=body)
    assert again.json() == first.json()

    read_a = client_a.get("/api/m11/subtable-operation", params={"request_id": rid}).json()
    assert read_a["status"] == "completed" and read_a["result"] == first.json()

    client_b = TestClient(app)
    client_b.cookies.set(SESS.COOKIE_NAME, SESS.make("__acc_b__"))
    read_b = client_b.get("/api/m11/subtable-operation", params={"request_id": rid}).json()
    assert read_b == {"ok": True, "status": "not_found"}


def test_http不传标识的老调用照旧可用(rollback_db):
    from app.core import session as SESS
    from app.main import create_app
    from tests._auth import TestClient

    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        cid = contract.id

    app = create_app()
    client = TestClient(app)
    client.cookies.set(SESS.COOKIE_NAME, SESS.make("__acc_a__"))
    res = client.post("/api/m11/invoice/add",
                      json={"id": cid, "kind": "supplier", "date": "2026-09-18", "amount": "1000"})
    assert res.status_code == 200 and res.json()["ok"] is True


# ======================================================== ⑤ 事务失败不留成功回执

def test_事务失败既不留事实也不留成功回执(rollback_db, account):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        cid = contract.id

    rid = f"boom-{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            assert SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                                      date="2026-09-18", amount="1000",
                                      request_id=rid)["ok"] is True
            raise RuntimeError("模拟提交前失败")

    with session_scope() as s:
        assert _facts(s, contract_id=cid) == {"invoice": 0, "payment": 0}
        assert R.subtable_operation_by_request(s, rid) is None
        assert SV.subtable_operation(s, request_id=rid) == {"ok": True, "status": "not_found"}
        # ⭐ 而且这个标识**还能正常用**（失败没占坑）
        assert SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                                  date="2026-09-18", amount="1000", request_id=rid)["ok"] is True
        s.rollback()


def test_业务校验失败也不写回执(rollback_db):
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        rid = f"bad-{uuid.uuid4().hex}"
        bad = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                 date="", amount="1000", request_id=rid)
        assert bad["ok"] is False
        assert R.subtable_operation_by_request(s, rid) is None
        # 同一标识改对之后再提交 ⇒ 正常成功（失败没占坑）
        good = SV.act_add_invoice(s, contract_id=contract.id, kind="supplier",
                                  date="2026-09-18", amount="1000", request_id=rid)
        assert good["ok"] is True
        s.rollback()


# ======================================================== ⑥ 既有撤销通道不受回执影响

def test_回执不进撤销白名单且历史行为与不带标识时一致(rollback_db, account):
    """子表写口在历史里本来就是"不支持撤销"（barrier）⇒ 加回执后**行为一模一样**。"""
    configure()
    assert "jc_subtable_operation" not in history._rules      # ⛔ 别把它加进撤销白名单

    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id)
        cid = contract.id

    def perform(path, fn, actor="__jc_subop__"):
        token, state = history.begin_request(actor, "POST", path)
        try:
            with session_scope() as s:
                out = fn(s)
            # ⚠️ `state.result` 由 `session_scope()` 退出时的 `committed()` 才写 ⇒ 必须出了 with 再读。
            return out, state.result
        finally:
            history.end_request(token)

    # 不带标识（既有行为）
    plain, plain_state = perform("/api/m11/invoice/add",
                                 lambda s: SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                                                              date="2026-09-18", amount="100"))
    # 带标识
    keyed, keyed_state = perform("/api/m11/invoice/add",
                                 lambda s: SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                                                              date="2026-09-18", amount="200",
                                                              request_id=f"hist-{uuid.uuid4().hex}"))
    assert plain["ok"] is True and keyed["ok"] is True
    assert plain_state == keyed_state == "unsupported"        # 与既有行为一致，不是回归

    with session_scope() as s:
        assert _facts(s, contract_id=cid)["invoice"] == 2
        assert _n(s, JcSubtableOperation) == 1                # 回执照常落了，⛔ 没被历史吞掉


def test_回执存在时真实撤销通道仍然可用(rollback_db, account):
    """回执不影响**白名单模型**的撤销：三态改动照旧能撤销，回执行一行不少。"""
    configure()
    wh = _warehouse()
    with session_scope() as s:
        project = _project(s, wh)
        contract = _contract(s, project_id=project.id, tag="不纳入")
        cid = contract.id
        assert SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                                  date="2026-09-18", amount="1000",
                                  request_id=f"undo-{uuid.uuid4().hex}")["ok"] is True

    actor = "__jc_subop_undo__"

    def perform(fn, path="/api/m11/tag"):
        token, state = history.begin_request(actor, "POST", path)
        try:
            with session_scope() as s:
                out = fn(s)
            return out, state.result        # 同上：`state.result` 只在提交后才写
        finally:
            history.end_request(token)

    _, recorded = perform(lambda s: SV.act_set_tag(s, contract_id=cid, tag=TAG_IN))
    assert recorded == "recorded"

    with session_scope() as s:
        assert s.get(JcContract, cid).tag == TAG_IN
        top = history.status(s, actor)["undo"]
        assert top is not None and top["count"] > 0            # 撤的是三态那一步（被回执的 barrier 截断在下面）
        history.replay(s, actor, "undo", top["id"])
        s.flush()
        assert s.get(JcContract, cid).tag == "不纳入"
        assert _n(s, JcSubtableOperation) == 1                # 回执没被撤销动作影响
