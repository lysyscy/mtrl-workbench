"""⑦′ · 台账「项目」面板展开/收起 round-trip

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations



def check(page, errors) -> None:
    """⑦′ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- ⭐ `#1` 面板**展开 / 收起** round-trip（2026-09-26 补 · 注册表 `PJ_OPEN` 的真机证据）
    # 判词三件（都在**真机**上，⛔ 离线断言看不见）：① 真点「项目」⇒ 面板出现；
    # ② 真点面板**之外** ⇒ 收起（委托层把注册表里所有展开的一起关）；
    # ③ 真点**当前已选中**那个 ⇒ 自动收起（`#1` 新加的行为：面板内选一个就收）。
    # ⚠️ ③ 刻意点**已选中**的那个（`checked`）—— 落库语义不变 ⇒ 不打扰后面几段的取数
    #    （点别的项目会把台账当前项目改掉，m06/m07 那几段读的数就跟着变 ⇒ 那是"自检自己动了数据"）。
    # ⚠️ 用 `.click()`（DOM 原生事件）而不是 `page.mouse`：委托挂在 `document` 上，原生 click
    #    同样**冒泡** ⇒ 走的是同一条委托路径；而它能在一次 `evaluate` 里读完三个状态的中间值。
    pj = page.evaluate("""() => {
        const v = document.querySelector('#view');
        const t = v.querySelector('[data-act="ledPjToggle"]');
        if (!t) return {err: '台账那格的「项目」没有 ledPjToggle'};
        t.click();
        const open = v.querySelectorAll('[data-act="ledPjPick"]').length;
        const picked = [...v.querySelectorAll('[data-act="ledPjPick"]')].find(el => el.checked);
        document.querySelector('#ttl').click();          /* 点面板**之外**（顶栏那行状态） */
        const outside = v.querySelectorAll('[data-act="ledPjPick"]').length;
        let byPick = -1;
        if (picked) { t.click(); picked.click(); byPick = v.querySelectorAll('[data-act="ledPjPick"]').length; }
        return {open: open, outside: outside, byPick: byPick, hasPicked: !!picked};
    }""")
    print("⑦′ 面板 round-trip =", pj)
    oks33 = [
        (not pj.get("err") and pj.get("open", 0) >= 1,
         "真点「项目」⇒ 面板出现（`ledPjToggle` ⇒ `ledPjPick`）" + ("：" + pj["err"] if pj.get("err") else "")),
        (pj.get("outside") == 0, "真点面板**之外** ⇒ 收起（`PJ_OPEN` 注册表全关）"),
        (pj.get("hasPicked") and pj.get("byPick") == 0,
         "真点**已选中**那个 ⇒ 自动收起（`radio` ⇒ 面板自己收）"),
    ]
    for ok, what in oks33:
        print(("  ✅ " if ok else "  ⛔ ") + "⑳′ " + what)
        if not ok:
            errors.append("面板 round-trip 自检未通过：" + what)


