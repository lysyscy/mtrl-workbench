"""`§7.8`**「i8 的账号与密码…绑定到本系统账号、每人一份」** —— 它的可执行形态（`MOD-15`）。

⚠️ **为什么单独成件**：这条口径的实现在**两个域的交界处** ——
   写入住在 `mod15_user`（账号表那两列），**读取**住在 `core/identity.py`（身份层），
   而**消费方**是 `mod02_i8`（九个抓取/导出入口建的 `I8Client`）。
   把它塞进任何一边的单测里，另外两边就没人管（⭐ 本仓的老毛病：「同一件事横跨三处，
   每处都以为别人测过了」）。

⚠️ 库级断言**非破坏**：临时账号用完即删（`finally` 里逐行删干净）。

⚠️⚠️ **落点**：⭐⭐ 2026-09-21 **已按此处原先的建议，在交付面新建判据点 `001-13`**
   （专管 §7.8「i8 账号与密码**绑定到本系统账号、每人一份**」，由 `tools/oneoff/_acc_add_i8bind.py` 加）
   ⇒ 本文件两条断言**改挂 `001-13`**。
   ⚠️ 原先挂在 `001-11`（「留痕的改前人与录入人一律取当前登录用户，不得写死成某个名字」）——
   那条管的是**留痕的人名**，i8 凭据只是它的一处 consumer（**拿错账号 = 顶了别人的号去抓数**）
   ⇒ **两件事、判词对不上**（本仓的 `T7a` 那类缺口正是这么攒出来的）。
"""

from __future__ import annotations

from app.core import identity as ID
from app.core import session as SESS
from app.core.config import get_settings
from app.core.errors import MustReportError
from app.core.db import session_scope
from app.mod15_user import repository as R

TMP = "__自检_i8甲__"


def _env_creds() -> tuple[str, str]:
    """`.env` 的那一份（过渡期兜底）—— ⛔ 不写死值：`.env` 因机而异。"""
    s = get_settings()
    return (s.i8_user or "").strip(), (s.i8_password or "")


def _drop_tmp() -> None:
    with session_scope() as s:
        for u in R.all_users(s):
            if u.account == TMP:
                s.delete(u)
        s.commit()


def test_i8凭据取当前登录用户绑定且未绑拒抓取():
    """① 绑了 ⇒ 用绑的；② **查无此人** ⇒ 回落 `.env`；③ **绑了但密码空 ⇒ 密码就是空**（⛔ 不回落）；
    ⭐⭐ ④ `TAIL-202`（2026-09-30）：**有身份却没绑 i8 ⇒ 拒绝抓取并给人话提示**（⛔ 不回落）。
    """
    env_user, env_pwd = _env_creds()
    _drop_tmp()
    try:
        with session_scope() as s:
            u = R.create(s, account=TMP, name='自检i8甲', password='')
            R.set_i8(s, u.id, i8_user='i8acc-A', i8_password='i8pwd-A')
            uid = u.id
            s.commit()
        try:
            SESS.set_current_name('自检i8甲')
            assert ID.current_i8_credentials() == ('i8acc-A', 'i8pwd-A'), '绑了 i8 账号却没用它 ⇒ 抓取仍拿 `.env` 的账号去登录（§7.8「每人一份」没落地）'
            SESS.set_current_name('__查无此人的名字__')
            assert ID.current_i8_credentials() == (env_user, env_pwd), '对不上账号时没有回落 `.env` ⇒ 那批不带 cookie 的路径（脚本 / 测试）会直接崩'
            with session_scope() as s:
                R.set_i8(s, uid, i8_user='i8acc-B', i8_password='')
                s.commit()
            SESS.set_current_name('自检i8甲')
            got = ID.current_i8_credentials()
            assert got == ('i8acc-B', ''), f'账号与密码**不是同一个来源**：拿到 {got!r} —— 密码回落了 `.env` ⇒ 混搭登录'
            with session_scope() as s:
                R.set_i8(s, uid, i8_user='', i8_password='')
                s.commit()
            SESS.set_current_name('自检i8甲')
            try:
                ID.current_i8_credentials()
            except MustReportError as exc:
                msg = exc.message
                assert '自检i8甲' in msg and '用户管理' in msg, f'拒绝时的提示没写清「是谁 / 去哪儿填」：{msg!r}'
                for tech in ('.env', 'I8_USER'):
                    assert tech not in msg, f'给用户看的提示里出现了**内部配置名** {tech!r}（守则 §3.1）：{msg!r}'
            else:
                raise AssertionError('有身份却没绑 i8 时**没有拒绝** —— 它悄悄回落用了共享账号 ⇒ 会把同事的 i8 会话顶掉、执行记录也记错人（《说明书》§7.8「未填即拒绝抓取、不回落」）')
        finally:
            SESS.set_current_name('')
    finally:
        _drop_tmp()


def test_i8客户端用当前用户那份凭据且缓存按账号分(monkeypatch):
    """消费方那半：`I8Client` **登录用的是当前用户那份**，**cookie 缓存也按账号分**。

    ⚠️ 为什么必须钉"缓存也按账号"：`cookie_store` 按账号分文件（`artifacts/i8_cookie/<账号>.json`）
       ⇒ 不传账号的话，**A 的会话会被 B 用掉**（一个会话两人共用 ⇒ 一人登录把另一人顶下线，
       而界面上只会看到"抓取时好时坏"）。
    """
    from app.mod02_i8 import client as C

    seen: dict = {}

    class _Result:
        ok = True
        cookie = "COOKIE-X"
        detail = ""

    monkeypatch.setattr(C, "http_login", lambda **kw: (seen.update(kw), _Result())[1])
    monkeypatch.setattr(C.cookie_store, "load",
                        lambda user=None: (seen.__setitem__("load_user", user), None)[1])
    monkeypatch.setattr(C.cookie_store, "save",
                        lambda cookie, source="", user=None: seen.__setitem__("save_user", user))
    monkeypatch.setattr(C, "current_i8_credentials", lambda: ("i8acc-A", "i8pwd-A"))

    c = C.I8Client(allow_kick=False)
    c._ensure_cookie()
    assert seen.get("user") == "i8acc-A" and seen.get("password") == "i8pwd-A", (
        f"`I8Client` 登录时没用当前用户绑定的那份凭据：{seen!r}（仍取的是 `.env`？）")
    assert seen.get("load_user") == "i8acc-A", "读 cookie 缓存时**没带账号** ⇒ 会读到别人的会话"
    assert seen.get("save_user") == "i8acc-A", "写 cookie 缓存时**没带账号** ⇒ 会把会话写到别人的文件里"


def test_set_i8的三种写法省略密码不改解绑一并清空():
    """`repository.set_i8` 的**三态**（`None` / 空串 / 有值）—— 它是"静默抹掉密码"的唯一入口。

    ⚠️ 为什么值得单钉：列表出参**不带** i8 密码（脱敏）⇒ 界面上那个框**默认是空的**；
       ⛔ 若把"空"当成"清空"，**只改 i8 账号**那一步就会把同事的 i8 密码**静默抹掉**
       （下次抓取登不上，而**没有任何地方提示"密码被清了"**）。
    """
    _drop_tmp()
    try:
        with session_scope() as s:
            u = R.create(s, account=TMP, name='自检i8甲', password='')
            R.set_i8(s, u.id, i8_user='acc-1', i8_password='pwd-1')
            assert (u.i8_user, u.i8_password) == ('acc-1', 'pwd-1')
            R.set_i8(s, u.id, i8_user='acc-1')
            assert (u.i8_user, u.i8_password) == ('acc-1', 'pwd-1'), '省略密码把已有密码抹掉了'
            R.set_i8(s, u.id, i8_user='acc-1', i8_password='')
            assert (u.i8_user, u.i8_password) == ('acc-1', ''), '显式空串没能清空密码'
            R.set_i8(s, u.id, i8_user='', i8_password='')
            assert (u.i8_user, u.i8_password) == ('', ''), '解绑只清了账号、留了个没人解释得清的密码'
            s.rollback()
    finally:
        _drop_tmp()

    # 壳那半：**空框 = 不改**（⛔ 不是清空）—— 与后端同一口径，两处必须一致。
    # ⚠️ 两半都要在：① 弹窗里把空串翻成 `null`；② `API.m15I8` 见到 `null` 就**不带那个键**
    #    （带着 `i8_password: null` 也算"传了" —— 后端会当成"要改成 null"而拒掉/写成空）。
