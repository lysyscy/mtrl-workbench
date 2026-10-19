# -*- coding: utf-8 -*-
"""路径①（**模板填充**）的模板：入库齐全性 ＋ 闸门登记 ＋ **可读性**（`openpyxl` 要读得开）。

⚠️ 本单元（`TAIL-04` 余下的路径①）**判据尚未立**（走 §四 要新用例）⇒ 本文件全部 `@acc()` 显式声明**不绑定**。
   这里只钉**资产前提**：模板必须在仓、必须登记 SHA256、必须**读得开**（读不开 = 路径①无从谈起）。

⚠️ 与路径② 的一条重要差异（实测）：`模板_库存单据明细表.xlsx` **`openpyxl` 打不开**
   （`TypeError: Nested.from_tree() … 'node'`，见 `docs/reference/template-export.md` §六）；
   而**路径① 这 4 份必须读得开** —— 因为路径① 的做法就是 `openpyxl` 读模板再填数。
"""

from __future__ import annotations

import hashlib

import openpyxl
import pytest

from app.core.errors import MustReportError
from app.report_export import resources as R
from tests.acc_plugin import acc


@acc()
def test_路径1四份模板都在仓且都登记了SHA256():
    """资产前提：**要在仓、要登记** —— 否则闸门形同虚设（`require_template` 对未登记的名字只查存在）。"""
    assert len(R.PATH1_TEMPLATES) == 6, "路径① 的模板数变了？回 `docs/requirements/report-templates.md` §一/§二 核对"
    for p in R.PATH1_TEMPLATES:
        assert p.exists(), f"模板缺失：{p.name}（模板是产物的**基底本体**，不是「形态样例」）"
        assert p.name in R.EXPECTED_SHA256, f"`{p.name}` 没登记 SHA256 ⇒ 闸门对它只查存在、不查损坏"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == R.EXPECTED_SHA256[p.name], f"`{p.name}` 与登记不符（可能被回退/损坏）"
        # 闸门要真的拦得住这一份（不是"只有那两份才走闸门"）
        assert R.require_template(p) == p


@acc()
def test_路径1四份模板openpyxl读得开():
    """⭐ 路径① 的做法就是 `openpyxl` 读模板 ⇒ **读不开 = 这条路根本走不通**（在资产层面先拦）。

    ⚠️ 与路径② 的差异：那份 `模板_库存单据明细表.xlsx` 恰恰**读不开**（属 zip 字节替换那条路）。
    """
    names = set()
    for p in R.PATH1_TEMPLATES:
        wb = openpyxl.load_workbook(p)            # ⛔ 不带 read_only —— 要的就是"完整解析得开"
        try:
            names.update(wb.sheetnames)
        finally:
            wb.close()
    # 7 张 sheet 的**名字**来自 `docs/requirements/report-templates.md` §二（唯一登记处）—— 这里只核对到"出现了"
    for sn in ("辅材", "机械", "特殊费用月报表", "汇总表", "焊材", "气", "Sheet1"):
        assert sn in names, f"模板里找不到工作表 `{sn}` ⇒ 清单 §二 与实物不符"


@acc()
def test_闸门对未登记名字只查存在不查损坏_已文档化():
    """⚠️ **诚实边界**：`require_template` 对**没登记**的名字**查不出损坏**（只查存在）。

    这条不是"缺陷"、是**已知边界** ⇒ 上一条断言就是为它兜底的（4 份都必须在册）。
    """
    missing = R.TEMPLATE_DIR / "__不存在的模板__.xlsx"
    with pytest.raises(MustReportError) as e:
        R.require_template(missing)
    assert "模板缺失" in str(e.value)
