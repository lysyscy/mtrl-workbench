"""`TAIL-68`（2026-09-21）· **落盘归一**：`report_export/save.py::save_workbook()` 是唯一出口。

⭐ 为什么要有本件（普查当场抓到的真隐患）：落盘原先散在 6 处，其中 **`setl_export` 没有 `mkdir`**
   ⇒ 换一个不存在的导出目录**直接崩**。收到一个出口之后，"先建目录"这一步**不可能再被漏**。

⛔ **命名不抽**（`file_name` / `title_of` 是各报表的业务口径，`period_label` 已是期间标签的主人）
   ⇒ 本件**不**钉命名，只钉落盘。
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re

import openpyxl

from app.mod05_flow import debt_export as DEBT
from app.report_export.save import save_workbook
from tests.acc_plugin import acc          # ⭐ 工具自检：显式声明"不绑定判据点"（`@acc()`）

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


@acc()
def test_落盘到不存在的多级目录也要成功(tmp_path):
    """⭐ 这条是 `TAIL-68` 存在的理由：`mkdir(parents=True)` **一步都不能省**。"""
    out = tmp_path / "a" / "b" / "c" / "报表.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "你好"
    got = save_workbook(wb, out)
    assert got.is_absolute(), f"返回的不是绝对路径：{got}"
    assert got.exists() and got.stat().st_size > 0
    assert openpyxl.load_workbook(got).active["A1"].value == "你好"


@acc()
def test_接受字符串路径():
    wb = openpyxl.Workbook()
    got = save_workbook(wb, str(pathlib.Path(__file__).parent / "_tmp_save_str.xlsx"))
    try:
        assert got.is_absolute()
    finally:
        got.unlink(missing_ok=True)


@acc()
def test_落盘出口只剩一个():
    """⭐ **静态扫描**：除 `save.py` 自己，全站**不得再有** `wb.save(`
    ⇒ 防止以后有人新增一处"不带 mkdir 的落盘"（这正是 `setl_export` 当年的形态）。

    ⚠️ 只扫业务代码（`backend/app/**`）；`wb.save(buf)` 存进 `BytesIO` 那种**不是落盘**，
       由 `save_workbook` 之外的方式存在 —— 但为判据简单起见，**一律要求走出口**。
    """
    bad = []
    for p in sorted(APP.rglob("*.py")):
        rel = str(p).replace("\\", "/").split("/app/")[-1]
        if rel == "report_export/save.py" or "tests" in rel:
            continue
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = l.split("#", 1)[0]          # ⭐ 去掉注释再匹配（注释里**说** `wb.save(` 是正当的）
            if re.search(r"\bwb\.save\s*\(", code):
                bad.append(f"{rel}:{i}: {l.strip()[:70]}")
    assert not bad, "还有裸 `wb.save(`（落盘必须走 `save_workbook`）：\n  " + "\n  ".join(bad)


@acc()
def test_总欠款导出走落盘件_且文件名按口径(tmp_path):
    """端到端：`debt_export`（自足、不依赖模板）落到**不存在的子目录**也要成功。"""
    items = [{"index": 1, "project": "甲项目", "jc": "10.5", "material": "2", "mech": "0"},
             {"index": 2, "project": "乙项目", "jc": "3", "material": "0", "mech": "1.25"}]
    out = DEBT.build_xlsx(items, tmp_path / "导出" / "嵌套", today=dt.date(2026, 9, 21))
    p = pathlib.Path(out)
    assert p.exists() and p.stat().st_size > 0
    assert p.name == "总欠款_20260921.xlsx", f"文件名不合口径：{p.name}"
    ws = openpyxl.load_workbook(p).active
    assert ws["B2"].value == "甲项目"
    assert isinstance(ws["C2"].value, float), "金额必须是数字（⛔ 不是字符串）"
    assert ws["B4"].value == "合计"                 # 合计写在**第 2 列**（本页口径，⛔ 别挪到第 1 列）
