"""`ACC-USR-MGMT-001`（`MOD-15` 用户管理）· **账号主体与密码**的验收断言（《说明书》§1.5.1）。

⚠️ 库级断言**一律非破坏**：本机测试连的是**同一个测试库** ⇒ 每个用例末尾 `s.rollback()`（⛔ 一行不留）。

⚠️ **本件只钉「账号主体」＋「密码」能证明的那几条**：
   `001-07` 防锁死 · `001-08` 停用 ≠ 删除 · `001-09` 删除 = 软删 · `001-10` 转让管理员 ·
   `001-12` 系统外干系人不设账号 · `001-04` 新增账号一律「在用·普通用户」/ 密码可为空 ·
   `001-05` 账号重复或为空必须拒 · `001-06` 密码无长度限制可清空。
   ⛔ 仍**不**钉"密码怎么存"：§7.8 要求账号装 i8 凭证（i8 密码**必须可逆**）⇒ 属**口径待定**，
   按「⛔ 口径没定就不动实现」留待定案后补（⛔ 不用别的断言顶替去凑绿）。
   ⚠️ 2026-09-20 用户裁定「明文」⇒ `001-04/05/06` 由"留待定案"转为**可钉**（本件 2026-09-21 补记）。

⚠️ **2026-09-21（`T5` 拆分：751 行 ⇒ 三件 ≤400）**——本件此后只管**账号主体与密码**：
   · 登录 · 会话 · 登出 · 身份出口（`001-01` / `001-03` / `001-11`）⇒ `test_acc_usr_login.py`；
   · 管理员闸（`001-02`）⇒ `test_acc_usr_admin.py`。
   ⛔ **断言一字未改**（搬动只动住址）；`_admin` 助手的**主人是本件**（另一件 import 它）。
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


@acc("ACC-USR-MGMT-001", "001-09")
def test_软删的账号仍带出到界面_且在回收站里单独可见可恢复():
    """⭐ 2026-09-21（用户裁定「用户管理要加**回收站**：已删账号**从主列表移出**、单独可见可恢复」）。

    补的是 `001-09` 的**界面那一半** —— 上一支只钉了数据那一半（行在库里、可恢复），
    而"**页面上也要能看见那一行**"此前**只有一句注释、没有断言**（注释不会变红）。

    ⚠️ 两半缺一不可，而且**坏起来是同一个症状**（用户看不到、恢复不了）：

    ① **后端不许过滤**：`GET /api/m15/users` 必须**仍带出**已删账号（`deleted=True`）
       ＋ `counts.deleted` 是**真数**。⛔ 一过滤就同时坏两件事：
       「已删除 N」恒 **0**（对用户说**假话**）＋ 回收站**永远空**（claim 的「可恢复」没了入口）。
       ⇒ `api._payload` 的注释写着"⛔ 别在这里默认过滤掉已删除的"，本条就是那句话的机械化。
    ② **壳不许改切片**：回收站靠**渲染后搬 DOM**（`BIND.m15`，`:has` 语义的选择器是
       **已删除行的唯一特征** —— 操作列那个 `userRestore` 按钮）。⛔ 也不许按中文「已删除」文本
       去匹配：那等于在壳里**再造一份"哪些算已删"的判据**（切片里已经有一份 ⇒ 必然漂）。
    """
    import re

    from app.mod15_user import api as API
    from tests.shell_src import SHELL, with_tbl

    # ---------- ① 后端：软删之后**仍带出来**，且计数是真数 ----------
    with session_scope() as s:
        actor = _admin(s)
        u = _new(s, "__自检_回收站__", name="自检回收站")
        uid, acc_name = u.id, u.account
        R.soft_delete(s, uid, actor=actor)
        s.flush()
        # ⚠️ 这里调 **`_payload(s)`** 而不是 `api_users()`：后者自己开一个会话（另一条连接），
        #    而本用例**不提交**（库级断言一律非破坏）⇒ 跨会话看不到 ⇒ 会得到"没过滤"的**假绿**。
        #    `api_users()` 只是 `with session_scope(): return _payload(s)` 的一行包装。
        d = API._payload(s)

        row = [x for x in d["users"] if x["id"] == uid]
        assert row, (
            "`/api/m15/users` 把已删账号**过滤掉了** —— 回收站会永远空着、"
            "标题里「已删除 N」还会变成 0（对用户说假话）；claim `001-09` 的「可恢复」也没了入口")
        assert row[0]["deleted"] is True, f"已删账号带出来了，但 `deleted` 是 {row[0]['deleted']!r}"
        assert row[0]["account"] == acc_name, "软删改动了账号名 —— 与 `001-09`「账号名可识别」冲突"
        assert row[0]["state"] == D.STATE_DELETED, f"三态不对：{row[0]['state']!r}"
        del_n = sum(1 for x in d["users"] if x["deleted"])
        assert d["counts"]["deleted"] == del_n, (
            f"计数 {d['counts']['deleted']} 与列表里实际 {del_n} 行对不上 —— "
            "两个数必须同源（都从全量 `users` 算），否则界面上的数字会说假话")
        s.rollback()

    # ---------- ② 壳：搬 DOM 的机制在，且壳里没有第二份"哪些算已删"的判据 ----------
    m = re.search(r"function m15Trash\(\)\s*\{(.*?)\n\}", SHELL, re.S)
    assert m, "找不到 `m15Trash` —— 回收站没实现（或改了名）"
    # ⚠️ **先把注释剥掉**再查（本仓的既有教训：注释里会举反例、也会写选择器名 ⇒ 会喂饱/绊倒断言）
    code = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    assert re.search(r"BIND\.m15\s*=", SHELL), (
        "回收站没挂到渲染后钩子 `BIND.m15` 上 ⇒ **它根本不会被调用**"
        "（`render()` 里只有 `if(BIND[VIEW]) BIND[VIEW]()` 这一处调用）")
    assert """querySelectorAll('[data-act="userRestore"]')""" in code, (
        "搬行没有按**已删除行的唯一特征**（操作列那个 `userRestore` 按钮）来选 —— "
        "它是切片 `V.m15` 里判「这一行已删」的**同一处依据**")
    assert "status" not in code, (
        "回收站里又按 `status` 判了一遍「哪些算已删」—— ⛔ 切片 `V.m15` 已经判过 ⇒ 两份必漂；"
        "用 `userRestore` 按钮当选择器就**天然对齐**（那正是切片按同一条件渲染出来的）")
    # ⭐ 2026-09-24（`TAIL-64` P1b）：**判据从「钉字面」改成「钉意图」** ——
    #   原写法断言壳全文里有 `${USERS.map(u=>` 字面；表外壳抽进统一件 `TBL` 之后，那段变成
    #   `...USERS.map(u=>`（进了 `rows:[…]`）⇒ **当场假红**。⛔ 反例：为省事把判据退回钉字面
    #   ⇒ 等于宣布"以后不许抽通用件"（与 `TAIL-64/67` 相反）。
    #   ⇒ 现在断三件事：① 切片**委托 `TBL`**；② rows 仍来自**全量 `USERS`**；③ **`TBL` 内核真把 rows
    #     拼进 `tbody`**（`shell_src.with_tbl()` 把两段拼起来看 —— 照 `test_wired_m09.py` 的 P0 范式）。
    #   自证 = `tools/mut/_mut_tbl.py`（去掉委托 / 掏空内核 ⇒ 必须红）。
    i = SHELL.find("\nV.m15=()=>{")
    j = SHELL.find("\n};", i) if i >= 0 else -1
    m15 = SHELL[i:j] if i >= 0 and j > i else ""
    assert m15, "壳里找不到 `V.m15` 切片"
    assert "TBL({" in m15, "本页主表没走统一出口 `TBL`（`TAIL-64` P1b）"
    assert "USERS.map(u=>" in m15, (
        "`V.m15` 的切片被改了（主表不再从全量 `USERS` 渲染）—— 回收站**必须**靠搬 DOM 实现，"
        "⛔ 不许改原型切片：`ui_parity` 的 `U1` 要它与 `demo/` 逐行一致，登记簿**只准变短**")
    assert "rows.join('')" in with_tbl(m15), (
        "`TBL` 内核没有把 rows 拼进 `tbody` ⇒ 表被掏空了（判据的两段拼接：切片委托 ＋ 内核真做事）")


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
