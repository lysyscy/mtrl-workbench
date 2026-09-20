"""`ACC-USR-MGMT-001`（`MOD-15` 用户管理）· **账号主体**的验收断言（《说明书》§1.5.1）。

⚠️ 库级断言**一律非破坏**：本机测试连的是**同一个测试库** ⇒ 每个用例末尾 `s.rollback()`（⛔ 一行不留）。

⚠️ 与 `ACC-X-DEL-001/001-03`（账号软删 = 行保留 / 可识别 / 可恢复）**同源**：
   那条是"删除分档"那一侧看账号，本条是"账号"这一侧看删除 —— 两边都钉，⛔ 不复述对方。

⚠️ **本文件只钉「账号主体」能证明的那几条**（§1.5.1 里不依赖"密码存储方式"的部分）：
   `001-07` 防锁死 · `001-08` 停用 ≠ 删除 · `001-09` 删除 = 软删 · `001-10` 转让管理员 ·
   `001-12` 系统外干系人不设账号。
   ⛔ **密码相关**（`001-04` 新增账号默认「在用·普通用户」/ 密码可为空 · `001-05` 账号重复或为空必须拒 ·
   `001-06` 密码无长度限制可清空）**不在本文件** —— §1.5.1 只说了对**输入**的要求、
   **没说存储方式**，而 §7.8 又要求账号装 i8 凭证（i8 密码**必须可逆**）⇒ 属**口径待定**，
   按「⛔ 口径没定就不动实现」留待定案后补（⛔ 不用别的断言顶替去凑绿）。
"""

from __future__ import annotations

import pytest

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from tests.acc_plugin import acc


def _admin(s):
    """当前**在用的管理员**（由迁移预置的那个 —— 也就是"首个管理员"的真实形态）。"""
    R.ensure_seeded(s)
    return D.active_admins(R.all_users(s))[0]


def _new(s, account: str, name: str = "自检用户"):
    return R.create(s, account=account, name=name)


@acc("ACC-USR-MGMT-001", "001-12")
def test_系统外干系人一律不设账号():
    """claim：「**系统外干系人一律不设账号**」（§1.5.1 的账号表只覆盖「系统内」）。

    ⚠️ 这条最容易被"顺手加个角色"破坏（"给外部人一个只读角色吧"）——
       所以钉的是**角色集合本身是封闭的两值**，而不是"我搜了一圈没看见外部角色"。

    ⚠️ 一并钉 §1.5.1 的另一半（claim `001-02` 后半句）：「**不设业务权限配置界面**」——
       因为「两人业务权限**无区别**」⇒ 角色**只有"能不能管理账号"这一个区别**
       ⇒ 模型里⛔ **不得**出现 `perm_*` / `can_*` 这类**业务权限列**（有列就会有界面）。
    """
    assert D.ROLES == (D.ROLE_ADMIN, D.ROLE_USER), (
        f"角色集合变成了 {D.ROLES} —— §1.5.1 只有「管理员 / 普通用户」两值，"
        "⛔ 多一个值就等于给「系统外干系人」开了个口子（claim `001-12`）")
    cols = set(R.UserAccount.__table__.columns.keys())
    permish = [c for c in cols if c.startswith(("perm", "can_", "allow_", "scope"))]
    assert not permish, (
        f"账号表出现了**业务权限列** {permish} —— §1.5.1：「两人业务权限**无区别**」"
        "⇒ 「角色」的唯一区别是**能不能管理账号**，⛔ 不设业务权限配置（claim `001-02` 后半句）。"
        "⚠️ 有列就会有界面 ⇒ 这是「不设界面」最靠前的那道闸。")


@acc("ACC-USR-MGMT-001", "001-08")
def test_停用不等于删除_行数不变且可来回切():
    """claim：「**停用 ≠ 删除**：**行数不变**、**状态可来回切**」（§1.5.1）。

    ⚠️ 这两件事在**结构上**就该是分开的（`status` vs `deleted_at`）——
       所以断言要**两边都看**：停用时 `deleted_at` 一动不动、删除时 `status` 一动不动。
       ⛔ 只断"停用后 status 变了"是不够的：如果把停用实现成"打个删除标记"，
          状态看着也变了，但那已经是**删除**了（会从列表里消失）。
    """
    with session_scope() as s:
        _admin(s)
        u = _new(s, "__自检_停用__")
        n0 = len(R.all_users(s))

        R.set_status(s, u.id, D.STATUS_DISABLED)
        assert u.status == D.STATUS_DISABLED
        assert u.deleted_at is None, "停用**顺手打了删除标记** —— 那就不是停用了（§1.5.1）"
        assert len(R.all_users(s)) == n0, "停用改了行数 —— claim 明写「行数不变」"
        assert D.state_of(u) == D.STATUS_DISABLED

        R.set_status(s, u.id, D.STATUS_ACTIVE)
        assert u.status == D.STATUS_ACTIVE and u.deleted_at is None, "状态没能**来回切**回来"
        assert len(R.all_users(s)) == n0
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-09")
def test_删除是软删_行保留可识别可恢复():
    """claim：「删除 = **软删**：**行保留**、**账号名可识别**、**可恢复**」（§1.5.1）＋
    `ACC-X-DEL-001/001-03` 的同一件事。

    ⚠️ 三半**逐个**钉（少一半就不是软删）：
       ① **行保留** ⇒ 从表里**查得到**（⛔ 不是 `s.delete`）；
       ② **账号名可识别** ⇒ `account` 字段**原样还在**（软删**不许**去改名/清空 ——
          否则历史留痕里的"张三"就变成一个认不出的字符串了）；
       ③ **可恢复** ⇒ `restore` 之后回到未删、且**账号名还能用来登录**（`by_account` 找得到）。
    ⚠️ 另钉一条**留痕**：`deleted_by` 要记下是谁删的（§1.5.1「软删除**+ 留痕**」。
       只打标记不记人 = 有删无痕）。
    """
    with session_scope() as s:
        actor = _admin(s)
        u = _new(s, "__自检_软删__", name="自检被删人")
        uid, acc_name = u.id, u.account
        n0 = len(R.all_users(s))

        R.soft_delete(s, uid, actor=actor)

        # ① 行保留（查封库能查到、行数不变）
        assert len(R.all_users(s)) == n0, "删除改了行数 —— 那不是软删（§1.5.1）"
        assert R.get(s, uid) is not None, "删完查不到了 —— 那是硬删"
        # ② 账号名可识别
        row = R.get(s, uid)
        assert row.account == acc_name, "软删把账号名改了/清了 —— 历史留痕里的人名会认不出来"
        assert R.by_account(s, acc_name) is not None, "软删后按账号名**找不到**这一行了"
        # ⭐ 留痕
        assert row.deleted_at is not None and (row.deleted_by or "").strip(), \
            "软删没留痕（§1.5.1 是「软删除 **+ 留痕**」——只打标记不记人 = 有删无痕）"
        # ③ 可恢复
        R.restore(s, uid)
        assert R.get(s, uid).deleted_at is None, "恢复不回来"
        assert D.is_deleted(R.get(s, uid)) is False
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-10")
def test_转让管理员后恒只有一个在用管理员():
    """claim：「**转让管理员**：目标变管理员、自己转为普通用户，**恒只有一个在用管理员**」（§1.5.1）。

    ⚠️ 「**恒只有一个**」要**两半都断**（只断"目标变管理员了"会漏掉一半）：
       ① 目标 `admin` ✅ **且** 自己 `user`（⛔ 不是"自己还是管理员" ⇒ 那是两个管理员）；
       ② `active_admins()` 的**长度恰好 1**（这是"恒"字的机械化落点）。
    ⚠️ 另钉三个**必须拦**的边界（少一个转让就能把系统搞成 0 个或 2 个管理员）：
       ⛔ 转给**已停用**的、⛔ 转给**已删除**的、⛔ 转给**自己**。
    """
    with session_scope() as s:
        a = _admin(s)
        b = _new(s, "__自检_被转让__")

        R.transfer_admin(s, a, b)
        assert b.role == D.ROLE_ADMIN, "转让后目标没变成管理员"
        assert a.role == D.ROLE_USER, "转让后自己没转成普通用户 ⇒ 系统里出现了两个管理员"
        assert len(D.active_admins(R.all_users(s))) == 1, "「恒只有一个在用管理员」被破坏"

        # 边界：转给停用的 / 已删的 / 自己 —— 三条都要拦
        c = _new(s, "__自检_停用的__")
        R.set_status(s, c.id, D.STATUS_DISABLED)
        with pytest.raises(MustReportError):
            R.transfer_admin(s, b, c)

        d = _new(s, "__自检_已删的__")
        R.soft_delete(s, d.id, actor=b)
        with pytest.raises(MustReportError):
            R.transfer_admin(s, b, d)

        with pytest.raises(MustReportError):
            R.transfer_admin(s, b, b)
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-07")
def test_防锁死_最后一个在用管理员不能停用也不能删除():
    """claim：「**不能停用 / 删除「最后一个在用管理员」**（防锁死）；**直接调写操作也必须被拦，
    不只靠按钮禁用**」（§1.5.1）。

    ⚠️⚠️ 「**直接调写操作也必须被拦**」是这条的**全部重点** ——
       所以本用例**故意绕开壳**、**直接调 `repository`**（壳里的 `disabled` 是"体验"、
       ⛔ 不是防线；JSON API / 将来的批处理都会走仓储 ⇒ 防线必须在**域层**）。
    ⚠️ 还要证明它**不是"一律拦"**（那样普通操作也没法做了）：
       转让之后，**已经变成普通用户**的那个人**可以**被停用/删除 ⇒ 放行 ✓
    ⚠️ 以及 §1.5.1 后半句「**不能删除自己**」—— ⚠️ 注意旧口径里的「不能**停用**自己」
       **已作废**（§1.5.1 明列）⇒ ⛔ 本用例**不**去要求它，也不去反对它（只是不钉 ——
       免得把作废的规则又钉回绿灯里）。
    """
    with session_scope() as s:
        a = _admin(s)
        assert len(D.active_admins(R.all_users(s))) == 1

        # ① 停用最后一个在用管理员 ⇒ **直接调仓储**也必须拦
        with pytest.raises(MustReportError):
            R.set_status(s, a.id, D.STATUS_DISABLED)

        # ② 删除最后一个在用管理员 ⇒ 拦（⚠️ 用一个**别人**当 actor，先排除"不能删自己"那条）
        b = _new(s, "__自检_防锁死甲__")
        R.transfer_admin(s, a, b)                      # 现在 b 是唯一管理员、a 是普通用户
        with pytest.raises(MustReportError):
            R.soft_delete(s, b.id, actor=a)            # actor 是普通用户，但拦的是"最后一个管理员"

        # ③ ⛔ 不能删除自己（§1.5.1 防锁死后半句）
        with pytest.raises(MustReportError):
            R.soft_delete(s, b.id, actor=b)

        # ④ 反向：**不再是在用管理员**的人 ⇒ 能停用、也能删（证明不是"一律拦"）
        R.set_status(s, a.id, D.STATUS_DISABLED)       # a 已是普通用户 ⇒ 放行
        assert a.status == D.STATUS_DISABLED
        R.soft_delete(s, a.id, actor=b)                # 删普通用户 ⇒ 放行
        assert D.is_deleted(a)
        assert len(D.active_admins(R.all_users(s))) == 1, "折腾一圈后管理员数变了"
        s.rollback()
