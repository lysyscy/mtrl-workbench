"""真机自检的**共用小件**（`_shell_*.py` 之间共享，⛔ 不各写一份）。

⭐ 2026-09-26 立件（**它自己就是"别再靠自觉"的一次收口**）：此前"切页等多久""写动作等多久"
   散在各 `_shell_*.py` 里，全是 `page.wait_for_timeout(600~1800)` 的**纯睡** ⇒ 既慢、又
   **超时也是绿的**（页面没动时下面的断言会读到上一屏，报出"这页好好的" = 假绿）。

本件只放**与具体页面无关**的三件：
  · `goto()`          —— 切页（等"这一屏画完"）
  · `wait_db()`       —— 等**库里的结果**出现（写动作的判据本来就是库里的行）
  · `session_cookie()` —— 造一张「以**在用管理员**身份登录」的会话票
    （⭐ `TAIL-215` 批 2 从 `_shell_smoke.py` 搬来 —— ⓪ 段与 `tools/oneoff/_p5c_survey.py` 共用）
"""

from __future__ import annotations

import time


def settle(page, timeout: int = 15000) -> None:
    """等**当前这屏的 DOM 稳定下来**（内容长度连续两段 120 ms 不变）—— 壳的 `render()` 是一次画完的。

    ⚠️ **为什么它必须单独存在**（2026-09-26 实测换来的）：写动作之后的等待，原先那些 `1800 ms`
       同时盖住了**两件事** —— ① 服务端**库写入** ② 壳拿到响应后的**界面重绘**。
       只等①（`wait_db` 只保证库里有）⇒ 后面的**界面断言会读到还没重绘的画**（实测：建档/指认
       两条链路当场报"界面如实报出结果"失败）。⇒ ②单独等（本函数）。

    ⭐⭐ 2026-09-27（`TAIL-117` 批次 6）：**先等"离开加载态"再等稳定** —— 批次 6 给壳加了页级四态
       （`pageState()`：数据没回来时画「正在读取…」而不是空表），而**状态页的 DOM 也是稳的**
       ⇒ 只等"长度不变"会在**加载中**就返回（实测当场红：`m06` 量到 `tables: 0`）。
       ⇒ 判据改成两步：① `pageState().kind !== 'loading'`（下称"不忙了"）② 再等 DOM 稳定。
    ⚠️ 只等"不忙"、**不等"没问题"**：`error` 态也放过去 ⇒ 让下面那些断言**如实报红**
       （等它就等于把"这页坏了"变成"探针超时"，那是把真故障说成探针故障）。
    """
    page.wait_for_function(
        "() => (typeof pageState !== 'function') || pageState().kind !== 'loading'",
        timeout=timeout)
    page.wait_for_function(
        """() => new Promise(res => {
             const len = () => (document.querySelector('#view').innerHTML || '').length;
             const a = len();
             if (!a) return res(false);                     /* 还空着 = 没画 ⇒ 接着等 */
             setTimeout(() => { const b = len();
               setTimeout(() => res(b === len() && b > 0), 120);
             }, 120);
           })""", timeout=timeout)


def goto(page, key: str, timeout: int = 15000) -> None:
    """切页（点 `[data-k=key]`）并等**这一屏画完**（⛔ 不是睡固定毫秒）= 「路由到位」＋ `settle`。

    ⚠️ 条件为什么这样取：
      · ⛔ **不能用 `networkidle`** —— 壳里有持续请求，它**永远等不到**（`_shell_smoke.py` 文件头坑 1）；
      · ⛔ 也不能等"某个元素在" —— 那要**猜数据**（空库时同一页长得不一样）⇒ 猜错就是**假红**；
      · ✅ 用"**长度连续两段不变**"（见 `settle`）：壳是"取数完再 render"⇒ 稳住了 ≈ 画完了；
        且它**与数据无关**（空库/满库都成立）。
    ⚠️ 好处不止快：**等不到会超时抛错** —— 原来睡够就往下，页面没动时断言读到上一屏 = **假绿**。
    """
    page.click(f'[data-k="{key}"]')
    page.wait_for_function("(k) => VIEW === k", arg=key, timeout=timeout)
    settle(page, timeout=timeout)


def wait_db(pred, timeout: float = 20.0, interval: float = 0.15) -> bool:
    """等**库里的结果**出现（`pred(session)` 为真即返回 `True`；超时返回 `False`）。

    ⭐ 什么时候用它：写动作之后的等待 —— 那条判据**本来就是"库里该有这一行"**，
       所以直接等它，比"等弹窗消失"更贴判据、也比"睡 1800 ms"更准（写完就往下，不等满）。
    ⚠️ 每次开一个短会话轮询（`interval=0.15 s`）⇒ 不会把事务开着等（那才是坏味道）。
    """
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
    from app.core.db import session_scope

    end = time.time() + timeout
    while time.time() < end:
        try:
            with session_scope() as s:
                if pred(s):
                    return True
        except Exception:      # noqa: BLE001
            pass               # ⚠️ 库正被写事务占着（"database is locked"）是**正常**的 ⇒ 接着轮询
        time.sleep(interval)
    return False


def session_cookie() -> tuple[str, str]:
    """造一张「以**在用管理员**身份登录」的会话票 —— 返回 `(cookie 名, 票)`。

    ⭐ 2026-09-21（③ 收紧「未登录不回落首个管理员」之后**必须**补的一步）：
       壳不再"没登录也算管理员"⇒ 不带会话跑本自检，所有**写动作**都会被后端**正当地**拒掉
       （那是我们要的行为）⇒ 那几条链路就没法验了。⇒ 先给浏览器播一张会话票。

    ⚠️ 用**壳自己的** `core/session.make`（⛔ 不硬编码账号/密码，⛔ 不绕开自己的签名）——
       票的载荷 = 那个管理员的**姓名**（与登录页写进 cookie 的东西一致，见 `api_do_login`）。
    ⚠️ 这里**不走登录页**是有意的：登录页 / 验签 / 会话隔离是 `test_acc_usr_login.py` 的事，
       本件只关心**壳的运行时**。
    """
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


__all__ = ["goto", "session_cookie", "wait_db"]
