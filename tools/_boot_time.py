"""前端壳 **首屏到数据齐** 的耗时实测 ＋ **逐路耗时明细**（性能 `P2`/`P3` 的取舍依据）。

口径（**说清楚量的是什么**）：
- **实测**：`goto('/app')` 起算 → 等到 `NO`（付款通知书）与 `PJs`（项目档案）**都非空**
  ⇒ 即「**数据可用**时间」（⛔ 不是白屏时间、也不是完全静默时间）。跑 4 次、**丢掉第 1 次**
  （含浏览器冷启动）取中位数，避免单次抖动误导。
- **逐路明细**：同一页面里读 `performance.getEntriesByType('resource')` 的 `/api/*` 请求
  ⇒ 每路的**真实耗时**与**合计**。⭐ 合计 = 「若仍一路一等」的**串行下界**，与上面对照即得
  `P2`（boot 并行）的效果；同时它也是 `P3`（按需取数）**该先动哪几路**的清单。

⚠️ 它**不是判据**（耗时随机器 / 数据量波动，写进断言只会变噪音）—— 只做"看数字说话"的实测。
用法（⚠️ 需先跑着常驻服务 `:8000`）：
    backend/.venv/Scripts/python.exe tools/_boot_time.py [标签]
"""

from __future__ import annotations

import statistics
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/app"
READY = "() => (typeof NO !== 'undefined') && NO.length > 0 && PJs.length > 0"
#: 取每个 `/api/*` 请求的耗时（去掉 query，便于归组）
RES = """() => performance.getEntriesByType('resource')
  .filter(e => e.name.includes('/api/'))
  .map(e => [e.name.replace(/^.*\\/api\\//, '').replace(/\\?.*$/, ''), Math.round(e.duration)])"""


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else ""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        ts: list[float] = []
        last: list[list] = []
        for _ in range(4):
            t0 = time.perf_counter()
            pg.goto(URL, wait_until="load")
            pg.wait_for_function(READY, timeout=60000)
            ts.append((time.perf_counter() - t0) * 1000)
            # ⚠️ 等取数**全部落地**再读资源表：READY 只等前两路（数据可用），此刻其余各路可能还在飞
            #    ⇒ 不等就只收到一部分（曾实测只收到 5 个 /api，串行下界被少算）。
            pg.wait_for_timeout(1800)
            last = pg.evaluate(RES)
            pg.wait_for_timeout(400)
        b.close()

    print("=" * 70)
    print(f" 外壳首屏到「数据可用」· {label or 'boot'}")
    print("=" * 70)
    print(f" 实测(ms)：{ [round(x) for x in ts] } → 中位数(丢首次) = **{round(statistics.median(ts[1:]))}**")
    print()
    print(f" 逐路耗时（末次实际发出的 {len(last)} 个 /api 请求）：")
    for name, ms in sorted(last, key=lambda x: -x[1]):
        print(f"   {ms:>6} ms  /api/{name}")
    total = sum(ms for _, ms in last)
    print()
    print(f" ⭐ 各路合计（= 若仍「一路一等」的**串行下界**）= {total} ms"
          f" · 最长一路 = {max((ms for _, ms in last), default=0)} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
