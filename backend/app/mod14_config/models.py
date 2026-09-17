"""系统设置的落库模型（`MOD-14` · §7.8）。

⚠️ 本页设置项**必须留痕**（§7.8 ②）—— 与「规则配置」的**硬删不留痕**（§9.4）**有意不同**：
   版式 ID 配错会**印错正式件**、i8 地址配错会**抓错数据**，属**高风险**，故留痕。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    """设置项的**当前值**（键清单 = `app/core/app_settings.py::SPECS` 的 `key`）。

    ⚠️ `value` 为空串 = 「未设置」⇒ 取值**回落到 `.env`**（§7.8 ② 的优先级）。
    """

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), default="", server_default="")
    updated_by: Mapped[str] = mapped_column(String(64), default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AppSettingLog(Base):
    """设置项**变更留痕**：改前值 / 改后值 / 改动人 / 时间（§7.8 ②）。"""

    __tablename__ = "app_setting_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    old_value: Mapped[str] = mapped_column(String(512), default="", server_default="")
    new_value: Mapped[str] = mapped_column(String(512), default="", server_default="")
    operator: Mapped[str] = mapped_column(String(64), default="", server_default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


__all__ = ["AppSetting", "AppSettingLog"]
