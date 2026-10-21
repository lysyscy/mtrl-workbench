"""剔除判定（§4.2.2 / §4.2.3）与分类落实（§4.2.4）的验收断言。

判据点归属（2026-09-16 起）：
- `ACC-PAY-EXCL-001` —— 剔除**判定逻辑**（4 类规则命中 / 集采不走剔除 / 分类三类）⇒ `§4.2.2` `§4.2.3`
- `ACC-PAY-CAT-001`  —— **批量改分类 + 手改分类保护**（`§4.2.4`）与**恢复剔除按勾选**（`§4.2.2`）

⚠️ `ACC-CFG-RULE-001`（`MOD-14`）只管**配置页的只读展示**，**不 cover** 本文件的判定逻辑
   —— 两者是两件事，别把判据点挂过去（挂了会造出"看着有主人、其实没验"的假绿）。

口径出处：《说明书》§4.2.2（剔除 4 类）· §4.2.3（分类三类）· §4.2.4（手改保护）。
"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.mod03_notice.classify import (
    DEFAULT_RULES,
    FORBIDDEN_PAYEE_VALUE,
    ExcludeRule,
    KIND_PAYEE,
    apply_manual_exclude,
    decide_placement,
    is_excluded,
    match_exclude_rule,
    restore_excluded,
    validate_rules,
)
from app.mod05_flow.domain import CATEGORY_JC, CATEGORY_MATERIAL, CATEGORY_MECH


def _rec(**kw) -> dict:
    """一条 `_map_record` 形态的记录。"""
    base = {"biz_type": "", "project_name": "", "payee": "", "input_by": "", "fields": {}}
    base.update(kw)
    return base


# ---------------------------------------------------------------- §4.2.2 四类规则


def test_四类规则各自命中():
    # ① 业务类型（等值）
    assert match_exclude_rule(_rec(biz_type="付劳务公司款")) is not None
    assert match_exclude_rule(_rec(biz_type="付材料采购款")) is not None
    # ② 付款项目名（等值）
    assert match_exclude_rule(_rec(project_name="集团公司第四分公司机关工程")) is not None
    # ③ 单据名称**关键字**（包含）—— 走 fields.BillName（表里没有独立列）
    r = _rec(fields={"BillName": "2026年9月水电费结算单"})
    assert match_exclude_rule(r) is not None
    # ④ 录入人（等值）
    assert match_exclude_rule(_rec(input_by="梁丽佳")) is not None


def test_不命中的记录不算剔除():
    r = _rec(biz_type="付设备租赁款", payee="某租赁公司", input_by="王潜森",
             fields={"BillName": "材料款结算单"})
    assert match_exclude_rule(r) is None
    assert is_excluded(r) is False


def test_业务类型是等值而不是包含():
    """口径给的是完整值 ⇒ 「付材料采购款」不得因为"包含"而误命中别的写法。"""
    assert match_exclude_rule(_rec(biz_type="付材料采购款项下")) is None


# ---------------------------------------------------------------- 集采不走剔除（硬约束）


def test_集采收款单位不参与剔除():
    r = _rec(biz_type="", payee=FORBIDDEN_PAYEE_VALUE)
    assert match_exclude_rule(r) is None           # **不剔除**
    assert decide_placement(r).category == CATEGORY_JC   # 而是**参与分类**


def test_规则集里出现集采收款单位要显式拒绝():
    with pytest.raises(MustReportError):
        validate_rules((ExcludeRule(KIND_PAYEE, (FORBIDDEN_PAYEE_VALUE,)),))
    with pytest.raises(MustReportError):
        # 塞进别的类别也不行（绕法要堵住）
        validate_rules((ExcludeRule("biz_type", (FORBIDDEN_PAYEE_VALUE,)),))
    with pytest.raises(MustReportError):
        validate_rules((ExcludeRule("biz_type", ()),))     # 空命中值
    validate_rules(DEFAULT_RULES)                          # 默认规则集合法


# ---------------------------------------------------------------- §4.2.3 分类


def test_分类三类且顺序正确():
    # ① 付设备租赁款 → 机械（**优先于**集采收款单位）
    assert decide_placement(_rec(biz_type="付设备租赁款", payee=FORBIDDEN_PAYEE_VALUE)).category == CATEGORY_MECH
    # ② 收款单位 = 资产处集中采购 → 集采
    assert decide_placement(_rec(payee=FORBIDDEN_PAYEE_VALUE)).category == CATEGORY_JC
    # ③ 其余 → 辅材（**没有"其他"类**）
    assert decide_placement(_rec(biz_type="付其他供应商款", payee="某公司")).category == CATEGORY_MATERIAL


# ---------------------------------------------------------------- §4.2.4 手改保护


def test_手改过的分类不被重抓覆盖():
    rec = _rec(biz_type="付其他供应商款")             # 自动判定本应是「辅材」
    auto = decide_placement(rec)
    assert auto.category == CATEGORY_MATERIAL and auto.category_kept is False

    manual = decide_placement(rec, manual_category=CATEGORY_MECH)
    assert manual.category == CATEGORY_MECH           # 人工判断优先
    assert manual.category_kept is True


# ---------------------------------------------------------------- 人工剔除 vs 规则命中


def test_人工剔除不会被规则结果降级():
    """`current_source=manual` 时必须保持人工 —— 否则"恢复剔除"会突然能放开它（§4.2.2）。"""
    rec = _rec(biz_type="付其他供应商款")             # 不命中任何规则
    p = decide_placement(rec, current_source="manual")
    assert p.excluded is True and p.exclude_source == "manual"

    # 命中规则的行：来源应为 rule
    p2 = decide_placement(_rec(biz_type="付劳务公司款"))
    assert p2.excluded is True and p2.exclude_source == "rule"
    assert p2.matched_rule is not None and "业务类型" in p2.reason


# ---------------------------------------------------------------- 「恢复剔除」（按勾选）


def test_恢复剔除人工与规则命中的都放回且必须勾选():
    """⭐ 2026-10-08 用户裁定：**规则命中的也恢复**（原先只放人工剔除的）。

    ⚠️ 改这条的理由：旧口径说"要放开只能改规则配置"，而 `mod14_config.rules_api` 明写
    **改规则不重算历史剔除标记**、再次导入时 `merge.PROTECTED` 又不覆盖这两个字段
    ⇒ 规则命中的行**没有任何放开出口**。既然那条路走不通，就让「恢复剔除」本身能放开。
    代价（用户已知）：恢复后重新进统计与付款，再次抓取不会反弹。
    """
    rows = [
        {"id": 1, "exclude_source": "manual"},     # 人工批量剔除 ⇒ 恢复
        {"id": 2, "exclude_source": "rule"},       # ⭐ 规则命中 ⇒ **也恢复**（旧口径是不恢复）
        {"id": 3, "exclude_source": ""},           # 本就未剔除 ⇒ 不动
    ]
    with pytest.raises(MustReportError):
        restore_excluded(rows, [])                 # **不做整表一键放回**

    rep = restore_excluded(rows, [1, 2, 3])
    assert rep.restored == [1, 2], "人工 ＋ 规则命中的都要放回"
    assert rep.restored_by_rule == [2], "「其中规则命中的那几条」要单独记一份（回执要分档说清）"
    assert rep.untouched == [3], "本就未剔除的行不该被算成恢复"
    assert not hasattr(rep, "kept_by_rule"), "旧字段 `kept_by_rule`（=不恢复）已随口径作废，别留着骗人"
    # **分开回报**（口径要求界面把两类说清）＋ 把"要长期剔除该改规则"讲明白
    assert "已恢复 2 条" in rep.message
    assert "「规则命中」" in rep.message and "一并放回" in rep.message
    assert "不恢复" not in rep.message, "回执还在说「不恢复」（与实际行为相反 = 界面在说假话）"


def test_批量人工剔除必须勾选():
    rows = [{"id": 7}, {"id": 8}]
    with pytest.raises(MustReportError):
        apply_manual_exclude(rows, [])
    assert apply_manual_exclude(rows, [8]) == [8]


# ---------------------------------------------------------------- 注入 M2 的钩子


def test_is_excluded_可直接注入M2抓取预览():
    """M2 `fetch_task.preview(rows, is_excluded=...)` 的钩子形态（§4.2.2 由付款域提供）。"""
    rows = [
        _rec(biz_type="付设备租赁款"),                 # 留
        _rec(input_by="梁丽佳"),                        # 剔
    ]
    kept = [r for r in rows if not is_excluded(r)]
    assert len(kept) == 1 and kept[0]["biz_type"] == "付设备租赁款"


def test_current_rule_hint_does_not_claim_historical_provenance():
    from app.mod03_notice.classify import current_exclude_hint
    rules=(ExcludeRule('bill_name', ('水电','房租')), ExcludeRule('input_by', ('张三',)))
    hint=current_exclude_hint({'fields':{'BillName':'十月房租'},'input_by':'张三'},rules)
    assert '单据名称关键字（房租）' in hint and '水电' not in hint
    assert '当前匹配规则' in hint and '历史命中规则未保存' in hint
    assert '录入人（张三）' in current_exclude_hint({'input_by':'张三'},rules)
    assert '当前无匹配规则' in current_exclude_hint({'input_by':'李四'},rules)
    assert '无法追溯' in current_exclude_hint({},())
