"""`MOD-15` 用户管理 · **账号主体**的落库模型（《说明书》§1.5.1 ＋ §7.5）。

依据：《说明书》**§1.5.1「系统内（仅 2 人）」** —— 该表末行明写「**本口径即为最终口径**——
系统与权限一律按此实现」，并列出**已作废**的旧规则（账号名"字母开头≥3 位" · 密码"≥6 位" ·
"只停用不物理删除" · **"不能停用自己"**）⇒ ⛔ 别按那些写。

⚠️⚠️ **本文件只装"账号主体"，⛔ 一个密码列都没有** —— 这是**有意切的**：
   §1.5.1 只说密码「**无格式要求、可为空**」（那是**对用户输入的要求**），**没说存储方式**；
   而 §7.8 L2318 又要求账号**还要装 i8 的账号与密码**（「绑定到本系统账号、每人一份」）。
   ⚠️ i8 密码**必须能以明文取出**（要拿去登录 i8）⇒ ⛔ 不能只存哈希 ⇒ **怎么存是口径问题**。
   ⇒ ⭐ 按本仓铁律「口径没定就不动实现」，**先把不依赖它的部分做完**（能覆盖 6 条判据），
     密码列**等口径定下来再补一次迁移**（⚠️ 本仓加列是常规操作，已有 26 个迁移）。

⚠️⚠️ **「删除」是软删，而账号名要**继续占着** —— 这是本表最容易做错的一处**：
   §1.5.1：「删除 = **软删除**（账号名**保留**、不销毁数据，历史留痕里的人名**仍认得出来**，
   **必要时可恢复**）」⇒ ⭐ **软删行不能把账号名让出来**，否则「恢复」时会撞名；
   而 claim `ACC-USR-MGMT-001/001-05` 又要求「登录账号**重复**或为空时必须拒绝创建」——
   那个"重复"**必须把已删除的行也算进去**。
   ⇒ 所以 `account` 上的**唯一约束不过滤软删**（`uq_user_account`）—— ⚠️ 这是**有意**的，⛔ 别"顺手"改成部分唯一索引。

⚠️ **三态 = 两列的组合**（⛔ 不是三个 `status` 取值）：`status` ∈ {在用, 已停用}，
   再叠 `deleted_at` 是否为空 ⇒ 「在用 / 已停用 / **已删除**」。
   ⭐ 这样「停用 ≠ 删除」（claim `001-08`：行数不变、状态可来回切）**由结构保证** ——
      停用只改 `status`、删除只填 `deleted_at`，两件事**碰不到同一个字段**。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserAccount(Base):
    """一个**系统账号**（§1.5.1）。

    ⚠️ 表名用 `user_account` 而**不是** `user` —— `user` 在 PG 里是**保留字**，
       裸写会逼得每个 SQL 都加引号（⛔ 那是给后来人埋雷）。
    """

    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: **登录账号** —— §1.5.1「非空 + **不重复**即可（**不限制字符与长度**）」。
    #: ⚠️ 列宽给到 64 只是"够用"，⛔ **不是**长度校验（口径明说"不限制长度"）；
    #:    真要超长由实现方按库能力兜，⛔ 别在这里写 `len() <= 64` 那种校验。
    account: Mapped[str] = mapped_column(String(64), nullable=False)

    #: **姓名** —— 历史留痕里的「人名」取它（§1.5.1 末行：「留痕里的改前人**统一取当前登录用户**」）。
    name: Mapped[str] = mapped_column(String(64), default="", server_default="")

    #: 角色：`admin` = 能管理账号 / `user` = 普通。
    #: ⚠️ §1.5.1：「**两人业务权限无区别**」⇒ 「角色」的**唯一**区别就是**能不能管理账号**
    #:    ⇒ ⛔ 本系统**不设业务权限配置**（claim `001-02` 后半句）。
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")

    #: 状态：`在用` / `已停用`（**不含"已删除"** —— 那由 `deleted_at` 表达，见模块头）。
    status: Mapped[str] = mapped_column(String(16), default="在用", server_default="在用")

    #: ⭐ **软删标记**（§1.5.1「删除 = 软删除」）—— 非空 = 已删除。
    #: ⚠️ 这是**全仓第一个真软删**（`ACC-X-DEL-001/001-08` 的"软删档双向开"断言在这里**落地**）。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    #: 软删**留痕**：谁删的（§1.5.1 的"留痕"那一半）。
    deleted_by: Mapped[str] = mapped_column(String(64), default="", server_default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = ["UserAccount"]
