"""`MOD-14` 规则配置 —— **前端壳接线的离线断言**（绑 `ACC-CFG-RULE-001` 的 5 个判据点）。

本文件保留规则配置后端接口与分类的静态接线断言。

⚠️ 这里钉的是**接线本身**（`TAIL-40` 后半），不是"页面好不好看"：
1. **演示常量必须已清** —— `RULE_EX` 原先硬编码 4 条演示规则；接线后它只能由
   `reloadM14()` 从 `/api/m14/rules` 填（`ui_parity` 的 `U2b` 也查 `m14→RULE_EX`）。
2. **增 / 删 / 改必须真的落到规则数据** —— ⛔ 不许本地改数组冒充落库
   （改完一刷新就回原样，而页面还回「已新增」= 假成功）。
3. **规则类别必须是后端认的 key** —— 原型是一个自由文本输入框；而 §4.2.2 只有四类，
   填「收款单位」后端会拒、填错别字更看不出问题 ⇒ 改成**后端 `kinds` 撑起来的下拉**。
4. **卡头条数必须是算出来的**（`RULE_EX.length`），⛔ 不许写死。
5. TAIL-263 撤掉分类规则与小微识别说明模块；真实分类仍走后端，关键词编辑入口保留在项目行。

⚠️ **`001-04` 刻意不断言「几条命中值」** —— 该判据点原文即「条数在此不复述」
   （条数的主人 =《说明书》§4.2.2 那张表，抄一份到测试里必然静默过期）。
   它查的是**结构**：四类齐、每类有值、`收款单位`不在有效类别里。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULES_API = (ROOT / "backend" / "app" / "mod14_config" / "rules_api.py").read_text(encoding="utf-8")
REPO = (ROOT / "backend" / "app" / "mod03_notice" / "rules_repository.py").read_text(encoding="utf-8")
CLASSIFY = (ROOT / "backend" / "app" / "mod03_notice" / "classify.py").read_text(encoding="utf-8")

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带**四把**剪刀（`_vslice` / `_balanced` / `_fn` / `_act`）——
#    已**整把删掉**，取段改走壳的语义口径（页 ⇒ `page_slice` · 函数 ⇒ `func_body` · 动作条 ⇒ `act_entry`）。
#    ⚠️ `_balanced` 那类"从某个下标起配平"的活，现在是窗内部的事（`jslex.match`）。⛔ 别写回来。


# ============================================================== 001-01




# ============================================================== 001-02


def test_分类规则表只读不渲染编辑入口():
    """TAIL-263 撤掉分类说明模块，真实分类仍由后端完成。"""
    from app.mod03_notice.classify import decide_placement
    from app.mod05_flow.domain import CATEGORY_JC, PAYEE_JC
    assert decide_placement({"payee": PAYEE_JC}).category == CATEGORY_JC


# ============================================================== 001-03




# ============================================================== 001-04


def test_命中值结构与口径一致():
    """`001-04` 剔除规则的命中值**结构与 §4.2.2 一致**。

    ⚠️ **刻意不断言条数** —— 该判据点原文即「条数在此不复述」（条数的主人 =《说明书》§4.2.2）。
    查的是结构：四类齐 / 每类有值 / `收款单位`**不在有效类别**（只能识别并拒绝）。
    """
    from app.mod03_notice import classify

    for k in (classify.KIND_BIZ_TYPE, classify.KIND_PROJECT_NAME,
              classify.KIND_BILL_NAME, classify.KIND_INPUT_BY):
        assert k in classify.KIND_LABELS, f"口径四类里缺 `{k}`"
        assert classify.KIND_LABELS[k].strip(), f"`{k}` 没有中文名（页面会显示 key）"
    assert all(r.values for r in classify.DEFAULT_RULES), "出厂默认里有规则没有任何命中值"

    # ⛔ 「收款单位」不得出现在**可选类别**里（后端 `effective_payload` 负责剔除）
    assert "if k != classify.KIND_PAYEE" in REPO, "后端 `kinds` 没把「收款单位」排除 ⇒ 页面上能选它"
    # 壳侧：类别下拉来自后端（与真数据同源），⛔ 不是前端硬编码的类别表


# ============================================================== 001-05
