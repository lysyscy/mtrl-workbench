"""`ACC-ODDVAL-001` · 不标准值处理（《说明书》§9.6）。

判据点归属：`MOD-13` 能力 11（此前无用例认领 —— 2026-09-17 补）。

§9.6 四行口径：**原样入库（不擅自清洗）** · 提供**批量修改**入口 · **只认关键字段** · **标准化由用户做**。

⚠️ 本件钉的是 **§9.6 这一层的全局原则**（系统**只报不改**、判断权交回用户）；
各域导入的**细判据**仍归各域用例（如 `ACC-FLOW-IMPORT-002` 钉「空 ≠ 兜底现汇」）—— **别交叉挂**。
✅ `001-04`（批量修改入口）—— **2026-09-20 已钉**（原先写"尚未实现"是 09-17 的当时的判断，
   现已过期）：入口 = `MOD-03` 的「**批量改分类**」（勾选多行 ⇒ 点一次「→ 辅材 / → 机械 / → 集采」
   即整批改到同一个值）。⚠️ 这就是 §9.6 那句「提供**批量修改**入口」的落点 ——
   「不擅自清洗」要配一个**由人发起**的批量修正口，否则用户只能一行一行改。
"""

from __future__ import annotations

import pathlib
import re

from decimal import Decimal

import app
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


@acc("ACC-ODDVAL-001", "001-04")
def test_提供批量修改入口_勾选多行统一改同一字段():
    """§9.6 第 2 行「**提供批量修改入口**」—— ⚠️ claim 括注写明了形态：
    **（勾选多行 ⇒ 统一改同一字段）**。

    ⚠️ 为什么这一条不能只看"有没有一个改分类的入口"：
       单行改分类（在下拉里点一下）**早就有了**，但它**不解决**"不标准值"这个场景 ——
       不标准值往往是**成批**的（一次导进来几十行都认不出），一行一行改就是几十次点击。
       ⇒ 判据必须钉住**"勾选多行 ⇒ 一次改一整批"**这个形态：
         ① 入口按**分类值**逐个给按钮（`enumVals('cat').map`）—— 点一次就说清"改成哪个值"；
         ② 按钮**跟勾选集走**（`pickSet`）—— ⛔ 不是只作用于某一行；
         ③ 未勾选**先禁用**（`disabled`）—— 与全站同款（⛔ 不是点了才拦）。
    """
    web = pathlib.Path(app.__file__).resolve().parent / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    acts = (web / "shell" / "actions.js").read_text(encoding="utf-8")

    tags = re.findall(r"<button[^>]*data-act=\"batchCatApply\"[^>]*>", html)
    assert tags, "找不到「批量改分类」入口（`data-act=\"batchCatApply\"`）—— 落点变了"
    for tag in tags:
        assert "data-c=" in tag, (
            "批量改分类的按钮没有声明「改成哪个值」（`data-c`）⇒ 那就说不清「统一改成同一个字段」：\n"
            f"  {tag[:140]}")
        assert "disabled" in tag and "pk.length" in tag, (
            "批量按钮没跟**勾选数**走（未勾选先禁用）—— 用户会先点一下被拒才知道要先勾选：\n"
            f"  {tag[:140]}")

    body = acts[acts.index("batchCatApply:"):]
    body = body[:body.index("/* 单行改分类")]
    assert "pickSet" in body, (
        "`batchCatApply` 没有作用于**勾选集**（`pickSet`）—— 那就不是「勾选多行统一改」，"
        "而是单行改（claim 的形态是**批量**）")
    assert "setCategory" in body, "批量改分类没有走后端同一出口（`setCategory`）"

    # ⭐ 反向：单行改分类**仍然要在**（批量不是拿单行换来的）—— 两者是互补，不是替代
    assert "单行改分类" in acts, "单行改分类的入口不见了 —— 批量与单行应当**并存**（互补）"
    assert importer.normalize_method("现汇") == ("现汇", True)   # 标准值本来就认
    assert Decimal("1000.00") == importer.parse_amount("1,000.00")   # 金额只做**格式**归一，不做业务判断
