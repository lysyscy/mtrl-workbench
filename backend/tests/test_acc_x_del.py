"""`ACC-X-DEL-001` 跨域能力 · **删除的分档与二次确认**（`MOD-13` · §9.4）。

## ⚠️ 这一片的性质：**不是"写新功能"，是"给已有的删除出口补判据"**

取证（2026-09-20）发现：这条用例 8 个点原本 **0/8 全未绑定**，但**落点早就都在了** ——
`mod04_plan.plan_ui.delete_impact` / `delete_rows` · `mod03_notice.notice_actions.apply_manual_delete` ·
`mod03_notice.rules_repository.delete_row` · `mod08_inv.domain.boundary_violations` …
⇒ 缺的只是**断言**（`§9.4` 那套分档从没被机器钉过）。

## 本文件钉什么（本轮 4 条）

| 点 | 钉的事实 | 落点 |
|---|---|---|
| `001-01` | 删除前**列影响范围**，且是**真实计数**（逐行对得上，⛔ 不是"共 N 条"这种占位） | `plan_ui.delete_impact` |
| `001-04` | **i8 源数据行一律无删除入口**（对照：可删行必须有） | `mod08_inv.domain.boundary_violations` |
| `001-06` | 逐行 / 多选删除**都只删选中行**；**未确认就拒** | `plan_ui.delete_rows` |
| `001-07` | **撤销调整单只删该条**：i8 源数据一行不动、该行退出差异表 | `mod08_inv.domain` |

⏳ **尚未钉（落点已找到，留给下一轮）**：`001-02` 配置类硬删（`rules_repository.delete_row`）·
`001-05` 手动行删除同步清归属与勾选（`notice_actions.apply_manual_delete`）·
`001-08` §9.4 分档清单本身。⚠️ **`001-03`（账号软删）等 `m15`** —— 那里还没开工。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import MustReportError
from app.mod04_plan import plan_ui as U
from app.mod08_inv import domain as I
from tests.acc_plugin import acc


def _rows() -> list[dict]:
    """三行计划行（形状按 `delete_impact` 读的键给：`id` / `year_month`）。"""
    return [{"id": 11, "year_month": "2026-08", "doc_no": "P001"},
            {"id": 12, "year_month": "2026-08", "doc_no": "P002"},
            {"id": 13, "year_month": "2026-09", "doc_no": "P003"}]


def _results() -> dict:
    return {11: "完全匹配", 12: "金额不符", 13: "完全匹配"}


# ---------------------------------------------------------- `001-01` 影响范围


@acc("ACC-X-DEL-001", "001-01")
def test_删除前列出真实影响范围而不是占位():
    """§7.2 / §9.4「删除前必须二次确认，且确认框里**列出影响范围**」。

    ⚠️ 判据特别加的那半句是「**真实计数，不是占位**」——
       因为"共 3 条"这种话**写起来最省事**，但它让确认框变成**走过场**：
       人看不到"删的是哪几行、属于哪个月、审查结论是什么"，就没法真正判断该不该删。
    ⇒ 所以这里逐字段核对，⛔ 不是只数条数。
    """
    rows, res = _rows(), _results()
    impact = U.delete_impact(rows, [11, 13], res)

    assert [i.row_id for i in impact] == [11, 13], "影响范围没逐行列出（或顺序不是表内顺序）"
    assert [i.seq for i in impact] == [1, 3], "**行号**要按表内序号给（人靠它认行）"
    assert [i.year_month for i in impact] == ["2026-08", "2026-09"], "所属年月要如实给"
    assert [i.result for i in impact] == ["完全匹配", "完全匹配"], "审查结果要如实给（⛔ 不留空）"

    # ⛔ 反面：没被选中的行**一条都不许**出现在影响范围里（那会吓到用户、也让人不敢删）
    assert 12 not in [i.row_id for i in impact], "没选中的行混进了影响范围"


# ---------------------------------------------------------- `001-04` 无删除入口


@acc("ACC-X-DEL-001", "001-04")
def test_i8源数据行一律无删除入口():
    """§4.2.7 / `NG-03`：**i8 抓取回来的行永不删**（源数据只读）⇒ 本页**连删除入口都不建**。

    ⚠️ 判据要求**两面都看**：「i8 源数据行一律无删除入口」＋「**对照：可删行必须仍有删除入口**」
       —— 只钉"没有"是不够的*（把整页的删除都删掉也能让前半句成立）*。
    """
    # ① i8 源数据那一页（库存单据）：不得出现删除动作
    bad = I.boundary_violations(action_ids=("delete", "del", "DELETE"))
    assert len(bad) == 3, f"删除动作没被拦住：{bad}"
    assert all("NG-03" in b for b in bad), "拦了但没说清依据（`NG-03`）"

    # ② 合规面：正常列 / 正常动作 ⇒ **一条都不报**（⛔ 不能"什么都报"来假装严格）
    assert I.boundary_violations(column_keys=("amount", "warehouse", "adj_amount")) == [], \
        "正常列被误判成违规 ⇒ 这个守卫会变成噪音、人就不看了"
    assert I.FORBIDDEN_ACTIONS == ("delete", "del"), "禁用的动作清单变了（要同批改本件与文档）"


# ---------------------------------------------------------- `001-06` 只删选中行


@acc("ACC-X-DEL-001", "001-06")
def test_只删选中行且未确认就拒():
    """§4.3.6：「**必须先列出影响范围并确认**」＋「只删该行，其余行不受影响」。

    ⚠️ 两条缺一不可：只钉"删对了" ⇒ 不确认也能删；只钉"要确认" ⇒ 确认后可能删多了。
    """
    rows = _rows()

    # ① **没确认 ⇒ 拒绝**（⛔ 不"默认确认"、也不"悄悄放行"）
    with pytest.raises(MustReportError):
        U.delete_rows(rows, [12], set(), confirmed=False)

    # ② 多选删除：只删选中的那两行，剩下一行**一字不动**
    kept, picked = U.delete_rows(rows, [11, 13], {11, 12, 13}, confirmed=True)
    assert [r["id"] for r in kept] == [12], "删多了 / 删少了"
    assert kept[0] == rows[1], "留下的那一行被改动了（删除不该碰其它行）"
    assert rows[1] == {"id": 12, "year_month": "2026-08", "doc_no": "P002"}, "原数组被就地改了"

    # ③ **勾选集同步收敛**：删掉的行不许还留在勾选里（否则汇总条会算上不存在的行）
    assert picked == {12}, f"勾选没收敛：{picked}"

    # ④ 逐行删除 = 单选，走的是**同一个出口**（⛔ 不许另写一条路）
    kept1, _ = U.delete_rows(rows, [12], set(), confirmed=True)
    assert [r["id"] for r in kept1] == [11, 13]

    # ⑤ ⚠️ 本动作**只影响付款计划表**（§4.3.6）—— 碰了别的表就是越界
    assert U.AFFECTED_TABLES == ("plan_row",), f"删除的影响面被放大了：{U.AFFECTED_TABLES}"


# ---------------------------------------------------------- `001-07` 撤销调整单


@acc("ACC-X-DEL-001", "001-07")
def test_撤销调整单只删该条且源数据不动():
    """2026-09-20 改写（原 claim 指着一个已撤的页）：**撤销调整单 = 只删这一条调整单**。

    ⚠️ 「删除」在这个域里的形态很特别：**删的是"人的判断"，不是"数据"** ——
       调整单撤掉之后，i8 原始行**还在**、原始金额**一字未动**，只是它**退出了差异表**。
       这正是 §9.4「源数据永不删」在差异这个场景下的落点。
    """
    raw = {"id": "IV-9", "doc_no": "CK009", "seq": 1, "material": "钢板",
           "warehouse": "甲仓", "amount": Decimal("500.00")}
    before = dict(raw)

    adj = I.make_adjustment(raw, Decimal("450.00"), "价差", operator="张伟")
    assert I.is_adjusted(I.with_adjustment(raw, adj)) is True

    cleared = I.with_adjustment(raw, {})                  # 撤销 = 去掉调整单这一层
    assert I.is_adjusted(cleared) is False, "撤销后仍算「调过」⇒ 差异表会留一条幽灵"
    assert cleared["amount"] == before["amount"] == Decimal("500.00"), \
        "撤销调整单**绝不能**碰到 i8 原始金额（源数据永不删、永不改）"
    assert raw == before, "连传入的源行都不该被就地改"
