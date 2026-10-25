"""`MOD-02` i8 接入层 · 运行记录（执行记录 / 技术台账）。

依据：
- 《说明书》**§3.1.3**：每次抓取**须保留一条执行记录**（时间 · 抓取对象 · 结果 · 失败原因），
  供看板提示「本月尚未抓取」「最近一次抓取失败」。
- 《技术栈选型分析》§3.1「运行记录」：时间 · 类型（抓取 / 打印）· 对象 · 结果 · 失败原因；**不参与业务统计**。

⚠️ **2026-09-15 搬家**：本表原挂 `mod03_notice`，但它属 **`MOD-02`**（抓取执行记录）⇒ 移到本模块，
   避免 `mod01`/`mod03` → 互相反向依赖。**表名与列不变、迁移不动。**
⚠️ 技术台账、不参与任何业务统计；按 `run_type` 区分：`fetch`（抓取）/ `print`（打印）/ `export_pdf`（仅导出 PDF）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RunRecord(Base):
    """运行记录（执行记录 / 技术台账）。"""

    __tablename__ = "run_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String(32), index=True)  # fetch / print / export_pdf
    target: Mapped[str] = mapped_column(String(512), default="")  # 对象：月份 / 单号集合
    status: Mapped[str] = mapped_column(String(32), default="running")  # running / success / partial / failed
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    triggered_by: Mapped[str] = mapped_column(String(64), default="manual")
    error_message: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # 逐单据结果 / 失败原因
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
