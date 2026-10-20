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


def test_切换器住系统设置且清单由该页自取且不刷新页面():
    """⭐ 2026-09-21（用户报障「换主题无效 ＋ 换完被扔回看板」）⇒ 三件事一起钉住：

    ① **入口住 `MOD-14` 系统设置**（用户裁定「移过去更符合逻辑」）+ ⛔ 旧入口不留（壳里只许有一处）；
    ② ⭐⭐ **主题清单由「系统设置」那一页自己取** —— 这是那个 bug 的真因：
       清单原先只在 `reloadM15()` 里取，而**系统设置页永不执行它** ⇒ `THEMES_LIST` 恒为空
       ⇒ 下拉一个选项都没有、`themeSet` 把**空串**写回后端 ⇒ 换主题**看着在做、实际没换**，
       而且**全程不报错**（判据只能靠这条结构性断言拦）。
    ③ **就地生效**（`applyThemeLive`）＋ ⛔ **壳里不许再用 `location.reload()` 换主题** ——
       整页刷新会把壳的视图状态清零 ⇒ 用户在系统设置上点一下，就被**扔回看板**。

    ⚠️ 「用户是否觉得颜色好看」断言测不了；这里钉的是**机制**（进得去、取得到、切得动、不跳页）。
    """
    import re

    from tests.shell_load_helpers import loaders, page_load
    from tests.shell_src import SHELL

    # ① 入口只许一处（搬走之后别把旧的那个留下 —— 两处会各改各的）
    # ⚠️ 按**标签**数（`<… data-act="themeSet"`），⛔ 不用裸 `in` ——
    #    注释里提一句"这个动作叫什么"就会把裸计数喂饱（2026-09-21 实测踩到，同类坑第三次）。
    entries = re.findall(r"""<[^>]*data-act=["']themeSet["']""", SHELL)
    assert len(entries) == 1, (
        f"`themeSet` 的入口出现了 {len(entries)} 处（都应是**一个标签**）—— "
        "必须**只有一处**（2026-09-21 已从「用户管理」搬进「系统设置」）")
    # ② 那一页要自己取清单
    pl, ls = page_load(), loaders()
    assert "外观主题" in pl.get("set", []), (
        "`PAGE_LOAD['set']` 里没有「外观主题」⇒ 系统设置页取不到主题清单（下拉会是空的）")
    assert "外观主题" in ls, "`LOADERS` 里没有「外观主题」这一路"
    m15 = re.search(r"async function reloadM15\(\)\s*\{(.*?)\n\}", SHELL, re.S)
    assert m15, "找不到 `reloadM15` 的函数体"
    assert "m15Theme" not in m15.group(1), (
        "主题清单又被塞回 `reloadM15` 了 —— 系统设置页**不进**那一页 ⇒ 下拉恒为空、"
        "`themeSet` 写回空串（症状 = 「换主题没用」且**不报错**）")
    # ②b ⭐⭐ **取主题名必须先认 `data-theme`**（2026-09-21 实测踩到的坑）：
    #   切换器从 `<select>` 换成 `<button>` 之后，写成"`t.value === undefined` 才用 `data-theme`" ——
    #   ⚠️ 而 **`<button>` 也有 `value` 属性**（默认 **空串**）⇒ 走 `value` 分支 ⇒ 把**空串**写回后端
    #   ⇒ 主题回落默认套 ⇒ 症状正是用户报的「**换了没反应**」（而且**全程不报错**）。
    i_ts = SHELL.find("themeSet:async t=>")
    assert i_ts > 0, "找不到 `themeSet` 动作 —— 落点变了"
    # ⚠️⚠️ **先把块注释剥掉再比顺序** —— 这条注释里**必须**提到 `t.value`（就是为了讲这个坑），
    #    而本断言读的是**文本** ⇒ 不剥注释就会被自己的注释绊倒（同一类坑今天第 4 次）。
    #    ⭐ 通法：凡"读源码文本"的断言，**先把注释剥掉**，否则它会惩罚"把坑写在注释里的人"。
    body_ts = re.sub(r"/\*.*?\*/", "", SHELL[i_ts:i_ts + 1200], flags=re.S)
    i_ds, i_val = body_ts.find("dataset.theme"), body_ts.find("t.value")
    assert i_ds > 0 and i_val > 0, "`themeSet` 既没读 `data-theme` 也没读 `value` —— 主题名从哪儿来？"
    assert i_ds < i_val, (
        "`themeSet` **先读了 `t.value`** ⇒ 按钮那条路上它恒为空串（`<button>` 也有 `value`）"
        " ⇒ 把空串写回后端、主题回落到默认套（用户看到的是「换了没反应」）")

    # ③ 就地生效、不刷新
    assert "function applyThemeLive(" in SHELL, "缺「就地换主题」的函数 `applyThemeLive`"
    assert "applyThemeLive();" in SHELL, "`themeSet` 没有调 `applyThemeLive()`（换了不生效？）"
    assert not re.search(r"location\.reload\s*\(", SHELL), (
        "壳里又出现 `location.reload()` —— 用来换主题时它会把用户从当前页**扔回看板**"
        "（用户 2026-09-21 报的就是这个）")


def test_每套主题都给出一份配色标本且主色互不相同():
    """⭐ 2026-09-21（用户反馈「换主题**感觉不到颜色变化**」）⇒ 把"看得见差异"机械化：

    `GET /api/m15/theme` 除了清单，还要给**每套自己的配色标本**（`palette`）——
    壳拿它画「每套一张卡」（底色/文字/主色都用该套自己的取值）。

    ⚠️⚠️ **主色必须两两不同**：这是"换一套看得出来"的**最低条件**。实测那次报障的成因里，
       浅色系几套只差一个主色 ⇒ 真要是**两套主色一样**，换它等于没换（而且**没有任何报错**）。
    ⚠️ 取值一律来自**唯一真源**（`page.render_theme`）⇒ 这里顺便钉住"没有第二份色值表"。
    """
    from app.mod15_user.api import api_theme

    d = api_theme()
    pal = d.get("palette") or []
    assert [p["name"] for p in pal] == list(d["themes"]), (
        "配色标本没有覆盖**全部**主题（或顺序与清单不一致）⇒ 界面上会缺卡")
    for p in pal:
        assert p.get("pri", "").startswith("#") and len(p["pri"]) in (4, 7), (
            f"「{p['name']}」的主色取值不是色值：{p.get('pri')!r} —— ⛔ 别自己拼，回真源取")
        for k in ("bg", "sf", "bd", "tx", "on"):
            assert p.get(k, "").startswith("#"), f"「{p['name']}」的 `{k}` 没取到（卡片会缺一块）"
    pris = [p["pri"] for p in pal]
    assert len(set(pris)) == len(pris), (
        "有两套主题的**主色完全相同** ⇒ 换它等于没换（用户会说「没反应」）："
        f"{[x for x in pris if pris.count(x) > 1]}")
    # 深浅两族必须真的分得开（否则"卡面用它自己的底色画"这件事没有意义）
    bgs = {p["name"]: p["bg"] for p in pal}
    assert bgs[d["default"]] != bgs.get("深色", bgs[d["default"]]), (
        "「默认」与「深色」的底色一样 ⇒ 深色套没生效（或 seed 写错了）")


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
