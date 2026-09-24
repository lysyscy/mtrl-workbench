"""`m11` 集采台账导入 · **B4**（`TAIL-75`）—— 引擎接入的**建议 / 交叉校验 / 记忆**三件。

⭐ 纪律（三条，写在这里免得日后被"顺手"破坏）：
1. **判定权不搬走**：自动映射的唯一权威仍是 `excel_parse.ALIASES` ＋ 人在预览页手点的 `mapping`
   ⇒ 引擎建议**再高分也不许自动变成 `fields`**（本文件第 1 条就钉这个）；
2. **建议一律标「需你确认」**、**记忆一律标「来自记忆 · 可改」**；
3. **记忆不许跨域套用**（`profile_store` 里有域校验，本文件第 4 条从 `m11` 这侧再钉一次）。

⚠️ 与本目录 `test_acc_jc_import.py` 分工：那份守**判定与落库**（合并区/表头探测/合计行/锚点匹配），
本份守**B4 加的三件**。
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from openpyxl import Workbook

from app.mod11_jc import excel_parse as P
from app.mod11_jc.import_service import DOMAIN, commit, preview
from tests.acc_plugin import acc

#: r2 = 一级表头（`供应商` 那格合并到发票金额）· r3 = 二级表头（只有 `合同总价`/`发票金额`）
#: ⚠️ 末三列（`供货商名称` / `单据日期` / `录入日期`）都是**别名表认不出**的 ⇒ 考"引擎建议"那条路：
#:   前一个能干净地建议到 `supplier`；后两个都会被建议成 `contract_date` ⇒ **撞车 ⇒ 不预选**。
R2 = ["序号", "合同日期", "材料名称", "供应商", "", "供货商名称", "付款方式", "结算",
      "单据日期", "录入日期"]
R3 = ["", "", "", "合同总价", "发票金额", "", "", "", "", ""]
MERGES = [("A1", "J1"), ("D2", "E2")]


def _book(r2=None, r3=None, rows=None) -> bytes:
    """造一份**像真台账**的最小表（标题行 ＋ 两级表头 ＋ 数据）。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "台账"
    ws.append(["晋江污泥处理项目集采台账"])                    # r1 大标题
    ws.append(list(r2 if r2 is not None else R2))
    ws.append(list(r3 if r3 is not None else R3))
    for row in (rows if rows is not None else _rows()):
        ws.append(list(row))
    for a, b in MERGES:
        ws.merge_cells(f"{a}:{b}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rows(pay=("电汇", "承兑")):
    """两条数据行：金额/日期/材料名齐（够 `looks_like_data_row` 认）。⚠️ 付款方式那列由参数给。"""
    return [
        (1, "20240723", "钢材", "42799.80", "40731.17", "亿管通", pay[0], "40731.17", "", ""),
        (2, "20260313", "油漆", "309999.00", "54556.61", "洛阳桐玺", pay[1], "54556.61", "", ""),
    ]


def _sheet(data: bytes) -> dict:
    res = preview(data, "自检台账.xlsx")
    assert res["ok"], res
    return next(s for s in res["sheets"] if s.get("name") == "台账")


@acc("ACC-JC-IMPORT-001", "001-01")
def test_未认出的列给引擎建议_但一律需你确认_且不改判定():
    """⭐ `供货商名称` 不在别名表里（别名表只有「供货商」）⇒ 引擎建议 `supplier`，**但 `fields` 里没有它**。

    ⛔ 这是 B4 的关键边界：建议是"预选给人点"，**不是**判定 —— 判定一变，历史导入口径就跟着变。
    """
    sh = _sheet(_book())
    sug = {x["label"]: x for x in sh["suggest"]}
    assert "供货商名称" in sug, sh["suggest"]
    assert sug["供货商名称"]["field"] == "supplier" and sug["供货商名称"]["conf"] >= 0.9
    assert sug["供货商名称"]["level"] == "需你确认", "建议的档位只能是「需你确认」"
    assert sug["供货商名称"]["preselect"] is True
    assert "supplier" not in sh["mapping"]["fields"], "⛔ 建议不许自动变成判定"
    assert {"col", "label"} <= set(sh["mapping"]["unknown"][0]), "建议来自「未认出」那一档，两者要并存"
    assert [u["label"] for u in sh["mapping"]["unknown"]] == ["供货商名称", "单据日期", "录入日期"]
    # ⚠️ `单据日期` / `录入日期` 都会被"包含词"建议成 `合同日期`（0.90）——⭐ 但**同一字段被多列建议**
    #    ⇒ 全都**不预选**（真文件实测：非台账的 sheet 上「单据日期/录入日期/核准日期」三列都被建议成
    #    `合同日期`、「编号」被建议成 `存档序号` —— 那是包含词在短标签上过度命中）
    for lb in ("单据日期", "录入日期"):
        assert sug[lb]["field"] == "contract_date", sug[lb]
        assert sug[lb]["dup"] is True and sug[lb]["preselect"] is False, sug[lb]


@acc("ACC-JC-IMPORT-001", "001-02")
def test_值画像交叉校验_名字认对但值不像就提示_且不改判定():
    """⭐ 防"**名字认对、列拿错**"：`付款方式` 那列里全装着日期 ⇒ 报 `suspect`（⛔ 系统不替你改列）。"""
    sh = _sheet(_book(rows=_rows(pay=("20260701", "20260702"))))
    suspect = sh["mapping"]["suspect"]
    assert [x["field"] for x in suspect] == ["method"], suspect
    assert suspect[0]["prof"] == "日期" and "不符" in suspect[0]["why"]
    assert sh["mapping"]["fields"].get("method") is not None, "⛔ 只提示，不许改判定"
    # 正常值（电汇/承兑）⇒ 不瞎报
    assert _sheet(_book())["mapping"]["suspect"] == []


@acc("ACC-JC-IMPORT-001", "001-03")
def test_确认过的映射按表头指纹记住_下次预填并标明来源(tmp_path):
    """⭐ `commit` 落库后存记忆（表头指纹 → 映射）⇒ 下次 `preview` **预填**并标「来自记忆」。

    ⚠️ 记忆按**源列原文**存 ⇒ 取回时按原文对回列下标；⛔ 只是预选，人还能改。
    """
    from app.core.db import session_scope
    from app.import_kit.profile_store import ProfileStore
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc.models import JcContract

    store = ProfileStore(tmp_path / "profiles.json")
    data = _book()
    before = preview(data, "自检台账.xlsx", store=store)
    first = next(s for s in before["sheets"] if s.get("name") == "台账")
    assert first["memory"] is None, "第一次导入不该有记忆"

    amts = [str(r["contract_amt"]) for r in first["sample"]]
    # ⚠️ 仓库名**每次跑都换**（测试库是持久库：写死重名会在第二次跑时撞 `uq_project_warehouse_name` 约束）
    key = "__自检仓_B4_" + uuid.uuid4().hex[:8] + "__"
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_B4记忆__",
                                   warehouse_name=key, phid="")
        s.flush()
        for i, amt in enumerate(amts):
            s.add(JcContract(contract_no=f"__自检_B4_{i}__", project_id=int(p.id),
                             contract_date="2026-01-01", material_name="i8给的材料名",
                             supplier="i8给的供应商", contract_amt=Decimal(amt)))
        s.flush()
        out = commit(s, data, "自检台账.xlsx", sheet="台账", project_key=key, store=store)
    assert out["ok"] and out["updated"] == 2, out

    after = preview(data, "自检台账.xlsx", store=store)["sheets"]
    second = next(s for s in after if s.get("name") == "台账")
    mem = second["memory"]
    assert mem and "来自记忆" in mem["note"], second.get("memory")
    assert set(mem["mapping"].values()) >= {"contract_date", "material_name", "contract_amt"}
    assert store.count(DOMAIN) == 1


@acc("ACC-JC-IMPORT-001", "001-04")
def test_记忆不许跨域套用(tmp_path):
    """⚠️ 别的域（如 `m04`）记下的映射，`m11` 这里**不许**拿来预填 —— 表头长得像不代表语义一样。"""
    from app.import_kit.profile_store import ProfileStore

    store = ProfileStore(tmp_path / "profiles.json")
    store.save("m04_plan", ["序号", "合同日期", "材料名称"], {"合同日期": "付款时间"})
    res = preview(_book(), "自检台账.xlsx", store=store)
    sh = next(s for s in res["sheets"] if s.get("name") == "台账")
    assert sh["memory"] is None, "跨域的记忆不许套用"
    assert P.FIELD_LABELS["contract_date"] == "合同日期"        # 顺带钉住 label 真源
