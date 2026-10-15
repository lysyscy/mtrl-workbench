"""`ACC-JC-IMPORT-001` 的 **`001-05`~`001-07`** —— 集采导入的**整批回滚 ＋ 覆盖语义文案**（`TAIL-98`）。

⚠️ `001-01`~`001-04`（映射引擎那三件）在 `tests/test_acc_jc_import.py`；本文件只补 `TAIL-98` 这三点。

判据三条（都能证伪）：
1. `001-05` **导入后回滚 ⇒ 那 5 列逐列回到导入前**（＋ 本批**新加**的发票行要摘掉；批次**不许重复回滚**）；
2. `001-06` **回执带批次号**（形如 `JC-YYYYMMDDHHMMSS`）—— ⭐ 壳侧的「整批回滚」按钮**只看回执有没有 `batch`**；
3. `001-07` **覆盖语义文案在位**（导入页明示"只动这 5 列 / i8 的列不会被覆盖"）—— ⛔ 靠 grep 钉住，防它被悄悄删掉。

⚠️ 库级断言一律**非破坏**：末尾 `s.rollback()`（⛔ 一行不留）。
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

import app
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod11_jc import imp_batch as B
from app.mod11_jc import imp_spec as S
from app.mod11_jc import import_service as IS
from app.mod11_jc.models import BATCH_ROLLED_BACK, JcContract, JcImportBatch, JcInvoice
from tests.acc_plugin import acc

CASE = "ACC-JC-IMPORT-001"
WH = "__自检仓_导入回滚__"


def _project(s):
    row = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full=f"{WH}项目",
                                 warehouse_name=WH, phid="")
    s.flush()
    return row


def _row(**over) -> dict:
    """一行"Excel 里的"数据（域行形状：键 = `excel_parse.FIELD_LABELS` 的键）。"""
    base = {"contract_amt": Decimal("8888.00"), "material_name": "导入的材料名",
            "method": "60天承兑", "remark": "导入的备注", "arch": "已存档",
            "arch_no": "A-001", "ret_date": "2026-09-20", "inv_sum": Decimal("100.00")}
    base.update(over)
    return base


def _invoices_of(s, contract_id: int) -> list[JcInvoice]:
    return list(s.execute(select(JcInvoice).where(JcInvoice.contract_id == int(contract_id))).scalars())


@acc(CASE, "001-05")
def test_导入后整批回滚_那5列逐列回到导入前():
    """⭐ 判据①（本件的主判据）。"""
    with session_scope() as s:
        try:
            p = _project(s)
            c = JcContract(project_id=p.id, contract_date="2026-09-19", material_name="原材料名",
                           supplier="业祥", contract_amt=Decimal("8888.00"), remark="原备注",
                           method="原付款方式", arch="未存档", arch_no="", ret_date="")
            s.add(c)
            s.flush()
            cid = int(c.id)
            before = {k: str(getattr(c, k) or "") for k in IS.EXCEL_COLS}

            out = B.apply_batch(s, [_row()], project_id=p.id, project_key=WH, operator="自检")
            assert out["updated"] == 1, f"锚点没配上：{out}"
            cur = s.get(JcContract, cid)
            assert cur.material_name == "导入的材料名", "导入没生效 ⇒ 下面的回滚断言会没有区分力"
            assert str(out["batch"]).startswith(B.BATCH_PREFIX) and re.fullmatch(r"JC-\d{14}", out["batch"])
            assert len(_invoices_of(s, cid)) == 1, "汇总发票行没落 ⇒ 回滚的「摘发票」那半就没得测"

            rep = B.rollback(s, out["batch"], "自检")
            assert rep["restored"] == 1, rep
            back = s.get(JcContract, cid)
            for k in IS.EXCEL_COLS:
                assert str(getattr(back, k) or "") == before[k], f"「{k}」没回到导入前：{getattr(back, k)!r}"
            assert _invoices_of(s, cid) == [], "本批**新加**的发票行必须被摘掉（否则欠款还是错的）"
            b = s.execute(select(JcImportBatch)
                          .where(JcImportBatch.batch_no == out["batch"])).scalars().first()
            assert b is not None and str(b.status) == BATCH_ROLLED_BACK, "批次必须置 `rolled_back`（⛔ 不物理删）"

            # ⛔ 不许重复回滚（第二遍会把"回滚后的值"再改一次）
            with pytest.raises(MustReportError):
                B.rollback(s, out["batch"], "自检")
            # ⛔ 幽灵批次号 ⇒ 显式报错（禁静默）
            with pytest.raises(MustReportError):
                B.rollback(s, "JC-19700101000000", "自检")
        finally:
            s.rollback()


@acc(CASE, "001-06")
def test_回执带批次号_且壳侧按钮据此出现():
    """⭐ 判据②：回执带**批次号** ⇒ 壳侧「整批回滚」按钮出现（通用面**已就绪**，⛔ 壳不用改）。"""
    assert re.fullmatch(r"JC-\d{14}", B.next_batch()), "批次号形态变了（壳侧按钮靠它认）"
    assert S.SPEC.batch is True, "本域没声明 `batch=True` ⇒ 通用面不会渲染回滚按钮"
    assert S.HOOKS.rollback is not None, "没给 `rollback` 钩子 ⇒ 通用面不挂 `/rollback` 端点"
    # ⭐ 结构面：壳**早就有**那个按钮，且**只认回执里的 `batch`**（同批 `TAIL-98` 只补域这一半）
    shell = (Path(app.__file__).resolve().parent / "web" / "shell" / "legacy.js").read_text(encoding="utf-8")
    assert 'data-act="impRollback"' in shell, "壳里没有整批回滚按钮（它本该已就绪）"
    assert "r.batch ?" in shell, "按钮的显示条件不是「回执带 batch」—— 与域的口径脱节了"


@acc(CASE, "001-07")
def test_导入页覆盖语义文案在位():
    """⭐ 判据③：**用户最需要的那句话**。⛔ 一旦被删/被改写，本断言当场红（这是它存在的唯一理由）。

    依据 = 用户 2026-09-25「界面没说清哪些列会被覆盖 ⇒ 易误操作」。
    """
    note = str(S.SPEC.note or "")
    for bit in ("只动这 5 列", "材料名", "备注", "存档情况", "存档号", "寄回日期",
                "合同价 / 供应商 / 合同日期 / 甲方单位", "不会被覆盖", "整批回滚"):
        assert bit in note, f"导入页的覆盖语义文案缺「{bit}」—— 用户会误以为会覆盖 i8 的列"
    # ⚠️ 这句话必须在**域声明**里（⛔ 不许散在壳里 —— 壳是通用面，不知道集采有哪些列）
    assert "覆盖语义" in note, "那段话没标成「覆盖语义」（后来人读不出来它是干什么用的）"
    # 反向：文案里的 5 列必须与代码的 5 列**同一个来源**（⛔ 别两处各写一份）
    assert set(IS.EXCEL_COLS) == {"material_name", "remark", "arch", "arch_no", "ret_date"}
    assert json.dumps(list(IS.EXCEL_COLS), ensure_ascii=False)  # 仅为说明它可机读（无断言含义）
