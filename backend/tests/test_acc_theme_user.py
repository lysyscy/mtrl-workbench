"""`ACC-UI-THEME-001` **001-06**：主题选择**按用户隔离**（需连库 ⇒ 与 `test_theme.py` 分开放）。

⚠️ 为什么不塞进 `test_theme.py`：那个文件的定位是「**离线 · 不连库**」（守的是变量层机制）——
   本判据要**真账号 ＋ 真会话 ＋ 真 HTTP**，混进去会把那个文件的定位搞浑
   （⭐ 而"这个文件连不连库"是**回来看的人**最先要判断的事）。

⚠️ 判据原文：「主题选择**按用户隔离**：A 与 B 各自的选择互不影响；**未设置时回落默认套**」
   —— 它长期列在基线的 `A_waiting_for_impl` 里，备注「**属 M6 登录体系**」：
   没有"用户主体"，"A 与 B" 根本无从谈起 ⇒ **`m15` 片 3 落地后本条才可钉** ✓

⭐⭐ 钉法（**为什么要走 HTTP 那一层**）：
   本条最容易被"看起来对"的实现骗过去 —— 比如把主题存成一个**全局变量**或**进程级缓存**：
   单用户测起来**全绿**（A 设了、A 读到了），而**两个人用起来互相覆盖**。
   ⭐ 所以必须**两个独立的会话**（两个 cookie jar）打**同一个 URL**（`/static/theme.css`），
     看它们**拿到不同的 CSS** —— 这才是"隔离"的可执行含义。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.db import session_scope
from app.main import app
from app.mod03_notice import page as P
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from tests.acc_plugin import acc

#: 挑两套**互不相同**的主题（⚠️ 断言里要确认它们真的不同 —— ⛔ 别假设）
THEME_A = "靛青"
THEME_B = "松绿"


def _login(account: str, password: str) -> TestClient:
    """开一个**独立会话**（自己一个 cookie jar）并登录。"""
    c = TestClient(app)
    r = c.post("/m15/login", data={"account": account, "password": password, "next": "/app"},
               follow_redirects=False)
    assert r.status_code == 303, f"登录没成功（{r.status_code}）—— 后面的隔离就无从谈起"
    return c


def _css(c: TestClient) -> str:
    r = c.get("/static/theme.css")
    assert r.status_code == 200, f"/static/theme.css 拿不到（{r.status_code}）"
    return r.text


@acc("ACC-UI-THEME-001", "001-06")
def test_主题按用户隔离且未设置回落默认套():
    """两个账号各选各的主题，**互不影响**；都没设置时各自回落默认套。"""
    # ⚠️ 先证明这两套真的不同（否则整条断言是空的 —— 两边都是同一份 CSS 也会"通过"）
    assert THEME_A != THEME_B
    assert P.render_theme(THEME_A) != P.render_theme(THEME_B), (
        f"主题「{THEME_A}」与「{THEME_B}」产出的 CSS **一模一样** ⇒ 本判据会变成假绿")

    with session_scope() as s:
        R.ensure_seeded(s)
        admin = D.active_admins(R.all_users(s))[0]
        acc_a, acc_b = admin.account, "__自检_主题乙__"
        # ⭐ 甲：把预置管理员的主题**清成未设置**（保证起点干净，⛔ 别依赖上一次跑剩什么）
        R.set_theme(s, admin.id, "")
        R.set_password(s, admin.id, "")
        # 乙：新建一个普通用户（未设置主题）
        b = R.create(s, account=acc_b, name="主题自检乙", password="")
        R.set_theme(s, b.id, "")
        s.commit()                                   # ⚠️ 跨 HTTP 请求 ⇒ 必须落库

    try:
        ca, cb = _login(acc_a, ""), _login(acc_b, "")

        # ① 都未设置 ⇒ 各自回落**默认套**
        assert _css(ca) == P.render_theme(P.DEFAULT_THEME), "甲：未设置时没回落默认套"
        assert _css(cb) == P.render_theme(P.DEFAULT_THEME), "乙：未设置时没回落默认套"

        # ② 甲选一套 ⇒ **只有甲变**
        assert ca.post("/api/m15/theme", json={"theme": THEME_A}).json()["ok"], "甲设主题失败"
        assert _css(ca) == P.render_theme(THEME_A), "甲设了主题，但拿到的 CSS 不是那一套"
        assert _css(cb) == P.render_theme(P.DEFAULT_THEME), (
            "⭐ 甲改了主题，**乙也跟着变了** ⇒ 主题没按用户隔离（很可能是全局变量/进程缓存）")

        # ③ 乙也选一套（另一套）⇒ 两边**各是各的**
        assert cb.post("/api/m15/theme", json={"theme": THEME_B}).json()["ok"], "乙设主题失败"
        assert _css(cb) == P.render_theme(THEME_B), "乙设了主题，但拿到的 CSS 不是那一套"
        assert _css(ca) == P.render_theme(THEME_A), "⭐ 乙改了主题，把甲的那份也改了 ⇒ 没隔离"

        # ④ 清空 = 回到"未设置" ⇒ 又回落默认（⛔ 不是"保留上一次的选择"）
        assert ca.post("/api/m15/theme", json={"theme": ""}).json()["ok"]
        assert _css(ca) == P.render_theme(P.DEFAULT_THEME), (
            "清空主题后没回落默认套 —— 「未设置」与「选了默认套」被混成一件事了")
        assert _css(cb) == P.render_theme(THEME_B), "甲清空主题把乙的也清了"

        # ⑤ 非法主题名 ⇒ 回落默认（跟上 `001-07` 的裁决：**回落**，不是报错）
        assert cb.post("/api/m15/theme", json={"theme": "__不存在的主题__"}).json()["ok"]
        assert _css(cb) == P.render_theme(P.DEFAULT_THEME), (
            "非法主题名没有显式回落 ⇒ 页面可能半套样式（`001-07` 已定：回落默认套）")

        # ⑥ ⚠️ **未登录**也要有样式（⛔ 不能白屏）—— 未登录拿默认套
        anon = TestClient(app)
        assert _css(anon) == P.render_theme(P.DEFAULT_THEME), "未登录时 /static/theme.css 没给默认套"
    finally:
        # ⚠️ 本条**故意落库**（要跨 HTTP 请求）⇒ 必须自己收拾干净
        with session_scope() as s:
            for u in R.all_users(s):
                if u.account == "__自检_主题乙__":
                    s.delete(u)
            for u in R.all_users(s):
                if u.role == D.ROLE_ADMIN:
                    u.theme = ""
            s.commit()


@acc("ACC-UI-THEME-001", "001-06")
def test_主题偏好存在账号上而不是进程里():
    """隔离的**结构性**一半：偏好得落在**账号那一行**上（⛔ 不是模块级变量 / 全局缓存）。

    ⚠️ 为什么还要单独钉这一条：上一条是**行为**（两个会话互不影响），
       它挡得住"服务端把主题存在一个人身上"，但挡不住"存在**当前进程**里"
       （单机跑、单进程时看着也对，**重启即丢、多进程即错**）。
       ⇒ 所以直接查"那一行里有没有这个字段"。
    """
    from app.mod15_user.models import UserAccount

    cols = set(UserAccount.__table__.columns.keys())
    assert "theme" in cols, "账号表里没有 theme 列 ⇒ 主题偏好没落在账号上（那就不叫'按用户'）"

    with session_scope() as s:
        R.ensure_seeded(s)
        u = D.active_admins(R.all_users(s))[0]
        R.set_theme(s, u.id, THEME_A)
        s.commit()
    # ⭐ 换一个会话再看（证明**落的是库**，不是内存里那个对象）
    with session_scope() as s:
        u = D.active_admins(R.all_users(s))[0]
        assert D.effective_theme(u) == THEME_A, "换个会话就读不到了 ⇒ 偏好没落库"
        assert R.theme_by_account(s, u.account) == THEME_A, (
            "`theme_by_account`（`/static/theme.css` 的取数口）读不到刚存的偏好")
        R.set_theme(s, u.id, "")
        s.commit()
