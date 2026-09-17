"""项目档案（`MOD-01` 主数据）—— 切片 2 最小字段 ＋ 字段留痕。

依据：
- 《说明书》§2.2（三类项目）· §2.3（四个名字）· §2.3.1（命名约束）· §2.6（属性矩阵）· §2.7（状态）
- 下沉专项《全自动建档-实施计划》§二 决策 1/2/3/5/6
- 工程坑 1.2-5：schema 变更唯一入口 = 迁移；落库走 ORM

⚠️ **唯一约束只设在「仓库名」上**（`decision 2`）—— 壳没有仓库 ⇒ NULL（Postgres 视多个 NULL 互不冲突）；
   **不设在全名上** —— 壳与具体小微**共用同一个全名**（1 壳 + N 小微）。
⚠️ **占位行不另加字段**（决策 5）：靠 `warehouse_name LIKE '未建仓-%'` 判定。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# --- 类型 / 状态字面量（**实现约定**；口径回《说明书》§2.2 / §2.7）---
TYPE_NORMAL = "normal"      # 普通项目
TYPE_SHELL = "shell"        # 小微壳（无仓库）
TYPE_SMALL = "small"        # 具体小微（借壳全名，有自己的仓库）

STATUS_ACTIVE = "active"        # 在建
STATUS_ARCHIVED = "archived"    # 归档

# 占位仓库名前缀（决策 5：靠前缀判定，不加字段）
PLACEHOLDER_PREFIX = "未建仓-"

# 留痕字段白名单（§9.3：**只有**项目全名与项目状态留痕；展示名 / ord **不留痕**）
LOGGED_FIELDS: tuple[str, ...] = ("name_full", "status")


class Project(Base):
    """项目档案行（一仓库一行；壳无仓库）。

    - `warehouse_name`：**唯一标识 / 候选键**（§2.7.4），不允许人工修改（§2.3.1）—— 壳为 NULL
    - `name_full`：项目全名（可人工改、**需留痕**）—— 只作 i8 抓取匹配（§2.7.4）
    - `disp`：展示名（默认取仓库名、可改、不留痕）
    - `match_keywords`：小微识别关键词（挂在小微身上，可多个、允许重复）
    - `ord`：自定义排序序号（挂档案行上；**不留痕**）
    """

    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("warehouse_name", name="uq_project_warehouse_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_type: Mapped[str] = mapped_column(String(16), index=True, default=TYPE_NORMAL)
    name_full: Mapped[str] = mapped_column(String(512), index=True, default="")
    warehouse_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    disp: Mapped[str] = mapped_column(String(255), default="")
    phid: Mapped[str] = mapped_column(String(64), index=True, default="")
    status: Mapped[str] = mapped_column(String(16), index=True, default=STATUS_ACTIVE)
    ord: Mapped[int] = mapped_column(Integer, index=True, default=0)
    parent_shell_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True
    )
    match_keywords: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # --- 派生属性（不落库；口径 = 决策 5 / §2.2）---
    @property
    def has_warehouse(self) -> bool:
        return bool(self.warehouse_name)

    @property
    def is_placeholder(self) -> bool:
        """占位行（仓库名 = `未建仓-序号`）。"""
        return bool(self.warehouse_name) and self.warehouse_name.startswith(PLACEHOLDER_PREFIX)

    @property
    def is_shell(self) -> bool:
        return self.project_type == TYPE_SHELL

    @property
    def is_archived(self) -> bool:
        return self.status == STATUS_ARCHIVED


class ProjectFieldLog(Base):
    """项目字段留痕（§9.3 留痕范围）。

    仅 **项目全名** 与 **项目状态** 留痕（改前值 / 改后值 / 改动人 / 时间）；
    ⚠️ **展示名 · `ord` 不留痕**（展示名只是显示别名、`ord` 只是展示顺序）。
    """

    __tablename__ = "project_field_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(32))  # name_full / status
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(String(255), default="")  # 如「壳自动跟随归档」
    changed_by: Mapped[str] = mapped_column(String(64), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
