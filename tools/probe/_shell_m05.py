"""⑦ · m05 付款流水与欠款：KPI 墓碑 ＋ 表在线 ＋ 后端欠款可取

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑦ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m05 付款流水与欠款：四张 KPI ＋ 三张表；⭐ **KPI 的数必须来自后端**（可观测证据）
    goto(page, "m05")
    m05 = page.evaluate("""() => {
        const kpis=[...document.querySelectorAll('#view .kpi')].map(x=>x.innerText.replace(/\\s+/g,' '));
        /* ⚠️ 2026-09-27（`TAIL-117` 批次 4 给金额 KPI 加了单位「元」）——
           **只取第一个数字 token**（`83,191,167.72`），⛔ 别再用"把所有数字字符拼起来"那种写法：
           副行里还有别的数字（时点 / 期初 / 容差），拼起来必然 NaN（本批就是这么把真机打红的）。 */
        const num=s=>{ const m=String(s).match(/-?\\d[\\d,]*(?:\\.\\d+)?/); return m?Number(m[0].replace(/,/g,'')):null; };
        const k0=document.querySelector('#view .kpi');
        const v0=k0?k0.querySelector('.v'):null;
        return {
          kpis: kpis.length,
          kpiTotal: num(v0?v0.innerText:''),
          debtTotal: M05.debt?Number(M05.debt.total):null,
          flows: FLs.length, openings: LGs.length,
          tables: document.querySelectorAll('#view table').length,
          wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
        };
    }""")
    print("⑦ m05 =", m05)
    oks3 = [
        # ⚠️ 2026-09-28（用户口径 · 看板清账）：m05 那 4 条欠款 KPI **已删**（用户判「无用」）⇒
        #    ① 原「四张 KPI」断言改**反向墓碑**：⛔ 不许长回来；
        #    ② 原「KPI 欠款合计 == 后端 total」的**屏上锚点**随之撤除 ⇒ 保留它的**数据侧**那半
        #       （后端确实取到真数 = 可观测证据），屏上锚点改由「按项目看…」三栏承载。
        (m05["kpis"] < 4, "已撤的 4 条欠款 KPI 没有长回页面"),
        (m05["tables"] >= 2, "表在线（按项目欠款 ×3 ＋ 台账 ＋ 流水）"),
        ("未接通" not in m05["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
        (m05["debtTotal"] is not None and m05["debtTotal"] > 0,
         f"⭐ 后端欠款总数可取到（`/api/m05/debt.total` = {m05['debtTotal']}）"
         f" —— 屏上锚点已随 KPI 撤除，改由「按项目看…」三栏承载"),
    ]
    for ok, what in oks3:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("m05 自检未通过：" + what)


