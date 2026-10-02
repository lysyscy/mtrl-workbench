"""`m11`（集采台账）**render 卡顿的 CPU 剖面**（CDP Profiler · ⛔ 不是判据）。

来历：用户 2026-10-02 报障「打开 mod11 页面有几秒卡顿」。
`_m11_open_time.py` 已量出：**T_nav ≈ render() ≈ 3 s**，而逐段点名（`V.m11()` 1ms · `applySorts` 2ms ·
`startVirtual` 0ms · `innerHTML` 19ms）**加起来只有几十毫秒** ⇒ 那 2.5 s 在**没被点名的地方**。

⇒ 本件用真剖器（Chrome DevTools Protocol `Profiler`）拿**自耗时排行**，把函数名点出来。
读法：看 top 的 `functionName @ url:line` —— 那几行就是"到底谁在烧 CPU / 谁在逼同步布局"。
用法（⚠️ 需先跑着常驻服务 `:8000`）：
    backend/.venv/Scripts/python.exe -X utf8 tools/probe/_m11_profile.py [render 次数]
"""
from __future__ import annotations

import collections
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/app"
READY = "() => (typeof NO !== 'undefined') && NO.length > 0 && PJs.length > 0"
DRAW = "() => { VIEW = 'm11'; render(); }"


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context()
        pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function(READY, timeout=60000)
        pg.evaluate('() => { document.querySelector(\'.sb-i[data-k="m11"]\').click(); }')
        pg.wait_for_timeout(2500)                     # 让 m11 先正常渲染出来（进到"数据已在"的状态）

        cdp.send("Profiler.enable")
        cdp.send("Profiler.setSamplingInterval", {"interval": 100})   # 100µs 采样
        cdp.send("Profiler.start")
        for _ in range(runs):
            pg.evaluate(DRAW)
        prof = cdp.send("Profiler.stop")["profile"]
        b.close()

    nodes = {n["id"]: n for n in prof["nodes"]}
    # ⚠️ native 调用（`getBoundingClientRect` 那种，url 是空的）**必须按调用者归账** ——
    #    否则只看它自己的名字，根本认不出是谁在逼布局（2026-10-02 第一版就是这么看错的）。
    parent: dict[int, int] = {}
    for n in prof["nodes"]:
        for c in n.get("children", []):
            parent[c] = n["id"]
    self_us: collections.Counter = collections.Counter()
    # `timeDeltas[i]` = 第 i 个样本与上一个样本的间隔 ⇒ 记在 samples[i] 那个节点上
    for sid, dt in zip(prof["samples"], prof["timeDeltas"]):
        self_us[sid] += max(dt, 0)

    rows = []
    for nid, us in self_us.items():
        f = nodes.get(nid, {}).get("callFrame", {})
        name = f.get("functionName") or "(anonymous)"
        url = (f.get("url") or "").split("/")[-1]
        rows.append((us / 1000.0, name, f"{url}:{f.get('lineNumber', -1) + 1}"))
    rows.sort(reverse=True)

    print("=" * 74)
    print(f"  m11 `render()` × {runs} 的 CPU 自耗时排行（CDP Profiler · 100µs 采样）")
    print("=" * 74)
    print(f" 合计 {sum(r[0] for r in rows):.0f} ms（{runs} 次 render）")
    print(f"{'ms':>8}  {'函数':<34} 位置")
    for ms, name, where in rows[:16]:
        if ms < 5:
            break
        print(f"{ms:>8.0f}  {name[:34]:<34} {where}")

    # ⭐ 把 native 那几笔**按调用者**重新归账（这才是"谁在逼同步布局"）
    by_caller: collections.Counter = collections.Counter()
    for sid, us in self_us.items():
        f = nodes.get(sid, {}).get("callFrame", {})
        if (f.get("functionName") or "") != "getBoundingClientRect":
            continue
        pid = parent.get(sid)
        pf = nodes.get(pid, {}).get("callFrame", {}) if pid else {}
        by_caller[(pf.get("functionName") or "(顶层)",
                   (pf.get("url") or "").split("/")[-1],
                   pf.get("lineNumber", -1) + 1)] += us
    print()
    print("  `getBoundingClientRect` **按调用者归账**（ms）：")
    for (name, url, ln), us in by_caller.most_common(8):
        print(f"   {us / 1000.0:>8.0f} ms  ← {name[:34]:<34} {url}:{ln}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
