"""机械费工作稿、来源事实及确认预览；有效金额仍只有 ProcMechManual。"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MechanicalWorkbenchRecord(Base):
    __tablename__ = "mechanical_workbench_record"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MechanicalWorkbenchPreview(Base):
    __tablename__ = "mechanical_workbench_preview"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
