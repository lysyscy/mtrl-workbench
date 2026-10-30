"""`ACC-PAY-VERIFY-001`（付款前只核验审批状态）6 个判据点的验收断言。

依据：《说明书》§4.4.1（**唯一自动核验项 = 已批**）· §4.4.4（前置禁用 · 逐行移出 · 兜底整批重算）
      · §4.4.3（集采**未关联不可付**——用户 2026-09-24 口述，无例外）· `DEV-P-06`。
"""

from __future__ import annotations

from app.core.money import to_money
from app.mod03_notice.domain import (
    BLOCK_JC_UNLINKED,
    BLOCK_NOTHING_DUE,
    BLOCK_STATUS,
    VERIFY_ITEMS,
    PayDraft,
    PayRow,
    check_batch,
    confirm_batch,
    remove_from_batch,
    verify_row,
)
from app.mod05_flow.domain import CATEGORY_JC, CATEGORY_MATERIAL


def _ok(nid: int = 1, amount: str = "100.00") -> PayRow:
    return PayRow(notice_id=nid, approve_status="已批", payable=to_money(amount))


def test_已批是唯一自动核验项():
    assert VERIFY_ITEMS == ("approve_status",)                      # 核验项收敛为 1 项
    assert not any(("发票" in x) or ("特例" in x) for x in VERIFY_ITEMS)   # 发票核验 / 先付款特例均不做
    assert verify_row(_ok()) is None                                # 已批 ⇒ 通过
    assert verify_row(PayRow(2, "未批", to_money("100"))) == BLOCK_STATUS
    assert verify_row(PayRow(3, "审批中", to_money("100"))) == BLOCK_STATUS
    # 「本次应付 ≤ 0」是**前置状态**（不是核验项）：同样不可付
    assert verify_row(PayRow(4, "已批", to_money("0"))) == BLOCK_NOTHING_DUE


def test_存在不可付行时确认付款处于禁用态():
    chk = check_batch([_ok(1), PayRow(2, "未批", to_money("100")), _ok(3)])
    assert chk.enabled is False                      # **直接禁用**（不是点了才拦）
    assert [r.notice_id for r in chk.blocked] == [2]
    assert chk.blocked_ids == [2]
    # 已批但本次应付为 0（已付清）同样进不可付集合
    chk2 = check_batch([_ok(1), PayRow(2, "已批", to_money("0"))])
    assert chk2.enabled is False and chk2.blocked_ids == [2]
    # 全部可付 ⇒ 恢复可点
    assert check_batch([_ok(1), _ok(2)]).enabled is True
    assert check_batch([_ok(1)]).blocked_ids == []


def test_禁用时必须给出原因与解除方式():
    chk = check_batch([PayRow(2, "未批", to_money("100")), PayRow(3, "已批", to_money("0"))])
    assert chk.reason and chk.how_to_fix                  # 原因 + 解除方式，两者都不得为空
    assert "未批" in chk.reason or "审批" in chk.reason
    assert "应付" in chk.reason
    assert str(len(chk.blocked)) in chk.reason             # 报数：几条不可付
    assert ("移出" in chk.how_to_fix) or ("删除" in chk.how_to_fix)
    # 可付时不得给"已禁用"的解释
    ok = check_batch([_ok(1)])
    assert ok.enabled is True and ok.reason == "" and ok.how_to_fix == ""


def test_不可付行可逐行移出移出后恢复可点():
    rows = [_ok(1), PayRow(2, "未批", to_money("100"))]
    drafts = {1: PayDraft(pay_method="承兑", amount=to_money("80.00"))}
    left, left_drafts = remove_from_batch(rows, drafts, 2)
    assert [r.notice_id for r in left] == [1]
    assert check_batch(left).enabled is True               # 移出后不再有不可付行 ⇒ 恢复可点
    assert left_drafts[1].pay_method == "承兑"             # 移出**不改**其它行已填的值
    # 移出会同步取消该行勾选（本次批次里不再有它）
    assert 2 not in {r.notice_id for r in left}
    # 移出不存在 / 不可付之外的行也不出错（幂等）
    left2, _ = remove_from_batch(left, left_drafts, 999)
    assert [r.notice_id for r in left2] == [1]


def test_移出重绘不丢失其它行已填的值():
    rows = [_ok(1, "100.00"), _ok(2, "200.00"), PayRow(3, "未批", to_money("300.00"))]
    drafts = {
        1: PayDraft(pay_method="承兑", amount=to_money("80.00")),
        2: PayDraft(pay_method="供应链", amount=to_money("150.00")),
    }
    r1, d1 = remove_from_batch(rows, drafts, 3)
    r2, d2 = remove_from_batch(r1, d1, 2)
    assert d2[1].pay_method == "承兑" and d2[1].amount == to_money("80.00")   # 逐步移出后仍保留
    assert 2 not in d2 and 3 not in d2                                        # 移出者的草稿一并清掉

    # 兜底校验（§4.4.4）：提交时仍**整批重算**，任一不过 ⇒ **整批不产生任何流水**（不落半批）
    res = confirm_batch(r2, d2, pay_date="2026-09-15")
    assert res.ok and len(res.flows) == 1
    assert res.flows[0]["notice_id"] == 1 and res.flows[0]["amount"] == to_money("80.00")
    assert res.flows[0]["pay_method"] == "承兑"

    bad = confirm_batch(
        [_ok(1), PayRow(2, "未批", to_money("100"))],
        {1: PayDraft(amount=to_money("10.00"))},
        pay_date="2026-09-15",
    )
    assert bad.ok is False and bad.flows == []              # 整批不产生任何流水
    assert bad.errors and "未批" in bad.errors[0]


# ============================================================== 001-06 · ⑤ 集采未关联不可付


def test_集采未关联合同不可付():
    """§4.4.3：集采分类的行**必须已关联集采合同**才可付（用户 2026-09-24 口述，**无例外**）。

    ⚠️ 本测试钉的是**纯函数侧**（`PayRow.block()`）；生产接线（`NoticeRow.category` / `has_link`
       ⇒ `PayRow`）在 `notice_pay_actions.apply_batch_pay` —— 若那里漏传，本测试**照样绿**
       （`jc_linked` 默认 `False` 的方向是"拦住"）；本测试不证明浏览器交互。
    """
    # 集采 + 未关联 ⇒ 不可付（即便已批、有额度）
    assert verify_row(PayRow(11, "已批", to_money("100"), CATEGORY_JC, False)) == BLOCK_JC_UNLINKED
    # 集采 + 已关联 ⇒ 可付（闸只认"有没有关联"，⛔ 不校验关联的是哪一张、金额对不对）
    assert verify_row(PayRow(12, "已批", to_money("100"), CATEGORY_JC, True)) is None
    # ⛔ 非集采 / 分类为空**一律不受影响** —— 这是"只拦集采"的关键：漏传不该误伤辅材 / 机械
    assert verify_row(PayRow(13, "已批", to_money("100"), CATEGORY_MATERIAL, False)) is None
    assert verify_row(PayRow(14, "已批", to_money("100"))) is None

    # 前置禁用（§4.4.4）：原因要报出来，且**出路是"去关联"，不是"删掉"**
    chk = check_batch([_ok(1), PayRow(2, "已批", to_money("100"), CATEGORY_JC, False)])
    assert chk.enabled is False and chk.blocked_ids == [2]
    assert "集采未关联合同" in chk.reason
    assert "关联" in chk.how_to_fix                          # 给了正确的出路
    assert ("删除" in chk.how_to_fix) or ("移出" in chk.how_to_fix)      # 原有的出路仍在

    # 兜底校验（§4.4.4）：整批重算不过 ⇒ **整批不产生任何流水**
    res = confirm_batch(
        [PayRow(2, "已批", to_money("100"), CATEGORY_JC, False)],
        {2: PayDraft(amount=to_money("100"))},
        pay_date="2026-09-24",
    )
    assert res.ok is False and res.flows == []
    assert any("集采未关联合同" in e for e in res.errors)
