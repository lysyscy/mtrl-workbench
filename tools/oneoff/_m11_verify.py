"""`m11` 卡顿 **单变量验证**：把 `scrollHost()` 打桩 ⇒ `render()` 是否立刻变快（一次性 · 2026-10-02）。

证据链（前两件探针）：
  `_m11_open_time.py`：T_nav ≈ render() ≈ **3 s**；接口 19 ms ⇒ 前端。
  `_m11_profile.py`：CDP 剖面 top1 = **`getBoundingClientRect` 10379 ms / 3 次**（≈3.4 s/次），
                     调用方 = **`scrollHost()`（`view.js:183`）** ⇒ 强制同步布局。
本件把这条链**钉死**（改一个变量、看症状是否消失）：
  ① 量**单次** `scrollHost()`（m11 的大表已在 DOM 里 ⇒ 它读 rect 会逼一次全量布局）
  ② 量 `render()` 基线（3 次取中位）
  ③ ⭐ 把 `scrollHost` 换成 `() => null` ⇒ 再量 `render()`（其余一律不动）
读法：③ 比 ② 快一个数量级 ⇒ 病因**就是**那几处 `scrollHost()` 逼出来的同步布局，与猜测无关。
用法：`backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_m11_verify.py`
"""
from __future__ import annotations

import statistics
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000/app"
READY = "() => (typeof NO !== 'undefined') && NO.length > 0 && PJs.length > 0"
DRAW = ("() => { const t0 = performance.now(); VIEW = 'm11'; render(); "
        " return Math.round(performance.now() - t0); }")
SH_TIME = "() => { const t0 = performance.now(); scrollHost(); return Math.round(performance.now() - t0); }"
STUB = "() => { window.__shOld = scrollHost; scrollHost = () => null; return typeof scrollHost; }"
RESTORE = "() => { scrollHost = window.__shOld; }"


def _med(pg, expr, n=3):
    out = []
    for _ in range(n):
        out.append(pg.evaluate(expr))
    return out, round(statistics.median(out))


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.goto(URL, wait_until="load")
        pg.wait_for_function(READY, timeout=60000)
        pg.evaluate('() => { document.querySelector(\'.sb-i[data-k="m11"]\').click(); }')
        pg.wait_for_timeout(2500)

        sh, sh_med = _med(pg, SH_TIME)
        base, base_med = _med(pg, DRAW)
        assert pg.evaluate(STUB) == "function", "`scrollHost` 不是可赋值的函数绑定 ⇒ 打桩失败"
        stubbed, st_med = _med(pg, DRAW)
        pg.evaluate(RESTORE)
        b.close()

    print("=" * 74)
    print("  m11 · `scrollHost()` ⇒ 强制同步布局 · 单变量验证")
    print("=" * 74)
    print(f" ① 单次 `scrollHost()`（大表已在 DOM）：{sh} → 中位数 = **{sh_med} ms**")
    print(f" ② `render()` 基线（不动任何东西）：      {base} → 中位数 = **{base_med} ms**")
    print(f" ③ `render()`（只把 `scrollHost` 打桩成 null）：{stubbed} → 中位数 = **{st_med} ms**")
    print("─" * 74)
    if base_med and st_med * 5 < base_med:
        print(f" ✅ 打桩后快 **{base_med / max(st_med, 1):.0f}×** ⇒ 病因 = `scrollHost()` 读 rect 逼出来的**同步布局**")
    else:
        print(" ❌ 打桩没有显著变快 ⇒ 病因不止这一处，回到 `_m11_profile.py` 看下一名")
    return 0


if __name__ == "__main__":
    sys.exit(main())
