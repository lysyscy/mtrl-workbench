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

from app.core import session as SESS
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod15_user import domain as D
from app.mod15_user import login as LG
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


# ---------------------------------------------------------- 密码（⭐ 用户裁定「明文」后可钉）


@acc("ACC-USR-MGMT-001", "001-04")
def test_新增账号一律在用普通用户且账号不限格式密码可为空():
    """claim：「新增账号一律「**在用 · 普通用户**」；登录账号**不限格式**、密码**可为空**」（§1.5.1）。

    ⚠️ 「一律」两个字是重点 —— 所以要证明**建不出**别的形态（⛔ 不是"我没去建"）：
       `create` 的 `role` 默认是普通用户、`status` 直接写死在在用；
       ⚠️ 真传一个 `role="admin"` 进去会怎样？—— 本函数**不测它**（那是"建号能不能直接造管理员"，
       属 `001-10` 转让那一条的边界）；这里钉的是**默认行为**就是"在用 · 普通用户"。

    ⚠️ 「登录账号**不限格式**」= ⛔ 不得有"字母开头 / ≥3 位 / 只能字母数字"这类校验
       （§1.5.1 把「账号名：字母开头且 ≥3 位」**明确列为已作废**）⇒
       用**一串很丑但合法**的账号名去打它：`2人·共用（甲）`（数字开头 ＋ 符号 ＋ 中文）。
    ⚠️ 「密码**可为空**」⇒ 不传密码也能建号成功（空串是**合法状态**，不是"未完成的表单"）。
    """
    with session_scope() as s:
        _admin(s)
        # ① 默认就是「在用 · 普通用户」（不传 role / status）
        u = R.create(s, account="2人·共用（甲）")            # ⚠️ 数字开头 ＋ 符号 ＋ 中文
        assert u.role == D.ROLE_USER, "新增账号默认不是普通用户（claim 明写「一律」）"
        assert u.status == D.STATUS_ACTIVE, "新增账号默认不是在用"
        assert u.deleted_at is None
        # ② 密码可为空（不传）
        assert (u.password or "") == "", "密码默认应当为空（§1.5.1「可为空」）"
        # ③ 「不限格式」：上面那个丑账号名**真的建成了**（没被任何格式校验拦掉）
        assert u.account == "2人·共用（甲）"
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-05")
def test_账号重复或为空必须拒绝创建且不得新增行():
    """claim：「登录账号**重复或为空**时必须拒绝创建（**不得新增行**）」（§1.5.1）。

    ⚠️ 括号里那半句「**不得新增行**」是本条的重点：`create` 里**先校验再 `s.add`**，
       如果实现顺序反了（先 add 再校验、靠异常回滚），**同一会话里 `all_users()` 就已经多了一行**
       —— 那种"看起来报了错、其实脏了一行"的形态最难查。
       ⇒ 所以每次失败后都**立刻数一遍行数**。

    ⚠️ 还钉一个**最容易漏**的边界：**已软删的账号名不能再被用**
       （§1.5.1 说软删**保留账号名**、必要时可恢复 ⇒ 那名字**还在占用**；
       ⛔ 若这里只比对"在用的"，就埋了一个"恢复时会撞名"的坑）。
    """
    with session_scope() as s:
        _admin(s)
        R.create(s, account="__自检_唯一__")
        n0 = len(R.all_users(s))

        # ① 重复 ⇒ 拒 ＋ 行数不变
        with pytest.raises(MustReportError) as ei_live:
            R.create(s, account="__自检_唯一__")
        assert len(R.all_users(s)) == n0, "拒绝创建却**新增了行** —— 那就是「先 add 再校验」写反了"

        # ② 空 / 全空白 ⇒ 拒 ＋ 行数不变
        for blank in ("", "   ", "\t"):
            with pytest.raises(MustReportError):
                R.create(s, account=blank)
            assert len(R.all_users(s)) == n0, f"空账号 {blank!r} 被拒绝却新增了行"

        # ③ ⭐ 已软删的名字**仍然占用**（否则"恢复"会撞名）
        actor = _admin(s)
        victim = R.create(s, account="__自检_删了还用__")
        R.soft_delete(s, victim.id, actor=actor)
        n1 = len(R.all_users(s))
        with pytest.raises(MustReportError) as ei_del:
            R.create(s, account="__自检_删了还用__")
        assert len(R.all_users(s)) == n1, "用已删除账号的名字建号被拒，却新增了行"

        # ⚠️⚠️ 这一条是**变异测试替我补上的**：光断"被拒"**不够** ——
        #    因为"在用重名"与"被已删账号占着"**如果实现里不区分**，两边都会抛
        #    `MustReportError`，于是"被拒"这半**看起来也绿**。我第一版就是这么写漏的
        #    （把 `if is_deleted(u):` 改成 `if False:` 后，测试**仍然全绿**）。
        # ⭐ 两件事必须**看得出区别**：
        #    ① 用户得被告知"这名字被一个**已删除**的账号占着，你可以先把它恢复出来" ——
        #       否则他只会看到"已存在"，然后满页找不到那个账号（它已经不显示了）；
        #    ② 这层区分**正是"软删保留账号名"这条口径在代码里的唯一落点**。
        assert "已删除" in str(ei_del.value), (
            "被已删账号占用时，提示里**没说是「已删除」占着** —— 用户会看到一个页面上根本不存在的账号名"
            f"（实际提示：{str(ei_del.value)[:60]}…）")
        assert str(ei_del.value) != str(ei_live.value), (
            "「在用重名」与「被**已删除**账号占着」给了**同一句话** ⇒ 实现里这两种情况没区分开"
            "（§1.5.1 说软删**保留账号名**、必要时可恢复 ⇒ 这一层必须看得见）")
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-06")
def test_密码无长度限制可清空且建号改密同一规则():
    """claim：「密码**无长度限制**、**可清空**（**建号与改密都不拦**）」（§1.5.1）。

    ⚠️ 「无长度限制」要**真拿一个很长的密码**去打（⛔ 不是"我看了代码没有 `len()`"）——
       断言必须能证明**写入路径真的照收**，包括能读回来。

    ⚠️⚠️ 「**建号与改密同一规则**」是这条里最值得机械化的一半：
       它的落点是 **`create` 必须走 `set_password` 这同一个出口**（⛔ 不各写一遍赋值）。
       用法：把 `set_password` **换成一个会记账的替身** ⇒ 若 `create` 自己赋值、
       没走这个出口，下面的断言就**当场变红** ✓
       ⭐ 这样钉的才是"同一规则"这件事本身，而不是"两个函数恰好都没写校验"。
    """
    with session_scope() as s:
        _admin(s)
        long_pw = "长" * 300 + "!@#45"

        # ① 建号时长密码照收
        u = R.create(s, account="__自检_长密码__", password=long_pw)
        assert u.password == long_pw, f"建号把 {len(long_pw)} 字符的密码截了 —— claim 明写「无长度限制」"

        # ② 改密：同样照收；**空串 = 清空**，也必须照收
        back = R.set_password(s, u.id, "短")
        assert back.password == "短"
        R.set_password(s, u.id, long_pw)
        assert R.get(s, u.id).password == long_pw
        R.set_password(s, u.id, "")                    # ⭐ 清空
        assert R.get(s, u.id).password == "", "密码清不掉 —— claim 明写「可清空」"

        # ③ ⭐ 「建号与改密同一规则」⇒ 建号**必须走 `set_password` 这个出口**
        calls = []
        real = R.set_password

        def _spy(sess, uid, password, **kw):
            calls.append(password)
            return real(sess, uid, password, **kw)

        R.set_password = _spy
        try:
            u2 = R.create(s, account="__自检_同规则__", password="走出口的密码")
        finally:
            R.set_password = real
        assert calls == ["走出口的密码"], (
            "建号**没走** `set_password` 这个出口（§1.5.1 要求「建号与改密**同一规则**」）"
            "⇒ 两处各写一遍赋值，迟早一处加校验、另一处没加 —— 那就不是同一规则了")
        assert u2.password == "走出口的密码"

        # ④ 空密码也能建号（与 ② 的"可清空"是同一条规则的两个入口）
        u3 = R.create(s, account="__自检_空密码__")
        assert (u3.password or "") == ""
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-01")
def test_当前登录用户是管理员且管理员恒一个():
    """claim：「**账号数与 §1.5.1 一致（数量在此不复述）**；**当前登录用户 = 管理员**」（§1.5.1）。

    ⚠️ claim 特意写了「**数量在此不复述**」⇒ ⛔ 判据**不许**把"2"写死成硬指标 ——
       §1.5.1 自己写着「账号**可增删**（**数量不写死**）」。所以要钉的是：
       ① 系统**确实有**在用的管理员（否则 §1.5.1「用户本人为管理员」不成立）；
       ② 在用管理员**恒只有一个**（转让那条口径的推论）；
       ③ ⭐ **登录后拿到的"我"就是那个管理员** —— 这才是"当前登录用户 = 管理员"的可执行含义。
    """
    from app.mod15_user.api import _me, _payload

    with session_scope() as s:
        R.ensure_seeded(s)
        users = R.all_users(s)
        admins = D.active_admins(users)
        assert len(admins) == 1, (
            f"在用管理员有 {len(admins)} 个（§1.5.1「用户本人为管理员」+「恒只有一个」要求恰好 1 个）")
        # ⛔ 不把账号数写死：只要求"至少一个账号"，且**管理员是其中之一**
        assert len(users) >= 1, "一个账号都没有 —— 系统进不去（死锁）"
        assert admins[0] in users

        # ③ 「当前登录用户 = 管理员」：整页数据里的 `me` 得是**在用管理员**
        data = _payload(s)
        me = data["me"]
        assert me is not None, "取不到「当前登录用户」—— 壳的顶栏身份标识会空掉"
        assert me["role"] == D.ROLE_ADMIN, (
            f"当前登录用户是「{me['role']}」而不是管理员 —— §1.5.1「**用户本人为管理员**」")
        assert me["state"] == D.STATUS_ACTIVE, "当前登录用户不是「在用」状态"
        # ⚠️ 三态计数要**自洽**（总数 = 在用 + 停用 + 已删）—— 它是页面顶部那行小字的数据源
        c = data["counts"]
        assert c["total"] == c["active"] + c["disabled"] + c["deleted"] == len(users)
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-03")
def test_登出入口与登出动作齐备():
    """claim：「**登出入口与登出动作齐备**」（§1.5.1「用户管理页提供**登出**入口；
    退出后**回到登录页**，**业务数据不受影响**」）。

    ⚠️ 三件**分别**钉（claim 那句话里其实是三件事）：
       ① **登出动作在**（端点存在，且**由后端清 cookie** —— ⛔ 不让壳各自清，那会多出几份"清法"）；
       ② **登录页在**（"退出后回到登录页" ⇒ 那页必须真的存在、且是**表单可提交**的）；
       ③ ⭐ **登出只清会话、不碰业务数据** —— 这条最容易在"顺手做点清理"时被破坏：
          拿一次真库快照比对数一遍，⛔ 不是"我看了代码没写 delete"。
    """
    from app.mod15_user.api import router as m15_router

    paths = {getattr(r, "path", "") for r in m15_router.routes}
    assert "/api/m15/logout" in paths, "没有登出端点（claim：登出入口与登出动作齐备）"
    assert "/login" in paths, "没有登录页 —— 「退出后回到登录页」回到哪去？"
    assert "/m15/login" in paths, "没有登录的**提交**入口（登录页只能看、不能登）"

    # ① 登出必须**由后端清 cookie**（⛔ 不靠壳）
    import inspect

    from app.mod15_user import api as API
    src = inspect.getsource(API.api_logout)
    assert "delete_cookie" in src, (
        "登出端点没清 cookie ⇒ 那样「登出」只是壳上做了个样子，刷新一下人还在登录态")

    # ② 登录页是**表单**（⛔ 不靠 JS —— 它是全系统唯一"进不去就用不了"的页）
    page = API.login_html(next_url="/app")
    assert "<form" in page and 'method="post"' in page, "登录页不是可提交的表单"
    assert 'name="password"' in page, "登录页没有密码输入框"
    # ⚠️ `next` 回跳要**收窄到站内**（⛔ 防开放跳转）
    assert API._safe_next("//evil.com") == "/app", "`next` 放行了协议相对地址（开放跳转）"
    assert API._safe_next("https://evil.com") == "/app", "`next` 放行了站外绝对地址"
    assert API._safe_next("/m03") == "/m03", "站内路径被错拒"

    # ③ 登出**不碰业务数据**：拿真库几张表数一遍
    from sqlalchemy import func, select

    from app.mod03_notice.models import PaymentNotice
    from app.mod04_plan.models import PlanRow
    from app.mod15_user.models import UserAccount

    def snapshot(s) -> tuple:
        return tuple(s.scalar(select(func.count()).select_from(t)) for t in
                     (UserAccount, PaymentNotice, PlanRow))

    with session_scope() as s:
        R.ensure_seeded(s)
        before = snapshot(s)
        LG.sign_out(s)
        assert snapshot(s) == before, (
            "登出动了业务数据 —— §1.5.1 明写「退出后…**业务数据不受影响**」")
        s.rollback()


def _me(s):
    """本文件里的"当前登录账号" —— 就是那个在用管理员（`001-01` 的口径）。"""
    return D.active_admins(R.all_users(s))[0]


def _login_ok(s, u, raw: str):
    return LG.sign_in(s, account=u.account, password=raw)


# ⚠️⚠️ 下面这一节测的是 `001-03`（登出入口与登出动作齐备）的**实现基础**：
#    会话是**密码学件**，它出错的形态是"谁的 cookie 都能伪造"，
#    而那种错**在界面上完全看不出来**（照样登录、照样留痕，只是身份是假的）。
# ⭐ 绑 `001-03` 而不是"另编一个用例号"：登录与登出在 §1.5.1 里本就是**一对**
#    （「登出 = 用户管理页提供登出入口；退出后回到登录页」—— 没有登录页，"退出后回到"就无从谈起）。
#    ⛔ 也不写成 `@acc()`（那是"工具自检"的标法）—— 这些是**业务行为**，不是工具自检。


@acc("ACC-USR-MGMT-001", "001-03")
def test_会话票可验签_篡改与过期一律不认():
    """自签 cookie 的三条底线：**往返认** · **篡改不认** · **过期不认**（＋换密钥不认）。

    ⚠️ 「换密钥不认」这条特别值得测：它保证 `SESSION_SECRET` **真的参与签名**
       —— 如果实现里忘了带密钥（或密钥是常量），前三条**照样全绿**，
       而实际效果是"**任何人都能自己造一张票登进来**"。
    """
    import datetime as dt

    u = "张伟"
    tok = SESS.make(u)
    assert SESS.read(tok) == u, "自己签的票自己认不出来"

    # ① 篡改账号名（把载荷改一位）⇒ 不认
    head, exp, sig = tok.split(".")
    tampered = base64_bump(head) + "." + exp + "." + sig
    assert SESS.read(tampered) is None, "改了账号名还能通过 ⇒ 签名没覆盖载荷"
    # ② 篡改过期时间（把自己续期）⇒ 不认
    assert SESS.read(f"{head}.{int(exp) + 99999}.{sig}") is None, "改了过期时间还能通过"
    # ③ 篡改签名 ⇒ 不认
    assert SESS.read(f"{head}.{exp}.{'A' * len(sig)}") is None, "签名被改还能通过"
    # ④ 过期 ⇒ 不认（拿"过去"的时间签一张）
    old = SESS.make(u, now=dt.datetime.now() - dt.timedelta(hours=SESS.SESSION_HOURS + 1))
    assert SESS.read(old) is None, "过期票还能用 —— 那「退出后回到登录页」就永远等不到"
    # ⑤ 换密钥 ⇒ 不认（证明密钥**真的**参与了签名）
    import app.core.session as _S

    real = _S.secret
    tok2 = SESS.make(u)
    _S.secret = lambda: b"another-secret"                  # type: ignore[assignment]
    try:
        assert SESS.read(tok2) is None, (
            "换掉密钥后旧票**仍然有效** ⇒ 密钥没真正参与签名（任何人都能伪造登录态）")
    finally:
        _S.secret = real                                   # type: ignore[assignment]
    # ⑥ ⭐ 账号名**含 `.`**（§1.5.1：账号名不限制字符）也要能往返
    for weird in ("a.b.c", "...", "张.伟"):
        assert SESS.read(SESS.make(weird)) == weird, (
            f"账号名 {weird!r} 往返失败 —— 拼票时没给账号名做转义（`.` 被当成分隔符了）")
    # ⑦ 空 / 垃圾一律不认（⛔ 不抛异常 —— 调用方只管判"有没有登录"）
    for junk in (None, "", "abc", "a.b", "a.b.c.d"):
        assert SESS.read(junk) is None, f"垃圾值 {junk!r} 应当被判为未登录"


def base64_bump(b64: str) -> str:
    """把 base64 串的**第一个字符换成另一个**（用于"篡改载荷"那条）。"""
    return ("A" if b64[:1] != "A" else "B") + b64[1:]


@acc("ACC-USR-MGMT-001", "001-03")
def test_登录判定的拒绝与最近登录只在成功时写():
    """登录的四条判定 ＋ ⭐「最近登录」的语义（**只在成功那一刻写**）。

    ⚠️ 四条判定里最要紧的是**提示的差异**：
       「账号不存在」与「密码不对」**必须同一句话**（⛔ 否则等于告诉别人哪个账号存在）；
       而「已停用」「已删除」**必须各自说清**（⛔ 否则用户只看到"登录失败"、无从下手）。
    ⚠️ 还有一条**口径后果**：密码「可为空」⇒ **空密码账号必须空着就能登进去**
       —— ⛔ 别在这里"顺手"加一道非空校验（那是把作废的旧口径又加回来）。
    """
    import datetime as dt

    with session_scope() as s:
        u = _me(s)
        # ① 密码不对 ⇒ 拒，提示 = 统一那句
        u2 = R.create(s, account="__自检_登录__", name="自检登录人", password="对")
        with pytest.raises(MustReportError) as e1:
            _login_ok(s, u2, "错")
        assert str(e1.value) == LG.BAD_CREDENTIALS
        # ② 账号不存在 ⇒ **同一句**（不泄露"这个账号存在"）
        with pytest.raises(MustReportError) as e2:
            LG.sign_in(s, account="__根本不存在__", password="x")
        assert str(e2.value) == LG.BAD_CREDENTIALS, (
            "账号不存在时的提示与「密码不对」**不一样** ⇒ 等于对外确认了哪些账号存在")
        # ③ ⭐ 密码为空 ⇒ **空着就能登**（§1.5.1「密码可为空」）
        u3 = R.create(s, account="__自检_空密码__", name="空密码人")
        assert _login_ok(s, u3, "").id == u3.id
        # ④ ⭐ 最近登录：**成功才写**、且**失败不写**
        assert u3.last_login_at is not None, "登录成功却没记「最近登录」"
        t_first = u3.last_login_at
        with pytest.raises(MustReportError):
            _login_ok(s, u2, "又错了")
        assert u2.last_login_at is None, "**登录失败**却记了「最近登录」—— 那列就没意义了"
        # ⑤ 已停用 ⇒ 拒 ＋ 提示说清"已停用"
        R.set_status(s, u3.id, D.STATUS_DISABLED)
        with pytest.raises(MustReportError) as e3:
            _login_ok(s, u3, "")
        assert "已停用" in str(e3.value), "被停用却只说「登录失败」—— 用户不知道要找管理员启用"
        # ⑥ 已删除 ⇒ 拒 ＋ 提示说清"已删除"
        u4 = R.create(s, account="__自检_已删登录__", name="已删人", password="p")
        R.soft_delete(s, u4.id, actor=u)
        with pytest.raises(MustReportError) as e4:
            _login_ok(s, u4, "p")
        # ⚠️ 用「删除」而不是「已删除」做子串：提示原文是「账号「…」**已被删除**（软删）…」
        #    —— ⛔ 别把断言写死在措辞的某个字数上（那句话随时可能改得更清楚，而是非不变）
        assert "删除" in str(e4.value) and "恢复" in str(e4.value), (
            "被软删却只说「登录失败」—— 用户不知道它是被删了、更不知道可以恢复")
        # ⑦ 「最近登录」记的是**登录那一刻**（不是建号时间）
        assert abs((dt.datetime.now() - t_first).total_seconds()) < 60, "「最近登录」不是登录时刻"
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-02")
def test_管理动作齐备且不设业务权限配置():
    """claim：「**管理动作齐备**（建号 / 改密 / 停用启用 / 删除 / 转让管理员），
    且**不设业务权限配置界面**」（§1.5.1 —— 「两人业务权限**无区别**」）

    ⚠️ 两半各钉各的：
    **① 「齐备」** ⇒ 钉在 **`APIRouter` 自己的路由表**上（⛔ 不是"我搜了一眼源码里有这些函数"）——
       函数存在 ≠ 挂上了端点；只有当**每个动作都有可调用的端点**时，"齐备"才成立。
    **② 「不设业务权限配置」** ⇒ ⭐ 钉在 **建号入口的字段集**上：
       若 `CreateIn` 里出现 `role`/`perm*`，那"两人权限无区别"就**当场被推翻**
       （有字段就迟早有界面）⇒ 这一条比"扫一遍页面找权限设置控件"**硬得多、也稳得多**。
    """
    from app.mod15_user.api import CreateIn, router as m15_router

    paths = {getattr(r, "path", "") for r in m15_router.routes}
    actions = {
        "建号": "/api/m15/actions/create",
        "改密": "/api/m15/actions/password",
        "停用启用": "/api/m15/actions/status",
        "删除": "/api/m15/actions/delete",
        "转让管理员": "/api/m15/actions/transfer",
    }
    missing = [name for name, p in actions.items() if p not in paths]
    assert not missing, (
        f"这些管理动作**没有端点**：{missing}（claim 要求「管理动作齐备」）"
        f"\n  实际端点：{sorted(paths)}")
    assert "/api/m15/users" in paths, "没有整页数据的读端点"

    # ② ⛔ 不设业务权限配置 —— 建号入口**不许有角色/权限字段**
    fields = set(CreateIn.model_fields.keys())
    forbid = {f for f in fields if f == "role" or f.startswith(("perm", "can_", "allow_", "scope"))}
    assert not forbid, (
        f"建号入口出现了 {sorted(forbid)} —— §1.5.1「两人业务权限**无区别**」"
        "⇒ 新增账号**一律普通用户**、**不需要选角色**（claim `001-02` 后半句）。"
        "⚠️ 有字段就迟早有界面 —— 这是「不设权限配置」最靠前的那道闸。")
    assert fields >= {"account", "name", "password"}, f"建号入口字段不全：{sorted(fields)}"

    # ②b 整个 mod15 模块里⛔ 不得出现"权限配置"类端点
    import pathlib

    import app
    mod = pathlib.Path(app.__file__).resolve().parent / "mod15_user"
    import re
    bad = []
    for p in sorted(mod.glob("*.py")):
        for k, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"@router\.(get|post)\([^)]*(perm|scope|role[s]?/)", ln, re.I):
                bad.append(f"{p.name}:{k}  {ln.strip()[:60]}")
    assert not bad, f"mod15 里出现了权限配置端点：{bad}"

    # ③ ⭐ 「齐备」还意味着**真的可用**：用户能触发到的拒绝必须是 `MustReportError`
    #    （API 把它转成 `ok=False` ＋ 原文给用户看），⛔ 不是 `ValueError` —— 那会变成 **HTTP 500**，
    #    用户只看到"请求失败"、原因全丢了。
    #    ⭐ 这条是**真机冒烟抓出来的**：拿一个不存在的 id 调改密 ⇒ 500（而不是"账号不存在"）。
    import inspect

    from app.mod15_user import api as API
    src = inspect.getsource(API._run)
    assert "except AppError" in src, (
        "写动作的兜底没在吞 `AppError` ⇒ 业务拒绝会变成 500（原文就丢给用户看不见了）")
    with session_scope() as s:
        _admin(s)
        actor = D.active_admins(R.all_users(s))[0]
        for label, call in (
            ("改密", lambda: R.set_password(s, 999999, "x")),
            ("停用", lambda: R.set_status(s, 999999, D.STATUS_DISABLED)),
            ("删除", lambda: R.soft_delete(s, 999999, actor=actor)),
            ("恢复", lambda: R.restore(s, 999999)),
            ("状态取值非法", lambda: R.set_status(s, actor.id, "已删除")),
        ):
            # ⚠️ 逐个点名：`pytest.raises(MustReportError)` 会在抛别的异常时**照样红**，
            #    所以这里不需要额外断言"不是 ValueError" —— 它**本来就**只放行这一种。
            with pytest.raises(MustReportError):
                call()
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-11")
def test_当前登录用户是唯一出口且不得写死人名():
    """claim：「「当前登录用户」的供给：**留痕的改前人与录入人一律取当前登录用户**，
    **不得写死成某个名字**」（§1.5.1 末行 —— 它自称是"账号体系与业务字段的**唯一接点**"）。

    ⚠️ 这条**现在就能钉**（不依赖登录态）：唯一的出口（`core/identity.py::current_operator`）
       **从第一天就立好了**，而 `MOD-15` 落地时**只改那一个文件** ⇒
       ⛔ 所以现在要钉的是**"不许绕过它写死人名"**，而不是"登录态已经接上了"。

    四半：
    ① **唯一出口**：`current_operator` 全仓**只有一处定义**（⛔ 别各模块自己实现一份）；
    ② **接线到位**：会写留痕 / 录入人的那些模块**都引了它**（⚠️ 对着实体清单，⛔ 不是"我搜了一眼"）；
    ③ ⛔ **没有写死的操作人字面量**：形如 `operator="张三"` 的赋值**全仓不得出现**
       —— 这才是"不得写死成某个名字"的机械化落点；
    ④ ⭐ **占位也不是人名**：未接登录态时的占位必须是**中性词**（`科室用户`），
       ⛔ 不能是"一个人名占位"（那种更难清理 —— 它长得像正常值，搜不出来）。
    """
    import pathlib
    import re

    import app
    from app.core import identity as ID

    root = pathlib.Path(app.__file__).resolve().parent

    # ① 唯一出口（⚠️ 路径一律转 POSIX —— 在 Windows 上 `relative_to` 给的是反斜杠，
    #    直接跟 "core/identity.py" 比会**因为分隔符**而红，那是假的失败）
    defs = [p.relative_to(root).as_posix() for p in root.rglob("*.py")
            if re.search(r"^def current_operator\s*\(", p.read_text(encoding="utf-8"), re.M)]
    assert defs == ["core/identity.py"], (
        f"`current_operator` 的定义出现在 {defs} —— 必须是**唯一出口**"
        "（§1.5.1：「统一取当前登录用户」；两份实现必然漂）")

    # ② 接线到位：会写留痕 / 录入人的模块都得引它
    must = ["mod01_projects/router.py", "mod03_notice/list_data.py", "mod07_setl/api.py",
            "mod08_inv/router.py", "mod11_jc/fetch_service.py", "mod14_config/router.py"]
    missing = [m for m in must
               if "current_operator" not in (root / m).read_text(encoding="utf-8")]
    assert not missing, (
        f"这些模块会写留痕 / 录入人，却没走 `current_operator`：{missing}"
        " ⇒ 它们很可能在写死名字（§1.5.1 明写「不再是一个写死的名字」）")

    # ③ ⛔ 全仓不得出现"写死的操作人字面量"
    bad = []
    pat = re.compile(r"(?:operator|改前人|录入人|改动?人)\s*=\s*[\"']([^\"']{1,12})[\"']")
    for p in sorted(root.rglob("*.py")):
        for k, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = pat.search(ln)
            if m and m.group(1) != "":
                bad.append(f"{p.relative_to(root)}:{k}  → {m.group(0)}")
    assert not bad, (
        "出现**写死的操作人**（§1.5.1：一律取当前登录用户）：\n  " + "\n  ".join(bad))

    # ④ 占位是中性词（⛔ 不是人名占位）
    assert ID.PLACEHOLDER_OPERATOR == "科室用户", (
        f"占位变成了 {ID.PLACEHOLDER_OPERATOR!r} —— 它必须是**中性词**"
        "（⛔ 不能用「一个人名」占位：那种形态最难清理，因为它长得像正常值）")
    assert ID.current_operator().strip(), "取不到当前操作人（不许返回空 —— 留痕字段会变成空串）"

    # ⭐⭐ **正面**：登录态一进上下文，`current_operator()` 就得跟着变 ——
    #    这才叫「统一取当前登录用户」（⛔ 否则前面那几半只是"没有写死"，而不是"用上了登录态"）。
    #    ⚠️ 这条链是 `middleware → core/session.ContextVar → core/identity`，
    #       断任何一环，"留痕里的人名"就悄悄退回 `.env` / 占位 —— **界面上一模一样**。
    SESS.set_current_name("张伟")
    try:
        assert ID.current_operator() == "张伟", (
            "登录态进了上下文，但 `current_operator()` 没取它 ⇒ 留痕里记的还是兜底那个名字")
    finally:
        SESS.set_current_name("")                       # ⚠️ 必须清（`ContextVar` 会串到下一个用例）
    # 清空后要**回落**（⛔ 不是继续返回上一个人 —— 那是"上一个请求的名字留在了这里"）
    assert ID.current_operator() != "张伟", (
        "清了登录态却仍返回上一个人 ⇒ 不带 cookie 的路径（定时任务 / 测试）会把留痕写成别人的名字")
