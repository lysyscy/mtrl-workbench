"""`ACC-ODDVAL-001` · 不标准值处理（《说明书》§9.6）。

判据点归属：`MOD-13` 能力 11（此前无用例认领 —— 2026-09-17 补）。

§9.6 四行口径：**原样入库（不擅自清洗）** · 提供**批量修改**入口 · **只认关键字段** · **标准化由用户做**。

⚠️ 本件钉的是 **§9.6 这一层的全局原则**（系统**只报不改**、判断权交回用户）；
各域导入的**细判据**仍归各域用例（如 `ACC-FLOW-IMPORT-002` 钉「空 ≠ 兜底现汇」）—— **别交叉挂**。
⚠️ `001-04`（批量修改入口）对应的入口**尚未实现** ⇒ 走「未绑定」态，不造假断言。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod05_flow import importer
from tests.acc_plugin import acc

#: 确实**归不进** §4.4.2 四类的写法（⚠️ 别用「电汇」—— 它是「现汇」的别名，会被认出来）
_ODD_METHODS = ("银行本票", "现金", "微信支付", "ABC")


@acc("ACC-ODDVAL-001", "001-01")
def test_认不出的取值不猜不丢_原文可核():
    """§9.6 第 1 行「**不标准值原样入库**（不擅自清洗）」的可观测面：

    认不出的取值 ⇒ 值只记**兜底类**，**原文一字不改地留下**（可核），并进「未识别」清单 ——
    ⚠️ 与 `ACC-FLOW-IMPORT-002` 的分工：那条钉「**空** ≠ 兜底成现汇」，本条钉「**认不出的原文不丢**」。
    """
    plan = importer.parse_rows([["FKTZS2026090466", "1000.00", "2025-12-05", "银行本票", ""]])
    row = plan.rows[0]
    assert row.method_recognized is False
    assert row.pay_method == "其他"                       # 只给兜底类，不猜成四类里的某一个
    assert "银行本票" in row.remark                        # 原文可核（信息不丢）
    assert plan.unknown_methods == ["银行本票"]


@acc("ACC-ODDVAL-001", "001-02")
def test_不标准值不得静默_带源行号且不让整批失败():
    """§9.6 第 1 行 ＋ 「系统不代替判断」：坏值**必须报出来**（带源行号），**不得静默跳过 / 静默变 0**，
    且**不得连累整批**。"""
    plan = importer.parse_rows([
        ["FKTZS2026090466", "100", "2025-12-05", "现汇", ""],
        ["FKTZS2026090467", "不是数字", "2025-12-05", "现汇", ""],
        ["FKTZS2026090468", "200", "2025-12-05", "现汇", ""],
    ])
    assert [r.bill_no for r in plan.rows] == ["FKTZS2026090466", "FKTZS2026090468"]   # 好的两行照常进
    assert len(plan.anomalies) == 1
    assert plan.anomalies[0]["line"] == 3                 # **Excel 1 基行号**（可直接回表定位）
    assert "无法解析" in plan.anomalies[0]["reason"]


@acc("ACC-ODDVAL-001", "001-03")
def test_匹配只认关键字段_精确一对一不做模糊匹配():
    """§9.6 第 3 行「**只认关键字段**」：匹配唯一键 = 单据号，**精确 1:1**；
    命中 0 一律列入「未匹配」，**不得凭相似（少一位 / 多一字）自动选定**。"""
    plan = importer.parse_rows([
        ["FKTZS2026090466", "100", "2025-12-05", "现汇", ""],
        ["FKTZS202609046", "200", "2025-12-05", "现汇", ""],        # 少一位：**不是**同一张单
    ])
    out = importer.split_by_match(plan, {"FKTZS2026090466": 7})
    assert [r.bill_no for r in out.rows] == ["FKTZS2026090466"]
    assert out.rows[0].notice_id == 7
    assert [u["bill_no"] for u in out.unmatched] == ["FKTZS202609046"]


@acc("ACC-ODDVAL-001", "001-05")
def test_标准化由用户做_系统只归类不改写():
    """§9.6 第 4 行「**标准化由用户做**，系统不代替判断」的可观测面：

    归一函数对认不出的写法**一律只给兜底类**（不替用户挑一个四类）；
    ⚠️ 空值是**合法留白**、不是「不标准值」—— 两者都不许被系统擅自改成标准值。
    """
    for odd in _ODD_METHODS:
        assert importer.normalize_method(odd) == ("其他", False), f"「{odd}」不该被猜成四类"
    assert importer.normalize_method("") == ("", True)          # 空 = 合法留白（不兜底成「现汇」）
    assert importer.normalize_method("其他") == ("其他", True)   # 用户自己写「其他」⇒ 认（那是用户的判断）
    assert importer.normalize_method("现汇") == ("现汇", True)   # 标准值本来就认
    assert Decimal("1000.00") == importer.parse_amount("1,000.00")   # 金额只做**格式**归一，不做业务判断
