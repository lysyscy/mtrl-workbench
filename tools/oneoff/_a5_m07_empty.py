#!/usr/bin/env python
"""`A5` 逐页（`m07`）：**真机**验「大表空态」的两个风险点（2026-09-29 · 一次性）。

**为什么只验这两点**（其余离线判据已钉）：
  ① **跨列数**：大表是**两行表头**（`<th>` 23 个 / 实列 20）⇒ 必须走 `thCols`（`thCount` 会多算 3）
     —— 这只有**在真页面里**跑一次 `thCols(BIG_THEAD)` 才知道到底是不是 20；
  ② **文案真的到了壳**：空态那句的主人**在后端**（`/api/m07/big` 的 `empty_text`）⇒ 要看
     **跑着的那个进程**给的是不是新包（⚠️ 后端没有热重载，改完必须重启；`_shell_live` 那课）。

⚠️ ⛔ **本脚本不试图造出"0 行"那个局面**：它只在「候选为空」时出现（`selected` 口径 = 未选题取**全部候选**），
   而本机库里**有在建项目** ⇒ 造不出来也不该造（⛔ 不去改库）。⇒ 空态那一行的**接线**由离线判据钉。
用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a5_m07_empty.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]


def _session_cookie() -> tuple[str, str]:
    """与 `_shell_smoke._session_cookie` 同款（用壳自己的 `core/session.make`）。"""
    sys.path.insert(0, str(REPO / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


def main() -> int:
    name, val = _session_cookie()
    bad: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        pg.click('[data-k="m07"]')
        pg.wait_for_function("() => VIEW === 'm07'", timeout=15000)
        pg.wait_for_timeout(1600)                     # 等三路取数落定（`reloadM07`）

        # ① 跨列数：三级表头必须用 `thCols`
        n = pg.evaluate("() => thCols(BIG_THEAD)")
        n2 = pg.evaluate("() => thCount(BIG_THEAD)")
        print(f"① 跨列数：thCols(BIG_THEAD) = {n}（期望 20）· thCount = {n2}（会多算 ⇒ ⛔ 不能用它）")
        if n != 20:
            bad.append(f"`thCols(BIG_THEAD)` = {n}（期望 20）⇒ 空态行跨列数会错")
        if n2 == 20:
            print("   ⚠️ 目标变了：`thCount` 也等于 20 ⇒ 那条「不许用 thCount」的判据该重新评估")

        # ② 后端那句真的到了壳（跑着的进程给的是不是新包）
        txt = pg.evaluate("() => String(BIG_EMPTY || '')")
        print(f"② 壳里的 BIG_EMPTY = {txt[:90]}")
        if not txt:
            bad.append("`BIG_EMPTY` 是空的 —— 后端那句没到壳（⚠️ 后端改完重启过没？）")
        else:
            if "在建" not in txt:
                bad.append(f"`BIG_EMPTY` 里没点出候选口径（在建）：{txt[:60]}")
            if "还没勾项目" in txt:
                bad.append("`BIG_EMPTY` 还是那句旧措辞（与「未选题 = 全部候选」不符）")

        # ③ 空态行的**标记**能生成、且跨列数正确（只验"能画出来"，⛔ 不造 0 行局面）
        html = pg.evaluate("() => EMPTYROW(thCols(BIG_THEAD), BIG_EMPTY, '先去「项目档案」把项目置为「在建」，或点「选择项目」看看候选')")
        ok3 = f'colspan="{n}"' in html and "还没有可显示的项目" in html
        print(f"③ 空态行标记：{'✅' if ok3 else '⛔'} {html[:120]}")
        if not ok3:
            bad.append("空态行的标记不对（跨列数或文案没进去）")

    print()
    if bad:
        print("结论：⛔ 必须修 ——\n  " + "\n  ".join(bad))
        sys.stdout.flush()
        os._exit(1)
    print("结论：✅ 跨列数 20（走 thCols）· 后端那句真到了壳 · 空态行能画出来")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
