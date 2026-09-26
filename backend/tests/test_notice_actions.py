"""`MOD-03` **行级动作 · 域内核**的验收断言（批量改分类 · 剔除 / 恢复剔除 · 手动行载荷）。

判据点归属（2026-09-16 起）：
- `ACC-PAY-CAT-001`    —— 批量改分类（三类 · 必须先勾选 · 分档回报 · 只动勾选行）⇒ `§4.2.4`
- `ACC-PAY-MANUAL-001` —— 手动新增行（统计结算恒 0 · 录入人 · 项目候选 · 编辑删除边界 · 上限）⇒ `§4.2.6`

⚠️ 本件只放**不碰页面与路由**的纯函数断言；渲染面见 `test_wired_m03_action.py`（原 `test_notice_action_page.py` —— 该件已不在仓里）、
端点见 `test_notice_action_api.py`（2026-09-16 自 `test_notice_actions.py` 拆出，断言未改）。
⚠️ 桩件的**唯一主人** = `tests/m03_action_helpers.py`；本文件当年的「兼容再导出」已清理
（2026-09-17 · `TAIL-22`）—— 5 个依赖方改为直接指向主人，本文件不再充当二传手。
⚠️ **2026-09-21（`T5` 拆分）**：手动行的出口（载荷 / 项目候选 / 编辑删除）搬进
`notice_manual_actions` ⇒ 本件分两个别名：`A.*` = `notice_actions`（分类 · 剔除）·
`M.*` = `notice_manual_actions`（手动行）。**断言一字未改。**
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import MustReportError
from app.mod03_notice import notice_actions as A
from app.mod03_notice import notice_manual_actions as M
from app.mod03_notice.models import PaymentNotice
from tests.acc_plugin import acc
from tests.m03_action_helpers import FakeWriteSession, _notice


# ============================================================ 能力 2 · 批量改分类


@acc("ACC-PAY-CAT-001", "001-04")
def test_批量改分类只允许三类():
    with pytest.raises(MustReportError) as err:
        A.change_category([{"id": 1, "category": "material"}], [1], "other")
    assert "没有「其他」类" in err.value.message


@acc("ACC-PAY-CAT-001", "001-05")
def test_批量改分类必须先勾选():
    with pytest.raises(MustReportError) as err:
        A.change_category([{"id": 1, "category": "material"}], [], "mechanical")
    assert "必须先勾选" in err.value.message


@acc("ACC-PAY-CAT-001", "001-06")
def test_批量改分类分档回报且只动勾选行():
    rows = [
        {"id": 1, "category": "material"},
        {"id": 2, "category": "mechanical"},     # 本来就是目标分类 ⇒ unchanged
        {"id": 3, "category": "material"},
    ]
    change = A.change_category(rows, [1, 2], "mechanical")
    assert change.changed == [1] and change.unchanged == [2]
    assert "已把 1 行改为「机械」" in change.message
    assert "不留痕" in change.message              # 手改分类不留痕（§9.3）


@acc("ACC-PAY-CAT-001", "001-07")
def test_批量改分类落库只改勾选行():
    from app.mod03_notice import repository as repo

    s = FakeWriteSession({PaymentNotice: [_notice(1), _notice(2)]})
    n = repo.apply_category(s, [1], "jc")
    assert n == 1
    assert s.by_model[PaymentNotice][0].category == "jc"
    assert s.by_model[PaymentNotice][1].category == "material"      # 未勾选行一个不动


# ============================================================ 能力 3 · 剔除 / 恢复剔除


@acc("ACC-PAY-CAT-001", "001-08")
def test_人工剔除标记来源为manual且分档回报():
    rows = [{"id": 1, "excluded": False}, {"id": 2, "excluded": True}]
    report = A.manual_exclude(rows, [1, 2])
    assert report.marked == [1] and report.already == [2]
    assert "人工批量剔除" in report.message


@acc("ACC-PAY-CAT-001", "001-09")
def test_恢复剔除只恢复人工剔除且分开回报():
    rows = [
        {"id": 1, "exclude_source": "manual"},
        {"id": 2, "exclude_source": "rule"},
        {"id": 3, "exclude_source": ""},
    ]
    report = A.restore_excluded(rows, [1, 2, 3])
    assert report.restored == [1]
    assert report.kept_by_rule == [2]               # 规则命中**不恢复**
    assert report.untouched == [3]
    assert "规则命中" in report.message and "不恢复" in report.message


@acc("ACC-PAY-CAT-001", "001-10")
def test_恢复剔除必须先勾选():
    """⚠️ 本 claim 有个**前提**：剔除行**必须勾得上** —— 否则"必须先勾选"变成**无路可走**
    （用户 2026-09-21 报障：勾选框对剔除行 `disabled`，而恢复又要求先勾 ⇒ 两道门互锁）。
    ⇒ 后端这条（空勾选被拦）＋ **壳侧那条（剔除行可勾）两头一起断言** —— ⛔ 只测一头，
       另一半被改坏时这里照样全绿（这正是当初互锁没被发现的原因）。
    """
    with pytest.raises(MustReportError) as err:
        A.restore_excluded([{"id": 1, "exclude_source": "manual"}], [])
    assert "必须先勾选" in err.value.message

    from tests.shell_src import SHELL  # noqa: PLC0415  ← `P4`① 读取点收敛

    assert "const ntSelectable=n=>ntPayCand(n)||!!n.excl;" in SHELL, \
        "剔除行勾不上 ⇒ 「恢复剔除」这条路根本走不通（勾选框的可勾口径丢了）"
    assert "${ntSelectable(n)?'':'disabled'}" in SHELL, "勾选框没走可勾选出口"
    # ⚠️⚠️ **逐处**断言，⛔ 不能写成 `"ntHit(fNt).filter(ntSelectable)" in SHELL` ——
    #     `pickAll` 与 `BIND.m03` **各有一处**，只改坏其中一处时全文查找照样命中另一处 ⇒ **假绿**
    #     （反向灵敏度第 3/4 条实测抓到过；这两条正是"全选框永久卡半选态"的成因）。
    assert "pickAll:t=>{ const ids=ntHit(fNt).filter(ntSelectable).map(n=>n.id);" in SHELL, \
        "全选没走可勾选出口 ⇒ 点「全选」漏掉剔除行"
    assert ("const vis=ntHit(fNt).filter(ntSelectable).map(n=>n.id), "
            "hit=vis.filter(i=>pickSet.has(i)).length;") in SHELL, \
        "全选框回显与勾选框走了**两个**出口 ⇒ 全选框会永久卡在半选态（勾满了还是个半选框）"


# ============================================================ 能力 4 · 手动新增行


@acc("ACC-PAY-MANUAL-001", "001-01")
def test_手动行统计结算恒为0且录入人取自当前操作人():
    payload = M.manual_row_payload(
        entered_by="张三", doc_date="2026-09-01", amount_approved="50000",
        stat_paid="30000", stat_settle="999999",     # ← 故意乱传：必须被忽略
        input_by="别人",                              # ← 故意乱传：必须被忽略
    )
    v = payload.values
    assert v["stat_settle"] == Decimal("0.00")       # §4.2.6：**恒 0 且不可改**
    assert v["input_by"] == "张三"                    # 录入人 = 当前登录用户
    assert v["stat_paid"] == Decimal("30000.00")
    assert v["is_manual"] is True
    assert v["ph_id"].startswith(M.MANUAL_PH_PREFIX)  # 本地编号，不是 i8 单据
    assert "恒为 0" in "；".join(payload.notes)


@acc("ACC-PAY-MANUAL-001", "001-02")
def test_手动行超上限被拦截且保留原值():
    with pytest.raises(MustReportError) as err:
        M.manual_row_payload(entered_by="张三", doc_date="2026-09-01",
                            amount_approved="100", stat_paid="200")
    assert "不能超过审批金额" in err.value.message and "保留原值" in err.value.message


@acc("ACC-PAY-MANUAL-001", "001-03")
def test_手动行必须填单据日期():
    with pytest.raises(MustReportError) as err:
        M.manual_row_payload(entered_by="张三", amount_approved="100")
    assert "单据日期" in err.value.message


@acc("ACC-PAY-MANUAL-001", "001-04")
def test_编辑删除只对手动行开放():
    with pytest.raises(MustReportError) as err:
        M.assert_manual_editable({"id": 1, "ph_id": "3700000000123", "is_manual": False})
    assert "只对**手动新增行**开放" in err.value.message
    M.assert_manual_editable({"id": 1, "ph_id": "MANUAL-abc123", "is_manual": True})   # 不抛


@acc("ACC-PAY-MANUAL-001", "001-05")
def test_手动行项目候选含归档但排除壳():
    class P:
        def __init__(self, pid, typ, status="active", disp="", wh=""):
            self.id, self.project_type, self.status = pid, typ, status
            self.disp, self.warehouse_name, self.name_full = disp, wh, ""

        @property
        def is_shell(self):
            return self.project_type == "shell"

        @property
        def is_archived(self):
            return self.status == "archived"

    opts = M.manual_project_options([
        P(1, "normal", disp="甲项目"),
        P(2, "shell", disp="某壳"),
        P(3, "small", status="archived", disp="乙小微"),
    ])
    assert [o["key"] for o in opts] == ["1", "3"]      # 壳被排除（§4.2.6）
    assert opts[1]["archived"] is True                 # 归档**保留**
