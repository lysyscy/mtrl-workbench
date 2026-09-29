"""`m04` 付款计划导入 · **真文件形态**的行为判据（`TAIL-75` B2 · 素材 = 用户 2026-09-22 给的真实模板）。

⚠️ 与本目录 `test_plan_import.py` 分工：那份守**通用链**（幂等/手改/手动行），
   本份守**真文件逼出来的五件**：多工作表挑表 · 表头续行 · 单据号单字段（2026-09-27 用户裁定）·
   中文月日 · ⭐ **表头竖合并时"收款单位"绝不许变成单据号**（用户报障的回归）。

⭐ 真文件形态（2026-09-22 实测）：一个工作簿 4 张表（`计划预收款明细` / `分包付款计划明细` /
   `人工费付款计划明细` / **`材机付款计划明细`**）；目标表 `r1` 是主体表头（**多数格竖合并到 r2**）、
   `r2` **只给"单据号"那一列**补一行（`外租机械：付款通知书（编号）`）、数据从 `r3` 起；
   付款时间是 `9月11号`；单据号列里混着 `FKTZS…` / `QTZC…`（**不分机械与材料**，2026-09-27 用户裁定）。
"""

from __future__ import annotations

import io

from openpyxl import Workbook

from app.mod04_plan.importer import parse_workbook
from tests.acc_plugin import acc

#: 真文件的表头（主体 ＋ 只给"单据号"列的续行）
MAIN = ("项目", "科目", "费用日期", "材料：其他支出付资产处/贸易公司（编号）", "收款单位",
        "该流程金额", "已付款金额", "本月预付款金额", "剩余付款金额", "付款时间", "付款方式", "备注")
CONT = ("", "", "", "外租机械：付款通知书  （编号）", "", "", "", "", "", "", "", "")


def real_book() -> bytes:
    """造一份**真文件形态**的工作簿：第 1 张是噪声表（预收款），第 2 张才是材机付款计划明细。"""
    wb = Workbook()
    noise = wb.active
    noise.title = "计划预收款明细"
    noise.append(["7月份各项目预收款"])
    noise.append(["序号", "项目名称", "合同额（万元）", "已收款（万元）", "本月计划收款（万元）",
                  "备注", "负责人", "项目状态", "收款", "付款计划"])
    noise.append([1, "灵宝二期", 2500, 1418.7, 150, "资金余额-124.88万", "王凤侠", "完工", "", ""])

    ws = wb.create_sheet("材机付款计划明细")
    ws.append(MAIN)
    ws.append(CONT)                                   # ⭐ 二级表头续行
    ws.append(["灵宝二期", "", "2025-12-03", "FKTZS2025120365", "资产处集中采购",
               797726.5, 397726.5, 400000, "", "9月11号", "承兑", "循环水管道（唐山盈）"])
    ws.append(["灵宝二期", "", "2026-04-01", "FKTZS2026040037", "河北耀辉管业有限公司",
               28922, 0, 28922, "", "9月11号", "现金", "PE管件（赫尔泰）"])
    ws.append(["灵宝二期", "辅材费", "2026-03-01", "QTZC2026031406", "三门峡翊轩电气安装有限公司",
               4500, 0, 4500, "", "9月15号", "现金", "电缆检测费"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def merged_book() -> bytes:
    """⭐ **表头竖合并**的真形态工作簿（`TAIL-129` 报障的复现素材）。

    ⚠️ 与 `real_book()` 的**唯一差别** = 表头第 1、2 行**竖合并**（除"单据号"那一列 ——
       它在真表里就是把「材料：…」与「外租机械：…」分两行写的）。
       合并格被 `read_grid(fill_merged_rows=…)` 铺开之后，**第一行数据**才有机会被误当"子表头"
       ⇒ 所以这条夹具的 `merge_cells` 是判据的**命门**，⛔ 删了就复现不出报障。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "材机付款计划明细"
    ws.append(MAIN)
    ws.append(CONT)
    for col in "ABCEFGHIJKL":                     # = 除第 4 列（单据号）外的所有列
        ws.merge_cells(f"{col}1:{col}2")
    ws.append(["灵宝二期", "", "2025-12-03", "FKTZS2025120365", "资产处集中采购",
               797726.5, 397726.5, 400000, "", "9月11号", "承兑", "循环水管道（唐山盈）"])
    ws.append(["灵宝二期", "", "2026-04-01", "FKTZS2026040037", "河北耀辉管业有限公司",
               28922, 0, 28922, "", "9月11号", "现金", "PE管件（赫尔泰）"])
    ws.append(["灵宝二期", "辅材费", "2026-03-01", "QTZC2026031406", "三门峡翊轩电气安装有限公司",
               4500, 0, 4500, "", "9月15号", "现金", "电缆检测费"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@acc("ACC-PLAN-IMPORT-001", "001-08")
def test_按认得出表头的那张工作表解析():
    """⭐ 真文件第 1 张是「计划预收款明细」（只认得出"项目名称/备注"）⇒ 必须挑到**第 2 张**。"""
    parsed = parse_workbook(real_book(), year_month="2026-09")
    assert parsed.sheet == "材机付款计划明细"
    assert parsed.header_row == 1
    assert parsed.columns["project_input"] == "项目"
    assert parsed.columns["doc_no"].startswith("材料：其他支出")   # ⭐ 取**第一列**的表头原文


@acc("ACC-PLAN-IMPORT-001", "001-09")
def test_单据号原样取不分形态_中文月日按所选年月补年份():
    """⭐ 2026-09-27（`TAIL-129` 用户裁定「**单据号不分机械和材料**」）：那一列**原样取**，
    ⛔ 不再按编号形态猜类别（`FKTZS…` 与 `QTZC…` 一样都只是单据号）；`9月11号` ⇒ `2026-09-11`。"""
    rows = parse_workbook(real_book(), year_month="2026-09").rows
    by_doc = {r["doc_no"]: r for r in rows}
    mech = by_doc["FKTZS2025120365"]
    assert mech["pay_date"] == "2026-09-11"                      # 中文月日按所选年月补
    assert "QTZC2026031406" in by_doc                            # 别的形态照收（不分"材料/机械"）
    assert not any("_material_doc" in k or "_mechanical_doc" in k
                   for r in rows for k in r["raw"])


@acc()
def test_表头竖合并不许把第一行数据当表头_收款单位绝不变单据号():
    """⭐⭐ 2026-09-27 **用户报障的直接回归**（原话：「最后落库的**单据号大多都变成供应商名**了」）。

    真文件里那张表的表头是**竖合并**的（`项目` 等格跨 r1:r2）⇒ `read_grid(fill_merged_rows=…)`
    会把 r1 的值铺到 r2 ⇒ 通用面挑表头时把「r2 ＋ **r3（第一行数据）**」拼成了"两级表头"
    ⇒ 列名成了 `收款单位**资产处集中采购**` ⇒ 别名「资产处」被"包含词命中"抢走这一列
    ⇒ **收款单位（供应商名）落成了单据号**，还白吃一行数据。

    ⚠️ 本条必须**用带竖合并的夹具**才复现得出来（没有合并 ⇒ 铺不出 r2 ⇒ 老实现也恰好是对的）
       —— 所以素材里那两行 `merge_cells` 是这个判据的**命门**，⛔ 别删。
    """
    rows = parse_workbook(merged_book(), year_month="2026-09").rows
    assert len(rows) == 3, "第一行数据**不许**被当成表头吃掉（老实现只剩 2 行）"
    assert [r["doc_no"] for r in rows] == ["FKTZS2025120365", "FKTZS2026040037", "QTZC2026031406"]
    for r in rows:
        assert "公司" not in r["doc_no"] and "资产处" != r["doc_no"], \
            "⛔ 收款单位（供应商名）绝不许落成单据号"


@acc()
def test_二级表头续行不被当成数据行():
    """⚠️ 真文件 `r2` 只给"单据号"列补一行 —— 它不是数据行（现状会凭空多收一行垃圾）。"""
    parsed = parse_workbook(real_book(), year_month="2026-09")
    assert len(parsed.rows) == 3                                 # 三条真数据，不含续行
    assert all(r["project_input"] == "灵宝二期" for r in parsed.rows)
    assert any("两级表头" in a for a in parsed.alerts)            # 识别到了，并说明
    assert not any("外租机械：付款通知书" in str(r.get("doc_no") or "") for r in parsed.rows)


@acc()
def test_没选年月时中文月日原样保留不猜():
    """⛔ 没给年月 ⇒ **不许猜年份**（可手改列，人看得见原文比猜一个值强）。"""
    rows = parse_workbook(real_book()).rows
    assert {r["pay_date"] for r in rows} == {"9月11号", "9月15号"}


@acc()
def test_真文件形态_无效列仍原样保留():
    """§4.3.3：科目 / 费用日期 / 收款单位 / 已付款金额 / 剩余付款金额 原样入库、不要求修正。"""
    rows = parse_workbook(real_book(), year_month="2026-09").rows
    first, third = rows[0], rows[2]
    assert first["raw"]["收款单位"] == "资产处集中采购"
    assert first["raw"]["已付款金额"] == "397726.5"
    assert "科目" not in first["raw"]                     # 空值不进 raw（只在有值时原样保留）
    assert third["raw"]["科目"] == "辅材费"
    assert "payee" not in first and "subject" not in first


@acc()
def test_多工作表_预览要说清读的是哪张表(tmp_path):
    """API 级：预览里带上**工作表名**（真文件里"读错了哪张"是最容易出的错，必须一眼看得见）。

    ⚠️ 2026-09-23（`TAIL-75` 余项 · **用户裁定**「只留通用面」）：打的门从**页内端点**换成**通用面**
       （`POST /api/imp/m04_plan/parse`）—— **判词一字未改**，仍钉"预览要说清读的是哪张表"。
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.import_kit import api as imp_api
    from app.import_kit.profile_store import ProfileStore
    from app.mod04_plan import imp_spec

    app = FastAPI()
    app.include_router(imp_api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
                                            store=ProfileStore(tmp_path / "p.json")))
    resp = TestClient(app).post(
        "/api/imp/m04_plan/parse",
        files={"file": ("real.xlsx", real_book(), "application/octet-stream")},
        data={"sheet": ""})                                  # 不指定工作表 ⇒ 让后端自己挑
    assert resp.status_code == 200, resp.text[:200]
    j = resp.json()
    assert j["ok"] and j["sheet"] == "材机付款计划明细", j       # ⭐ 挑到了第 2 张（第 1 张是噪声表）
    assert j["header_row"] == 1, j
