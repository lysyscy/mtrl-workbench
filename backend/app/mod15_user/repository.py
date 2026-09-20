"""`MOD-15` 账号的读写（《说明书》§1.5.1）—— **规则走 `domain.py`、本层只管落库**。

⚠️⚠️ **本层的每个写操作都必须先过 `domain` 的断言**（claim `001-07` 的硬要求：
   「**直接调写操作也必须被拦，不只靠按钮禁用**」）—— ⛔ 不许"壳里禁用了就行"，
   也不许"仓储里再写一份判断"（两份判断必漂）。
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod15_user import domain as D
from app.mod15_user.models import UserAccount

#: 系统**首个**管理员的账号名（`ensure_seeded` 用）。
#: ⚠️ 只预置**一个**，⛔ 不预置"第二个人" —— §1.5.1 说「2 人使用」是**使用现状**、
#:    同时说账号「**可增删**（数量不写死）」⇒ 第二个账号由用户在页面上自建。
#:    ⛔ 也**不把业务人名写进代码/迁移**（写进去就是第二份真相，改一次还得再来一次迁移）。
SEED_ACCOUNT = "admin"
SEED_NAME = "管理员"


def all_users(s: Session) -> list[UserAccount]:
    """**全部**账号（**含软删行** —— §1.5.1 说删除后账号名仍要认得出来）。

    ⚠️ 判重复、防锁死、转让资格都要看这个全集；⛔ 别拿"只查未删的"当默认口径。
    """
    return list(s.execute(select(UserAccount).order_by(UserAccount.id)).scalars())


def get(s: Session, uid: int) -> UserAccount | None:
    return s.get(UserAccount, uid)


def by_account(s: Session, account: str) -> UserAccount | None:
    """按账号名精确找（**含软删行** —— 与 `assert_account_usable` 同一口径）。"""
    want = D.normalize_account(account)
    return next((u for u in all_users(s) if D.normalize_account(u.account) == want), None)


def create(s: Session, *, account: str, name: str = "", role: str = D.ROLE_USER,
           password: str = "", i8_user: str = "", i8_password: str = "") -> UserAccount:
    """建号。⚠️ 规则：**非空 + 不重复**（含已删行）；claim `001-04` 另要求
    「新增账号一律「**在用 · 普通用户**」」—— 所以 `role` **默认就是普通用户**，
    ⛔ 建号时**不给**"直接建成管理员"的入口（管理员只能靠**转让**产生，§1.5.1「恒只有一个」）。

    ⚠️ **密码走 `set_password` 这同一个出口**（⛔ 不在这里另写一遍赋值）——
       §1.5.1 那句「**建号与改密同一规则**」的机械化落点就是**同一个函数**；
       两处各写一遍 = 迟早一处加校验、另一处没加（那就违反"同一规则"了）。
    """
    acc = D.assert_account_usable(account, all_users(s))
    if role not in D.ROLES:
        raise ValueError(f"角色取值非法：{role!r}（只允许 {D.ROLES}）")
    row = UserAccount(account=acc, name=(name or "").strip(),
                      role=role, status=D.STATUS_ACTIVE, deleted_at=None, deleted_by="")
    s.add(row)
    s.flush()
    set_password(s, row.id, password, i8_user=i8_user, i8_password=i8_password)
    return row


def set_password(s: Session, uid: int, password: str, *,
                 i8_user: str | None = None, i8_password: str | None = None) -> UserAccount:
    """**改密（＝建号设密的同一个出口）** —— §1.5.1「无格式要求、可为空（**建号与改密同一规则**）」。

    ⚠️⚠️ **本函数刻意"什么都不校验"** —— 这不是漏写，是**口径要求**：
       claim `001-06` 明写「密码**无长度限制**、**可清空**（建号与改密**都不拦**）」。
       ⇒ ⛔ 别"顺手"加 `len() >= 6`、别加非空校验、别 strip（⚠️ 前后空格也是密码的一部分）。
       ⚠️ 旧口径里的「密码 ≥6 位」**已作废**（§1.5.1 明列）—— 那是最容易"顺手加回来"的一条。

    ⚠️ i8 凭证与登录密码**分开传**（`None` = 本次不动它）—— 改登录密码**不该顺手把 i8 密码清了**。
    """
    row = s.get(UserAccount, uid)
    if row is None:
        raise ValueError(f"账号不存在：id={uid}")
    row.password = password if password is not None else ""
    if i8_user is not None:
        row.i8_user = i8_user
    if i8_password is not None:
        row.i8_password = i8_password
    s.flush()
    return row


def ensure_seeded(s: Session) -> UserAccount:
    """保证**至少有一个在用管理员** —— 否则**谁都进不去、也建不了号**（系统锁死）。

    ⚠️ 为什么放在这里（而不是只靠迁移预置）：迁移预置的是"**首次上线**那一行"，
       而"账号被全删了"这件事**任何时刻都可能发生**（虽然防锁死拦着，但要兜住）——
       本函数**幂等**：已有在用管理员就什么都不做。
    """
    if D.active_admins(all_users(s)):
        return next(u for u in all_users(s) if u.role == D.ROLE_ADMIN)
    row = UserAccount(account=SEED_ACCOUNT, name=SEED_NAME, role=D.ROLE_ADMIN,
                      status=D.STATUS_ACTIVE, deleted_at=None, deleted_by="")
    s.add(row)
    s.flush()
    return row


def set_status(s: Session, uid: int, status: str) -> UserAccount:
    """停用 / 启用（**≤ 两个动作**：`在用` ⇄ `已停用`）。

    ⚠️ 与"删除"**完全两件事**（claim `001-08`：停用 ≠ 删除）：本函数**只碰 `status`**，
       ⛔ 一动不动 `deleted_at` ⇒ 「行数不变、状态可来回切」**由结构保证**。
    ⚠️ 停用**最后一个在用管理员**会被 `domain` 拦下（防锁死）。
    """
    if status not in D.STATUSES:
        raise ValueError(f"状态取值非法：{status!r}（只允许 {D.STATUSES}）")
    row = s.get(UserAccount, uid)
    if row is None:
        raise ValueError(f"账号不存在：id={uid}")
    if status == D.STATUS_DISABLED:
        D.assert_last_admin_protected(all_users(s), row)
    row.status = status
    s.flush()
    return row


def soft_delete(s: Session, uid: int, *, actor: UserAccount) -> UserAccount:
    """**软删**（§1.5.1：账号名保留、不销毁数据、可恢复）—— ⚠️ ⛔ **不 `s.delete`**。

    ⚠️ 两道闸都要走（claim `001-07`：防锁死 ＋ §1.5.1："不能删除自己"）：
       ① 不能删**自己**；② 不能删**最后一个在用管理员**。
       ⚠️ 顺序：**先查自己**（那是"动作本身就不该做"），再查防锁死（那是"做了会锁死"）——
          两条都会被拦，但先报"不能删自己"更贴用户意图。
    """
    row = s.get(UserAccount, uid)
    if row is None:
        raise ValueError(f"账号不存在：id={uid}")
    D.assert_not_self_delete(actor, row)
    D.assert_last_admin_protected(all_users(s), row)
    row.deleted_at = _dt.datetime.now()
    row.deleted_by = (actor.name or actor.account or "")
    s.flush()
    return row


def restore(s: Session, uid: int) -> UserAccount:
    """**恢复**软删的账号（§1.5.1「必要时可恢复」）。

    ⚠️ 恢复**不改 `status`** —— 停用与删除是**两回事**：一个走之前是"已停用"的账号，
       恢复回来后**仍然是已停用**（⛔ 不替用户"顺手启用"）。
    """
    row = s.get(UserAccount, uid)
    if row is None:
        raise ValueError(f"账号不存在：id={uid}")
    row.deleted_at = None
    row.deleted_by = ""
    s.flush()
    return row


def transfer_admin(s: Session, actor: UserAccount, target: UserAccount) -> tuple[UserAccount, UserAccount]:
    """**转让管理员**（§1.5.1）⇒ 返回 `(promote 谁, demote 谁)`。

    ⚠️ 两行**在同一个事务里改**（⛔ 不能"先提后降"分两次）—— 中间态是**两个管理员**，
       若那一步失败就会留下"系统里有两个管理员"，而 §1.5.1 要求**恒只有一个**。
    """
    plan = D.transfer_plan(actor, target)
    promote, demote = plan["promote"], plan["demote"]
    demote.role = D.ROLE_USER
    promote.role = D.ROLE_ADMIN
    s.flush()
    return promote, demote


__all__ = [
    "SEED_ACCOUNT", "SEED_NAME", "all_users", "by_account", "create", "ensure_seeded",
    "get", "restore", "set_password", "set_status", "soft_delete", "transfer_admin",
]
