#!/usr/bin/env python
"""`A6b`（用户「按推荐」）· **真机**复验（2026-09-29 · 一次性 · ⛔ 只读 ＋ 开完弹窗就关）。

**验三件只有真机能确认的**：
  ① `m01` 的「确认删除」**真的置灰了**（源码里写了 `disabled` ≠ 屏幕上点了没用），
     且**理由真的上屏**（不是只挂 `title` —— 那是给鼠标的，置灰时多半看不到）；
  ② ⭐ **顺便把那个断言探明**：置灰的 `disabled` 元素，浏览器到底算不算 `:hover`
     （`_mut` 与 `test_ux_pages` 的判词里写了"多半不弹 `title`" —— 这一条必须有实测撑着）；
  ③ `m05` 期初行的删除确认里**不再出现「软删留痕」**、且写着「删了不能恢复」
     （⚠️ 期初行只在**已录入**时才有删除入口 —— 没有就如实说"本机没有期初行，验不到"）。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a6b_check.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]


def _session_cookie() -> tuple[str, str]:
    sys.path.insert(0, str(REPO / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


def _goto(pg, key: str) -> None:
    pg.click(f'[data-k="{key}"]')
    pg.wait_for_function("(k) => VIEW === k", arg=key, timeout=15000)
    pg.wait_for_timeout(1200)


def _modal_text(pg):
    """弹窗文本（真容器 = **`#modalRoot`**）；**没有弹窗就返回 `None`**
    （⚠️ 2026-09-29 修两处：① 原先回退到 `document.body` ⇒ 拿整页文本断言"没有软删留痕"**必然通过**
     = 假绿；② 原先找 `.mp` —— 那是**时间选择器浮层**的类名，不是弹窗容器）。"""
    return pg.evaluate("""() => { const r = document.querySelector('#modalRoot');
        const t = r ? (r.innerText || '').trim() : '';
        return t ? t.replace(/\\s+/g, ' ') : null; }""")


def _toast_text(pg) -> str:
    return pg.evaluate("() => { const t=document.querySelector('.toast');"
                       " return t ? (t.innerText||'').replace(/\\s+/g,' ') : ''; }")


def main() -> int:
    name, val = _session_cookie()
    bad: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)

        # ── ① + ② m01 的删除确认 ──────────────────────────────────────────
        _goto(pg, "m01")
        pg.evaluate("""() => { const b=document.querySelector('#view [data-act="delPj"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(600)
        if _modal_text(pg) is None:                 # ⚠️ 弹窗没开 ⇒ 这一段**验不到**（⛔ 不许静默通过）
            print("① ⛔ `m01` 的删除确认**没弹出来** ⇒ 本段验不到（先查 `delPj` 那一路）")
            bad.append("`m01` 的删除确认没弹出来（本段验不到）")
        m = _modal_text(pg) or ""
        st = pg.evaluate("""() => { const b=document.querySelector('[data-act="delPjOk"]');
            if(!b) return {err:'没找到「确认删除」那枚按钮'};
            return {disabled: !!b.disabled, hasTitle: !!b.title, title: (b.title||'').slice(0,60)}; }""")
        ok1 = (not st.get("err")) and st["disabled"] and st["hasTitle"]
        print(f"① `m01`「确认删除」置灰 ＋ 有 `title`：{'✅' if ok1 else '⛔'} {st}")
        if not ok1:
            bad.append("「确认删除」没置灰 / 没写 title")
        ok2 = "删除这一项还没打通" in m
        print(f"①′ **可见的理由**在弹窗里：{'✅' if ok2 else '⛔'}")
        print(f"     弹窗尾巴：…{m[-90:]}")
        if not ok2:
            bad.append("置灰按钮没有**可见**的理由（只挂 title ⇒ 用户看不到）")

        # ⭐ ② 探明：置灰元素算不算 `:hover`（这决定 `title` 到底看不看得见）
        box = pg.evaluate("""() => { const b=document.querySelector('[data-act="delPjOk"]');
            if(!b) return null; const r=b.getBoundingClientRect();
            return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; }""")
        hov = None
        if box:
            pg.mouse.move(box["x"], box["y"])
            pg.wait_for_timeout(250)
            hov = pg.evaluate("""() => { const b=document.querySelector('[data-act="delPjOk"]');
                return {hover: b.matches(':hover'), pe: getComputedStyle(b).pointerEvents}; }""")
            print(f"② 置灰按钮的悬停实测：`matches(':hover')` = **{hov['hover']}** · "
                  f"`pointer-events` = {hov['pe']} ⇒ "
                  f"{'⚠️ 悬停状态不成立 ⇒ `title` 基本不会弹（所以理由必须上屏）' if not hov['hover'] else '悬停状态成立（`title` 有机会弹）'}")
        pg.evaluate("""() => { const b=document.querySelector('[data-act="closeModal"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(300)

        # ── ③ m05 期初行的删除确认 ────────────────────────────────────────
        _goto(pg, "m05")
        has = pg.evaluate("() => !!document.querySelector('#view [data-act=\"delLg\"]')")
        if not has:
            print("③ `m05` 本机没有期初行（没有删除入口）⇒ 这一段**验不到**（如实说，⛔ 不算通过）")
        else:
            pg.evaluate("""() => { const b=document.querySelector('#view [data-act="delLg"]'); if(b) b.click(); }""")
            pg.wait_for_timeout(700)
            m5 = _modal_text(pg)
            if m5 is None:
                print(f"③ ⛔ `m05` 点了期初行「删除」**弹窗没开**（toast = {_toast_text(pg)[:90]!r}）"
                      " ⇒ 这一段验不到（⛔ 不许拿整页文本冒充）")
                bad.append("`m05` 的期初行删除弹窗没开（本段验不到；⚠️ 别让「没弹出来」变成「通过」）")
            else:
                ok3 = ("软删留痕" not in m5) and ("删了不能恢复" in m5) and ("必须列出" not in m5)
                print(f"③ `m05` 期初行删除确认：{'✅' if ok3 else '⛔'}（无「软删留痕」· "
                      f"有「删了不能恢复」· 无要求句）")
                print(f"     弹窗：…{m5[:150]}")
                if not ok3:
                    bad.append("`m05` 期初行删除确认还在说「软删留痕」/ 缺真删后果说明")
                pg.evaluate("""() => { const b=document.querySelector('[data-act="closeModal"]'); if(b) b.click(); }""")
                pg.wait_for_timeout(300)

    print()
    if bad:
        print("结论：⛔ 必须修 ——\n  " + "\n  ".join(bad))
        sys.stdout.flush()
        os._exit(1)
    print("结论：✅ 真机复验通过")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
