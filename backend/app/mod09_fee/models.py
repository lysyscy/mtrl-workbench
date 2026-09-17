"""`MOD-09` 特殊费用月报表 · **手填项**表（`ENT-*` 未单列；口径主人 = 《说明书》§5.5）。

⚠️ **只存手填项** —— 唯一自动项（安全文明施工费）**不落库**：它由库存单据明细**现场派生**
   （`domain.auto_amount`）⇒ 落了库就是第二份真相（§5.2.3「材料数据单向流」同理）。

键 = **核算年月 ＋ 项目**（§5.5）：
- 比较 / 筛选一律用**仓库名**（§2.7.4）；
- **写库按档案 id**（§2.7.4 末行）⇒ 本表存 `project_id`（FK，**已命名**），
  仓库名不可人工修改（§9.8-4）⇒ 与「仓库名各存一份」等价，且不产生第二份可漂的键。

取值判据 = `domain.amount_problem`（**只拦非数字，允许 0 与负数**，§5.5 / §8.4 第 ③ 档）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, MONEY


class FeeManualItem(Base):
    """一条手填项（某核算年月 · 某项目下的一行费用）。"""

    __tablename__ = "fee_manual_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ym: Mapped[str] = mapped_column(String(7), index=True, default="")            # 核算年月（§9.2）
    project_id: Mapped[int] = mapped_column(                                # 档案 id（§2.7.4 写库按 id）
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    item_name: Mapped[str] = mapped_column(String(128), default="")               # 项名（可改、可重名）
    amount: Mapped[float] = mapped_column(MONEY, default=0)                      # 金额（允许 0 与负数）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = ["FeeManualItem"]
