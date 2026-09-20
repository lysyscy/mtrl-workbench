"""`MOD-15` 用户管理的 **JSON API** —— 前端壳直接接数据（同 `mod07` / `mod09` / `mod11` 的做法）。

⚠️ 本层**不写任何判定**：全部调 `repository`，而 `repository` 又调 `domain` 的断言
   （claim `001-07` 那句「**直接调写操作也必须被拦**」在这里表现为：**API 里没有第二份校验**）。

⚠️ 写动作**恒 HTTP 200**，成败看 `ok` 标志（同 `mod03` / `mod07` / `mod09` 的约定）——
   「账号重复」「不能停用最后一个管理员」都是 §1.5.1 规定的**可预期的拒绝**，
   要把那句话**原样给用户看**；若回 HTTP 400，壳只会看到"请求失败"、原因就丢了。

⚠️⚠️ **出参一律不带密码**（⛔ 连 `i8_password` 也不带）—— 列表接口是**最容易被顺手带出去**的地方。
   明文裁定的理由之一是"管理员能读出密码告诉用户"，但**壳里并没有这个出口**
   （列表列是 登录账号/姓名/角色/状态/最近登录/操作）⇒ ⛔ 我不自己发明一个"查看密码"端点；
   要不要给这个出口**登记待裁定**（见计划）。

⚠️ 关于「**当前登录用户**」：登录态（登录页 ＋ 会话）**还没做** ⇒ 本层按 `core/identity.py` 的
   既有设计取 `current_operator()`，再**对到一个账号**；对不上就回落到**首个在用管理员**。
   ⭐ `identity.py` 的模块头写着「等 `MOD-15` 落地时**只改本文件**」——
   登录态落地时改的是**那里**，本层不用动。

⚠️ ⚠️ 本页**不设业务权限配置**（§1.5.1「两人业务权限**无区别**」）⇒ 本文件里⛔ 不会有
   任何 "权限 / perm / scope" 之类的端点或字段 —— claim `001-02` 后半句的机械化落点。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import session_scope
from app.core.errors import AppError
from app.core.identity import current_operator
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from app.mod15_user.models import UserAccount

router = APIRouter(tags=["mod15"])


# ============================================================ 形状


def _row(u: UserAccount) -> dict:
    """一个账号 → JSON。

    ⚠️⚠️ **逐个字段列出来**（⛔ 不是 `{c.name: getattr(u, c.name)}` 那种"整个模型倒出去"）——
       后者会在**下一次加列**时（比如加个 `token` / `reset_code`）**静默**把新字段泄出去。
       ⭐ 白名单是"默认安全"的写法：漏列一个字段，用户看得见（少一列）；
         黑名单漏一个，**没人看得见**（除非出事）。
    """
    return {
        "id": u.id,
        "account": u.account,
        "name": u.name,
        "role": u.role,
        "state": D.state_of(u),                 # 三态：在用 / 已停用 / 已删除
        "deleted": D.is_deleted(u),
        "deleted_by": u.deleted_by or "",
        # ⚠️ i8 账号**只出账号名、不出密码**（§7.8：每人一份 ⇒ 界面要能看出"还没填"）
        "i8_user": u.i8_user or "",
        "i8_bound": bool((u.i8_user or "").strip()),
    }


def _me(s) -> UserAccount | None:
    """**当前登录用户** → 账号行。

    ⚠️ 现在的"登录态"其实还不存在 ⇒ 按 `core/identity.py` 取当前操作人，
       先按**姓名**、再按**账号**去匹配；都对不上（占位「科室用户」）就回落到
       **首个在用管理员** —— §1.5.1「**用户本人为管理员**」⇒ 过渡期的合理默认。
    ⚠️ 这**不是**"写死成管理员"：`current_operator()` 一旦接上登录态，这里自然就对了。
    """
    who = current_operator().strip()
    users = R.all_users(s)
    for u in users:
        if not D.is_deleted(u) and (u.name or "").strip() == who:
            return u
    for u in users:
        if not D.is_deleted(u) and (u.account or "").strip() == who:
            return u
    admins = D.active_admins(users)
    return admins[0] if admins else None


def _payload(s) -> dict:
    """整页数据：账号列表 ＋ 当前登录用户 ＋ 三态计数。

    ⚠️ 返回**全部**账号（**含已删除**）—— §1.5.1 说软删后"账号名保留、历史留痕里的人名仍认得出来"，
       页面上也要能看见那一行（`V.m15` 里就有"已删除"这一态和"恢复"按钮）。
       ⛔ 别在这里"默认过滤掉已删除的"。
    """
    me = _me(s)
    users = R.all_users(s)
    return {
        "users": [_row(u) for u in users],
        "me": (_row(me) if me is not None else None),
        "counts": {
            "total": len(users),
            "active": sum(1 for u in users if D.state_of(u) == D.STATUS_ACTIVE),
            "disabled": sum(1 for u in users if D.state_of(u) == D.STATUS_DISABLED),
            "deleted": sum(1 for u in users if D.is_deleted(u)),
        },
        "roles": list(D.ROLES),
        "states": [D.STATUS_ACTIVE, D.STATUS_DISABLED, D.STATE_DELETED],
    }


def _flash(kind: str, message: str) -> dict:
    return {"ok": kind == "ok", "kind": kind, "message": message}


def _run(fn) -> dict:
    """跑一个写动作：**可预期的拒绝**返回 `ok=False` ＋ 原文（⛔ 不抛 400）。

    ⚠️ 只吞 `AppError`（业务可预期）—— ⛔ 别写成裸 `except Exception`：
       那会把真 bug（`AttributeError` / 库错误）也变成一句"操作失败"，从此没人查得动。
    """
    try:
        return _flash("ok", fn() or "已完成")
    except AppError as e:
        return _flash("err", e.message)


# ============================================================ 读


@router.get("/api/m15/users")
def api_users(request: Request) -> dict:  # noqa: ARG001 —— 形状与别的模块一致（便于将来加筛选）
    """账号列表 ＋ 当前登录用户（`MOD-15` 的整页数据）。"""
    with session_scope() as s:
        return _payload(s)


# ============================================================ 写（5 类管理动作 · §1.5.1）


class CreateIn(BaseModel):
    """建号：账号（**非空 + 不重复**，⛔ 不限格式与长度）＋ 姓名 ＋ 初始密码（**可为空**）。"""

    account: str = ""
    name: str = ""
    password: str = ""


class IdIn(BaseModel):
    """只认一个账号 id（删除 / 恢复 / 转让）。"""

    id: Any = 0


class PwdIn(BaseModel):
    """改密：⚠️ `password` **无格式要求**（⛔ 不 strip —— 前后空格也是密码的一部分）。"""

    id: Any = 0
    password: str = ""


class StatusIn(BaseModel):
    """停用 / 启用（≤ 两个动作；`已删除` 不在这里 —— 那是"删除"，见 `/delete` 与 `/restore`）。"""

    id: Any = 0
    status: str = ""


def _uid(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        raise AppError(f"账号 id 不合法：{x!r}") from None


@router.post("/api/m15/actions/create")
def api_create(req: CreateIn) -> dict:
    """**建号**（§1.5.1 管理动作之一）——新账号**一律「在用 · 普通用户」**（claim `001-04`）。

    ⚠️ ⛔ **不接受 `role`**：管理员只能靠**转让**产生（§1.5.1「恒只有一个管理员」）
       ⇒ API 里就没有"建一个管理员"这条路（有入口就有人用）。
    """
    def go() -> str:
        with session_scope() as s:
            u = R.create(s, account=req.account, name=req.name, password=req.password)
            return f"已创建普通用户 {u.name or u.account}（{u.account}）"
    return _run(go)


@router.post("/api/m15/actions/password")
def api_password(req: PwdIn) -> dict:
    """**改密**（建号设密与它**同一个出口** ⇒ 「建号与改密同一规则」，claim `001-06`）。"""
    def go() -> str:
        with session_scope() as s:
            u = R.set_password(s, _uid(req.id), req.password)
            return f"{u.name or u.account} 的密码已更新" + ("" if req.password else "（已清空 · 密码可为空）")
    return _run(go)


@router.post("/api/m15/actions/status")
def api_status(req: StatusIn) -> dict:
    """**停用 / 启用**（§1.5.1）—— ⚠️ 与"删除"是两回事（claim `001-08`：只碰 `status`）。"""
    def go() -> str:
        with session_scope() as s:
            u = R.set_status(s, _uid(req.id), req.status)
            return (f"账号 {u.name or u.account} 已停用 · 停用不删除，历史留痕里仍能认出这个人"
                    if u.status == D.STATUS_DISABLED
                    else f"账号 {u.name or u.account} 已启用")
    return _run(go)


@router.post("/api/m15/actions/delete")
def api_delete(req: IdIn) -> dict:
    """**删除 = 软删**（§1.5.1：账号名保留、不销毁数据、必要时可恢复）。

    ⚠️ 两条防锁死闸都在 `repository`（不能删自己 ＋ 不能删最后一个在用管理员）——
       本层**不重复判断**（⛔ 两份判断必漂）。
    """
    def go() -> str:
        with session_scope() as s:
            actor = _me(s)
            u = R.soft_delete(s, _uid(req.id), actor=actor or R.ensure_seeded(s))
            return f"账号 {u.name or u.account} 已删除（软删）· 账号名保留，历史留痕里仍能认出这个人"
    return _run(go)


@router.post("/api/m15/actions/restore")
def api_restore(req: IdIn) -> dict:
    """**恢复**软删的账号（§1.5.1「必要时可恢复」）—— ⚠️ 恢复**不改 `status`**（停用是另一回事）。"""
    def go() -> str:
        with session_scope() as s:
            u = R.restore(s, _uid(req.id))
            return f"账号 {u.name or u.account} 已恢复" + ("" if u.status == D.STATUS_ACTIVE else "（该账号仍是「已停用」）")
    return _run(go)


@router.post("/api/m15/actions/transfer")
def api_transfer(req: IdIn) -> dict:
    """**转让管理员**（§1.5.1）—— 转让后对方为管理员、自己转为普通用户 ⇒ **恒只有一个管理员**。"""
    def go() -> str:
        with session_scope() as s:
            actor = _me(s) or R.ensure_seeded(s)
            target = R.get(s, _uid(req.id))
            if target is None:
                raise AppError(f"账号不存在：id={req.id!r}")
            promote, demote = R.transfer_admin(s, actor, target)
            return (f"管理员已转让给 {promote.name or promote.account}；"
                    f"{demote.name or demote.account} 现在是普通用户，不再能管理账号")
    return _run(go)


__all__ = ["router"]
