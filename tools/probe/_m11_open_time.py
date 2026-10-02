"""`m11`（集采台账）**打开耗时**实测 ＋ 逐段拆解（性能定位用 · ⛔ 不是判据）。

为什么要它：用户 2026-10-02 报障「打开 mod11 页面时有几秒的卡顿，之后才进入页面」。
按仓规**先复现、先量**（同族：`_boot_time.py` / `_ai_map_bench.py`）—— 耗时随机器/数据量波动，
⭐ 所以它**不写断言**（写进断言只会变噪音），只做"看数字说话"。

它把"慢"拆成**四段**（这样才定位得到，⛔ 不是只报一个总数）：
  ① `T_nav`  点侧栏 `m11` → 表格**出现且行数 > 0**（用户"进入页面"的体感时间）
  ② `T_api`  同一次里 `GET /api/m11/list` 的耗时（取自 `performance` 资源表 ⇒ 后端那一段）
  ③ `T_drawA` 进页那次 `render()`（用**旧数据**先画一次 —— `go()` 里就是这样）
  ④ `T_drawB` 数据回来后再 `render()` 一次（**20 列 × 330 行**那张大表就在这一段）

读法：`T_nav ≈ T_drawA + T_api + T_drawB + 其它`。哪一段占大头 ⇒ 定位就落在哪。
用法（⚠️ 需先跑着常驻服务 `:8000`）：
    backend/.venv/Scripts/python.exe -X utf8 tools/probe/_m11_open_time.py
"""
from __future__ import annotations

import statistics
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/app"
BOOT_READY = "() => (typeof NO !== 'undefined') && NO.length > 0 && PJs.length > 0"
NAV_TO_HOME = '() => { document.querySelector(\'.sb-i[data-k="home"]\').click(); }'
NAV_TO_M11 = '() => { document.querySelector(\'.sb-i[data-k="m11"]\').click(); }'
#: m11 表格就绪 = 那张表的行数 > 0
M11_READY = ('() => { const t = document.querySelector(\'#view table[data-sort-key="m11:jc"]\');'
             " return !!t && t.querySelectorAll('tbody tr').length > 0; }")
#: 单次 `render()` 在 m11 上花多少 ms（⭐ 直接量那段"整页重画"）
DRAW = ("(sel) => { const t0 = performance.now(); VIEW = 'm11'; render(); "
        " return Math.round(performance.now() - t0); }")
#: `/api/m11/list` 那次请求的耗时（ms）
API_MS = """() => { const e = performance.getEntriesByType('resource')
   .filter(x => x.name.includes('/api/m11/list')).pop();
  return e ? Math.round(e.duration) : -1; }"""
#: ⭐ 把那次 `render()` **再拆一层**：① 生成 HTML 串 ② 塞进 DOM（浏览器解析 + 布局）
#: ③ 表里实际落地多少行（⇒ 虚拟滚动有没有生效）④ `jcVisible()` 的行数
INNER = """() => {
  const out = {};
  let t0 = performance.now();
  const raw = V.m11();
  out.gen = Math.round(performance.now() - t0);
  out.html_kb = Math.round(raw.length / 1024);
  t0 = performance.now();
  const sorted = applySorts(raw, 'm11');          /* ⭐ render() 里 V[VIEW]() 外面包的就是它 */
  out.sort = Math.round(performance.now() - t0);
  t0 = performance.now();
  out.vs_took = startVirtual(sorted, 0);          /* ⭐ 虚拟滚动那条路（含量行高 / 写 DOM） */
  out.vs = Math.round(performance.now() - t0);
  t0 = performance.now();
  placePops(); applyPjFilters();
  out.after = Math.round(performance.now() - t0);
  t0 = performance.now();
  render();                                       /* 还原页面（上面动过 DOM） */
  out.full_render = Math.round(performance.now() - t0);
  out.rows_dom = document.querySelectorAll('#view table[data-sort-key="m11:jc"] tbody tr').length;
  out.vscroll = (typeof VSCROLL !== 'undefined' && VSCROLL.m11)
    ? JSON.stringify(VSCROLL.m11) : '(无配置)';
  out.vis = jcVisible().length;
  out.all = JCs.length;
  out.sorted_kb = Math.round(sorted.length / 1024);
  return out; }"""


def main() -> int:
    runs = 3
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(URL, wait_until="load")
        pg.wait_for_function(BOOT_READY, timeout=60000)
        pg.wait_for_timeout(1500)                      # 等 boot 那几路取数落地（别把 boot 算进本页）

        nav, api, draw_a, draw_b, rows = [], [], [], [], []
        for i in range(runs):
            pg.evaluate(NAV_TO_HOME)                   # 先离开 m11（否则"进页"可能是空操作）
            pg.wait_for_timeout(600)
            t0 = time.perf_counter()
            pg.evaluate(NAV_TO_M11)                    # ⚠️ 起算点 = 用户点侧栏那一刻
            pg.wait_for_function(M11_READY, timeout=60000)
            nav.append((time.perf_counter() - t0) * 1000)
            pg.wait_for_timeout(700)                   # 等资源表落地
            api.append(pg.evaluate(API_MS))
            draw_a.append(pg.evaluate(DRAW))
            draw_b.append(pg.evaluate(DRAW))
            rows.append(pg.evaluate("() => (typeof JCs !== 'undefined' ? JCs.length : -1)"))

        pg.evaluate(NAV_TO_M11)
        pg.wait_for_function(M11_READY, timeout=60000)
        pg.wait_for_timeout(400)
        inner = [pg.evaluate(INNER) for _ in range(2)]
        pg.evaluate("() => render()")                  # 把页面还原（上面动过 innerHTML）

        # 后端半边：同一路接口连打 3 次（绕开浏览器，看纯粹的服务端耗时）
        srv = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = pg.request.get("http://127.0.0.1:8000/api/m11/list")
            srv.append((time.perf_counter() - t0) * 1000)
            assert r.ok, f"/api/m11/list 回了 {r.status}"
        b.close()

    def med(xs):
        return round(statistics.median([x for x in xs if x >= 0])) if xs else -1

    print("=" * 72)
    print("  m11（集采台账）打开耗时 · 逐段拆解")
    print("=" * 72)
    print(f" 行数 JCs（每次）：{rows}（后端那张表 20 列 × 这些行）")
    print(f" ① T_nav（点侧栏 → 表格有行，用户体感）：{ [round(x) for x in nav] } → 中位数 = **{med(nav)} ms**")
    print(f" ② T_api（`GET /api/m11/list`，浏览器侧）：{api} → 中位数 = **{med(api)} ms**")
    print(f" ③ 后端直连同一路（3 次）：{ [round(x) for x in srv] } → 中位数 = **{med(srv)} ms**")
    print(f" ④ render() 单次（m11 · 数据已在）：{draw_a} / {draw_b} → 中位数 = **{med(draw_a + draw_b)} ms**")
    print("─" * 72)
    print(f" 拆解：T_nav({med(nav)}) ≈ 进页那次 render({med(draw_a)}) ＋ T_api({med(api)}) ＋ 数据到后再 render({med(draw_b)})")
    it = inner[-1]
    print()
    print(" ⑤ 那次 render() **逐步**拆（数据已在 m11 上 · 单位 ms）：")
    print(f"     · `V.m11()` 生成 HTML 串：**{it['gen']}**（{it['html_kb']} KB）")
    print(f"     · `applySorts(html,'m11')` 表头排序：**{it['sort']}**（排序后 {it['sorted_kb']} KB）")
    print(f"     · `startVirtual(html,0)` 虚拟滚动那条路：**{it['vs']}**（接管？{it['vs_took']}）")
    print(f"     · `placePops()+applyPjFilters()`：**{it['after']}**")
    print(f"     · ⭐ 连起来整个 `render()`：**{it['full_render']}**")
    print(f"     · 表里落地行数 {it['rows_dom']}（数据 {it['all']} · 筛选 {it['vis']}）· `VSCROLL.m11` = {it['vscroll']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
