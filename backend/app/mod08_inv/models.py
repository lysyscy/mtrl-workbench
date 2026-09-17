"""`MOD-08` 库存单据明细 与 **调整单**（`ENT-04`）。

依据：
- 《说明书》**§3.4**（库存单据明细 = 对账主工具；「仓库 + 项目全名」两把钥匙）
- 《说明书》**§5.2.4** · `DEV-R-07`（**调整单**：打在**单据行**上 · **不被 i8 导出覆盖** · 留痕 + 必填备注）
- 《说明书》**§9.3**（留痕 = 改前 / 改后 / 改动人 / 时间 + 备注）

⛔ **不建「是否作废」字段**（`NG-06`：i8 源里有、本系统不建）。
⛔ **不建删除入口**（`NG-03`）。
⚠️ 金额一律走 `MONEY`（`numeric(18,2)`，技术栈 §3.2）；金额判据走 `domain.adjustment_problem`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class InvDetail(Base):
    """库存单据明细行（i8 导出 `API-03` 落地）。

    ⚠️ **源数据永不被人工修改**（§9.3）：本表只由 i8 导出刷新；人工判断一律落 `InvAdjustment`。
    """

    __tablename__ = "inv_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")            # 核算年月（§9.2）
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")  # 键 = 仓库名（§2.7.4）
    bill_name_full: Mapped[str] = mapped_column(String(256), default="")          # 项目全名（第二把钥匙）
    doc_no: Mapped[str] = mapped_column(String(64), index=True, default="")       # 单据编号
    seq: Mapped[str] = mapped_column(String(32), default="")                      # 序号
    direction: Mapped[str] = mapped_column(String(8), index=True, default="")     # 出入库方向
    material_name: Mapped[str] = mapped_column(String(128), default="")
    # 物料性质 —— **过程资料「材料 5 类别」的取值字段**（用户口述 2026-09-16：
    # 「物料性质分 主材 / 辅材 / 工具 / 劳保 / 周转材料 / 临时设施」；归集规则见 `mod06_proc.domain`）
    material_property: Mapped[str] = mapped_column(String(32), index=True, default="")
    spec: Mapped[str] = mapped_column(String(128), default="")
    unit: Mapped[str] = mapped_column(String(32), default="")
    qty: Mapped[float] = mapped_column(MONEY, default=0)
    price_excl: Mapped[float] = mapped_column(MONEY, default=0)                   # 不含税单价
    price_incl: Mapped[float] = mapped_column(MONEY, default=0)                   # 含税单价
    amount: Mapped[float] = mapped_column(MONEY, default=0)                       # 金额（i8 原始值）
    tax_total: Mapped[float] = mapped_column(MONEY, default=0)                    # 价税合计
    biz_type: Mapped[str] = mapped_column(String(64), default="")
    vendor: Mapped[str] = mapped_column(String(128), default="")                  # 供应商 / 班组
    doc_date: Mapped[str] = mapped_column(String(32), index=True, default="")     # 单据日期
    audit_date: Mapped[str] = mapped_column(String(32), default="")               # 审核日期
    wbs_name: Mapped[str] = mapped_column(String(128), default="")
    cbs_name: Mapped[str] = mapped_column(String(128), default="")
    raw: Mapped[dict] = mapped_column(JSON, default=dict)                         # 非结构化源字段留存
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class InvAdjustment(Base):
    """**调整单** —— 打在**单据行**上的人工修正（`ENT-04` · §5.2.4）。

    ⭐ **独立存储** ⇒ i8 重新导出**只刷新 `inv_detail`、不动本表**（"不被 i8 导出覆盖"）。
    ⭐ 留痕 = `before_amount` / `amount` / `operator` / `changed_at` + **必填 `remark`**（§9.3）。
    """

    __tablename__ = "inv_adjustment"
    __table_args__ = (
        UniqueConstraint("row_id", name="uq_inv_adjustment_row"),   # 一行至多一张调整单
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    row_id: Mapped[int] = mapped_column(
        ForeignKey("inv_detail.id", ondelete="CASCADE"), index=True
    )
    before_amount: Mapped[float] = mapped_column(MONEY, default=0)   # 改前（i8 原始金额）
    amount: Mapped[float] = mapped_column(MONEY, default=0)          # 改后（调整后金额，≥ 0）
    remark: Mapped[str] = mapped_column(String(512), default="")     # ⚠️ 必填（为什么调）
    operator: Mapped[str] = mapped_column(String(64), default="")    # 改动人（唯一出口 = identity）
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


__all__ = ["InvDetail", "InvAdjustment"]
