"""`P5-c` 的**铺量前量测**（⛔ 只读 · 真机）：**页级那条虚拟滚动路还有没有页在走？**

**为什么必须先量**（施工图 §7.4 对 `P5-c` 的要求就是"先出量测"）：

- `P5-c` = **把页级那条路删掉**（`startVirtual` 里"整页一张大表"的那一半 ＋ 页级实例 `VS`）。
  能不能删，取决于**还有没有页真的依赖它** —— 而这件事**离线判据看不出来**：
  `TBL` 现在**每一张表**都带 `data-vs` ⇒ `startVirtual` 一到表级那半就 `return` 了
  ⇒ 从源码看"页级那半永远走不到"，但**页面 HTML 里不带标记的大块行**（手写的 `<tr>` 列表 / 别的件拼的表）
  仍然只有页级那条路能接管。
- ⇒ 本件逐页量四件事，**证据说话**：
  ① **页级实例 `VS` 有没有被建出来**（非空 = 这页真的走了页级那条路）；② 每页**带标记**的表：几张、
     各多少行、**有没有 `.tw`**（⛔ 表级那条路**必须有 `.tw`** —— 没有自带滚动容器的表，表级接管不了）；
  ③ **不带标记**的 `tbody`：几张、各多少行、够不够阈值（≥ `VS_MIN`）—— 那些才是页级那条路**唯一**还能服务的东西；
  ④ 每页的 `VS_TS`（表级实例）＋ `scrollHost()` 指到谁。

⚠️ **读法**：`VS` / `VS_TS` / `NAV` / `scrollHost` 都是壳里的**顶层 `let`/`const`/函数**（`view.js` 是普通
   `<script src>` ⇒ 全局词法绑定）⇒ `page.evaluate` 里按名字直接读得到（同 `_shell_vskeep.py` 读 `VS_TS`）。

⚠️ **口径**：本件**只读**（切页 ＋ 读数；不点任何写动作、不改数据）。跑法（需服务在跑）：
   `backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_p5c_survey.py`
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "probe"))
sys.path.insert(0, str(ROOT / "backend"))

BASE = "http://127.0.0.1:8000"

#: 逐页读数（⚠️ 每个 `try` 都留着：某页坏了要**如实报出来**，⛔ 别让它把那页的量测吞成"空"）
_PROBE = r"""() => {
  const q = (s) => [...document.querySelectorAll(s)];
  let pvs = null;
  try { if (typeof VS !== 'undefined' && VS) pvs = {view: VS.view, n: VS.rows.length,
        tw: !!(VS.tw), hasTw: Object.prototype.hasOwnProperty.call(VS, 'tw')}; } catch (e) { pvs = 'ERR:' + e; }
  let ts = null;
  try { ts = (typeof VS_TS !== 'undefined' ? VS_TS : []).map(x => ({key: x.key, n: x.rows.length,
        tw: !!x.tw, a: x.a, b: x.b})); } catch (e) { ts = 'ERR:' + e; }
  let host = null;
  try { const h = (typeof scrollHost === 'function') ? scrollHost() : null;
        host = h ? (h.id || h.className || h.tagName) : null; } catch (e) { host = 'ERR:' + e; }
  return {
    tables: q('#view table').length,
    marked: q('#view tbody[data-vs]').map(tb => ({key: tb.getAttribute('data-vs'),
             tw: !!tb.closest('.tw'), domN: tb.children.length})),
    unmarked: q('#view tbody').filter(tb => !tb.hasAttribute('data-vs'))
             .map(tb => ({domN: tb.children.length, tw: !!(tb.closest && tb.closest('.tw'))})),
    pvs: pvs, ts: ts, host: host,
    vsMin: (typeof VS_MIN !== 'undefined') ? VS_MIN : null,
    scroll: (() => { const t = document.querySelector('#view .tw');
             return t ? {sh: t.scrollHeight, ch: t.clientHeight} : null; })(),
  };
}"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    from _shell_common import goto, settle
    from _shell_common import session_cookie

    out: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        errs: list[str] = []
        page.on("console", lambda m: errs.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"[pageerror] {e}"))
        ck, val = session_cookie()
        page.context.add_cookies([{"name": ck, "value": val, "url": BASE}])
        page.goto(BASE + "/app", wait_until="load", timeout=45000)
        page.wait_for_function("() => (PJs.length > 0) || (NO.length > 0) || BOOT_ERROR", timeout=20000)
        page.wait_for_function("() => document.querySelectorAll('#nav .sb-i').length > 0", timeout=20000)

        keys = page.evaluate("() => NAV.flatMap(g => g.items.map(i => i[0]))")
        print(f"逐页量测（NAV 共 {len(keys)} 页）：{', '.join(keys)}\n")
        print(f"{'页':<6}{'表':<4}{'带标记表(行数/tw)':<34}{'无标记 tbody(行数)':<24}{'页级 VS':<16}表级实例")
        print("-" * 118)
        for k in keys:
            try:
                goto(page, k)
                settle(page, timeout=15000)
                d = page.evaluate(_PROBE)
            except Exception as e:                       # noqa: BLE001
                out[k] = {"error": f"{type(e).__name__}: {e}"}
                print(f"{k:<6}⛔ 量不了：{type(e).__name__}: {e}")
                continue
            out[k] = d
            mk = ",".join(f"{m['key']}:{m['domN']}{'' if m['tw'] else '⛔无tw'}" for m in d["marked"]) or "—"
            ts = d["ts"] if isinstance(d["ts"], list) else []
            tsx = ",".join(f"{x['key']}:{x['n']}" for x in ts) or "—"
            un = ",".join(str(u["domN"]) for u in d["unmarked"]) or "—"
            pv = "**有**" if isinstance(d["pvs"], dict) else "无"
            print(f"{k:<6}{d['tables']:<4}{mk:<34}{un:<24}{pv:<16}{tsx}")
            #: ⚠️ 无标记但已经够阈值的 tbody —— 页级那条路**唯一**还服务的东西（删它会变"不虚拟化"）
            big = [u for u in d["unmarked"] if u["domN"] >= (d["vsMin"] or 400)]
            if big:
                print(f"       ⚠️ 本页有 **{len(big)}** 个无标记 tbody 已够阈值：{[u['domN'] for u in big]}"
                      f"（删了页级那条路 ⇒ 这些**不再虚拟化**）")

    print("\n" + "=" * 118)
    pv_pages = [k for k, d in out.items()
                if isinstance(d, dict) and isinstance(d.get("pvs"), dict)]
    notw = [(k, m["key"], m["domN"]) for k, d in out.items() if isinstance(d, dict)
            for m in d.get("marked", []) if not m["tw"]]
    bigpages = [(k, [u["domN"] for u in d["unmarked"]]) for k, d in out.items()
                if isinstance(d, dict)
                and any(u["domN"] >= (d.get("vsMin") or 400) for u in d.get("unmarked", []))]
    print(f"① **页级实例 `VS` 非空**的页：{pv_pages or '无'} —— "
          + ("⭐ `P5-c`（2026-09-30）之后壳里**已经没有这个变量**了 ⇒ 本行**恒为「无」**；"
             "若哪天又冒出来一页 ⇒ 页级那条路**被人加回来了**（判据 `test_页级虚拟滚动那条死路已删` 会先红）"
             if not pv_pages else "⛔ 还有页在走页级那条路（`P5-c` 之前的口径：**别删**）"))
    print(f"② 带标记却**没有 `.tw`** 的表：{notw or '无'} "
          f"{'⇒ 表级那条路覆盖了全部带标记的表' if not notw else '⇒ ⚠️ 这些表**表级接管不了**（`P5-c` 起会**原样写回、不虚拟化**）'}")
    print(f"③ 有**够阈值的无标记 tbody**的页：{bigpages or '无'} "
          f"{'⇒ 没有页指望页级那条路' if not bigpages else '⇒ ⛔ 这些行块删了页级就**不再虚拟化**（该收进 `TBL`）'}")
    print(f"④ 真机 console 错误：{len(errs)} 条" + ("" if not errs else f" —— {errs[:3]}"))

    dst = ROOT / "artifacts" / "_p5c_survey.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n逐页读数已落：{dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"C:\ProgramData\ms-playwright")
    raise SystemExit(main())
