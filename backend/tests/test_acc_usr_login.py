"""`ACC-USR-MGMT-001`（`MOD-15`）· **登录 · 会话 · 登出 · 身份出口**的验收断言（§1.5.1）。

⚠️ 库级断言**一律非破坏**：末尾 `s.rollback()`（⛔ 一行不留）。

⚠️ **2026-09-21 自 `test_acc_usr_mgmt.py`（751 行）整块搬出**（`T5` 拆分）—— **断言一字未改**：
   `001-01` 当前登录用户 = 管理员 · `001-03` 登出入口与登出动作齐备（＋**会话票**那几件）·
   `001-11` 「当前登录用户」是唯一出口、不得写死人名。

⚠️ **会话是密码学件**：它出错的形态是"谁的 cookie 都能伪造"，而那种错**在界面上完全看不出来**
   （照样登录、照样留痕，只是身份是假的）⇒ 这一节单独成件、单独钉。

⚠️ `001-11` 为什么不与 `001-02` 同件：那条钉的是**身份从哪来**（登录态 → `current_operator`），
   不是"谁能管理账号"⇒ 判据邻居是 `001-03`。管理员闸见 `test_acc_usr_admin.py`。
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
from tests.shell_load_helpers import boot_body   # ⭐ ⑤⑥ 要读 `boot()` 的函数体
from tests.shell_src import SHELL                # ⚠️ 壳源码的唯一出口（⛔ 别直接读 index.html）


def _me(s):
    """本文件里的"当前登录账号" —— 就是那个在用管理员（`001-01` 的口径）。"""
    return D.active_admins(R.all_users(s))[0]


def _login_ok(s, u, raw: str):
    return LG.sign_in(s, account=u.account, password=raw)


@acc("ACC-USR-MGMT-001", "001-01")
def test_当前登录用户是管理员且管理员恒一个(monkeypatch):
    """claim：「**账号数与 §1.5.1 一致（数量在此不复述）**；**当前登录用户 = 管理员**」（§1.5.1）。

    ⚠️ claim 特意写了「**数量在此不复述**」⇒ ⛔ 判据**不许**把"2"写死成硬指标 ——
       §1.5.1 自己写着「账号**可增删**（**数量不写死**）」。所以要钉的是：
       ① 系统**确实有**在用的管理员（否则 §1.5.1「用户本人为管理员」不成立）；
       ② 在用管理员**恒只有一个**（转让那条口径的推论）；
       ③ ⭐ **登录后拿到的"我"就是那个管理员** —— 这才是"当前登录用户 = 管理员"的可执行含义。
       ⚠️ ③ 要**仿真出会话**才算验到（`_me` 只认登录态）⇒ 本支用 `monkeypatch` 给用户名，
          等价于"中间件从 cookie 解出名字"那一步。

    ⭐⭐ 2026-09-21（用户裁定「**收紧：未登录不回落首个管理员**」）—— 一并补钉**反向**那一半：
       ⛔ **没有会话 ⇒ `me` 必须是 `None`**（⛔ 不是"回落成首个管理员"）。
       ⚠️ 本条此前**正是被那个回落喂饱的**：它调 `_payload(s)` 时**根本没有会话**，
          却照样拿到管理员 ⇒ 断言是绿的，但它证明的是"**回落有效**"，而不是"登录后是管理员"。
          而那个回落的代价是**实测过**的：不带 cookie 调 `/api/m15/users`，返回的 `me` 就是管理员行
          ⇒ 所有写动作的闸（`assert_is_admin(_me(s))`）在未登录时**全部放行**
          （能建号 / 删号 / 停用 / 转让管理员）。
    """
    from app.core import session as SESS
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

        # ⓪ **没有会话** ⇒ 「当前登录用户」**取不到**（⛔ 不许回落成首个管理员）
        monkeypatch.setattr(SESS, "current_name", lambda: "")
        assert _me(s) is None, (
            "**没有会话时 `_me` 竟然还给出了一个账号** —— 那就是「回落首个管理员」又回来了："
            "任何不带 cookie 的请求都会被当成管理员 ⇒ 写动作的闸全部失效（用户 2026-09-21 裁定要掐掉它）")
        assert _payload(s)["me"] is None, "整页数据里 `me` 也不许在未登录时给出一个人"

        # ③ **有会话** ⇒ 拿到的"我"就是在用管理员
        monkeypatch.setattr(SESS, "current_name", lambda: admins[0].name or admins[0].account)
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

    # ④ 壳：**"没有身份"**与**"取数失败"**必须分得开 —— ⛔ 别把取数失败说成"你没登录"（那是假话，
    #    而且用户会照着去登录、白折腾）；同时"没身份"时要说清**怎么办**（按钮全是禁用的）。
    from tests.shell_src import SHELL

    assert "WHO_STATE = me.id ? 'in' : 'none';" in SHELL, (
        "壳没有把「后端答了但没身份」记下来 —— 顶栏就没法区分「未登录」与「取数失败」")
    assert "WHO_STATE==='none'" in SHELL, (
        "顶栏没按 `WHO_STATE` 分叉 ⇒ 两种情形会显示同一句话（必有一句是假话）")
    assert 'href="/login"' in SHELL, (
        "「没身份」时没有**去登录**的出口 —— 用户只会看到按钮全灰、以为页面坏了")


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
    # ⚠️ 2026-09-21（`§19` 四个暂留件收口）：系统设置页搬进新壳 ⇒ 那个"写留痕的模块"从
    #    `mod14_config/router.py`（服务端渲染 ＋ PRG，**已删**）换成 `mod14_config/settings_api.py`
    #    （JSON 保存路径，同样 `save(..., operator=current_operator())`）—— ①③④ 半一字未动。
    must = ["mod01_projects/router.py", "mod03_notice/list_data.py", "mod07_setl/api.py",
            "mod08_inv/router.py", "mod11_jc/fetch_service.py", "mod14_config/settings_api.py"]
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

    # ⑤ ⭐⭐ **壳里也不许有"写死的身份"**（2026-09-21 加宽观测面 —— 原先只扫 `.py`，漏了壳）。
    #    ⚠️ 实测踩到：壳里 `CUR` 的初值写着 `{id:'U01',acc:'zhangwei',name:'张伟',role:'admin'}`
    #       —— 而库里根本没有这个账号 ⇒ **顶栏首屏显示的是假人名**，进过一次「用户管理」才变真名。
    #       用户看到的是"**同一个人两个名字**"，而且**全程没有任何报错** ⇒ 只有这条断言拦得住。
    m_cur = re.search(r"let CUR\s*=\s*\{([^}]*)\}", SHELL)
    assert m_cur, "壳里找不到 `CUR`（当前登录用户）的声明 —— 顶栏身份没了着落"
    # ⚠️ 正则用**三引号原始串**写：它里面要出现引号字符，普通原始串会被转义写法搞乱
    #    （2026-09-21 实测：那种写法让字符串**提前闭合** ⇒ 报一处莫名其妙的 `unmatched ')'`）。
    quoted_identity = re.search(r"""(?:id|acc|name|role)\s*:\s*["'][^"']+["']""", m_cur.group(1))
    assert not quoted_identity, (
        "壳里 `CUR` 的初值带着**写死的身份**（人名 / 账号 / id / 角色）—— 那是**假值**："
        f"实际命中 {quoted_identity.group(0) if quoted_identity else m_cur.group(0)}"
        "  ⇒ 首屏顶栏会先说一个假名字、进过「用户管理」才变真名（必须留空，由后端填）")

    # ⑥ ⭐ **首屏就得是真身份**：`boot()` 里必须去取它
    #    （⛔ 不是"等用户点进用户管理页才取" —— 那样顶栏第一帧必然是假的或空的）。
    boot = boot_body()
    assert "soft('当前登录用户', reloadWho)" in boot, (
        "`boot()` 没有（逐路容错地）取当前登录用户 ⇒ 顶栏第一帧是空的/假的"
        "（必须走 `soft('当前登录用户', reloadWho)` —— ⛔ 也不许让它把首屏拖成串行等待）")
    assert "esc(CUR.name" in SHELL, "顶栏身份没从 `CUR.name` 渲染（那取的是哪儿）"



# ==================================================== 001-14 · 未登录 ⇒ 写动作一律拒（2026-09-25 补）
# ⚠️ 搬进本件（而不是单开一件）的记录：单开新件时 `acc_report` 报"未绑定"（绑定在结果档里明明有）
#    ⇒ 疑为"新测试件"的认领问题 ⇒ 搬进本件后立刻变绿（见 journal 2026-09-25 §67/§68）。


@acc("ACC-USR-MGMT-001", "001-14")
def test_未登录只能看_写动作一律拒():
    """未登录：**读放行**（落到路由层 404）· **写一律拒**（闸门先拦 401）· 登录/登出放行 · 带票写放行。

    口径 =《说明书》§1.5.1（2026-09-21 用户裁定「未登录 = 无身份」）：「未登录**只能看**，**写动作一律拒**」。
    ⚠️ 口径**不是**「未登录只能访问登录页」（更严、会把不带会话的真机自检全打白屏）⇒ 本判据专钉"**读放行**"这一半。
    ⚠️ 断言用"**幽灵路径**"（既不存在、也不碰业务）⇒ 只比**闸门先裁决了没有**：读 ⇒ 404 · 写 ⇒ 401（⛔ 不是 404）。
    """
    from fastapi.testclient import TestClient

    from app.core import session as SESS
    from app.main import create_app

    ghost = "/api/__gate_probe__"
    anon = TestClient(create_app())

    # ① 读：未登录也**放行**
    assert anon.get(ghost).status_code == 404, "未登录的读被拦了 —— 与 §1.5.1「只能看」冲突"

    # ② 写：未登录 ⇒ **闸门先拦**（401，且**不是** 404 ⇒ 证明是进业务之前拦的）
    for method in ("post", "put", "patch", "delete"):
        r = getattr(anon, method)(ghost)
        assert r.status_code == 401, f"未登录的 {method.upper()} 没被拦（{r.status_code}）"
        assert "未登录" in r.json().get("message", ""), "401 得说清原因（禁静默）"

    # ③ 登录 / 登出本身放行（否则永远登不进来）
    assert anon.post("/api/m15/logout").status_code != 401, "登出被自己的闸拦住了"

    # ④ 带有效会话票 ⇒ 写**放行**（落到路由层 ⇒ 404）
    logged = TestClient(create_app())
    logged.cookies.set(SESS.COOKIE_NAME, SESS.make("闸门自检"))
    assert logged.post(ghost).status_code == 404, "带票的写被拦了 —— 那已登录的人也没法干活"
