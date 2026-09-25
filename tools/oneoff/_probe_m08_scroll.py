"""一次性诊断探针（2026-09-25 · 用户报障「库存单据页几乎无法滚动」）：**真机量一遍**。

⚠️ **只读**：只加载页面 ＋ 读 DOM/JS 状态，⛔ 不改任何数据、不写库。
⚠️ 会**登录**（播会话票，同 `_shell_smoke.py` —— 不登录跑，写动作会被正当拒掉、页面态也不同）。

要回答的问题是：m08 到底哪一步算错 ——
· 真正承接溢出的容器是谁（`.tw` 还是 `.view`）？它有几个？
· 虚拟滚动窗口在推进吗（`VS.base` / 已渲行数 / 垫高行总高）？
· 把宿主滚到 50% / 100% 时，`scrollHeight` 与窗口**会不会动**？

用法：先确保服务在跑，再
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_probe_m08_scroll.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "probe"))

from playwright.sync_api import sync_playwright                       # noqa: E402

BASE = "http://127.0.0.1:8000"

MEASURE = r"""() => {
  const q = s => document.querySelector(s);
  const box = el => el ? {
    cls: String(el.className || el.tagName).slice(0, 46),
    ch: el.clientHeight, sh: el.scrollHeight, st: el.scrollTop,
    ov: getComputedStyle(el).overflowY, mh: getComputedStyle(el).maxHeight,
    rows: el.querySelectorAll('tbody tr').length,
    vis: el.offsetParent !== null,
  } : null;
  const v = q('#view');
  const host = (typeof scrollHost === 'function') ? scrollHost() : null;
  const tws = [...document.querySelectorAll('.tw')];
  return {
    view: VIEW,
    vsOn: (typeof vsOn === 'function') ? vsOn(VIEW) : null,
    vsMin: (typeof vsMin === 'function') ? vsMin(VIEW) : null,
    dataRows: (typeof IVs !== 'undefined' && IVs) ? IVs.length : -1,
    viewBox: box(v),
    twCount: tws.length,
    tws: tws.map(box),
    host: box(host),
    hostIdx: host ? tws.indexOf(host) : null,
    vs: (typeof VS !== 'undefined' && VS)
      ? { view: VS.view, rows: VS.rows.length, base: VS.base,
          hFilled: VS.h.filter(x => x > 0).length, colN: VS.colN, pending: VS.pending }
      : null,
    domRows: v ? v.querySelectorAll('tbody tr').length : 0,
    spacerLift: v ? v.querySelectorAll('tr[style*="height"]').length : 0,
  };
}"""


def main() -> int:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        ck = (SESS.COOKIE_NAME, SESS.make(admin.name or admin.account))

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: print(f"[console.{m.type}] {m.text[:160]}") if m.type == "error" else None)
        page.on("pageerror", lambda e: print(f"[pageerror] {str(e)[:200]}"))
        page.context.add_cookies([{"name": ck[0], "value": ck[1], "url": BASE}])
        page.goto(BASE + "/app", wait_until="load", timeout=45000)
        page.wait_for_function("() => PJs.length > 0 || NO.length > 0 || BOOT_ERROR", timeout=20000)

        # 进 m08（优先用壳自己的导航函数，退而点侧栏）
        page.evaluate("() => { if (typeof go === 'function') go('m08'); }")
        page.wait_for_timeout(1200)
        if page.evaluate("() => VIEW") != "m08":
            page.locator("#nav .sb-i", has_text="库存单据").first.click()
            page.wait_for_timeout(1200)
        print("当前页 =", page.evaluate("() => VIEW"))

        def show(tag: str) -> None:
            m = page.evaluate(MEASURE)
            h = m.get("host") or {}
            vs = m.get("vs") or {}
            print(f"\n================ {tag} ================")
            print(f"  宿主 .tw : sh={h.get('sh')} ch={h.get('ch')} **st={h.get('st')}** rows={h.get('rows')}")
            print(f"  虚拟态   : base={vs.get('base')} 总行={vs.get('rows')} 已实测={vs.get('hFilled')}"
                  f" ｜ dom 行={m.get('domRows')} ｜ 数据行={m.get('dataRows')}")
            print(json.dumps(m, ensure_ascii=False, indent=2))

        show("① 刚进页")

        # 滚到 50% / 100%，看窗口与 scrollHeight 动不动
        for frac in (0.5, 1.0):
            ok = page.evaluate(
                """(f) => {
                    const h = (typeof scrollHost === 'function') ? scrollHost() : null;
                    if (!h) return false;
                    h.scrollTop = Math.round((h.scrollHeight - h.clientHeight) * f);
                    return true;
                }""", frac)
            page.wait_for_timeout(700)
            show(f"② 宿主滚到 {int(frac * 100)}%（设置 {ok}）")

        page.screenshot(path=str(pathlib.Path(__file__).resolve().parents[2] /
                                 ".workbuddy" / "scratch" / "_m08_scroll.png"), full_page=False)
        print("\n截图 → .workbuddy/scratch/_m08_scroll.png")
    os._exit(0)          # ⚠️ 见 `_shell_smoke.py` 文件头坑 2：别走正常关闭路径
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
