"""差异登记的落库模型（`MOD-12` · 《说明书》§5.8.3 / `DEV-R-06` / §8.3 状态机）。

⚠️ 本表是**手工清单**：行的唯一来源是人点「＋ 登记差异」——
   ⛔ 不存在"由库存单据 / 过程资料自动生成行"的写入路径（§5.8.3）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.mod12_diff.domain import DEFAULT_STATUS, OWNER_INV


class DiffRecord(Base):
    """一条差异登记（半年度对账时人工登记，量级"半年十几~几十笔"）。"""

    __tablename__ = "diff_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    seq: Mapped[int] = mapped_column(Integer, index=True)
    """编号的**序号**（`code` 由它派生）。

    ⚠️ 与 `code` **分两列**存：判据点 `001-02` 要求"编号**不撞既有行**"——
       本页**可以删行** ⇒ 若拿"条数 + 1"当编号，删一条再新增就会**撞号**。
       ⇒ 序号取 `max(seq) + 1`（`domain.next_seq`），删行不回退。
    """

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    """业务编号（`DF01` / `DF02` …）—— ⚠️ **不是主键**：主键是 `id`（§9.8.2-5「按 id 定位」）。"""

    month: Mapped[str] = mapped_column(String(7), index=True)
    """核算月（`YYYY-MM`）—— 对账按核算月看（§5.8.3）。"""

    owner: Mapped[str] = mapped_column(String(16), default=OWNER_INV, server_default=OWNER_INV)
    """**归属** —— ⚠️ **恒为「库存单据」**（§5.8.3）。列本身就留着，是为了让"它只能取这一个值"
    这件事**在数据里看得见**（而不是靠"反正没人写别的"）。写入口由 `domain` 强制，⛔ 不开放给调用方。"""

    project_name: Mapped[str] = mapped_column(String(256))
    """项目**全名**（落库写全名，显示走展示名 —— 与全站同口径，§2.7.4）。"""

    detail: Mapped[str] = mapped_column(Text)
    """差异内容（一句话说明差在哪 —— 半年度对账时要能看懂）。"""

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    """差异金额 —— **带符号**（+ 上调 / − 下调）。⚠️ 与 `MOD-08` 调整单差额**同源同形态**；
    尚无对应调整单的差异按登记额记**正数**（§5.8.3）。⛔ 无上限概念（差异金额不设 cap）。"""

    status: Mapped[str] = mapped_column(String(16), index=True, default=DEFAULT_STATUS)
    """状态 —— `待核对 → 已核对 / 差异保留`（§8.3，**手工标记**）。⚠️ 取值主人 = `domain.STATUSES`。"""

    remark: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by: Mapped[str] = mapped_column(String(64), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


__all__ = ["DiffRecord"]
