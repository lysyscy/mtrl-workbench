"""打印件的**字段值组装**（`API-07` 模板里的 `fieldId` → 值）—— 纯函数。

## 它解决什么

模板驱动渲染（`print/template.py`）只认 `values["<dataSetId>.<fieldId>"]`；
**哪个格子该填什么**由本模块回答。字段名（`fieldId`）以**真机模板**为准
（`tests/fixtures/i8_print_design_sample.json` 里的 31 个字段格），取值来源 = i8 的三个接口：

| 来源 | 用途 |
|---|---|
| `getList`（`PaymentNotice.fields`） | 列表级字段（单据号 / 项目 / 审批金额 …） |
| `getInfo`（**主表**） | 付款单位 / 录入人 / 审核人 / 备注 … |
| `getDetInfo`（**明细**） | 收款银行 / 收款账号 / 账户 / 合同金额（Σ`ConAmtFc`）|
| `getFlowHisForPrint`（**流程**） | 签名图（另行绑定，见 `print/signatures.py`） |

## 显示口径

- **金额 = 千分位 ＋ 2 位小数**（`{:,.2f}`），**零值留空**（i8 规则「0 不印」）——
  与 `ACC-PAY-PRINT-001/001-10` 的「零值金额格留空」是**同一条口径**。
- ⚠️ 口径主人：《说明书》§4.2.5（四金额）· §4.2.3（分类）。
  本模块的**字段名**取自素材包旁证，**业务取值一律回《说明书》**，不得反推。
- ⚠️ **未覆盖的 `fieldId` 不静默丢弃**：`uncovered_field_ids()` 会把"模板要、我们不给"的格子列出来，
  供页面/日志报警（避免"少填一个字段却看不出来"）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.core.money import to_money

# 模板里的数据集 id（**与 `print/template.py` 必须一致** —— 有自检钉住）
DS_HEADER = "3700000000000010"        # 主表
DS_DETAIL_ID = "3700000000000212"     # 明细（模板里明细格用的就是它）
DS_PAYMENT_BILL = "PaymentBill"       # 单据级自定义字段（user_rmbje 等）

# ---------------------------------------------------------------- 显示格式


def money(value, *, blank_zero: bool = False) -> str:
    """金额显示：**千分位 ＋ 2 位小数**；**零值留空**（`blank_zero=True` 时非零也按该规则处理）。

    ⚠️ 与素材包 `i8_http.money` 的口径一致（`"{:,.2f}"`、`abs(v) < 0.005 ⇒ ""`）；
    素材包该函数在 `blank_zero=True` 分支**反编译漏了 return**，本实现按 docstring 语义补齐。
    """
    if value in (None, "", "None"):
        text = ""
    else:
        text = str(value)
    try:
        amount = to_money(text)
    except (InvalidOperation, ValueError, TypeError):
        return text                        # 非数值 ⇒ 原样显示（不吞、不猜）
    if blank_zero or abs(Decimal(amount)) < Decimal("0.005"):
        return ""
    return f"{Decimal(amount):,.2f}"


def _num(value) -> Decimal:
    """金额求和用（**先 str() 再归一** —— 避免 float 直接进 `to_money` 的往返告警）。"""
    if value in (None, ""):
        return Decimal("0")
    try:
        return to_money(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


# ---------------------------------------------------------------- 主表 values


def build_values(info: dict, detail: list[dict] | None = None, *, now: datetime | None = None) -> dict:
    """主表 + 单据级字段 → `values`（键 = `"<dataSetId>.<fieldId>"`）。

    字段名对齐**真机模板**（31 个字段格里的主表那批）；值来源见模块头。
    """
    info = dict(info or {})
    detail = list(detail or ())
    first = detail[0] if detail else {}
    plan_total = sum((_num(r.get("ApplyAmt")) for r in detail), Decimal("0")) or _num(info.get("ApplyAmt"))
    contract_total = sum((_num(r.get("ConAmtFc")) for r in detail), Decimal("0"))
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    h = DS_HEADER
    return {
        # ⚠️ 「业务组织」在**付款通知书模板**里有格（其他支出模板没有）—— 素材包 `build_values` 亦有此键
        f"{h}.业务组织": str(info.get("PhidBusOrg_EXName") or ""),
        f"{h}.付款单位": str(info.get("PhidPayOrg_EXName") or ""),
        f"{h}.print_count": str(info.get("PrintCount") or 1),
        f"{h}.编码": str(info.get("BillNo") or ""),
        f"{h}.名称": str(info.get("BillName") or ""),
        f"{h}.项目名称": str(info.get("PhidPc_EXName") or ""),
        # 收款单位：**优先取明细第一条**（明细更精确），退回单据头
        f"{h}.收款单位": str(first.get("RecName") or info.get("user_skdw_EXName") or ""),
        # ⭐⭐ 2026-09-21（`TAIL-60` · 用户报障 `FKTZS2026050366` 账号印空）：**收款账号/银行取
        #    「自定义字段」优先** —— i8 原生打印读的就是 `user_yhzh` / `user_bank_EXName`
        #    （**模板里那格的名字就叫 `user_yhzh`**）。标准字段（`RecAccNo`/`PhidBank_EXName`）
        #    多数单恰好同值，**不一致的那批会印空/印错值**：
        #    全量 355 张实测（`artifacts/_probe_acct_scan.json`）：**11 张错值 ＋ 63 张空白（74/353 = 21%）**，
        #    ⭐ **反向 0 例**（标准有值而自定义为空）⇒ 自定义字段是超集，方向唯一确定。
        #    ⚠️ 标准字段保留为**兜底**（保守起见；因反向 0 例、无数据能证伪它 ⇒ **不作断言**）。
        #    诊断全文：`docs/archive/troubleshooting/排查-收款账号印错-20260921.md`。
        f"{h}.收款银行1": str(first.get("user_bank_EXName") or first.get("PhidBank_EXName") or ""),
        f"{h}.user_yhzh": str(first.get("user_yhzh") or first.get("RecAccNo") or ""),
        f"{h}.计划总额": money(plan_total),
        f"{h}.本次支付总额": money(info.get("ApplyAmt")),
        f"{h}.本次结算金额": money(info.get("ApproveAmt")),
        f"{h}.本次支付金额": money(info.get("ApplyAmt")),
        f"{h}.合同金额": money(contract_total),
        f"{h}.录入人": str(info.get("PhidFillPsn_EXName") or ""),
        f"{h}.审核人": str(info.get("PhidApp_EXName") or ""),
        f"{h}.备注": str(info.get("Remark") or ""),
        f"{h}.sj": stamp,
        # 单据级自定义金额：**零值不印**（素材包 blank_zero=True 的同一条规则）
        f"{DS_PAYMENT_BILL}.user_rmbje": money(info.get("user_rmbje"), blank_zero=True),
        f"{DS_PAYMENT_BILL}.user_dfgz": money(info.get("user_dfgz"), blank_zero=True),
        f"{DS_PAYMENT_BILL}.user_qtkx": money(info.get("user_qtkx"), blank_zero=True),
    }


def build_detail_rows(detail: list[dict] | None = None) -> list[dict]:
    """明细 → **模板里明细行的各格值**（键 = `fieldId`，不含数据集前缀）。"""
    rows: list[dict] = []
    for r in detail or ():
        rows.append({
            "单据类型": str(r.get("ResourceType") or ""),
            "单据号": str(r.get("ResourceBillCode") or ""),
            "支付金额": money(r.get("ApplyAmt")),
            # 外币金额 = 外币支付 − 本币支付（素材包 build_detail_rows 同式）
            "外币金额": money(_num(r.get("ApplyAmtFc")) - _num(r.get("ApplyAmt"))),
            "账户": str(r.get("RecAccName") or r.get("RecName") or ""),
            "备注": str(r.get("Remark") or ""),
        })
    return rows


# ---------------------------------------------------------------- 覆盖度自检


MAPPED_HEADER_FIELDS: tuple[str, ...] = (
    "业务组织", "付款单位", "print_count", "编码", "名称", "项目名称", "收款单位", "收款银行1", "user_yhzh",
    "计划总额", "本次支付总额", "本次结算金额", "本次支付金额", "合同金额",
    "录入人", "审核人", "备注", "sj",
    "user_rmbje", "user_dfgz", "user_qtkx",
)
MAPPED_DETAIL_FIELDS: tuple[str, ...] = ("单据类型", "单据号", "支付金额", "外币金额", "账户", "备注")


def uncovered_field_ids(tpl, *, detail_ids: frozenset | None = None) -> list[str]:
    """**模板里要、但我们不给值**的字段格（`"<dataSetId>.<fieldId>"`）—— 用于报警。

    只统计**非图片格**（图片是签名图，走 `print/signatures.py` 那条路）。
    """
    from app.mod03_notice.print.template import DS_DETAIL, is_image_cell

    detail_ids = detail_ids or DS_DETAIL
    out: list[str] = []
    for c in tpl.field_cells():
        if is_image_cell(c):
            continue
        cd = c.get("cellData") or {}
        ds = str(cd.get("dataSetId") or "")
        fid = str(cd.get("fieldId") or "")
        if ds in detail_ids:
            if fid not in MAPPED_DETAIL_FIELDS:
                out.append(f"{ds}.{fid}")
        elif ds == DS_HEADER:
            if fid not in MAPPED_HEADER_FIELDS:
                out.append(f"{ds}.{fid}")
        elif ds == DS_PAYMENT_BILL:
            if fid not in MAPPED_HEADER_FIELDS:
                out.append(f"{ds}.{fid}")
        else:
            out.append(f"{ds}.{fid}")
    return sorted(set(out))


__all__ = [
    "DS_HEADER", "DS_DETAIL_ID", "DS_PAYMENT_BILL",
    "money", "build_values", "build_detail_rows",
    "MAPPED_HEADER_FIELDS", "MAPPED_DETAIL_FIELDS", "uncovered_field_ids",
]
