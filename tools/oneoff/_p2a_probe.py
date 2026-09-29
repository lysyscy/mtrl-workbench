"""`P2-a` 拆件排查用**最小真机探针**（只读）：打开 `/app`，抓 console / pageerror，再看几页渲染出来没有。

跑法（⚠️ 8000 上的服务必须是**当前代码**起的那一个）：
    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_probe.py [页名…]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
PAGES = sys.argv[1:] or ["m01", "m04", "m05"]


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs: list[tuple[str, str]] = []
        pg.on("pageerror", lambda e: errs.append(("pageerror", str(e)[:400])))
        pg.on("console", lambda m: errs.append((f"console.{m.type}", m.text[:300]))
              if m.type in ("error", "warning") else None)
        pg.goto(BASE + "/app", wait_until="load", timeout=45000)
        pg.wait_for_timeout(3000)
        print("PJs =", pg.evaluate("typeof PJs!=='undefined' ? PJs.length : 'undef'"))
        print("BOOT_ERROR =", repr(pg.evaluate("typeof BOOT_ERROR!=='undefined'?BOOT_ERROR:'undef'")))
        for k in PAGES:
            pg.click(f'[data-k="{k}"]')
            pg.wait_for_timeout(1200)
            print(k, pg.evaluate(
                "() => ({rows: document.querySelectorAll('#view tbody tr').length,"
                " html: document.querySelector('#view').innerHTML.length,"
                " view: (typeof VIEW!=='undefined'?VIEW:'?')})"))
        for t, m in errs[:12]:
            print("ERR", t, "|", m)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
