#!/usr/bin/env python
"""一次性排查（2026-09-29）：`m11` 页上那个 `<div class="tip dg">` 是什么、挡住了哪枚按钮。

**起因**：真机 ㉝-⑤ 想点「隐藏贸易公司列」（`#jcTradeBtn`，卡头里）时，Playwright 报
`<div class="tip dg">…</div> intercepts pointer events` ⇒ 点不到。㉑（点命中）那一段本来就在守
「提示条不许吃掉可点区」（守则 §5.5 / §4.6），所以这值得当场看清 —— 是**真的漂了**，还是本段
自己姿势不对（比如没等浮层散掉）。
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "probe"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from _shell_common import goto                              # noqa: E402
from playwright.sync_api import sync_playwright             # noqa: E402

BASE = "http://127.0.0.1:8000"

JS = r"""() => {
  const box = e => { const r = e.getBoundingClientRect();
    return {l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)}; };
  const dgs = [...document.querySelectorAll('.tip.dg')].map(e => ({
    cls: e.className, ...box(e),
    txt: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 70),
    pos: getComputedStyle(e).position, zi: getComputedStyle(e).zIndex,
  }));
  const btn = document.querySelector('#jcTradeBtn');
  return {dgs, btn: btn ? box(btn) : null,
          btnParent: btn ? (btn.parentElement.tagName + '.' + btn.parentElement.className) : null,
          /* 该点处**最上层**是谁（`elementFromPoint` = 用户真点得到的那个） */
          at: (() => { if (!btn) return null; const b = btn.getBoundingClientRect();
            const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
            return e ? (e.tagName + '.' + e.className + ' :: ' + (e.innerText || '').slice(0, 40)) : null; })()};
}"""


def main() -> int:
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D, repository as R

    with session_scope() as s:
        a = D.active_admins(R.all_users(s))[0]
        name, val = SESS.COOKIE_NAME, SESS.make(a.name or a.account)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(BASE + "/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        goto(pg, "m11")
        pg.wait_for_timeout(900)
        d = pg.evaluate(JS)
        print(f"`m11` 上的 `.tip.dg`：{len(d['dgs'])} 个")
        for x in d["dgs"]:
            print(f"  · {x['cls']!r} @({x['l']},{x['t']}) {x['w']}×{x['h']} pos={x['pos']} z={x['zi']}"
                  f"\n      {x['txt']}")
        print(f"\n`#jcTradeBtn` 在 {d['btnParent']} 里 · 盒 {d['btn']}")
        print(f"该按钮**正中间**用户实际点到的是：{d['at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
