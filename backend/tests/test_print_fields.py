"""打印件**字段值组装**的自检（离线 · 不连库 · **不绑定 `ACC-*` 判据点**）。

守两件事：
1. **显示口径**：金额 = 千分位 ＋ 2 位小数、**零值留空**（与 001-10 同一条口径）；
2. **覆盖度**：真机模板（79 格 / 31 字段格）里**每个非图片格都能拿到值** —— 用
   `uncovered_field_ids()` 自动兜住"模板加了格子、我们没填"的漂移。
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.mod03_notice.print.fields import (
    DS_DETAIL_ID,
    DS_HEADER,
    DS_PAYMENT_BILL,
    build_detail_rows,
    build_values,
    money,
    uncovered_field_ids,
)
from app.mod03_notice.print.template import DS_DETAIL, parse_design
from tests.acc_plugin import acc

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "i8_print_design_sample.json"
NOW = datetime(2026, 9, 15, 21, 40)


def _tpl():
    return parse_design(json.loads(FIXTURE.read_text(encoding="utf-8")))


INFO = {
    "BillNo": "FKTZS2026090065", "BillName": "龙源项目/尚坤/钢筋（102765元）",
    "PhidPc_EXName": "某某项目", "PhidPayOrg_EXName": "第四工程公司",
    "ApplyAmt": 102765.0, "ApproveAmt": 102765.0,
    "PhidFillPsn_EXName": "王潜森", "PhidApp_EXName": "李超",
    "PrintCount": 0, "Remark": "",
    "user_skdw_EXName": "资产处集中采购",
    "user_rmbje": 0, "user_dfgz": "", "user_qtkx": None,
}
DETAIL = [
    {"ResourceType": "采购入库", "ResourceBillCode": "RK001",
     "ApplyAmt": 60000.0, "ApplyAmtFc": 60000.0, "ConAmtFc": 50000.0,
     "RecName": "某某商贸", "RecAccName": "某某商贸", "RecAccNo": "102902", "Remark": "第一批"},
    {"ResourceType": "采购入库", "ResourceBillCode": "RK002",
     "ApplyAmt": 42765.0, "ApplyAmtFc": 42765.0, "ConAmtFc": 0,
     "RecName": "某某商贸", "RecAccName": "", "RecAccNo": "", "Remark": ""},
]


# ---------------------------------------------------------------- 金额格式


@acc()
def test_金额千分位两位小数():
    assert money(102765.0) == "102,765.00"
    assert money("1234.5") == "1,234.50"
    assert money(Decimal("0.01")) == "0.01"


@acc()
def test_金额零值留空():
    assert money(0) == "" and money("0.00") == "" and money(None) == "" and money("") == ""
    assert money(0.004) == ""                     # < 0.005 视为零


@acc()
def test_自定义金额字段blank_zero也留空():
    assert money(123.45, blank_zero=True) == ""    # 与素材包 blank_zero=True 的语义一致
    assert money("0", blank_zero=True) == ""


@acc()
def test_非数值金额原样显示不吞不猜():
    assert money("待定") == "待定"


# ---------------------------------------------------------------- 主表 values


@acc()
def test_主表字段名与真机模板对齐且能全部取到值():
    tpl = _tpl()
    values = build_values(INFO, DETAIL, now=NOW)
    # 模板里每个**非明细、非图片**的字段格都应有键（值可为空串，但键必须在）
    # ⚠️ 明细格的值走 `build_detail_rows()`（键是裸 fieldId），不在 `values` 里
    for c in tpl.field_cells():
        cd = c.get("cellData") or {}
        if cd.get("otherShowType") == "image" or cd.get("dataSetId") in DS_DETAIL:
            continue
        key = "%s.%s" % (cd["dataSetId"], cd["fieldId"])
        assert key in values, key


@acc()
def test_值组装的关键语义():
    v = build_values(INFO, DETAIL, now=NOW)
    h = DS_HEADER
    assert v[f"{h}.编码"] == "FKTZS2026090065"
    assert v[f"{h}.付款单位"] == "第四工程公司"
    assert v[f"{h}.print_count"] == "1"                     # 0 ⇒ 兜底 1
    assert v[f"{h}.收款单位"] == "某某商贸"                    # **明细优先**
    assert v[f"{h}.计划总额"] == "102,765.00"                # Σ 明细 ApplyAmt
    assert v[f"{h}.合同金额"] == "50,000.00"                 # Σ 明细 ConAmtFc（第 2 条为 0）
    assert v[f"{h}.sj"] == "2026-09-15 21:40"
    # 自定义金额：零值/空 ⇒ 留空
    assert v[f"{DS_PAYMENT_BILL}.user_rmbje"] == ""
    assert v[f"{DS_PAYMENT_BILL}.user_dfgz"] == ""


@acc()
def test_计划总额在无明细时退回单据头():
    v = build_values(INFO, [], now=NOW)
    assert v[f"{DS_HEADER}.计划总额"] == "102,765.00"
    assert v[f"{DS_HEADER}.收款单位"] == "资产处集中采购"        # 退回 info.user_skdw_EXName


#: ⭐⭐ **真机形态**（2026-09-21 全量取证 · `artifacts/_probe_acct_scan.json` ＋ 诊断
#: `docs/archive/troubleshooting/排查-收款账号印错-20260921.md`）：标准字段（`RecAccNo`/`PhidBank_EXName`）与
#: 自定义字段（`user_yhzh`/`user_bank_EXName`）**不是一回事** —— 74/353 张不一致，
#: 其中 **11 张两套都有值且不同**（i8 原生印自定义 = **本单实际收款账号**）。
#: ⛔ **别拿"单行标准形态"当 fixture** —— 那正是这个 bug 被掩盖多年的原因。
_TWO_ACCOUNT_SHAPES: tuple[dict, ...] = (
    # 形态①：标准字段**空**、自定义有值（= 用户报障的 `FKTZS2026050366`）
    {"ResourceType": "采购入库", "ResourceBillCode": "RK1", "ApplyAmt": 60000.0, "ApplyAmtFc": 60000.0,
     "ConAmtFc": 0, "RecName": "伊宁市健民气体工贸有限公司", "RecAccName": "伊宁市健民气体工贸有限公司",
     "RecAccNo": "", "PhidBank_EXName": "",
     "user_yhzh": "300602200902456652", "user_bank_EXName": "中国工商银行股份有限公司伊犁哈萨克自治州分行"},
    # 形态②：**两套都有值且不同**（= 11 张"印错值"那类；旧逻辑印出的是错的）
    {"ResourceType": "采购入库", "ResourceBillCode": "RK2", "ApplyAmt": 21160.0, "ApplyAmtFc": 21160.0,
     "ConAmtFc": 0, "RecName": "宁夏小巨人起重吊装有限公司", "RecAccName": "宁夏小巨人起重吊装有限公司",
     "RecAccNo": "8111101013902057084", "PhidBank_EXName": "中信银行王城支行",
     "user_yhzh": "41050168860800001011", "user_bank_EXName": "中国建设银行股份有限公司洛阳分行"},
)


@acc("ACC-PAY-PRINT-001", "001-13")
def test_收款账号银行取自定义字段_与i8原生打印同款():
    """`TAIL-60`（2026-09-21 用户报障「收款账号为空，和 i8 原生打印不符」）。

    ⭐ 判据 = **模板里那格的名字就叫 `user_yhzh`** ⇒ i8 原生打印读自定义字段；
    全量实测**反向 0 例**（标准有值而自定义为空）⇒ 自定义是超集、方向唯一确定。
    ⚠️ 这条能红的前提 = fixture 用**真机的两种形态**（① 标准空/自定义有 ② 两套不同值）。
    """
    h = DS_HEADER
    v1 = build_values(INFO, [_TWO_ACCOUNT_SHAPES[0]], now=NOW)
    assert v1[f"{h}.user_yhzh"] == "300602200902456652"          # 旧逻辑：空串（用户报障形态）
    assert v1[f"{h}.收款银行1"] == "中国工商银行股份有限公司伊犁哈萨克自治州分行"
    v2 = build_values(INFO, [_TWO_ACCOUNT_SHAPES[1]], now=NOW)
    assert v2[f"{h}.user_yhzh"] == "41050168860800001011"        # 旧逻辑：印成档案默认账号（错值）
    assert v2[f"{h}.收款银行1"] == "中国建设银行股份有限公司洛阳分行"


@acc()
def test_自定义字段缺失时退回标准字段_兜底():
    """⚠️ 反向 0 例 ⇒ 这条**没有真实数据能证伪**，只是保守行为；⛔ 不拿它当"与 i8 一致"的依据。"""
    d = {"RecAccNo": "8600003838000188", "PhidBank_EXName": "乌海银行股份有限公司乌达支行"}
    v = build_values(INFO, [d], now=NOW)
    h = DS_HEADER
    assert v[f"{h}.user_yhzh"] == "8600003838000188"
    assert v[f"{h}.收款银行1"] == "乌海银行股份有限公司乌达支行"


# ---------------------------------------------------------------- 明细行


@acc()
def test_明细行字段与外币金额算式():
    rows = build_detail_rows(DETAIL)
    assert len(rows) == 2
    assert rows[0]["单据类型"] == "采购入库" and rows[0]["单据号"] == "RK001"
    assert rows[0]["支付金额"] == "60,000.00"
    assert rows[0]["外币金额"] == ""                        # Fc − 本币 = 0 ⇒ 留空
    assert rows[0]["账户"] == "某某商贸"                      # RecAccName 优先
    assert build_detail_rows([{"ApplyAmt": 100, "ApplyAmtFc": 120}])[0]["外币金额"] == "20.00"


# ---------------------------------------------------------------- 覆盖度


@acc()
def test_真机模板的每个非图片格都被覆盖():
    """**防漂移的关键断言**：模板改了（加字段格）⇒ 这条会红，提醒补映射。"""
    assert uncovered_field_ids(_tpl()) == []


@acc()
def test_数据集常量与模板模块一致():
    from app.mod03_notice.print import template as tpl_mod

    assert DS_DETAIL_ID in DS_DETAIL
    assert tpl_mod.DS_HEADER == DS_HEADER
    assert tpl_mod.DS_DETAIL == DS_DETAIL
