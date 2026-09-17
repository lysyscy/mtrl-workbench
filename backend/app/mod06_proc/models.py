"""`MOD-06` 过程资料 · **机械 6 列的手录旁路表**。

依据：《说明书》**§5.2.3 ②**（机械费各项 = 人工录入 —— 机械费近期不做，先手录）·
**§5.2.5 ③**（机械 6 列**全段手录**，但**必须与材料列同构**：同一「列取值出口」、数据源可插拔）。

⚠️ 旁路载体（与调整单同源思路）：**不被重抓 i8 / 重导历史覆盖**（§9.3）。
⚠️ 键 = **核算月 ＋ 仓库名**（项目键 = 仓库名，§2.7.4）。
⚠️ 金额一律 `MONEY`（`numeric(18,2)`，技术栈 §3.2）—— **不得**用 JSON 装金额。
⚠️ 列名 `mech_0`…`mech_5` 与 `domain.MECH_COLUMNS` 的**下标**一一对应；两处的**列数**由
   `tests/test_acc_proc_001.py` 的断言钉住（改了这边没改那边 ⇒ 直接报红）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class ProcMechManual(Base):
    """过程资料 · 机械 6 列手录值（一「核算月 × 仓库」一行）。"""

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
    mech_0: Mapped[float] = mapped_column(MONEY, default=0)   # 租分公司设备
    mech_1: Mapped[float] = mapped_column(MONEY, default=0)   # 内租设备
    mech_2: Mapped[float] = mapped_column(MONEY, default=0)   # 外租零租含税
    mech_3: Mapped[float] = mapped_column(MONEY, default=0)   # 外租包月含税
    mech_4: Mapped[float] = mapped_column(MONEY, default=0)   # 外租零租不含税
    mech_5: Mapped[float] = mapped_column(MONEY, default=0)   # 外租包月不含税

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ============================================================ 历史段（§5.2.5）
#
# 历史段（核算月 ≤ 截止核算月）的材料列 = **导入的定稿快照**，**不引用库存单据**。
# ⚠️ 与源系统**完全独立**：i8 重抓 / 库存单据改数**都动不到它**；要改只能**再导一次**（§5.2.5 ②）。

BATCH_ACTIVE = "active"
BATCH_ROLLED_BACK = "rolled_back"


class ProcHistoryBatch(Base):
    """一次「过程资料历史导入」的批次（**整批回滚**以它为单位，§5.2.5 ②）。"""

    __tablename__ = "proc_history_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, default="")
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")
    cutoff_ym: Mapped[str] = mapped_column(String(7), default="")      # 本次设定 / 沿用的截止核算月
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    operator: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), index=True, default=BATCH_ACTIVE)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ProcHistorySnapshot(Base):
    """历史段定稿快照的一条记录（键 = **批次 ＋ 核算月 ＋ 仓库名**；材料 10 列）。"""

    __tablename__ = "proc_history_snapshot"

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


class ProcCutoff(Base):
    """**截止核算月**（**一项目一行**；分界 = 历史段 ≤ 截止 < 正式段；一次设定、可改，§5.2.5 ①）。"""

    __tablename__ = "proc_cutoff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, default="")
    cutoff_ym: Mapped[str] = mapped_column(String(7), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


__all__ = ["ProcMechManual", "ProcHistoryBatch", "ProcHistorySnapshot", "ProcCutoff",
           "BATCH_ACTIVE", "BATCH_ROLLED_BACK"]
