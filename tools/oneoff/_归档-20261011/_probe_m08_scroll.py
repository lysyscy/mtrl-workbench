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

        # ⭐⭐ 真·用户手势（2026-09-25 补 —— 用户报"还是滚不动"）：
        #    程序化改 `scrollTop` **不能**代表用户能不能滚 ⇒ 必须**把鼠标放到表上、真的滚轮滚**。
        #    ⚠️ 这一步才回答"用户滚的时候到底发生了什么"。
        box = page.locator("#view .tw").first.bounding_box()
        print("\n================ ③ 真滚轮（鼠标压在表格上） ================")
        print("  表格框 =", {k: round(v) for k, v in (box or {}).items()})
        # ⚠️ 先拉回**顶部**（不去管它，往下滚本来就该有位移）；再量**真滚轮** ＋ **首行内容**变没变
        page.evaluate("() => { const h = scrollHost(); if (h) h.scrollTop = 0; }")
        page.wait_for_timeout(400)
        geo = page.evaluate("""() => { const t = document.querySelector('#view .tw');
            if (!t) return null; const r = t.getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height}; }""")
        print("  表格几何 =", geo)
        page.mouse.move(geo["x"] if geo else 640, geo["y"] if geo else 400)
        prev = 0
        for k in range(6):
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(300)
            m = page.evaluate(MEASURE)
            h = m.get("host") or {}
            first = page.evaluate("""() => { const tr = document.querySelector('#view tbody tr:nth-child(2)');
                return tr ? (tr.innerText || '').replace(/\\s+/g, ' ').slice(0, 44) : '(无)'; }""")
            print(f"  滚轮第 {k + 1} 下 → st={h.get('st')} 位移={(h.get('st') or 0) - prev} "
                  f"rows={h.get('rows')} ｜ 首行={first}")
            prev = h.get("st") or 0

        # ⭐⭐ 2026-09-25（用户第二次报障）④ **复现用户的操作路径**：先点一下页内的**筛选框**（焦点留在那儿），
        #    再滚 —— 这正是"三种滚法全滚不动"的现场。同时把 `vsEditing()` / `VS.pending` 打出来。
        print("\n================ ④ 焦点在筛选框里时滚（复现用户现场） ================")
        info = page.evaluate("""() => {
            const inp = document.querySelector('#view input, #view select');
            if (inp) inp.focus();
            return {focused: document.activeElement ? (document.activeElement.tagName + '#' +
                    (document.activeElement.id || document.activeElement.className.slice(0, 24))) : '(无)',
                    vsEditing: (typeof vsEditing === 'function') ? vsEditing() : null,
                    pending: (typeof VS !== 'undefined' && VS) ? VS.pending : null};
        }""")
        print("  焦点 =", info["focused"], "｜ vsEditing() =", info["vsEditing"], "｜ VS.pending =", info["pending"])
        page.mouse.move(geo["x"] if geo else 640, geo["y"] if geo else 400)
        seq4 = []
        for k in range(3):
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(280)
            seq4.append(page.evaluate("""() => {
                const v=document.querySelector('#view');
                const t=v&&v.querySelector('.tw'); const s=(t&&t.scrollHeight>t.clientHeight+1)?t:v;
                const tr=document.querySelector('#view tbody tr:nth-child(2)');
                return {st:s.scrollTop, waiting:(typeof VS!=='undefined'&&VS)?VS.pending:null,
                        first:tr?(tr.innerText||'').replace(/\\s+/g,' ').slice(0,26):''};
            }"""))
        for k, x in enumerate(seq4, 1):
            print(f"  带焦点滚第 {k} 下 → st={x['st']} pending={x['waiting']} ｜ 首行={x['first']}")
        changed = len({x["first"] for x in seq4}) > 1
        print(f"  ⇒ 结论：首行内容{'**有**变（滚得动 ✓）' if changed else '**没变**（内容冻结 ✗）'}")

        # ⭐⭐ ⑤ **A/B 证据**：把**旧规则**原样模拟回来（`vsEditing` 恒 true = 旧"焦点在本页就算在编辑"）
        #    ⇒ 看内容是不是就**冻住**了。这一步回答"根因是不是那道焦点护栏"，⛔ 不是靠推断。
        print("\n================ ⑤ A/B：模拟旧规则（vsEditing 恒 true） ================")
        page.evaluate("""() => { window.__vsOld = vsEditing; window.vsEditing = () => true; }""")
        page.evaluate("""() => { const h=scrollHost(); if(h) h.scrollTop = 20000; }""")
        page.wait_for_timeout(400)
        ab = []
        for k in range(3):
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(280)
            ab.append(page.evaluate("""() => {
                const v=document.querySelector('#view');
                const t=v&&v.querySelector('.tw'); const s=(t&&t.scrollHeight>t.clientHeight+1)?t:v;
                const tr=document.querySelector('#view tbody tr:nth-child(2)');
                return {st:s.scrollTop, pending:(typeof VS!=='undefined'&&VS)?VS.pending:null,
                        first:tr?(tr.innerText||'').replace(/\\s+/g,' ').slice(0,26):''};
            }"""))
        for k, x in enumerate(ab, 1):
            print(f"  旧规则下滚第 {k} 下 → st={x['st']} pending={x['pending']} ｜ 首行={x['first']}")
        print(f"  ⇒ 旧规则：首行内容{'**有**变' if len({x['first'] for x in ab}) > 1 else '**没变（内容冻结 ✗ —— 这就是用户报的"滚不动"）**'}")
        page.evaluate("""() => { window.vsEditing = window.__vsOld; }""")

        page.screenshot(path=str(pathlib.Path(__file__).resolve().parents[2] /
                                 ".workbuddy" / "scratch" / "_m08_scroll.png"), full_page=False)
        print("\n截图 → .workbuddy/scratch/_m08_scroll.png")
    os._exit(0)          # ⚠️ 见 `_shell_smoke.py` 文件头坑 2：别走正常关闭路径
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
