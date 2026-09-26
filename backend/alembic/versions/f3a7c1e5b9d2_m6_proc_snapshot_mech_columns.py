"""m6 proc snapshot mech columns —— 历史段快照补**机械 6 列**

## 为什么加（`TAIL-107` · 用户 2026-09-26 裁定）

用户原话：「导入过程资料，**机械费也要导进去**，**机械费手录仅限于正式启用系统后**，
历史机械费都填在过程资料 excel 里」。

⚠️ 改前的形态是**反的**：`proc_history_snapshot` **只有材料 10 列**（`in_0..in_4` / `out_0..out_4`），
   而 `imp_spec` 还**专门把机械 6 列过滤掉**（口径"机械全段手录，导入只提示不落库"）
   ⇒ 历史机械费**没有落点** ⇒ 只能手录（而手录本是"启用后"才用的）⇒ 用户得把 29 行 × 6 列手工敲一遍。

## 本迁移只做一件事

给 `proc_history_snapshot` 加 `mech_0…mech_5`（顺序/下标照 `domain.MECH_COLUMNS`）。

⚠️ **非空表加非空列必须给 `server_default`**（否则 `upgrade` 对已有行直接报错）——
   金额列给 `0`，语义与手录侧一致（**空按 0 记**；"0 是合法值"）。
   ⭐ 模型那一侧（`models.ProcHistorySnapshot`）**同批声明了 `server_default="0"`** ——
   ⛔ 只加库不加模型 ⇒ `alembic check` 永远报 `modify_default`（`TAIL-102` 那次就是这么红的）。

⚠️ **不预置、不回填任何数据**：历史机械费由用户在页面上**导入**（⛔ 不编数，本项目最忌）。

⚠️ 版本链：本迁移接**当时的真 head** `a2b4c6d8e0f2`（用 `alembic heads` 算的，⛔ 不是拿文本正则推的）。
⚠️ **两个库都要到 head**（开发库 + `.env` 的 `TEST_DATABASE_URL`）—— 漏一个 ⇒ 那条"元数据与测试库
   0 差异"的守卫（`test_schema_drift.py`）会红，那是**对的**（它就是要你两边都升）。

Revision ID: f3a7c1e5b9d2
Revises: a2b4c6d8e0f2
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c1e5b9d2'
down_revision: Union[str, Sequence[str], None] = 'a2b4c6d8e0f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 机械 6 列（下标 ↔ `domain.MECH_COLUMNS`；列名与 `proc_mech_manual` 同款）
_MECH = ("mech_0", "mech_1", "mech_2", "mech_3", "mech_4", "mech_5")


def upgrade() -> None:
    """加机械 6 列（`numeric(18,2) NOT NULL DEFAULT 0`）。"""
    for name in _MECH:
        op.add_column(
            "proc_history_snapshot",
            sa.Column(name, sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    """真反演：把这 6 列删掉（⚠️ 会**丢掉历史段已导入的机械费** —— 只在下定决心退回旧口径时才用）。"""
    for name in reversed(_MECH):
        op.drop_column("proc_history_snapshot", name)
