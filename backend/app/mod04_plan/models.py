"""付款计划（`MOD-04`）—— 计划行模型。

依据：《说明书》§4.3.3（数据入口与 Excel 结构）· §4.3.4（审查规则）· §4.3.6（历史保留）。

⚠️ **审查结果不存字段**（`ACC-PLAN-AUDIT-001 / 001-01`）：它按行**实时派生**（数据一变判定随之变）
   ⇒ 本表**没有** `audit_result` 列，判定由 `domain.audit()` 现算。
⚠️ 可手改列（付款时间 / 付款方式 / 备注）**落库、不被导入覆盖、不留痕**（不属 §9.3 留痕范围）。
⚠️ **无效列原样入库、不参与审查、不要求修正**（§4.3.3）⇒ 整条原始行进 `raw`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY

# 项目列匹配状态（匹配键 = **展示名 / 仓库名**，§4.3.3）
MATCH_MATCHED = "matched"        # 命中 1 条
MATCH_UNMATCHED = "unmatched"    # 命中 0 条 ⇒ 标「未匹配」
MATCH_AMBIGUOUS = "ambiguous"    # 命中多条 ⇒ 标「重名 N 条」

# 可手改列（§4.3.3）—— ⚠️ 不留痕
EDITABLE_COLUMNS: tuple[str, ...] = ("pay_date", "pay_method", "remark")


class PlanRow(Base):
    """付款计划行（一次导入的一行；按月归档）。"""

    __tablename__ = "plan_row"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year_month: Mapped[str] = mapped_column(String(7), index=True)   # 导入前**先选月份**（001-01）
    project_input: Mapped[str] = mapped_column(String(255), default="")  # Excel「项目」列填报值（留悬停）
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    match_status: Mapped[str] = mapped_column(String(16), default=MATCH_UNMATCHED)
    match_candidates: Mapped[int] = mapped_column(Integer, default=0)  # 命中条数（重名 N 条）

    doc_no: Mapped[str] = mapped_column(String(64), index=True, default="")  # 单据号（**允许为空**）
    flow_amount: Mapped[float] = mapped_column(MONEY, default=0)      # 该流程金额
    planned_amount: Mapped[float] = mapped_column(MONEY, default=0)   # 本月预付款金额

    pay_date: Mapped[str] = mapped_column(String(32), default="")     # 可手改
    pay_method: Mapped[str] = mapped_column(String(32), default="")   # 可手改（现汇/承兑/供应链/其他）
    remark: Mapped[str] = mapped_column(String(512), default="")      # 可手改

    forced_through: Mapped[bool] = mapped_column(Boolean, default=False)  # 强制通过
    forced_remark: Mapped[str] = mapped_column(String(512), default="")   # ⚠️ 强制通过**必须**留备注

    # 手动行标记（§9.5「导入只清理并重写**自动行**，手动行与其手改内容不被触碰」）
    # ⚠️ 付款计划**当前没有**手动新增入口（§4.3 的能力清单未要求）⇒ 本列恒 False；
    #    它是为 §9.5 这条通用铁律留的**落地点**：导入只处理 is_manual=False 的行。
    is_manual: Mapped[bool] = mapped_column(Boolean, index=True, default=False)

    raw: Mapped[dict] = mapped_column(JSON, default=dict)             # 原始行（无效列原样入库）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
