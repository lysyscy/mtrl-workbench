"""`MOD-15` 用户管理 · **账号主体**的落库模型（《说明书》§1.5.1 ＋ §7.5）。

依据：《说明书》**§1.5.1「系统内（仅 2 人）」** —— 该表末行明写「**本口径即为最终口径**——
系统与权限一律按此实现」，并列出**已作废**的旧规则（账号名"字母开头≥3 位" · 密码"≥6 位" ·
"只停用不物理删除" · **"不能停用自己"**）⇒ ⛔ 别按那些写。

⚠️⚠️ **密码列是"口径定了才加"的第二批**（⭐ 记一笔过程，别当成一开始就有）：
   片 1 先只做"账号主体"、**一个密码列都没加**，因为 §1.5.1 只说密码
   「**无格式要求、可为空**」（那是**对用户输入的要求**）、**没说存储方式**；
   而 §7.8 又要求账号**还要装 i8 的账号与密码**（「绑定到本系统账号、每人一份」）。
   ⚠️ i8 密码**必须能以明文取出**（要拿去登录 i8）⇒ ⛔ 不能只存哈希 ⇒ **怎么存是口径问题**。
   ⇒ 按铁律「口径没定就不动实现」先做主体（覆盖 6 条判据），
     ⭐ **用户 2026-09-20 裁定「明文」** ⇒ 本批补上三个密码列（本系统密码 ＋ i8 账号密码）
     —— 走的是**新增一次迁移**（⛔ 没去改那个已经打到两个库的旧迁移）。

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

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# ⚠️⚠️ **「不限制长度」在存储层要用 `Text`（不限长），⛔ 不是"给个大一点的 varchar"**：
#    §1.5.1 明写账号名「**不限制字符与长度**」、密码「**无长度限制**」——
#    而 `varchar(N)` 是**一个真实的上限**（N 只是"你还没撞到而已"）。
#    ⭐ 这条**是断言真抓出来的**：`001-06` 拿 300 字的密码去打，Postgres 当场报
#      `value too long for type character varying(255)` ⇒ 口径说"无限制"、实现却会**静默截断/拒绝**。
#    ⇒ 凡口径写"不限制长度"的列，一律 `Text`（⛔ 别用 `String(255)` 那种"看起来够大"的写法）。


class UserAccount(Base):
    """一个**系统账号**（§1.5.1）。

    ⚠️ 表名用 `user_account` 而**不是** `user` —— `user` 在 PG 里是**保留字**，
       裸写会逼得每个 SQL 都加引号（⛔ 那是给后来人埋雷）。
    """

    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: **登录账号** —— §1.5.1「非空 + **不重复**即可（**不限制字符与长度**）」。
    #: ⚠️ 用 `Text`（不限长）—— ⛔ 别改回 `String(N)`：那是**一个真实的上限**，
    #:    而口径明写"不限制长度"。写入前的校验只在 `domain.assert_account_usable`
    #:    （它**只管非空与不重复**，⛔ 不管长度与格式）。
    account: Mapped[str] = mapped_column(Text, nullable=False)

    #: **姓名** —— 历史留痕里的「人名」取它（§1.5.1 末行：「留痕里的改前人**统一取当前登录用户**」）。
    name: Mapped[str] = mapped_column(String(64), default="", server_default="")

    #: 角色：`admin` = 能管理账号 / `user` = 普通。
    #: ⚠️ §1.5.1：「**两人业务权限无区别**」⇒ 「角色」的**唯一**区别就是**能不能管理账号**
    #:    ⇒ ⛔ 本系统**不设业务权限配置**（claim `001-02` 后半句）。
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")

    #: 状态：`在用` / `已停用`（**不含"已删除"** —— 那由 `deleted_at` 表达，见模块头）。
    status: Mapped[str] = mapped_column(String(16), default="在用", server_default="在用")

    #: **本系统登录密码** —— §1.5.1「**无格式要求、可为空**（**建号与改密同一规则**）」。
    #:
    #: ⚠️⚠️ **明文存储**（⭐ 用户裁定 2026-09-20，原话「**明文**」）—— 有意如此，⛔ 别"顺手"改成哈希：
    #:   §1.5.1 明写密码「**无格式要求、可为空**」，且本系统是**科室内部 2 人**用的局域网工具
    #:   （§1.5.1「账号数 2 人使用」）⇒ 加哈希层只会让"用户忘了密码、管理员也看不出"更难处理。
    #:   ⚠️ 但**也不是"随便存"**：它**必须能被管理员读出来告诉用户**（这正是选明文的原因）。
    #:
    #: ⚠️ 用 `Text`（不限长）—— claim `001-06` 明写「密码**无长度限制**、可清空（建号与改密**都不拦**）」，
    #:   ⛔ 别改回 `String(N)`：那会让"无限制"变成一句空话（⭐ 300 字的密码已经实测撞过一次 `varchar(255)`）。
    #:   写法上要保证：**空串 = 未设密码**（那也是合法状态），而**超长**一律照收。
    password: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: **i8 的账号** —— §7.8 L2318：「i8 的账号与密码…**绑定到本系统账号、每人一份**」
    #:   （过渡期暂用 `.env` 的 `I8_USER`；登录体系落地后**每人都必须在自己的账号里填**）。
    i8_user: Mapped[str] = mapped_column(String(64), default="", server_default="")

    #: **i8 的密码** —— ⚠️ 必须**可逆**（要原样拿去登录 i8，见 `mod02_i8/login.py` 的
    #:   `_build_plain`）⇒ 这也是"明文"裁定在**技术上唯一可行**的一档（哈希就登不上了）。
    #: ⚠️ 同样用 `Text`（i8 侧对密码长度**没有**任何已知约束 ⇒ ⛔ 别在这边自己编一个上限）。
    i8_password: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: ⭐ **软删标记**（§1.5.1「删除 = 软删除」）—— 非空 = 已删除。
    #: ⚠️ 这是**全仓第一个真软删**（`ACC-X-DEL-001/001-08` 的"软删档双向开"断言在这里**落地**）。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    #: 软删**留痕**：谁删的（§1.5.1 的"留痕"那一半）。
    deleted_by: Mapped[str] = mapped_column(String(64), default="", server_default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = ["UserAccount"]
