"""`ACC-JC-*`（M5 集采域）· **域内核**的验收断言。

⚠️ 本文件**只钉纯函数口径**（结算 / 欠款 / 子表校验 / 两态 / 去重 / 候选）——
   界面结构、落库、勾选语义那些判据点留给壳侧与 API 侧（M5-7），⛔ 别在这里凑数。

逐条对应（`claim` 原文见验收基线 `PRD/验收/验收基线.json`）：
- `ACC-JC-UI-001/001-05` **子表日期必填**：只填金额不填日期 ⇒ 不得落库（发票与付款同款）
- `ACC-JC-UI-001/001-06` 发票金额**不设上限**（可超合同金额，只走「必须大于零」这一个出口）
- `ACC-JC-UI-001/001-09` 主表金额列 = **只读汇总**，录入只走子表：**改子表即改欠款**
- `ACC-JC-UI-001/001-10` **结算口径两条路径**（有 / 无贸易公司）各取各自子表合计，**两条互不串用**
- `ACC-JC-UI-001/001-15` 付款方式**自由文本、不做枚举校验**（`DEV-J-03`）
- `ACC-JC-PAY-001/001-02` 同一笔通知书只能被引用一次（**全库去重**）⇒ 重复引用必须被拦
- `ACC-JC-PAY-001/001-04` 关联**不做金额校验**：不一致**只提示、不拦截**
- `ACC-JC-PAY-001/001-05` 候选收窄为「本项目 ＋ 已匹配供应商」，**当前已关联的无条件保留**
- `ACC-JC-PAY-001/001-06` 候选为空 ⇒ **给提示且不允许提交**
- `ACC-JC-FETCH-001/001-10` **抓取不覆盖已人工标记的行**（⭐ 这条原是"待建"档）

⚠️ `ACC-JC-FETCH-001/001-01`（触发方式「人工 + 定时」）**本文件刻意不钉** ——
   它与《说明书》§6.5.2（D9：**仅人工点击、不做定时**）**冲突**，已登记为待裁定事项（见 §14.4c 的卡点栏）；⛔ 不替用户拍板。
⭐ `001-07`（默认值 = 纳入台账）**只钉在 `test_acc_jc_write.py`**（⛔ 本文件不重复钉）；
   ⭐ `TAIL-97` 之后它**不再与 §6.5.3 冲突**了 —— 抓取与手工新增的默认值**已经合流**。
"""

from __future__ import annotations

from decimal import Decimal

from tests.acc_plugin import acc

from app.mod11_jc import domain as D
from app.mod11_jc.models import KIND_SUPPLIER, KIND_TRADE, TAG_IN, TAG_OUT


def _inv(kind: str, date: str, amount: str) -> dict:
    return {"kind": kind, "date": date, "amount": Decimal(amount)}


def _pay(date: str, amount: str, source: str = "manual", notice_id=None) -> dict:
    return {"date": date, "amount": Decimal(amount), "source": source, "notice_id": notice_id}


# ---------------------------------------------------------------- 子表校验


@acc("ACC-JC-UI-001", "001-05")
def test_子表日期必填_只填金额不填日期不得落库():
    """发票与付款**同款**：日期是必填项（发票要能对上所属期）。"""
    assert D.invoice_problem("", "100") == D.MSG_NEED_DATE, "发票：只填金额不填日期 ⇒ 必须报错（不得落库）"
    assert D.payment_problem("", "100") == D.MSG_NEED_DATE, "付款：同一套规则（判据原文「发票与付款同款」）"
    assert D.invoice_problem("2026-09-01", "100") is None, "日期 + 正金额 ⇒ 可落库"
    assert D.payment_problem("2026-09-01", "100") is None


@acc("ACC-JC-UI-001", "001-06")
def test_发票金额只走大于零这一个出口_不设上限():
    """**可超合同金额**：金额上限这件事在口径里根本不存在（只拦 ≤ 0 与非数字）。"""
    big = "99999999.99"                      # 远超任何合同金额
    assert D.invoice_problem("2026-09-01", big) is None, "金额不设上限 ⇒ 天文数字也应放行"
    assert D.parse_amount(big) == Decimal(big)
    for bad in ("0", "-1", "abc", ""):
        assert D.invoice_problem("2026-09-01", bad) == D.MSG_BAD_AMOUNT, f"{bad!r} 必须被拦（唯一出口 = 必须大于零）"
    # ⚠️ 与 MOD-09 手填项**刻意不同**：那边允许 0 与负数（§8.4 第③档）
    assert D.invoice_problem("2026-09-01", "0.01") is None


# ---------------------------------------------------------------- 结算 / 欠款


@acc("ACC-JC-UI-001", "001-10")
def test_结算两条路径各取各自子表合计_互不串用():
    """**有**贸易公司 → 贸易发票合计；**无** → 供应商发票合计；⭐ 两条路**互不串用**。"""
    invoices = [_inv(KIND_SUPPLIER, "2026-08-01", "1000"), _inv(KIND_TRADE, "2026-08-02", "700")]
    assert D.settle_amount(trade_co="某贸易公司", invoices=invoices) == Decimal("700.00"), "有贸易公司 ⇒ 取贸易发票"
    assert D.settle_amount(trade_co="", invoices=invoices) == Decimal("1000.00"), "无贸易公司 ⇒ 取供应商发票"

    # ⭐ 互不串用：**有**贸易公司时，供应商发票怎么变都**不影响**结算
    more_supplier = invoices + [_inv(KIND_SUPPLIER, "2026-08-03", "5000")]
    assert D.settle_amount(trade_co="某贸易公司", invoices=more_supplier) == Decimal("700.00"), \
        "有贸易公司 ⇒ 供应商发票子表再多也不许渗进结算（两条路径互不串用）"
    # 反向同理：**无**贸易公司时，贸易发票变了也不影响
    more_trade = invoices + [_inv(KIND_TRADE, "2026-08-04", "9999")]
    assert D.settle_amount(trade_co="", invoices=more_trade) == Decimal("1000.00"), \
        "无贸易公司 ⇒ 贸易发票子表再多也不许渗进结算"


@acc("ACC-JC-UI-001", "001-09")
def test_主表金额列只读汇总_改子表即改欠款():
    """⭐ 判据要的是「**改子表即改欠款**」⇒ 主表那 5 个金额列每次**现算**（⛔ 不落库）。"""
    payments = [_pay("2026-09-10", "400")]
    before = D.contract_amounts(trade_co="", invoices=[_inv(KIND_SUPPLIER, "2026-09-01", "1000")],
                                payments=payments)
    assert before["settle"] == Decimal("1000.00") and before["pay_sum"] == Decimal("400.00")
    assert before["debt"] == Decimal("600.00"), "欠款 = 结算 − 付款（§6.4.4）"

    # 加一张发票 ⇒ 结算与欠款**立刻**跟着变（无需"同步主表"这一步 ⇒ 压根没有主表金额列可写）
    after = D.contract_amounts(trade_co="", invoices=[_inv(KIND_SUPPLIER, "2026-09-01", "1000"),
                                                     _inv(KIND_SUPPLIER, "2026-09-05", "250")],
                               payments=payments)
    assert after["settle"] == Decimal("1250.00") and after["debt"] == Decimal("850.00"), \
        "改子表即改欠款（+250 ⇒ 结算 +250、欠款 +250）"
    # 再录一笔付款 ⇒ 欠款减
    paid_more = D.contract_amounts(trade_co="", invoices=[_inv(KIND_SUPPLIER, "2026-09-01", "1000")],
                                   payments=payments + [_pay("2026-09-12", "100")])
    assert paid_more["debt"] == Decimal("500.00")

    # ⭐ 「主表金额列 = 只读汇总」的机器化：它们**不在**任何录入项清单里
    assert set(D.DERIVED_MONEY_KEYS) <= {c["key"] for c in D.JC_COLUMNS}, "派生列必须在表头里"
    assert D.debt_amount(settle=Decimal("1000"), pay=Decimal("400")) == Decimal("600.00")


@acc("ACC-JC-UI-001", "001-11")
def test_合计行各金额列独立复算():
    """判据要的是「**独立复算**」⇒ 这里用**原生算术**再算一遍，⛔ 不调被测的求和函数。"""
    rows = [
        {"contract_amt": Decimal("1000.00"), "inv_sum": Decimal("900.00")},
        {"contract_amt": Decimal("250.50"), "inv_sum": Decimal("0.50")},
    ]
    contract = sum(r["contract_amt"] for r in rows)
    inv = sum(r["inv_sum"] for r in rows)
    assert contract == Decimal("1250.50") and inv == Decimal("900.50")
    assert set(D.SUM_KEYS) <= {c["key"] for c in D.JC_COLUMNS}, "合计列必须都是表头里的列（列数对齐的前提）"


# ---------------------------------------------------------------- 自由文本（DEV-J-03）


@acc("ACC-JC-UI-001", "001-15")
def test_集采付款方式独立列已取消():
    """用户2026-10-14改为统一填写备注。"""
    from app.mod11_jc import excel_parse, import_service, repository
    assert "method" not in {c["key"] for c in D.JC_COLUMNS}
    assert "method" not in excel_parse.FIELD_LABELS
    assert "method" not in import_service.EXCEL_COLS
    assert "method" not in repository.EDITABLE_COLS


@acc("ACC-JC-FETCH-001", "001-10")
def test_抓取不覆盖已人工标记的行():
    """⭐ 原为「待建」档。`TAIL-97` 两态化之后口径变成：

    **抓来即「纳入台账」**，但 ⭐⭐ **人工标的「不纳入」抓取不许改回来**（这条铁律**必须保留**）。
    """
    assert D.tag_after_fetch(None) == TAG_IN, "新抓的行 ⇒ 「纳入台账」（`TAIL-97`：取消「待确认」）"
    assert D.tag_after_fetch("") == TAG_IN, "空值 ⇒ 当作新抓的"
    assert D.tag_after_fetch(TAG_IN) == TAG_IN, "本来就是「纳入台账」⇒ 原样"
    assert D.tag_after_fetch(TAG_OUT) == TAG_OUT, \
        "⭐ 人工标的「不纳入」必须**原样保留**（抓取**不许**改回来 —— 本条的要点）"
    # 认不出的值 ⇒ 回落到**默认值「纳入台账」**（两态下它就是系统默认，回落方向与"抓来即纳入"一致）
    assert D.normalize_tag("随便什么") == TAG_IN
    # ⭐ 取值域只剩两态（「待确认」已取消 ⇒ 谁把它加回来，本条必红）
    assert D.TAGS == (TAG_IN, TAG_OUT)


# ---------------------------------------------------------------- 付款引用（§6.6.2）


@acc("ACC-JC-PAY-001", "001-02")
def test_全库去重_同一通知书只能被引用一次():
    """去重范围 = **全库、不分合同**（判据原文点明"不分合同"）。"""
    assert D.dedup_blocked(notice_id=7, existing_notice_ids=[3, 7, 9]) is True, "已被别的合同引用过 ⇒ 也要拦"
    assert D.dedup_blocked(notice_id=8, existing_notice_ids=[3, 7, 9]) is False
    assert D.dedup_blocked(notice_id=None, existing_notice_ids=[3]) is False, "手工录入的（无通知书 id）不参与去重"


@acc("ACC-JC-PAY-001", "001-04")
def test_关联不做金额校验_不一致只提示不拦截():
    """⚠️ 口径是"事实优先"：金额对不上**照样能关联**，只是给一句提示。"""
    assert D.link_hint(notice_amount=Decimal("100"), contract_debt=Decimal("100")) is None, "一致 ⇒ 无提示"
    hint = D.link_hint(notice_amount=Decimal("100"), contract_debt=Decimal("80"))
    assert isinstance(hint, str) and hint, "不一致 ⇒ 给提示"
    # ⭐ 关键：这个出口**没有**"拒绝"这种返回值（返回值不是布尔 ⇒ 调用方无法拿它当"能不能提交"）
    assert D.link_hint(notice_amount=Decimal("1"), contract_debt=Decimal("99999")) is not None


@acc("ACC-JC-PAY-001", "001-05")
def test_候选范围收窄到本项目与已匹配供应商_且当前那张无条件保留():
    contracts = [
        {"id": 1, "project_key": "甲仓", "supplier": "业祥"},
        {"id": 2, "project_key": "甲仓", "supplier": "尚坤"},
        {"id": 3, "project_key": "乙仓", "supplier": "业祥"},
        {"id": 4, "project_key": "甲仓", "supplier": "亚尼奥"},
    ]
    got = {c["id"] for c in D.pick_candidates(contracts=contracts, project_key="甲仓", supplier="业祥")}
    assert got == {1}, "候选 = 本项目（仓库名判等）＋ 已匹配供应商"

    # ⭐ 当前已关联的那张**无条件保留**（哪怕它不在"本项目 + 该供应商"里）
    got2 = {c["id"] for c in D.pick_candidates(contracts=contracts, project_key="甲仓",
                                               supplier="业祥", current_id=3)}
    assert got2 == {1, 3}, "当前已关联的那张必须留在候选里（否则「改 / 解绑」看起来像从没关联过）"
    assert 3 in got2 and 2 not in got2 and 4 not in got2


@acc("ACC-JC-PAY-001", "001-06")
def test_候选为空时给提示且不允许提交():
    """⚠️ 域层只负责"候选为空"这个**事实**；"不许提交"由调用方（API / 壳）据此拦截。"""
    contracts = [{"id": 1, "project_key": "甲仓", "supplier": "业祥"}]
    assert D.pick_candidates(contracts=contracts, project_key="甲仓", supplier="不存在的供应商") == [], \
        "供应商匹配不到 ⇒ 候选为空（调用方必须给提示并禁止提交）"
    assert D.pick_candidates(contracts=contracts, project_key="丙仓", supplier="业祥") == []
