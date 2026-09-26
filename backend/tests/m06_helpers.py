"""`MOD-06` 页面 / 域自检的公共桩（**离线：不连库**）。

会话桩与 `MOD-08` 共用（`tests/m08_helpers.FakeSession`）—— 只在这里补过程资料要的桩数据。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.mod06_proc.models import ProcMechManual
from app.mod08_inv.models import InvAdjustment, InvDetail
from tests.m08_helpers import FakeSession  # noqa: F401  —— 会话桩共用（不另写一份）

WAREHOUSE = "甲仓"
OTHER_WAREHOUSE = "乙仓"


def make_inv(
    row_id: int,
    *,
    ym: str,
    direction: str,
    material_property: str,
    amount: str,
    warehouse: str = WAREHOUSE,
) -> InvDetail:
    """一行库存单据明细（**带「物料性质」** —— 材料 5 类别的取值字段）。"""
    return InvDetail(
        id=row_id, ym=ym, warehouse_name=warehouse, bill_name_full=f"{warehouse}项目",
        doc_no=f"K{row_id}", seq=str(row_id), direction=direction,
        material_name=f"物料{row_id}", material_property=material_property, spec="—", unit="kg",
        qty=Decimal("1.00"), price_excl=Decimal(amount), price_incl=Decimal(amount),
        amount=Decimal(amount), tax_total=Decimal(amount), biz_type="采购入库",
        vendor="某供应商", doc_date=f"{ym}-05", audit_date=f"{ym}-06",
        wbs_name="W1", cbs_name="C1", raw={},
    )


def make_mech(row_id: int, *, ym: str, values: list[str], warehouse: str = WAREHOUSE) -> ProcMechManual:
    kw = {"id": row_id, "ym": ym, "warehouse_name": warehouse, "project_id": None,
          "updated_at": datetime(2026, 9, 16, 10, 0)}
    for i, v in enumerate(values):
        kw[f"mech_{i}"] = Decimal(v)
    return ProcMechManual(**kw)


def dataset() -> dict:
    """小样本：2 个核算月 · 6 种物料性质全覆盖 · **1 行入库被调整过** · 1 行未登记的物料性质。

    ⚠️ 刻意留一条 `物料性质 = 未登记类`（金额 999）—— 用来证明**认不出的类别不臆造、直接被跳过**。
    """
    return {
        InvDetail: [
            make_inv(1, ym="2026-08", direction="入库", material_property="主材", amount="100.00"),
            make_inv(2, ym="2026-08", direction="出库", material_property="辅材", amount="40.00"),
            make_inv(3, ym="2026-08", direction="入库", material_property="工具", amount="30.00"),
            make_inv(4, ym="2026-07", direction="入库", material_property="劳保", amount="20.00"),
            make_inv(5, ym="2026-07", direction="出库", material_property="周转材料", amount="10.00"),
            make_inv(6, ym="2026-07", direction="入库", material_property="临时设施", amount="50.00"),
            make_inv(7, ym="2026-07", direction="入库", material_property="未登记类", amount="999.00"),
            make_inv(8, ym="2026-08", direction="入库", material_property="主材", amount="500.00",
                     warehouse=OTHER_WAREHOUSE),
        ],
        InvAdjustment: [
            InvAdjustment(id=101, row_id=1, before_amount=Decimal("100.00"),
                          amount=Decimal("80.00"), remark="对账差异", operator="科室用户",
                          changed_at=datetime(2026, 9, 16, 10, 30)),
        ],
        ProcMechManual: [
            make_mech(201, ym="2026-08", values=["1.00", "2.00", "3.00", "4.00", "5.00", "6.00"]),
            make_mech(202, ym="2026-07", values=["0", "0", "0", "0", "0", "0"]),
        ],
    }


__all__ = ["FakeSession", "WAREHOUSE", "OTHER_WAREHOUSE", "make_inv", "make_mech", "dataset",
           "make_batch", "make_snapshot", "make_cutoff", "dataset_sections", "xlsx_bytes"]


def xlsx_bytes(rows: list[list], header: tuple | None = None) -> bytes:
    """把「表头 ＋ 若干行」打成 `.xlsx` 字节（**历史导入解析**的自检用；不写盘）。"""
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(header or ("核算月", "入库主辅材")))
    for row in rows:
        ws.append(list(row))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================ 分段样本（§5.2.5 · ACC-RPT-PROC-002）

CUTOFF_YM = "2026-06"          # 分界：≤ 2026-06 = 历史段；> = 正式段
_BATCH = "H20260916-01"


def make_batch(batch_no: str = _BATCH, *, warehouse: str = WAREHOUSE,
               cutoff_ym: str = CUTOFF_YM, status: str = "active"):
    from app.mod06_proc.models import ProcHistoryBatch

    return ProcHistoryBatch(id=1, batch_no=batch_no, warehouse_name=warehouse,
                            cutoff_ym=cutoff_ym, row_count=2, operator="科室用户",
                            status=status, at=datetime(2026, 9, 16, 9, 0))


def make_snapshot(row_id: int, *, ym: str, ins: str = "0", outs: str = "0",
                  warehouse: str = WAREHOUSE, batch_no: str = _BATCH,
                  mech: list[str] | None = None):
    """历史段定稿快照的一行：`ins` / `outs` 都是「主辅材」列的金额（够用即可）。

    ⭐ `mech` = **机械 6 列**（2026-09-26 · `TAIL-107`：历史段的机械费也来自快照）——
      不给 ⇒ 全 `0`（＝这份快照没导入机械费）。
    """
    from decimal import Decimal as D

    from app.mod06_proc.models import ProcHistorySnapshot

    vals = list(mech or [])
    kw = {f"mech_{i}": D(str(vals[i]) if i < len(vals) else "0")
          for i in range(6)}
    return ProcHistorySnapshot(id=row_id, batch_no=batch_no, ym=ym, warehouse_name=warehouse,
                               project_id=None, in_0=D(ins), in_1=D("0"), in_2=D("0"),
                               in_3=D("0"), in_4=D("0"), out_0=D(outs), out_1=D("0"),
                               out_2=D("0"), out_3=D("0"), out_4=D("0"), **kw)


def make_cutoff(cutoff_ym: str = CUTOFF_YM, *, warehouse: str = WAREHOUSE):
    from app.mod06_proc.models import ProcCutoff

    return ProcCutoff(id=1, warehouse_name=warehouse, cutoff_ym=cutoff_ym,
                      updated_at=datetime(2026, 9, 16, 9, 0))


def dataset_sections() -> dict:
    """两段并存的小样本：**历史段**（快照）/ **正式段**（库存单据）/ 机械手录跨两段。

    - 截止核算月 = `2026-06` ⇒ 历史段 = {05, 06}（快照）· 正式段 = {07, 08, 09, 10}（库存单据）
    - ⚠️ **库存单据里也放了一条 2026-05**（金额 9999）—— 用来证明**历史段不引用库存单据**
    - ⚠️ **2026-10 只有机械手录、没有库存单据** —— 用来证明**正式段空态不臆造 0**
    - ⭐⭐ **机械列刻意"两段各一份、值还不一样"**（2026-09-26 · `TAIL-107`）：
      历史段 `2026-06` 的**快照**有机械值（`mech_0 = 5.00`）而**手录表里也有** `2026-06`（`mech_0 = 7.00`，
      改前那条口径留下的行）⇒ 判据据此证明「**历史段以导入值为准**：读到的必须是 5.00、不是 7.00」；
      正式段 `2026-07` 只有手录（1.00）⇒ 证明正式段仍以手录为准。
    """
    from decimal import Decimal as D

    from app.mod06_proc.models import (
        ProcCutoff,
        ProcHistoryBatch,
        ProcHistorySnapshot,
        ProcMechManual,
    )
    from app.mod08_inv.models import InvDetail

    return {
        InvDetail: [
            make_inv(1, ym="2026-05", direction="入库", material_property="主材", amount="9999.00"),
            make_inv(2, ym="2026-07", direction="入库", material_property="主材", amount="100.00"),
            make_inv(3, ym="2026-08", direction="入库", material_property="主材", amount="200.00"),
            make_inv(4, ym="2026-09", direction="出库", material_property="工具", amount="50.00"),
        ],
        InvAdjustment: [],
        ProcMechManual: [
            make_mech(201, ym="2026-06", values=["7.00", "0", "0", "0", "0", "0"]),
            make_mech(202, ym="2026-07", values=["1.00", "0", "0", "0", "0", "0"]),
            make_mech(203, ym="2026-10", values=["9.00", "0", "0", "0", "0", "0"]),
        ],
        ProcHistoryBatch: [make_batch()],
        ProcHistorySnapshot: [
            make_snapshot(301, ym="2026-05", ins="1000.00"),
            # ⭐ 2026-06 的快照**带机械值**（5.00）—— 而手录表里同一格是 7.00 ⇒ 判据证明"快照说了算"
            make_snapshot(302, ym="2026-06", outs="200.00", mech=["5.00", "0", "0", "0", "0", "0"]),
        ],
        ProcCutoff: [make_cutoff()],
    }

