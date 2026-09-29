#!/usr/bin/env python
"""`A6` 逐页（`m01` 项目档案）：**真机**验那两处收口（2026-09-29 · 一次性）。

**为什么要它**：本批改的是两条**只有真机能确认"屏幕上真的这样"**的东西：
  ① 空态指路**指向真实入口**（离线判据只能证明"源码里那句改了"，证明不了"0 行那一刻画的是它"）；
  ② 删除确认第一句**是人话**（离线判据证明不了弹窗真的渲染成那样）。
⚠️ 两条都**只读 ＋ 点一下就关**：⛔ 不落任何写动作、⛔ 不真的删除（弹窗点「取消」）。

做法：
  · `m01` 把搜索词设成一个**不可能存在**的名字 ⇒ 表体进空态 ⇒ 读出那段文案；
  · 再把搜索词清掉 ⇒ 行回来（**正常路没被改坏**）；
  · 点第一行的「删除」⇒ 读出弹窗文案 ⇒ 点「取消」关掉。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a6_m01_check.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]


def _session_cookie() -> tuple[str, str]:
    """与 `_a3_m04_empty._session_cookie` 同款（用壳自己的 `core/session.make`，⛔ 不硬编码账号）。"""
    sys.path.insert(0, str(REPO / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


READ_VIEW = "() => (document.querySelector('#view').innerText || '').replace(/\\s+/g, ' ')"
READ_MODAL = ("() => { const m = document.querySelector('.mp') || document.querySelector('.modal')"
              " || document.body; return (m.innerText || '').replace(/\\s+/g, ' '); }")


def main() -> int:
    name, val = _session_cookie()
    bad: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        pg.click('[data-k="m01"]')
        pg.wait_for_function("() => VIEW === 'm01'", timeout=15000)
        pg.wait_for_timeout(1200)

        # ── ① 空态：指路必须指向**真实入口**，⛔ 不许再指向不存在的按钮
        pg.evaluate("() => { fPj.q='zzz__不可能存在的项目__'; fPj.status='全部'; fPj.type='全部';"
                    " render(); }")
        pg.wait_for_timeout(600)
        v = pg.evaluate(READ_VIEW)
        ok1 = ("当前筛选条件下没有项目档案" in v) and ("同步常用项目列表" in v) and ("同步仓库名单" in v)
        ok2 = "＋ 新增项目" not in v
        print(f"① 空态：{'✅' if ok1 else '⛔'} 第一句在 ＋ 指路点名两个**真实入口**")
        print(f"①′ 旧指路（指向不存在的按钮）：{'✅ 已不在' if ok2 else '⛔ 还在'}")
        print(f"     屏幕上：…{v[max(0, v.find('当前筛选条件下没有项目档案')):][:120]}")
        if not ok1:
            bad.append("空态没指向真实入口（用户按着它找不到东西）")
        if not ok2:
            bad.append("空态又在指一个不存在的按钮「＋ 新增项目」")

        # ── ② 正常路：清掉搜索词 ⇒ 行回来（⛔ 别把正常路改坏）
        pg.evaluate("() => { fPj.q=''; fPj.status='在建'; fPj.type='全部'; render(); }")
        pg.wait_for_timeout(600)
        n = pg.evaluate("() => document.querySelectorAll('#view tbody tr').length")
        ok3 = n >= 1 and "当前筛选条件下没有项目档案" not in pg.evaluate(READ_VIEW)
        print(f"② 正常路：{'✅' if ok3 else '⛔'} 清掉搜索词后表体 {n} 行（期望 ≥1）")
        if not ok3:
            bad.append("清掉搜索词后没有行 —— 正常路被改坏")

        # ── ③ 删除确认第一句必须是**人话**（⛔ 不真的删：读完就点「取消」）
        pg.evaluate("() => { const b=document.querySelector('#view [data-act=\"delPj\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(600)
        m = pg.evaluate(READ_MODAL)
        ok4 = "删除不可撤销" in m
        ok5 = "必须列出删除影响范围" not in m
        print(f"③ 删除确认：{'✅' if ok4 else '⛔'} 有人话的后果说明（「删除不可撤销…」）")
        print(f"③′ 要求句（写给实现的话）：{'✅ 已不在' if ok5 else '⛔ 还在'}")
        print(f"     弹窗里：…{m[:130]}")
        if not ok4:
            bad.append("删除确认没有人话的后果说明（用户不知道删了会怎样）")
        if not ok5:
            bad.append("删除确认又把《说明书》的要求句甩给用户了")
        pg.evaluate("""() => { const b = document.querySelector('[data-act="closeModal"]');
                       if (b) b.click(); }""")
        pg.wait_for_timeout(400)
        left = pg.evaluate("() => !!document.querySelector('.mp')")
        print(f"③″ 弹窗已关（⛔ 一个写动作都没做）：{'✅' if not left else '⛔ 还开着'}")

    print()
    if bad:
        print("结论：⛔ 必须修 ——\n  " + "\n  ".join(bad))
        sys.stdout.flush()
        os._exit(1)
    print("结论：✅ 空态指路与删除确认都对，且正常路没被改坏")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
