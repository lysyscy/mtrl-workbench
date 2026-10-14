"""`ACC-JC-*`（M5 集采域）· **写路径**（`M5-4`：手工新增 / 三态标记 / 收发登记 / 子表增删）的验收断言。

⚠️ 库级断言**一律非破坏**：本机测试连的是**同一个测试库** ⇒ 每个用例末尾 `s.rollback()`（⛔ 一行不留）。

逐条对应（`claim` 原文见验收基线）：
- `ACC-JC-UI-001/001-13` 手工新增合同 = **保存真的建档**；取消不入库
- `ACC-JC-FETCH-001/001-07` **三态默认值 = 纳入台账**
- `ACC-JC-FETCH-001/001-03` 三态标记**可逐条也可批量**
- `ACC-JC-FETCH-001/001-05` 批量**只作用于勾选行**、**动作后清空勾选**、**不改行数**
- `ACC-JC-UI-001/001-12` 合同收发登记**三列 ＋ 备注**可手改并**落值**
- `ACC-JC-UI-001/001-04` 发票子表字段 = **日期 ＋ 金额**，且数据行真的渲染出日期
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL, Project
# ⚠️ `jc_payment.notice_id` 的外键指向 `payment_notice` ⇒ 触库前该模型必须在**元数据里注册**
#    （生产侧由 `main.py` import 各 router 顺带注册；测试进程没有那一步 ⇒ 显式引一次）。
from app.mod03_notice import models as _m03  # noqa: F401
from app.mod11_jc import service as SV
from app.mod11_jc.models import TAG_IN, TAG_OUT, JcContract, JcInvoice
from tests.acc_plugin import acc

WH_A = "__自检仓_集采写甲__"


def _project(s, wh: str = WH_A) -> Project:
    """造一个自检档案行（键 = 仓库名 · §2.7.4；用完 rollback ⇒ ⛔ 不留痕）。"""
    row = pj_repo.create_project(
        s, project_type=TYPE_NORMAL, name_full=f"{wh}项目", warehouse_name=wh, phid=""
    )
    s.flush()
    return row


def _n_contracts(s, project_id: int) -> int:
    """**独立复算**：另起一条 SQL 数行数（⛔ 不用被测接口的返回值自证）。"""
    return int(s.execute(
        select(func.count()).select_from(JcContract).where(JcContract.project_id == int(project_id))
    ).scalar_one())


@acc("ACC-JC-UI-001", "001-13")
def test_手工新增保存真的建档_没调接口就不入库():
    """⭐ 判据「**保存真的建档**」—— 建档前后**独立复算**该仓下的行数。"""
    with session_scope() as s:
        p = _project(s)
        before = _n_contracts(s, p.id)
        r = SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                material_name="主材钢材", supplier="业祥", contract_amt="27269.82")
        assert r["ok"] is True and r["id"], "保存必须回一个真实的 id（= 已落库）"
        assert _n_contracts(s, p.id) == before + 1, "建档 ⇒ 该仓下恰好多 1 行（独立复算）"

        row = s.get(JcContract, int(r["id"]))
        assert row is not None and row.supplier == "业祥" and row.contract_amt == Decimal("27269.82")

        # 「取消不入库」= 前端**不调本接口** ⇒ 这里只能钉"没调用就没有新行"这一面
        assert _n_contracts(s, p.id) == before + 1, "（不调接口 ⇒ 不产生任何行）"
        s.rollback()


@acc("ACC-JC-FETCH-001", "001-07")
def test_手工新增的三态默认是纳入台账():
    """⭐ 判据**原文**「默认值 = **纳入台账**」（比对加载时快照）。

    ⚠️ 这条**曾经**钉的是「抓取 ≠ 手工新增、两个默认值分来源」（用户 2026-09-19 定案）——
       ⭐ `TAIL-97`（用户 2026-09-25 取消「待确认」）之后**那个口径已被取代**：
       抓取与手工新增的默认值**合流**，两条路都是 `TAG_IN`。
    ⇒ 本断言现在钉的是**合流这件事本身**：谁再把两条路拆回分叉，必红。
    """
    with session_scope() as s:
        p = _project(s)
        r = SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19", supplier="业祥")
        assert r["tag"] == TAG_IN == SV.DEFAULT_TAG_ON_CREATE, \
            "手工新增的默认值必须是「纳入台账」（判据原文）"
        assert s.get(JcContract, int(r["id"])).tag == TAG_IN
        assert fetch_default_is_same_as_create_default(), \
            "`TAIL-97` 起两条路的默认值必须**合流**（抓取与手工新增同为「纳入台账」）"

        # 显式给了就听给的（⛔ 不硬塞默认）
        r2 = SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                 supplier="尚坤", tag=TAG_OUT)
        assert r2["tag"] == TAG_OUT
        s.rollback()


def fetch_default_is_same_as_create_default() -> bool:
    """钉「两条路的默认值**已合流**」（`TAIL-97`）：手工新增的出口默认 ＝ 表列默认（抓取那条路）。

    ⚠️ 反过来说也一样：**谁把它们拆回分叉，本断言必红**（这正是它现在的区分力所在）。
    """
    col_default = JcContract.__table__.c.tag.default
    return (SV.DEFAULT_TAG_ON_CREATE == TAG_IN
            and col_default is not None and col_default.arg == TAG_IN)


@acc("ACC-JC-FETCH-001", "001-03")
def test_三态标记可逐条也可批量():
    """⭐ 判据原文只要求"**两种都能**" ⇒ 逐条与批量各做一次，结果一致。"""
    with session_scope() as s:
        p = _project(s)
        ids = [int(SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                       supplier=f"商{i}")["id"]) for i in range(3)]

        one = SV.act_set_tag(s, contract_id=ids[0], tag=TAG_OUT)          # 逐条
        assert one["ok"] is True and s.get(JcContract, ids[0]).tag == TAG_OUT

        many = SV.act_batch_tag(s, contract_ids=ids[1:], tag=TAG_OUT)     # 批量
        assert many["ok"] is True and set(many["affected_ids"]) == set(ids[1:])
        assert all(s.get(JcContract, i).tag == TAG_OUT for i in ids), "两种方式结果一致"

        # 认不出的值 ⇒ 回落**默认值「纳入台账」**（`TAIL-97`：两态下它就是系统默认）
        SV.act_set_tag(s, contract_id=ids[0], tag="随便写的")
        assert s.get(JcContract, ids[0]).tag == TAG_IN, "非法值回落「纳入台账」（两态下的默认值）"
        s.rollback()


@acc("ACC-JC-FETCH-001", "001-05")
def test_批量标记只作用勾选行_不改行数_并回受影响id():
    """⭐ 判据三条：**只作用勾选行** · **动作后清空勾选**（壳按 `affected_ids` 清）· **不改行数**。"""
    with session_scope() as s:
        p = _project(s)
        ids = [int(SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                       supplier=f"商{i}")["id"]) for i in range(4)]
        picked = ids[:2]                                   # 勾选前两行
        total_before = s.execute(select(func.count()).select_from(JcContract)).scalar_one()

        r = SV.act_batch_tag(s, contract_ids=picked, tag=TAG_IN)

        # ① 只作用勾选行（没勾的原样）
        assert r["affected_ids"] and set(r["affected_ids"]) == set(picked)
        assert all(s.get(JcContract, i).tag == TAG_IN for i in picked), "勾选的都改了"
        # ⚠️ 没勾的保持**原值** —— 本题里它们是手工新增的，默认就是「纳入台账」
        #    （⛔ 断言里不能写死 TAG_PENDING：那会把"手工新增默认纳入台账"这条口径写反）
        assert all(s.get(JcContract, i).tag == TAG_IN for i in ids[2:]), "没勾的一行都不许动"
        # ② 不改行数（独立复算，⛔ 不看接口自报）
        assert s.execute(select(func.count()).select_from(JcContract)).scalar_one() == total_before
        assert r["row_count_before"] == r["row_count_after"] == int(total_before)
        # ③ 空勾选 = 先拦住（壳侧禁用按钮是另一道；后端也不许静默全改）
        empty = SV.act_batch_tag(s, contract_ids=[], tag=TAG_IN)
        assert empty["ok"] is False and empty["affected_ids"] == []
        s.rollback()


@acc("ACC-JC-UI-001", "001-12")
def test_收发登记三列与备注可手改并落值():
    """⭐ 判据「合同收发登记三列 ＋ 备注可手改并**落值**」—— 改完**重新取一次**才叫落值。"""
    with session_scope() as s:
        p = _project(s)
        cid = int(SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                      supplier="业祥")["id"])
        r = SV.act_update_contract(s, contract_id=cid, arch="已存档", arch_no="1",
                                   ret_date="2026-09-20", remark="属工程款，不计集采欠款")
        assert r["ok"] is True

        row = s.get(JcContract, int(cid))                  # 重新取（走 ORM ⇒ 落库值）
        assert (row.arch, row.arch_no, row.ret_date) == ("已存档", "1", "2026-09-20")
        assert row.remark == "属工程款，不计集采欠款"

        # ⛔ 白名单外（三态）不许从这个口子改 —— 它有自己的出口
        SV.act_update_contract(s, contract_id=cid, tag=TAG_OUT)
        assert s.get(JcContract, int(cid)).tag == TAG_IN, \
            "三态必须走 act_set_tag，⛔ 不从这个口子（值应**保持原样** = 手工新增的默认「纳入台账」）"

        # 已取消的付款方式不再通过主表写入口修改。
        assert not SV.act_update_contract(s, contract_id=cid, method="60±7天承兑")["ok"]
        assert s.get(JcContract, int(cid)).method == ""
        s.rollback()


@acc("ACC-JC-UI-001", "001-04")
def test_发票子表字段是日期加金额_且日期必填():
    """⭐ 判据「发票子表字段 = **日期 ＋ 金额**，共用同一套表头且数据行**真的渲染出日期**」。

    ⚠️ 这里钉的是**落库那两列真的存在且有值**（"渲染"是壳的事，见 `M5-7`）；
    外加一条**同款**规则：只填金额不填日期 ⇒ **不得落库**（`001-05`，发票与付款同一出口）。
    """
    with session_scope() as s:
        p = _project(s)
        cid = int(SV.act_add_contract(s, project_id=p.id, contract_date="2026-09-19",
                                      supplier="业祥")["id"])
        r = SV.act_add_invoice(s, contract_id=cid, kind="supplier",
                               date="2026-09-18", amount="1000")
        assert r["ok"] is True
        row = s.get(JcInvoice, int(r["id"]))
        assert (row.invoice_date, row.amount) == ("2026-09-18", Decimal("1000.00")), \
            "发票子表两列 = 日期 ＋ 金额（日期非空）"

        # 两张同款子表都走同一出口（贸易公司那一侧）
        r2 = SV.act_add_invoice(s, contract_id=cid, kind="trade", date="2026-09-18", amount="40812.62")
        assert r2["ok"] is True and s.get(JcInvoice, int(r2["id"])).kind == "trade"

        # 同款规则：缺日期 ⇒ 拒写（发票与付款**同一个**校验出口）
        bad = SV.act_add_invoice(s, contract_id=cid, kind="supplier", date="", amount="500")
        assert bad["ok"] is False and "日期" in bad["message"]
        bad2 = SV.act_add_payment(s, contract_id=cid, date="", amount="500")
        assert bad2["ok"] is False, "付款与发票**同款**（缺日期都不许落）"

        # 增行不改别的行：删掉刚加的那张 ⇒ 回到 1 张
        assert SV.act_del_invoice(s, invoice_id=int(r2["id"]))["ok"] is True
        left = list(s.execute(select(JcInvoice).where(JcInvoice.contract_id == int(cid))).scalars())
        assert [x.id for x in left] == [row.id]
        s.rollback()
