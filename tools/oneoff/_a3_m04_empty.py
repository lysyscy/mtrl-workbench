#!/usr/bin/env python
"""`A3` 逐页（`m04`）：**真机**验「筛不到行必须给空态」这一条（2026-09-29 · 一次性）。

**为什么要它**：本批把 `V.m04` 合计行槽位从 `${list.length?…:''}`（空串 = 筛不到就只剩表头）
改成 `EMPTYROW(...)`。⚠️ **全站没有任何真机探针验过「空态」**（`_shell_states.py` 只覆盖
加载 / 错 / 重试 —— 见台账那条尾巴）⇒ 这一条**只能我自己验**：把日期筛到一个没有数据的月，
看屏幕上到底画了什么；再筛回当月，确认**正常路没被改坏**（合计行还在）。

⚠️ 跑法同 `_shell_smoke`：`browser.close()` 会挂在驱动连接上 ⇒ 末尾 `os._exit()`。
用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a3_m04_empty.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]


def _session_cookie() -> tuple[str, str]:
    """与 `_shell_smoke._session_cookie` 同款（用壳自己的 `core/session.make`，⛔ 不硬编码账号）。"""
    sys.path.insert(0, str(REPO / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


READ = """() => {
  const v = document.querySelector('#view') || {};
  const tb = v.querySelector('table tbody');
  return {
    txt: (v.innerText || '').replace(/\\s+/g, ' '),
    rows: tb ? tb.querySelectorAll('tr').length : -1,
    dataRows: tb ? tb.querySelectorAll('tr:not(.draftrow)').length : -1,
  };
}"""


def main() -> int:
    name, val = _session_cookie()
    bad: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        pg.click('[data-k="m04"]')
        pg.wait_for_function("() => VIEW === 'm04'", timeout=15000)
        pg.wait_for_timeout(1200)

        # ── ① 落到一个**没有数据的月** ⇒ 必须是空态，⛔ 不许只剩表头
        pg.evaluate("() => { plf.ym='2000-01'; plf.projs=[]; plf.review='全部'; render(); }")
        pg.wait_for_timeout(700)
        a = pg.evaluate(READ)
        ok1 = ("当前筛选条件下没有付款计划" in a["txt"]) and ("换个「单据年月 / 项目 / 审查结果」" in a["txt"])
        print(f"① 空态：{'✅' if ok1 else '⛔'} 行数={a['rows']}（期望 1 = 只有空态那一行）")
        print(f"     屏幕上：{a['txt'][:170]}")
        if not ok1:
            bad.append("筛不到行时没有给出空态（为什么空 ＋ 下一步）")
        if a["rows"] > 1:
            bad.append(f"筛不到行时表体还有 {a['rows']} 行 —— 空态没有取代空表")

        # ── ② 筛回当月 ⇒ 正常路没被改坏（有行 ＋ 合计行仍在表尾）
        pg.evaluate("() => { plf.ym=bjMonth(); plf.projs=[]; plf.review='全部'; render(); }")
        pg.wait_for_timeout(700)
        c = pg.evaluate(READ)
        ok2 = ("合计" in c["txt"]) and (c["dataRows"] >= 2)
        print(f"② 正常路：{'✅' if ok2 else '⛔'} 表体行数={c['dataRows']}（含合计行 ⇒ 期望 ≥2）")
        if not ok2:
            bad.append("筛回当月后：行或合计行不见了 —— 正常路被改坏")

    print()
    if bad:
        print("结论：⛔ 必须修 ——\n  " + "\n  ".join(bad))
        sys.stdout.flush()
        os._exit(1)
    print("结论：✅ 空态与正常路都对")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
