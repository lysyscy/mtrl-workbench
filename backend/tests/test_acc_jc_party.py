"""`M5-6b` · 甲方单位分类 ＋ **金额落位分叉**（用户 2026-09-20 口径）。

钉住三件事（**每一件写错都会静默出错**）：
1. **材料名"空才填"** —— 重抓不许覆盖用户手改过的材料名（i8 的 `ItemName` 确有错的）；
2. **金额按甲方类型落位** —— 正常甲方 ⇒ i8 的价落 `contract_amt`；
   **贸易公司甲方** ⇒ i8 的价落 `trade_contract_amt`，而 `contract_amt`（人工补的真供应商价）
   **绝不被抓取碰**；
3. **没见过的甲方自动落 `unknown`**（⛔ 不静默当成"正常"）。

⚠️ 非破坏：全部在 `session_scope` 里造数、结束 `rollback`（⛔ 不留痕）。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.acc_plugin import acc

from app.core.db import session_scope
from app.mod01_projects.models import Project
from app.mod11_jc import repository as R
from app.mod11_jc.models import (
    KIND_PARTY_NORMAL,
    KIND_PARTY_TRADE,
    KIND_PARTY_UNKNOWN,
    JcContract,
)


def _proj(s) -> Project:
    p = Project(name_full="__自检_甲方分类项目__", warehouse_name="__自检_甲分仓__", ord=9999)
    s.add(p)
    s.flush()
    return p


def _row(no: str, *, party: str, amt: str = "100.00", mat: str = "钢材") -> dict:
    return {"contract_no": no, "sign_date": "2026-09-20", "material_name": mat,
            "supplier_name": "真供应商有限公司", "contract_amt": amt,
            "bill_name": "自检单据名", "party_name": party, "remark": ""}


@acc()
def test_正常甲方_i8的价落contract_amt():
    """正常甲方（第四工程公司）⇒ i8 那个价就是**供应商价** ⇒ 落 `contract_amt`。"""
    with session_scope() as s:
        p = _proj(s)
        R.set_party_kind(s, "自检正常甲方", KIND_PARTY_NORMAL)
        kmap = R.party_kind_map(s)
        row = _row("__自检_N_001__", party="自检正常甲方", amt="888.00")
        row["party_kind"] = kmap["自检正常甲方"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[row])
        cur = R.one_by_no(s, "__自检_N_001__")
        assert Decimal(str(cur.contract_amt)) == Decimal("888.00"), "正常甲方 ⇒ 落 contract_amt"
        assert cur.trade_contract_amt is None, "正常合同不该有贸易公司金额"
        assert not str(cur.trade_co or "").strip(), "正常合同不该有贸易公司名"
        assert cur.party_name == "自检正常甲方", "甲方单位要落库（判据列）"
        s.rollback()


@acc()
def test_贸易公司甲方_i8的价落trade_contract_amt且不碰contract_amt():
    """⭐⭐ **本片的核心**：贸易公司甲方 ⇒ i8 的价是**贸易公司的价** ⇒ 落 `trade_contract_amt`；
    而 `contract_amt`（**锚点** · 真供应商价）要留给人从 Excel 供应商线补 ⇒ **抓取绝不碰它**。

    ⚠️ 这条写错 = 金额落错列 **且不报错**（两个数看着都合理）—— 所以必须钉死。
    """
    with session_scope() as s:
        p = _proj(s)
        R.set_party_kind(s, "自检维萨贸易", KIND_PARTY_TRADE)
        kmap = R.party_kind_map(s)
        # 第一次抓取：i8 给的价 = 维萨价 ⇒ 落 trade_contract_amt，contract_amt 留 0（等人补）
        r1 = _row("__自检_T_001__", party="自检维萨贸易", amt="171983.28")
        r1["party_kind"] = kmap["自检维萨贸易"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[r1])
        cur = R.one_by_no(s, "__自检_T_001__")
        assert Decimal(str(cur.trade_contract_amt)) == Decimal("171983.28"), "维萨价落贸易公司列"
        assert Decimal(str(cur.contract_amt)) == Decimal("0"), "供应商价留空等人补（i8 里没有这个数）"
        assert cur.trade_co == "自检维萨贸易", "贸易公司名 = 甲方单位名"

        # ② 人从 Excel 供应商线补上真供应商价
        #    ⭐ 2026-09-26（方案② 用户裁定）：走**导入的专用出口**（`空才填`），
        #    ⛔ 不再走 `update_contract` —— 「合同金额」已按裁定移出人手改白名单
        #    （界面上没有那一格；它的写入口只有"抓取分叉"与"导入空才填"两条）。
        assert R.fill_contract_amt_if_blank(s, int(cur.id), "150000.00") is True
        # ③ **再抓一次**（i8 仍回维萨价）——⛔ 人工填的值必须**留住**，且 trade 列也不被刷
        r2 = _row("__自检_T_001__", party="自检维萨贸易", amt="171983.28")
        r2["party_kind"] = kmap["自检维萨贸易"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[r2])
        cur = R.one_by_no(s, "__自检_T_001__")
        assert Decimal(str(cur.contract_amt)) == Decimal("150000.00"), (
            "⛔ 重抓**不许**碰人工补的供应商价 —— 被覆盖就是抹掉人工劳动（而且下次抓取才发现）")
        assert Decimal(str(cur.trade_contract_amt)) == Decimal("171983.28"), "贸易公司价已写过 ⇒ 不动"
        s.rollback()


@acc()
def test_材料名空才填_人工改过的不被覆盖():
    """⭐ 用户口径原话：「**后续再抓，这些材料名已经不为空，就不要被覆盖了**」。

    i8 的 `ItemName` 实测确有错的（`g'c` / `hong's模板`）⇒ 用户会逐一手改
      ⇒ 重抓把它覆盖掉 = 白改。
    """
    with session_scope() as s:
        p = _proj(s)
        R.set_party_kind(s, "自检正常甲方", KIND_PARTY_NORMAL)
        kmap = R.party_kind_map(s)
        r1 = _row("__自检_M_001__", party="自检正常甲方", mat="钢材")
        r1["party_kind"] = kmap["自检正常甲方"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[r1])
        cur = R.one_by_no(s, "__自检_M_001__")
        assert cur.material_name == "钢材", "首次抓取：i8 的材料名要落上"

        # 人改正（i8 给错了）
        R.update_contract(s, int(cur.id), material_name="不锈钢管道")
        # 再抓（i8 还是那个错值）
        r2 = _row("__自检_M_001__", party="自检正常甲方", mat="钢材")
        r2["party_kind"] = kmap["自检正常甲方"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[r2])
        cur = R.one_by_no(s, "__自检_M_001__")
        assert cur.material_name == "不锈钢管道", "⛔ 人工改过的材料名不许被 i8 覆盖"

        # 但**空着**时必须填（不然新抓的行永远没材料名）
        R.update_contract(s, int(cur.id), material_name="")
        r3 = _row("__自检_M_001__", party="自检正常甲方", mat="钢材")
        r3["party_kind"] = kmap["自检正常甲方"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[r3])
        cur = R.one_by_no(s, "__自检_M_001__")
        assert cur.material_name == "钢材", "空着 ⇒ 要补上（否则永远空）"
        s.rollback()


@acc()
def test_没见过的甲方自动落unknown_不静默当成正常():
    """⭐ 用户口径：「**你得给个地方让我填谁是正常的**」—— 那"没填过的"就必须**露头**。

    ⚠️ 若静默当成"正常"：贸易公司的价会被落进 `contract_amt`（= 锚点列）
      ⇒ 用户拿 Excel 匹配时**对不上**，而且**看不出为什么**。
    """
    with session_scope() as s:
        added = R.ensure_party_kinds(s, ["自检未知甲方", "自检未知甲方", "", "  "])
        assert added == ["自检未知甲方"], "去重 + 空串不算（重复调用不重复登记）"
        assert R.ensure_party_kinds(s, ["自检未知甲方"]) == [], "已登记过 ⇒ 不再报"
        kmap = R.party_kind_map(s)
        assert kmap["自检未知甲方"] == KIND_PARTY_UNKNOWN, "新甲方必须落「未指定」"

        # 未指定时**按正常落**（这个选择可逆 —— 金额在正常合同的落点，指定后一眼能看见）
        p = _proj(s)
        row = _row("__自检_U_001__", party="自检未知甲方", amt="500.00")
        row["party_kind"] = kmap["自检未知甲方"]
        R.upsert_fetched_contracts(s, project_id=int(p.id), rows=[row])
        cur = R.one_by_no(s, "__自检_U_001__")
        assert Decimal(str(cur.contract_amt)) == Decimal("500.00"), "unknown 按正常落（可逆）"
        assert cur.trade_contract_amt is None, "⛔ 不许按贸易公司落（那会埋进 trade 列、更难还原）"
        s.rollback()


@acc()
def test_分类表拒绝非法类型():
    """⛔ 类型非法一律拒（判定在后端，前端不自行判）—— 否则会写进一个谁都不认识的类型。"""
    with session_scope() as s:
        bad = SV_act_set(s, name="自检正常甲方", kind="normal_typo")
        assert bad["ok"] is False and "未知" in bad["message"]
        empty = SV_act_set(s, name="   ", kind=KIND_PARTY_NORMAL)
        assert empty["ok"] is False and "不能为空" in empty["message"]
        ok = SV_act_set(s, name="自检新甲方2", kind=KIND_PARTY_TRADE)
        assert ok["ok"] is True and ok["party_kind"] == KIND_PARTY_TRADE
        s.rollback()


def SV_act_set(s, *, name, kind):
    from app.mod11_jc.service import act_set_party_kind
    return act_set_party_kind(s, name=name, kind=kind)


pytestmark = pytest.mark.usefixtures()
