"""⑥ · m04 付款计划：结构件在线 ＋ 筛选条条数 == 数据源

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑥ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m04 付款计划：结构件在线 ＋ 空库时给**空态**（⛔ 不是"表都没了"）
    goto(page, "m04")
    # ⚠️⚠️ 2026-10-01（`TAIL-208`）：**先把日期筛到「全部时间」再读** —— 原判据直接比 `shown == plans`，
    #    而 m04 的日期筛选**默认是当月**、库里付款计划又全在 2026-09 ⇒ 一到 10 月 `shown` 就是 0
    #    ⇒ 这条**跨月必红**（把"立它时当月恰好有数据"当成了**恒定条件** · 实测 2026-10-01）。
    #    ⭐ 修法 = **驱动筛选到有数据的范围**（`tmIn` 对 `'全部'` 恒真）：验的还是"页面真接上了数据源"，
    #      但不依赖"当月恰好有数据"；⛔ **断言本身没放宽**（仍然是 `shown == plans`）。
    page.evaluate("() => { plf.ym='全部'; plf.projs=[]; render(); }")
    page.wait_for_timeout(400)
    m04 = page.evaluate("""() => {
        const pills=[...document.querySelectorAll('#view .pill')].map(x=>x.innerText).join(' | ');
        const m=pills.match(/显示\\s*(\\d+)\\s*条/);
        return {
          plans: PLs.length,
          tables: document.querySelectorAll('#view table').length,
          kpis: document.querySelectorAll('#view .kpi').length,
          rows: document.querySelectorAll('#view tbody tr').length,
          shown: m?Number(m[1]):null,
          wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
        };
    }""")
    print("⑥ m04 =", m04)
    # ⚠️ `V.m04` **没有空态行**（原型如此）⇒ 不能断言"至少一行"；
    #    改断**筛选条报出的条数 == 数据源条数** —— 这才是"页面真接上了数据源"的可观测证据。
    oks2 = [
        (m04["tables"] >= 1 and m04["kpis"] == 6, "结构件在线（表 ＋ 6 张判定卡）"),
        ("未接通" not in m04["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
        (m04["shown"] is not None and m04["shown"] == m04["plans"],
         f"筛选条条数 == 数据源条数（{m04['shown']} vs {m04['plans']}）"),
    ]
    for ok, what in oks2:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m04 自检未通过：" + what)


