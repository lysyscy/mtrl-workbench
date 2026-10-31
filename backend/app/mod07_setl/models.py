"""`MOD-07` 收发结存的落地表。

依据：
- 《说明书》**§5.3.2**（交付形态 = 分仓库表 ＋ 总表；金额按 2 位小数对平、容差 0）· **§9.5**（导入幂等）
- 《说明书》附录 **E.1.1**：i8 导出是 **xlsx 网格（不是实体行）**，**列清单的现行来源 = i8 导出表头**
- 《技术栈选型分析》**§9.8**（`API-02`：项目参数 `pc` · `reportName` = 表名）
- 实现层借鉴 = `PRD素材包-20260911/app/importer.py::import_sfjc`（⚠️ 只借鉴**落库形态**，口径不得反推）

⭐ **粒度 = 明细行**，与素材包的 `stock_monthly` 同款：**核算月 × 仓库 × 资源编码** 一行。
   （页面只显示按仓汇总，但 **焊材 / 气体提取**（§5.3.3）与**分仓库工作簿**都要明细 ⇒ 汇总在域内核做，不落汇总表。）
⚠️ 键 = 「核算年月 ＋ 仓库名 ＋ 资源编码」⇒ 同键重抓**幂等刷新**、**换月互不覆盖**。
⚠️ `source`：`auto`（抓取写入，会被下一次抓取刷新）/ 非 `auto`（人工，**不被抓取覆盖**）——
   与素材包 `DELETE ... WHERE month=? AND (source IS NULL OR source='auto')` 同一语义。
⚠️ 金额与数量一律走 `MONEY`（`numeric(18,2)`，技术栈 §3.2）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY

SOURCE_AUTO = "auto"

# 列顺序与 i8 导出表头一致（`schema_cols.SFJC_HEADER` 的 17 列，`仓库` → `warehouse_name`）
NUMERIC_COLUMNS: tuple[str, ...] = (
    "begin_qty", "begin_amt", "in_qty", "in_price", "in_amt",
    "out_qty", "out_price", "out_amt", "end_qty", "end_amt",
)


class SetlDetail(Base):
    """收发结存明细行（`API-02` 导出落地 / 手动导入）。

    ⚠️ 金额的四个口径列 = `begin_amt` / `in_amt` / `out_amt` / `end_amt`
       （对应导出表头的 期初金额 / 收金额 / 发金额 / 结存金额）—— **对平判据只用这四列**。
    """

    __tablename__ = "setl_detail"
    __table_args__ = (
        UniqueConstraint("ym", "warehouse_name", "resource_code", name="uq_setl_detail_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")                 # 核算年月
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")   # 键 = 仓库名（§2.7.4）
    resource_class: Mapped[str] = mapped_column(String(64), default="")                # 资源分类
    resource_code: Mapped[str] = mapped_column(String(64), index=True, default="")     # 资源编码
    resource_name: Mapped[str] = mapped_column(String(128), index=True, default="")    # 资源名称
    spec: Mapped[str] = mapped_column(String(128), default="")                         # 规格型号
    unit: Mapped[str] = mapped_column(String(32), default="")                          # 计量单位
    material_property: Mapped[str] = mapped_column(String(32), index=True, default="")  # 物料性质
    begin_qty: Mapped[float] = mapped_column(MONEY, default=0)      # 期初数量
    begin_amt: Mapped[float] = mapped_column(MONEY, default=0)      # 期初金额
    in_qty: Mapped[float] = mapped_column(MONEY, default=0)         # 收数量
    in_price: Mapped[float] = mapped_column(MONEY, default=0)       # 收单价
    in_amt: Mapped[float] = mapped_column(MONEY, default=0)         # 收金额
    out_qty: Mapped[float] = mapped_column(MONEY, default=0)        # 发数量
    out_price: Mapped[float] = mapped_column(MONEY, default=0)      # 发单价
    out_amt: Mapped[float] = mapped_column(MONEY, default=0)        # 发金额
    end_qty: Mapped[float] = mapped_column(MONEY, default=0)        # 结存数量
    end_amt: Mapped[float] = mapped_column(MONEY, default=0)        # 结存金额
    source: Mapped[str] = mapped_column(String(8), index=True, default=SOURCE_AUTO)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class WeldGasBalance(Base):
    """焊材 / 气体提取成品的**「结余」列**（§5.3.3 · `模板清单` §五 的 **B 类**）。

    ⭐ **2026-09-18 用户裁定：结余 = 历史结余、由用户手工录入** —— 系统**没有任何来源**
       （⛔ 不是收发结存的 `end_amt` 派生，那条口径已被作废）。本表就是那份录入值的落点。

    ⚠️ **粒度 = 类别 × 仓库 · 不按月**（用户维护的是"当前的结存"，改一次覆盖一次）；
       将来若要按月留痕 ⇒ 加 `ym` 列 ＋ 改唯一键（一次迁移）—— **现在不提前加**。
    ⚠️ **未录入 = 库里没有这一行**（域值 `None`）⇒ 导出里**如实留空**；
       **0 是合法录入值**（有行、`amount = 0`），⛔ 两者不得混为一谈。
    """

    __tablename__ = "weldgas_balance"
    __table_args__ = (
        UniqueConstraint("kind", "warehouse_name", name="uq_weldgas_balance_kind_wh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), index=True, default="")              # 取值域 = extract.KINDS
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")   # 键 = 仓库名（§2.7.4）
    amount: Mapped[float] = mapped_column(MONEY, default=0)                            # 结余（元 · 2 位小数）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AnalysisBigProject(Base):
    """旧全局名单与顺序，只读兼容基线；无真实月份依据，不迁成历史月配置。"""

    __tablename__ = "analysis_big_project"
    __table_args__ = (
        UniqueConstraint("warehouse_name", name="uq_big_project_wh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")   # 键 = 仓库名（§2.7.4）
    seq: Mapped[int] = mapped_column(Integer, default=0)                              # 大表自己的顺序
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AnalysisBigMonthProject(Base):
    """按月固定的大表名单；旧全局配置保留在 AnalysisBigProject 作只读基线。"""

    __tablename__ = "analysis_big_month_project"
    __table_args__ = (
        UniqueConstraint("ym", "warehouse_name", name="uq_big_month_project_ym_wh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True)
    warehouse_name: Mapped[str] = mapped_column(String(128))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AnalysisBigManual(Base):
    """活动大表手填及保留的旧用油完整总额，粒度 = **核算月 × 仓库**。

    ⭐ **未录入 = 该列为 `NULL`**（不是 0）—— 「上次值带入」（§5.7.2）就靠这个区分：
       `NULL` ⇒ 向前取最近一次录入值；**0 是合法录入值**，会终止带入（001-09）。
    ⚠️ 列名与 `big_domain.MANUAL_COLUMN` 一一对应（**唯一映射处**，别在仓储层再写一份）。
    ⚠️ 本表**只有手填值** —— 自动列（提取 / 机械）与派生列**一律现场算**，不落库：
       落库就是第二份真相（与 §5.2.3「材料数据单向流」同理）。
    """

    __tablename__ = "analysis_big_manual"
    __table_args__ = (
        UniqueConstraint("ym", "warehouse_name", name="uq_big_manual_ym_wh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")                 # 核算年月
    warehouse_name: Mapped[str] = mapped_column(String(128), index=True, default="")   # 键 = 仓库名
    project_id: Mapped[int | None] = mapped_column(
        # ⚠️ 外键**必须命名**：autogenerate 会生成无名约束 ⇒ `downgrade()` 必失败（迁移纪律）
        ForeignKey("project.id", ondelete="SET NULL", name="fk_analysis_big_manual_project"),
        nullable=True, index=True,
    )                                                                                  # 档案 id（可空：陌生仓库）
    open_ym: Mapped[str | None] = mapped_column(String(7), nullable=True)              # 开工时间 `YYYY-MM`
    mech_est: Mapped[float | None] = mapped_column(MONEY, nullable=True)               # 机械费测算
    contract_price: Mapped[float | None] = mapped_column(MONEY, nullable=True)         # 合同（预估）价
    output_cum: Mapped[float | None] = mapped_column(MONEY, nullable=True)             # 产值累计（含税）
    oil: Mapped[float | None] = mapped_column(MONEY, nullable=True)                    # 旧完整总额，仅供明确接续核对
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)               # 备注
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class BigOilBinding(Base):
    """大表用油明确接续的项目身份；完整旧值继续留在analysis_big_manual。"""
    __tablename__ = 'big_oil_binding'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('project.id'), unique=True)
    reviewed_json: Mapped[str] = mapped_column(Text)
    source_note: Mapped[str] = mapped_column(Text)
    enabled_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


__all__ = ["SetlDetail", "WeldGasBalance", "AnalysisBigProject", "AnalysisBigMonthProject", "AnalysisBigManual",
           "SOURCE_AUTO", "NUMERIC_COLUMNS"]
