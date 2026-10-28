"""MOD-06 有效机械、导入批次与材料快照。
机械手录和导入共用 proc_mech_manual，最后成功写入覆盖同月同列。
材料快照保留批次溯源，材料和机械截止仅筛选本次导入。
所有金额使用 MONEY；来源批号 JSON 只装字符串，回滚前值仍使用 MONEY。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class ProcMechMatchRule(Base):
    """机械报表项目名对照；仓库键关联档案，别名由规则配置编辑。"""

    __tablename__ = "proc_mech_match_rule"

    warehouse_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)


class ProcMechManual(Base):
    """过程资料 · 机械 6 列手录值（一「核算月 × 仓库」一行）；任何月份可编辑。"""

    __tablename__ = "proc_mech_manual"
    __table_args__ = (
        UniqueConstraint("ym", "warehouse_name", name="uq_proc_mech_ym_wh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")

    # 机械 6 列（顺序照 `domain.MECH_COLUMNS`）
    mech_0: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 租分公司设备
    mech_1: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 内租设备
    mech_2: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 外租零租含税
    mech_3: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 外租包月含税
    mech_4: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 外租零租不含税
    mech_5: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)   # 外租包月不含税

    source_batches: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'::json"))

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ============================================================ 历史段（§5.2.5）
#
# 材料同项目同月有 i8 则整月优先 i8，无 i8 才读有效快照。
# i8 重抓不改变快照记录；重新导入替换该项目有效历史材料。

BATCH_ACTIVE = "active"
BATCH_ROLLED_BACK = "rolled_back"
BATCH_REPLACED = "replaced"


class ProcHistoryBatch(Base):
    """一次「过程资料历史导入」的批次（**整批回滚**以它为单位，§5.2.5 ②）。"""

    __tablename__ = "proc_history_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, default="")
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")
    cutoff_ym: Mapped[str] = mapped_column(String(7), default="")      # 本次设定 / 沿用的截止核算月
    mechanical_cutoff_ym: Mapped[str] = mapped_column(String(7), default="", server_default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    operator: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), index=True, default=BATCH_ACTIVE)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ProcHistorySnapshot(Base):
    """历史段定稿快照的一条记录（键 = **批次 ＋ 核算月 ＋ 仓库名**；材料 10 列 ＋ **机械 6 列**）。

    ⭐ 2026-09-26：**机械 6 列也进快照**（用户裁定"历史机械费都填在过程资料 excel 里"）——
      此前只有材料 10 列 ⇒ 历史段的机械费没有落点（只能手录，而那本是"启用后"才用的）。
    机械快照只保留导入原值；显示统一读取 proc_mech_manual。
    """

    __tablename__ = "proc_history_snapshot"

    material_present: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")

    # 材料 10 列：`in_0..in_4` = 入库 5 类 · `out_0..out_4` = 出库 5 类
    # （下标与 `domain.CATEGORIES` 一一对应；列数由测试钉住）
    in_0: Mapped[float] = mapped_column(MONEY, default=0)
    in_1: Mapped[float] = mapped_column(MONEY, default=0)
    in_2: Mapped[float] = mapped_column(MONEY, default=0)
    in_3: Mapped[float] = mapped_column(MONEY, default=0)
    in_4: Mapped[float] = mapped_column(MONEY, default=0)
    out_0: Mapped[float] = mapped_column(MONEY, default=0)
    out_1: Mapped[float] = mapped_column(MONEY, default=0)
    out_2: Mapped[float] = mapped_column(MONEY, default=0)
    out_3: Mapped[float] = mapped_column(MONEY, default=0)
    out_4: Mapped[float] = mapped_column(MONEY, default=0)

    # 机械 6 列（下标与 `domain.MECH_COLUMNS` 一一对应；2026-09-26 补，迁移 `f3a7c1e5b9d2`）
    # ⚠️ `server_default="0"` 是**迁移给的**（往有行的表加非空列必须给默认值）—— 模型这行
    #    **必须一起声明**，否则 `alembic check` 天天报 `modify_default`（`TAIL-102` 的教训）。
    mech_0: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 租分公司设备
    mech_1: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 内租设备
    mech_2: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 外租零租含税
    mech_3: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 外租包月含税
    mech_4: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 外租零租不含税
    mech_5: Mapped[float] = mapped_column(MONEY, default=0, server_default="0")   # 外租包月不含税


class ProcMaterialManual(Base):
    """历史材料逐格手填；不改动导入快照。"""

    __tablename__ = "proc_material_manual"
    __table_args__ = (UniqueConstraint("warehouse_name", "ym", "column_key", name="uq_proc_material_cell"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey('project.id', ondelete='SET NULL'), nullable=True, index=True)
    ym: Mapped[str] = mapped_column(String(7), nullable=False)
    column_key: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[float | None] = mapped_column(MONEY, nullable=True)


class ProcCutoff(Base):
    """**截止核算月**（**一项目一行**；材料与机械本次导入截止；一项目一行）。"""

    __tablename__ = "proc_cutoff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, default="")
    cutoff_ym: Mapped[str] = mapped_column(String(7), default="")
    mechanical_cutoff_ym: Mapped[str] = mapped_column(String(7), default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ProcMechImportChange(Base):
    """每次导入的机械格前值；金额仍使用 MONEY，来源批号只作归属判断。"""

    __tablename__ = "proc_mech_import_change"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), index=True)
    warehouse_name: Mapped[str] = mapped_column(String(128))
    ym: Mapped[str] = mapped_column(String(7))
    column_key: Mapped[str] = mapped_column(String(16))
    before_amount: Mapped[float] = mapped_column(MONEY)
    before_batch: Mapped[str] = mapped_column(String(64), default="")


__all__ = ["ProcMechManual", "ProcMaterialManual", "ProcHistoryBatch", "ProcHistorySnapshot", "ProcCutoff",
           "BATCH_ACTIVE", "BATCH_ROLLED_BACK"]
