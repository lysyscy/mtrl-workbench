#!/usr/bin/env python
"""`A7` 逐页（`m11` 集采台账）· **量测先行**（2026-09-29 · 一次性 · ⛔ 只读）。

**为什么量这页**：`m11` 合同主表 **20 列**（`min-width` 视列而定），而**四个可编辑列**
（付款方式 / 备注 / 存档号 / 寄回日期）正好落在**最右**；首列只钉了「勾选框」（`TAIL-170`-③），
「序号 / 材料 / 供应商」**没钉** ⇒ 往右滚去填那 4 列时**看不见自己在给哪条合同填**（会填错行）——
与月度会大表（`TAIL-175`）**同族**。本案要量清：
  ① 表实际多宽 / 横向要滚多少；② 各列左缘与宽（尤其首 3 列与那 4 个可编辑列）；
  ③ 现在钉住的是哪几格；④ 滚到最右时**还能看见什么**。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a711_measure.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]

MEASURE = r"""
() => {
  const t = document.querySelector('.dt[data-sort-key="m11:jc"]');
  if (!t) return {err: '没找到 m11 的合同主表'};
  const wrap = t.parentElement;
  const ths = [...t.querySelectorAll('thead > tr:first-child > th')];
  const cols = ths.map((th, i) => {
    const r = th.getBoundingClientRect();
    return {i, txt: (th.innerText || '').replace(/\s+/g, '').slice(0, 8),
            left: Math.round(r.left), w: Math.round(r.width), fl: th.classList.contains('fl')};
  });
  const tr = t.querySelector('tbody tr');
  const cells = tr ? [...tr.children].map((td, i) => {
    const r = td.getBoundingClientRect();
    const inp = td.querySelector('input,select,button');
    return {i, cls: td.className, left: Math.round(r.left), w: Math.round(r.width),
            ctrl: inp ? (inp.tagName + (inp.dataset.act ? ':' + inp.dataset.act : '')) : ''};
  }) : [];
  return {
    rows: t.querySelectorAll('tbody tr').length,
    ncol: ths.length,
    tableW: Math.round(t.getBoundingClientRect().width),
    wrapW: Math.round(wrap.getBoundingClientRect().width),
    scrollW: wrap.scrollWidth, clientW: wrap.clientWidth,
    cols, cells,
    viewport: {w: window.innerWidth, h: window.innerHeight},
    /* ⭐ 「欠款」列（第 13 格）的**颜色分布** —— 判 §4.5「红只在真异常时才该出现」：
       若绝大多数行都被标红 ⇒ 红没有区分度（同 `TAIL-173`-② 的差额列那件事）。 */
    debt: (() => {
      const cells = [...t.querySelectorAll('tbody tr')].map(tr => tr.children[12]).filter(Boolean);
      const nz = cells.map(td => (td.innerText || '').trim()).filter(x => x && x !== '0.00');
      const red = cells.filter(td => (td.style.color || '').includes('--dg')).length;
      const green = cells.filter(td => (td.style.color || '').includes('--ok')).length;
      return {n: cells.length, nonzero: nz.length, red, green, sample: nz.slice(0, 5)};
    })(),
  };
}
"""

AFTER_SCROLL = r"""
() => {
  const t = document.querySelector('.dt[data-sort-key="m11:jc"]');
  const wrap = t.parentElement;
  wrap.scrollLeft = wrap.scrollWidth;                 /* 滚到最右 */
  const tr = t.querySelector('tbody tr');
  const first = tr ? tr.children[0].getBoundingClientRect() : null;
  const ths = [...t.querySelectorAll('thead > tr:first-child > th')];
  return {
    scrolledTo: Math.round(wrap.scrollLeft),
    /* 滚到最右后：屏幕上还能看见的表头列（左缘 ≥ 容器左缘） */
    visibleHeads: ths.filter(th => th.getBoundingClientRect().left >= wrap.getBoundingClientRect().left - 1)
      .map(th => (th.innerText || '').replace(/\s+/g, '').slice(0, 10)),
    /* 钉住的首格仍在原位吗（这是"钉住了"的定义） */
    firstCellLeft: first ? Math.round(first.left) : null,
    wrapLeft: Math.round(wrap.getBoundingClientRect().left),
  };
}
"""

#: 扫描：视口 × 界面大小档位 ⇒ 头几列宽是否是 `--fscale` 的**线性**函数
#  （线性 ⇒ 能写 `calc(Npx * var(--fscale))` 静态偏移；否则钉住要用别的机制 ⇒ 只报不改）
SCAN = r"""
() => {
  const t = document.querySelector('.dt[data-sort-key="m11:jc"]');
  if (!t) return null;
  const ths = [...t.querySelectorAll('thead > tr:first-child > th')];
  const w = i => Math.round(ths[i].getBoundingClientRect().width);
  return {f: getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim(),
          c0: w(0), c1: w(1), c3: w(3), c4: w(4)};
}
"""


def _session_cookie() -> tuple[str, str]:
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
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        pg.click('[data-k="m11"]')
        pg.wait_for_function("() => VIEW === 'm11'", timeout=15000)
        pg.wait_for_timeout(1500)

        d = pg.evaluate(MEASURE)
        if d.get("err"):
            print("⛔", d["err"])
            return 1
        print(f"视口 {d['viewport']['w']}×{d['viewport']['h']} · 表 {d['ncol']} 列 · "
              f"数据行 {d['rows']}")
        print(f"表宽 {d['tableW']} · 容器可见宽 {d['wrapW']} · 横向溢出 "
              f"{'**有**' if d['scrollW'] > d['clientW'] else '无'}（scrollW {d['scrollW']} / clientW {d['clientW']}）")
        print("\n列（左缘 / 宽 / 是否已钉 `.fl` / 内容）：")
        for c in d["cols"]:
            print(f"  #{c['i']:>2} L{c['left']:>6} w{c['w']:>4} {'🔒' if c['fl'] else '  '} {c['txt']}")
        print("\n数据行前 6 格 / 后 6 格（看可编辑控件落在哪）：")
        for c in (d["cells"][:6] + d["cells"][-6:]):
            print(f"  #{c['i']:>2} L{c['left']:>6} w{c['w']:>4} {c['cls'][:14]:<14} {c['ctrl']}"
                  f"{'   ← 已钉' if 'fl' in c['cls'] else ''}")

        dd = d["debt"]
        print(f"\n「欠款」列（第 13 格）颜色分布：共 {dd['n']} 行 · 非零 {dd['nonzero']} 行 · "
              f"红 {dd['red']} · 绿 {dd['green']}"
              f" ⇒ {'⚠️ 绝大多数都标红（红没有区分度）' if dd['n'] and dd['red'] / dd['n'] > 0.5 else '红/绿有区分度'}")
        print(f"  非零样例：{dd['sample']}")

        s = pg.evaluate(AFTER_SCROLL)
        print(f"\n滚到最右（scrollLeft = {s['scrolledTo']}）后：")
        print(f"  屏幕上还能看见的表头：{' / '.join(s['visibleHeads']) or '（无）'}")
        print(f"  勾选首格仍在原位？left={s['firstCellLeft']} vs 容器左缘 {s['wrapLeft']}"
              f" ⇒ {'✅ 钉住了' if s['firstCellLeft'] is not None and abs(s['firstCellLeft'] - s['wrapLeft']) <= 2 else '⛔ 没钉住/已滚走'}")
        print("\n⚠️ 量测结论供人判读：**序号 / 材料 / 供应商没钉** ⇒ 滚到最右填那 4 列时看不见行身份。")

        # ── 扫描：视口 × 档位 ⇒ 头几列宽是不是 `--fscale` 的线性函数（表头带排序箭头 ⇒ 可能不是）──
        print("\n扫描（列宽 vs `--fscale`）：勾选 #0 / 序号 #1 / 材料名 #3 / 供应商 #4")
        base = None
        for vw in (1440, 1920, 2560):
            pg.set_viewport_size({"width": vw, "height": 900})
            for scale in ("1", "1.4"):
                pg.evaluate("(s) => document.documentElement.style.setProperty('--fscale', s)", scale)
                pg.wait_for_timeout(350)
                d2 = pg.evaluate(SCAN)
                if base is None:
                    base = d2
                ratio = (f"预测×{d2['f']}：" +
                         " ".join(f"#k={round(base[k] * float(d2['f']))}" for k in ("c0", "c1", "c3", "c4")))
                mark = ""
                if abs(float(d2["f"]) - 1.0) > 1e-6 and base:
                    bad = [k for k in ("c0", "c1", "c3", "c4")
                           if abs(d2[k] - base[k] * float(d2["f"])) > 1.5]
                    mark = "  ⚠️ 非线性：" + ",".join(bad) if bad else "  ✅ 与线性预测一致"
                print(f"  视口 {vw} × 档 {d2['f']}: #0={d2['c0']} #1={d2['c1']} #3={d2['c3']} "
                      f"#4={d2['c4']}   {ratio}{mark}")
        print("\n判读：若「序号」列宽偏离线性预测 > 1.5px ⇒ 表头那个排序箭头是**固定像素** ⇒ "
              "⛔ 不能写 `calc(Npx * var(--fscale))`（那是 `TAIL-175` 的教训：先量再写算式）。")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
