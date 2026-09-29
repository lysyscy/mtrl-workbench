"""壳真机自检 · **㉞ 启动失败横幅「不许盖住内容」**（`TAIL-182` · `A` 案 · 2026-09-29 用户裁定）。

**它验什么**（守则 `§4.6`「提示与可见性」/ `§5.5`「点得到」）：
  `core.js::bootErrorBanner()` 那条横幅原先写的是 **`position:fixed;left:0;right:0;top:0;z-index:9999`**
  ⇒ **整带宽横幅压在页面之上** ⇒ 页首那一带的**卡头按钮全都点不着**（真机实测：`#jcTradeBtn` 被它挡住，
  `intercepts pointer events` 连重试 57 次；`elementFromPoint` 拿到的正是它）—— 守则 `§4.6` 的反例原文
  就是「提示条盖住可点区（本仓真例：`.toast` 吃掉浮层点击）」，**同一族**（当年只修了 `.toast`）。
  ⇒ `A` 案 = 横幅**进布局流**（插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto`）⇒ 它**占位**、把内容往下推。

**本段怎么做**（不求人、自己把那个状态造出来）：
  ① 把 `/api/**` 拦断 ＋ 刷新 ⇒ **启动取数必然失败** ⇒ 横幅该出现（不出现 ⇒ 本段**作废并报红**，
     否则"没盖住"这件事根本没被测到 = 假绿）；
  ② 放开拦截 ⇒ 切到 `m11`（⛔ **不刷新**：刷新会把横幅清掉，而复现的正是"横幅还在时还能不能点卡头"）；
  ③ 三条几何断言：**横幅在流里**（`position` 不是 `fixed`/`absolute`）· **它的下缘在卡头之上**（不重叠）·
     **卡头按钮正中间**用 `elementFromPoint` 拿到的**就是那枚按钮**；
  ④ 收尾：刷新一次（拦截已放开）⇒ 横幅自然消失，⛔ 不给后面的段留个"头上顶条横幅"的页。

⚠️ 本段**只读 ＋ 点一次导航**（拦断是浏览器层的，不碰任何业务数据；收尾会复原）。
"""

from __future__ import annotations

#: 启动那几路全拦掉 —— 用宽匹配（`/api/**`）而不是挑具体路：具体路会随 `PAGE_LOAD` 变，挑错了就假绿
ABORT = "**/api/**"
BTN = "#jcTradeBtn"          # 卡头里的一枚真按钮（`BIND.m11` 注入的「隐藏贸易公司列」）

JS = r"""(sel) => {
  const banner = [...document.querySelectorAll('.tip.dg')]
    .find(e => (e.innerText || '').indexOf('没拿到数据') >= 0);
  const btn = document.querySelector(sel);
  const box = e => { const r = e.getBoundingClientRect();
    return {l: Math.round(r.left), t: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom),
            w: Math.round(r.width), h: Math.round(r.height)}; };
  const cs = banner ? getComputedStyle(banner) : null;
  const at = btn ? document.elementFromPoint(btn.getBoundingClientRect().left + 6,
                                            btn.getBoundingClientRect().top + 6) : null;
  const view = document.getElementById('view');
  return {
    hasBanner: !!banner, pos: cs ? cs.position : '', zi: cs ? cs.zIndex : '',
    banner: banner ? box(banner) : null, btn: btn ? box(btn) : null,
    vp: window.innerWidth + 'x' + window.innerHeight,
    scroll: {y: Math.round(window.scrollY || 0),
             vy: view ? Math.round(view.scrollTop) : null,
             btnVisible: btn ? (btn.offsetParent !== null) : null},
    hit: at ? (at.tagName + (at.id ? '#' + at.id : '') + '.' + at.className) : null,
    hitIsBtn: !!(at && btn && (at === btn || btn.contains(at) || at.contains(btn))),
    bannerTxt: banner ? (banner.innerText || '').replace(/\s+/g, ' ').slice(0, 60) : '',
  };
}"""


def check(page, errors: list[str]) -> None:
    """㉞ 启动失败横幅不许盖住内容（见文件头）。"""
    from _shell_common import goto

    print("㉞ 启动失败横幅「不许盖住内容」（`TAIL-182` · `A` 案）：")
    before = len(errors)

    def _claim_noise() -> None:
        """⭐ 认领**本段自己造的**浏览器噪音 —— `route.abort()` 必然让 Chromium 打一串
        `Failed to load resource: net::ERR_FAILED`，而编排件把 `console.error` 一律当失败
        ⇒ 不认领就是**自检自己制造的假红**（同 `_shell_states.py` ㉗ / `_shell_err.py` ㉔ 的口径）。
        ⚠️ **只清本段触发之后新增的、且形状对得上的那些**（⛔ 别写成"把 ERR_FAILED 全滤掉"）。"""
        claimed = [e for e in errors[before:] if "net::ERR_FAILED" in e]
        for e in claimed:
            errors.remove(e)
        if claimed:
            print(f"   （已认领本段拦断产生的 {len(claimed)} 条浏览器噪音：`net::ERR_FAILED`）")

    try:
        # ① 造出"启动失败"那个状态
        page.route(ABORT, lambda route: route.abort())
        try:
            page.reload(wait_until="load")
            page.wait_for_function("() => typeof BOOTING !== 'undefined' && BOOTING === false",
                                   timeout=20000)
        except Exception as exc:                               # noqa: BLE001
            errors.append(f"㉞-① 造不出「启动失败」那个状态（{type(exc).__name__}: {str(exc)[:90]}）"
                          "⇒ 本段作废")
            return
        page.wait_for_timeout(400)
        d = page.evaluate(JS, BTN)
        if not d["hasBanner"]:
            errors.append("㉞-① 启动取数全拦断了，屏幕上却**没有**「没拿到数据」横幅 ⇒ 本段测不到东西"
                          "（⛔ 别让它静默通过 —— 那等于「横幅没盖住」从没被验过）")
            return
        print(f"   ✅㉞-① 造出来了：横幅在屏幕上（`position: {d['pos']}` · `z-index: {d['zi']}`）"
              f"· 正文 {d['bannerTxt']!r}")

        # ② 放开拦截、切到 m11（⛔ 不刷新 —— 刷新就把横幅清掉了，而复现的正是"横幅还在时"）
        page.unroute(ABORT)
        goto(page, "m11")
        d = page.evaluate(JS, BTN)
        if not d["hasBanner"] or not d["btn"]:
            errors.append(f"㉞-② 切页后量不到（横幅在 = {d['hasBanner']} · 卡头按钮在 = {bool(d['btn'])}）"
                          "—— 本段验不了")
            return

        # ⚠️ 把按钮**滚进视野**再量（实测踩到：横幅＋页面内容把它顶到视口之外，`elementFromPoint`
        #    对屏幕外的点返回 `null` ⇒ 报出"被别的东西占了"这种**假红**）。滚动容器是 `.view`，
        #    ⚠️ 横幅是它的**兄弟** ⇒ 滚内容**不会**把横幅带走（那正是 `A` 案要的形态）。
        page.evaluate("(sel) => { const b = document.querySelector(sel);"
                      " if (b) b.scrollIntoView({block: 'center'}); }", BTN)
        page.wait_for_timeout(250)
        d = page.evaluate(JS, BTN)

        # ③ 三条几何断言
        ok_flow = d["pos"] not in ("fixed", "absolute")
        print(("   ✅" if ok_flow else "   ⛔")
              + f"㉞-③ 横幅**在布局流里**（`position: {d['pos']}`，⛔ 不许 `fixed`/`absolute`）"
                f"· 盒 {d['banner']}")
        if not ok_flow:
            errors.append(f"㉞-③ 启动失败横幅又变成浮层了（`position: {d['pos']}` · `z-index: {d['zi']}`）"
                          "—— 它会盖住页首、把卡头按钮的点击全吃掉（`TAIL-182` 的原始症状）")

        gap = d["btn"]["t"] - d["banner"]["b"]
        print(("   ✅" if gap >= 0 else "   ⛔")
              + f"㉞-③′ 横幅**下缘在卡头之上**（横幅底 {d['banner']['b']} ≤ 按钮顶 {d['btn']['t']}，"
                f"差 {gap:+d}px）")
        if gap < 0:
            errors.append(f"㉞-③′ 横幅与卡头**重叠**了 {abs(gap)}px（横幅底 {d['banner']['b']} > 按钮顶 "
                          f"{d['btn']['t']}）—— 底下那排按钮会被挡着点不到")

        print(("   ✅" if d["hitIsBtn"] else "   ⛔")
              + f"㉞-③″ 卡头按钮**正中间**点得到（`elementFromPoint` = {d['hit']}）· 按钮盒 {d['btn']}"
                f"· 视口 {d.get('vp')} · 文档滚动 {d.get('scroll')}")
        if not d["hitIsBtn"]:
            errors.append(f"㉞-③″ 卡头按钮正中间被别的东西占了（`elementFromPoint` = {d['hit']}）"
                          "—— 用户点下去**没有反应**，还以为按钮坏了")

        # ④ 收尾：刷新一次 ⇒ 横幅自然消失（拦截已放开）
        page.reload(wait_until="load")
        page.wait_for_timeout(500)
        after = page.evaluate(JS, BTN)
        if after["hasBanner"]:
            print("   ⚠️㉞-④ 收尾刷新后横幅**还在**（拦截已放开却仍失败）—— 本段没给后面留干净状态，"
                  "但那不是本段要判的事（⚠️ 记一笔）")
    finally:
        page.unroute(ABORT)          # ⚠️ 任何一条提前 return 都要放开拦截（⛔ 别把后面的段拦死）
        _claim_noise()
