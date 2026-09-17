"""前端壳**运行时自检**（打样用）：真机加载 `/app`，抓 console / page 错误，断言导航与 `m03` 渲染。

⚠️ 这条自检**不进 `pytest`**（它要浏览器 + 活服务）⇒ 属工程自检（`tools/`），
   与 `tools/_verify_auto.py` 同款定位：**真机才能发现的那类问题**用它抓。

用法：先起服务，再 `python tools/_shell_smoke.py`。
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
errors: list[str] = []


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE + "/app", wait_until="networkidle", timeout=45000)

        nav = page.locator("#nav .sb-i").count()
        print(f"① 侧栏项数 = {nav}")
        print(f"② 顶栏 = {page.locator('#ttl').inner_text()[:70]}")

        # 数据层：证明真拉到后端（空库 ⇒ 0 条也是"真的拉到"）
        print(f"③ NO={page.evaluate('NO.length')} 条 · PJs={page.evaluate('PJs.length')} 条"
              f" · BOOT_ERROR={page.evaluate('BOOT_ERROR')!r}")

        # 切到 m03 并断言结构件（对照 ui_parity 的口径）
        page.click('[data-k="m03"]')
        page.wait_for_timeout(600)
        dims = page.evaluate("""() => ({
            tables: document.querySelectorAll('#view table').length,
            fbar:   document.querySelectorAll('#view .fbar').length,
            tip:    document.querySelectorAll('#view details.tip').length,
            sum:    document.querySelectorAll('#view tr.sumrow').length,
            pjwrap: document.querySelectorAll('#view .pjwrap').length,
            sortcol:document.querySelectorAll('#view [data-sort-col]').length,
            rows:   document.querySelectorAll('#view tbody tr').length,
            head:   (document.querySelector('#view .card h4')||{}).innerText||'',
        })""")
        print("④ m03 结构件 =", dims)
        browser.close()

    print("\n=== console / page 错误 ===")
    if errors:
        for e in errors[:20]:
            print("  ❌", e)
        return 1
    print("  （无）✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
