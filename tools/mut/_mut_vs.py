#!/usr/bin/env python
"""`TAIL-66` **反向灵敏度**（变异测试）：证明"虚拟滚动全局化 ＋ 焦点护栏"这两条**真有区分力**。

⭐ 为什么必须有本件：新做的机制若不证明"改坏了会被抓住"，它跟没做一样
   （本仓 2026-09-21 的教训：`_mut_boot.py` / `_mut_m03pay.py` 曾**静默崩掉**、无人知道）。

**两处变异 ⇒ 两处必须变红**：
| 变异 | 怎么改 | 期望 |
|---|---|---|
| A · 摘掉**焦点护栏** | 删掉 `if(!first && vsEditing()){ VS.pending=true; return; }` | 滚动重画 ⇒ **焦点与输入值都被蒸发**（断言失败） |
| B · 把阈值调到 10 万 | `const VS_MIN=400` ⇒ `100000` | m08 **不再虚拟化** ⇒ DOM 行变回全量（>1000） |

跑法：`backend/.venv/Scripts/python.exe tools/_mut_vs.py`（rc=0 = 两处都抓到且**逐字节复原**）。
⚠️ 需要壳在跑（`http://localhost:8000/app`）＋ Playwright。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys
import time

sys.path.insert(0, str(pathlib.Path(r"D:\dev\mtrl-workbench\backend")))
sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright               # noqa: E402
from app.core.db import session_scope                         # noqa: E402
import app.core.session as SESS                               # noqa: E402
from app.mod15_user.repository import all_users               # noqa: E402

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
HTML = ROOT / "backend" / "app" / "web" / "index.html"
GUARD = "  if(!first && vsEditing()){ VS.pending=true; return; }"
MIN400 = "const VS_MIN=400;"
BAK = ROOT / ".workbuddy" / "scratch" / "index.html.bak-mutvs"


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def run_checks(pg) -> dict:
    """真机量两件事：m08 的 DOM 行数 · m07 的焦点护栏。"""
    # ⚠️⭐ **必须绕开浏览器缓存**：第一版没绕 ⇒ 改了源文件、浏览器还在用**旧的 index.html**
    #    ⇒ 两处变异"都没抓到"（**假绿** —— 变异测试最危险的失败方式）。
    pg.goto(f"http://localhost:8000/app?_={int(time.time() * 1000)}", wait_until="networkidle")
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(1200)
    pg.click('[data-k="m08"]'); pg.wait_for_timeout(1200)
    rows = pg.evaluate("document.querySelectorAll('#view tbody tr').length")
    pg.click('[data-k="m07"]'); pg.wait_for_timeout(1200)
    pg.evaluate("VSCROLL.m07={min:5}; render();"); pg.wait_for_timeout(500)
    guard = pg.evaluate("""() => {
        const i=document.querySelector('#view input'); if(!i) return {ok:false, why:'没找到 input'};
        i.focus(); i.value='12345'; drawVirtual(false);
        const a=document.activeElement;
        return {ok: a && a.tagName==='INPUT' && String(a.value).includes('12345'),
                tag: a?a.tagName:null, v:(a&&a.value!==undefined)?a.value:null};
    }""")
    pg.evaluate("VSCROLL.m07={off:true}; render();")
    return {"m08_rows": rows, "guard": guard}


def main() -> int:
    orig = HTML.read_bytes()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HTML, BAK)
    h0 = md5(orig)
    with session_scope() as s:
        u = all_users(s)[0]
    token = SESS.make(u.account)
    rc = 0
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            pg = b.new_page(extra_http_headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            pg.context.add_cookies([{"name": getattr(SESS, "COOKIE_NAME", "mw_session"),
                                     "value": token, "url": "http://localhost:8000"}])
            base = run_checks(pg)
            print(f"基线：m08 DOM 行 {base['m08_rows']} · 护栏 {base['guard']}")
            if base["m08_rows"] > 200:
                print("❌ 基线就不对：m08 没被虚拟化（窗口应 <200 行）"); rc = 1
            if not base["guard"].get("ok"):
                print("❌ 基线就不对：护栏没保住焦点"); rc = 1

            # ── 变异 A：摘掉焦点护栏
            t = orig.decode("utf-8")
            if GUARD not in t:
                print("❌ 找不到护栏那一行（代码改过 ⇒ 本变异脚本要同步改）"); return 1
            HTML.write_text(t.replace(GUARD, "  /* 变异A：护栏已摘掉 */", 1), encoding="utf-8", newline="")
            a = run_checks(pg)
            ok_a = not a["guard"].get("ok")
            print(f"变异A（摘护栏）：护栏 {a['guard']} ⇒ {'✅ 抓到（焦点/值丢了）' if ok_a else '❌ 没抓到'}")
            rc = rc if ok_a else 1
            HTML.write_bytes(orig)

            # ── 变异 B：阈值调到 10 万
            t = orig.decode("utf-8")
            if MIN400 not in t:
                print("❌ 找不到 `const VS_MIN=400`"); return 1
            HTML.write_text(t.replace(MIN400, "const VS_MIN=100000;", 1), encoding="utf-8", newline="")
            bb = run_checks(pg)
            ok_b = bb["m08_rows"] > 1000
            print(f"变异B（阈值 10 万）：m08 DOM 行 {bb['m08_rows']} ⇒ "
                  f"{'✅ 抓到（退回全量渲染）' if ok_b else '❌ 没抓到'}")
            rc = rc if ok_b else 1
            HTML.write_bytes(orig)
            b.close()
    finally:
        HTML.write_bytes(orig)
    h1 = md5(HTML.read_bytes())
    same = h1 == h0
    print(f"复原：MD5 {'一致 ✅' if same else '❌ 不一致（' + h0 + ' vs ' + h1 + '）'}")
    if same:
        BAK.unlink(missing_ok=True)
    return rc if same else 1


if __name__ == "__main__":
    sys.exit(main())
