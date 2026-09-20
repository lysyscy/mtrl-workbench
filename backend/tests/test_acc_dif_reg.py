"""`ACC-DIF-REG-001` 差异登记（`MOD-12`）· **单元 1 = 后端判定与落库**。

依据（⛔ 不自己发明口径）：
· 《说明书》**§5.8.3**（差异登记正文）· **§8.3**（状态机）· §5.10 `DEV-R-06`
· `PRD/02-功能规格/MOD-12.md`（契约 · 只给节号）
· 原型 `V.m12` ＋ `ACT.dfSave`（**交互规格**：校验顺序与那句提示的措辞都照它）

⚠️ **本文件只覆盖 5 个判据点**（`001-02` `001-03` `001-04` `001-06` `001-10`）——
   其余 7 点钉的是**页面形态**（草稿行类名 / 筛选 / 空态 / 合计 / 展示名 / 默认值），
   要等**单元 2（壳取真数据）**之后才有意义：
   ⚠️ 现在就在**演示数据**上证形态 = **假绿**（数据都不是真的，形状对有什么用）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod12_diff import domain as D
from app.mod12_diff import repository as R
from tests.acc_plugin import acc


def _ok(**over) -> dict:
    """一份**合法**登记（各条用例只改自己关心的那格 ⇒ 失败时一眼看得出是谁的问题）。"""
    p = {"month": "2026-08", "project_name": "第四工程公司2026年小微项目",
         "detail": "__自检_差异__", "amount": "-220.00", "status": "待核对", "remark": ""}
    p.update(over)
    return p


# --------------------------------------------------------- `001-03` 必填校验


@acc("ACC-DIF-REG-001", "001-03")
def test_必填缺一即拒且金额合法不替它挡枪():
    """⭐ 判据原文特别加的那半句：「**金额即便合法也不得替它挡枪**」。

    ⚠️ 为什么值得单独钉：把校验写成"金额合法就放行"是很自然的写法（三个 if 合成一个），
       而它的后果是**缺了核算月的行也会进库** —— 之后对账按核算月归不了月，人也不知道它该算哪个月。
    """
    for missing in ("month", "project_name", "detail"):
        with pytest.raises(MustReportError):
            D.validate(_ok(**{missing: ""}))
        with pytest.raises(MustReportError):
            D.validate(_ok(**{missing: "   "}))          # 全空格也算缺（⛔ 不靠 strip 之外的宽放）

    # ⭐ 金额**合法**（甚至是合法负数）⇒ 三个必填照样各判各的
    for missing in ("month", "project_name", "detail"):
        with pytest.raises(MustReportError):
            D.validate(_ok(**{missing: "", "amount": "-220.00"}))

    # 核算月还要**格式**对（`YYYY-MM`）—— 只判非空会把 `2026/8` 放进去
    with pytest.raises(MustReportError):
        D.validate(_ok(month="2026/8"))
    D.validate(_ok())                                    # 正例：合法的那份必须过


# --------------------------------------------------------- `001-04` 金额出口


@acc("ACC-DIF-REG-001", "001-04")
def test_金额非数字被拒且负数必须放行():
    """§5.8.3：「差异金额的形态 = **带符号**（+ 上调 / − 下调）」。

    ⚠️ **负数必须放行**是这条判据的重点 —— 直觉上"金额不该是负的"，
       而差异金额**天生就是带符号的**（同 `MOD-08` 调整单差额「调整后 − i8 原始」）。
       `−220` 是**下调**，不是输入错误。
    """
    for bad in ("abc", "", "  ", "1,234", "--5", "NaN", "Infinity"):
        with pytest.raises(MustReportError):
            D.parse_amount(bad)

    assert D.parse_amount("-220.50") == Decimal("-220.50"), "负数（下调）必须放行"
    assert D.parse_amount("+1400") == Decimal("1400"), "显式正号（上调）必须放行"
    assert D.parse_amount("0") == Decimal("0")
    # ⛔ 无上限：差异金额**不设 cap**（与"统计两金额 ≤ 审批金额"那条不是一回事）
    assert D.parse_amount("999999999.99") == Decimal("999999999.99")


# --------------------------------------------------------- `001-10` 归属恒定


@acc("ACC-DIF-REG-001", "001-10")
def test_归属恒为库存单据且不存在过程资料归属():
    """§5.8.3：「差异归属枚举**恒为「库存单据」** —— 不再按「发现位置」区分过程资料 / 库存单据」。

    ⚠️ 判据钉的是「**不存在**归属为过程资料的记录」⇒ 光"默认值是库存单据"不够：
       得让它**传不进去**（⛔ 不写成 `payload.get("owner") or OWNER_INV` —— 那是留了个口子）。
    """
    assert D.OWNER_INV == "库存单据"
    for sneaky in ({"owner": "过程资料"}, {"owner": ""}, {"owner": "库存单"},
                   {"type": "过程资料"}, {"发现位置": "过程资料"}):
        rec = D.to_record(D.validate(_ok(**sneaky)))
        assert rec["owner"] == D.OWNER_INV, f"归属被调用方改了：{sneaky}"

    # 库里也不许出现别的取值
    with session_scope() as s:
        row = R.create_record(s, D.validate(_ok(detail="__自检_归属__", owner="过程资料")))
        assert row.owner == D.OWNER_INV
        assert {r.owner for r in R.list_records(s)} <= {D.OWNER_INV}, \
            "库里出现了非「库存单据」的归属 —— 口径「恒为库存单据」已破"
        s.rollback()


# --------------------------------------------------- `001-02` 登记 / 编号 / 默认态


@acc("ACC-DIF-REG-001", "001-02")
def test_登记落库编号不撞且默认待核对():
    """登记一条 = 落库 +1 · **编号不撞既有行** · 默认状态 = **待核对**。

    ⚠️⚠️ 「不撞号」这条**必须删着行验**：本页**可以删行**，
       若拿"条数 + 1"当编号 ⇒ 登记 3 条删掉中间那条再登记 ⇒ 又发一个已存在的号。
       所以这里**真的删一条再登记**，而不是只 check 递增。
    """
    with session_scope() as s:
        before = len(R.list_records(s))
        a = R.create_record(s, D.validate(_ok(month="2026-01", detail="__自检_A__")))
        b = R.create_record(s, D.validate(_ok(month="2026-01", detail="__自检_B__")))
        c = R.create_record(s, D.validate(_ok(month="2026-01", detail="__自检_C__")))
        assert len(R.list_records(s)) == before + 3, "登记一条要落库 +1"
        assert b.status == D.STATUS_PENDING, "新登记的默认状态 = 待核对（§8.3）"

        R.delete_record(s, b)                      # ⭐ 删中间那条
        d = R.create_record(s, D.validate(_ok(month="2026-01", detail="__自检_D__")))
        codes = [r.code for r in R.list_records(s)]
        assert len(set(codes)) == len(codes), f"编号撞号了：{codes}"
        assert d.code not in (a.code, c.code), "删行后新登记的编号撞上了现存行"
        s.rollback()


# --------------------------------------------------------- `001-06` 删除


@acc("ACC-DIF-REG-001", "001-06")
def test_删除只删该行其余一行不动():
    """判据：「删除只删该行，**其余行一行不动**」—— ⛔ 不是"删完重排"、更不是"清表重建"。"""
    with session_scope() as s:
        r1 = R.create_record(s, D.validate(_ok(month="2026-02", detail="__自检_删1__")))
        r2 = R.create_record(s, D.validate(_ok(month="2026-02", detail="__自检_删2__")))
        r3 = R.create_record(s, D.validate(_ok(month="2026-02", detail="__自检_删3__")))
        snapshot = {r.id: (r.code, r.seq, r.detail, r.status, str(r.amount))
                    for r in R.list_records(s)}

        R.delete_record(s, r2)
        left = {r.id: (r.code, r.seq, r.detail, r.status, str(r.amount))
                for r in R.list_records(s)}
        assert r2.id not in left, "目标行没删掉"
        for rid in (r1.id, r3.id):
            assert left[rid] == snapshot[rid], f"删一行动了别的行（id={rid}）"
        s.rollback()
