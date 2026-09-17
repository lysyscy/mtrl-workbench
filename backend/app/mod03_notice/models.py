"""付款通知书（`MOD-03`）。

⚠️ **运行记录（`RunRecord`）已移出本模块** —— 它属 `MOD-02`（抓取/打印的执行记录），
   现定义在 `app.mod02_i8.models`（表名不变、迁移不动）。

依据：
- 《说明书》§4.2.3（分类三类）· §4.2.5（四个金额字段 + 两统计字段）· §4.2.6（手动新增行）
  · §4.2.7（再次导入的合并 / i8 已撤单）· §4.4.2（付款状态判定基准 = 审批金额）
- §9.3（留痕范围：**只**统计两金额 / 调整单 / 项目全名与状态）
- 金额列 **一律** `MONEY`（`numeric(18,2)`，§3.2 全站唯一出口），**不得**自写 Numeric

设计注记（最容易做错的三处）：
1. ⭐ **「三个金额字段」＋ 一个派生列**：唯一 i8 源字段 = **审批金额**；两个旁路 = 统计结算金额 / 统计付款金额；
   列表上的「付款金额」= **派生列**「审批金额 − 已付金额」，可会话级覆盖、**不落库**（`domain.derived_pay_amount`）。
   ⚠️ 原「**付款金额（源）**」（`pay_amount_src`）**已于 2026-09-16 取消**（i8 申请金额与审批金额恒等、零消费点，§4.2.5）。
   ⭐ 「统计付款金额」的**默认值 = 已付金额（有效流水汇总）**（§4.4.7，2026-09-16 起）。
2. **「是否手改」不设状态位** —— 唯一事实来源 = `NoticeStatLog` 的留痕（§4.2.7；副本必然静默过期）。
3. **剔除来源（`exclude_source`）必须区分**：「恢复剔除」**只恢复人工批量剔除**的行，
   规则命中的剔除不因人工操作而放开（要放开只能改规则配置，§4.2.2）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY

# 剔除来源（§4.2.2）
EXCLUDE_NONE = ""                 # 未剔除
EXCLUDE_BY_RULE = "rule"          # 规则命中自动剔除
EXCLUDE_BY_MANUAL = "manual"      # 人工批量剔除（**只有这一类可被「恢复剔除」放开**）


class PaymentNotice(Base):
    """付款通知书。

    - `ph_id`：i8 单据主键（唯一，幂等落库键）
    - `bill_type`：两类版式分流依据 —— `mechanical`（机械类）/ `material`（辅材·集采类）
    - `doc_date`：**单据日期** —— 归月、筛选、归集的**同一条时间轴**（§4.5.4）
    - `fields`：取数时的**原始记录**（列表接口字段，渲染时**打底**用）。
      ⚠️ 版式渲染的正式数据来自 `getInfo` / `getDetInfo` / `getFlowHisForPrint`（见 `print/fields.py`）；
      **签名不落库** —— 渲染时现场从流程接口取（`sign_nodes` / `signatures` 两列已于 2026-09-15 清理）
    """

    __tablename__ = "payment_notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ph_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    bill_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    bill_type: Mapped[str] = mapped_column(String(32), index=True, default="material")
    project_name: Mapped[str] = mapped_column(String(255), default="")
    approve_status: Mapped[str] = mapped_column(String(32), default="")
    amount_approved: Mapped[float] = mapped_column(MONEY, default=0)
    amount_paid: Mapped[float] = mapped_column(MONEY, default=0)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # ---------------- M3 切片 3：付款域字段 ----------------
    doc_date: Mapped[str] = mapped_column(String(10), index=True, default="")   # 单据日期（归月依据）

    biz_type: Mapped[str] = mapped_column(String(64), default="")   # 业务类型（剔除规则 / 分类规则① 用）
    payee: Mapped[str] = mapped_column(String(255), default="")     # 收款单位（分类规则② 用）
    input_by: Mapped[str] = mapped_column(String(64), default="")   # 录入人（剔除规则命中值）

    category: Mapped[str] = mapped_column(String(16), index=True, default="")   # 分类（material/mechanical/jc）
    excluded: Mapped[bool] = mapped_column(Boolean, index=True, default=False)  # 剔除标记（默认隐藏）
    exclude_source: Mapped[str] = mapped_column(String(16), default=EXCLUDE_NONE)

    # 手动新增行（§4.2.6）：**只对手动行开放编辑 / 删除**；i8 抓取回来的行恒为 False（源数据只读）
    # ⚠️ 手动行的 `ph_id` 带 `MANUAL-` 前缀、**不是 i8 单据**（见 `notice_actions.MANUAL_PH_PREFIX`）
    is_manual: Mapped[bool] = mapped_column(Boolean, index=True, default=False)

    # ⚠️ 原「**付款金额（源）**」（`pay_amount_src`）**已于 2026-09-16 取消**（§4.2.5）——
    #    唯一 i8 源字段 = `amount_approved`（审批金额，见上）；不要再加回这个字段。
    # 两个**旁路统计**字段（可手改、上限 = 审批金额、留痕、不被导入覆盖）
    #   ⭐ 「统计付款金额」默认值 = **已付金额（有效流水汇总）**（§4.4.7）
    stat_settle: Mapped[float] = mapped_column(MONEY, default=0)
    stat_paid: Mapped[float] = mapped_column(MONEY, default=0)

    # i8 已撤单（§4.2.7）：保留可查 + 退出全部统计 + 默认隐藏；**有牵涉则硬拦**（不许静默退出）
    i8_revoked: Mapped[bool] = mapped_column(Boolean, index=True, default=False)
    revoked_joint: Mapped[bool] = mapped_column(Boolean, default=False)

    # 归属（§2.5.1）：付款通知书行必须回答"这笔钱属于哪个具体小微"
    ownership_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )


class NoticeStatLog(Base):
    """统计金额手改**留痕**（§4.5.3 · §9.3）—— 改前值 / 改后值 / 改动人 / 时间。

    ⚠️ 本表同时是「**是否手改**」的**唯一事实来源**（§4.2.7 再导入合并的判据）：
       不另开 `edited` 之类的状态位 —— 同一件事存两份，副本必然静默过期。

    ⚠️ 写入只走 `domain.adjust_stat` 的返回值，**不**在别处补写第二套排法。
    """

    __tablename__ = "notice_stat_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("payment_notice.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(32), index=True)      # stat_settle / stat_paid
    before_amount: Mapped[float] = mapped_column(MONEY, default=0)  # 改前值
    after_amount: Mapped[float] = mapped_column(MONEY, default=0)   # 改后值
    changed_by: Mapped[str] = mapped_column(String(64), default="")  # 改动人
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)   # 时间
    note: Mapped[str] = mapped_column(String(512), default="")
