#!/usr/bin/env python
"""`TAIL-175` 的量测先行 —— **真机量**大表（`m07` 月度会大表）的吸附几何（2026-09-29 · 只读）。

**为什么先量**（交接材料原话）：「给大表首列加固定 `.fl` · ⚠️ 两行表头 ⇒ sticky 要另算 top 偏移
⇒ **先真机量再动手**」。⚠️ 大表与房内既有先例（`m06` 机械表 / `m11` / `m03` / `m04`）**形态不同**：
  · 别人是**一行表头**，大表是**两行表头**（`rowspan="2"` ＋ `colspan`）⇒ `top:0` 会在第二行**压住第一行**；
  · 别人的合计行是 `leadSpan:1`，大表是 **`leadSpan:2`**（首格 `colspan="2"`）⇒ 固定列钉哪几列才有关系；
  · 大表**宽度是内容撑出来的**（`min-width:1620px` ＋ `table-layout:auto`）⇒
    「第 2 列的 `left` 偏移」能不能用一个**静态算式**写死，必须先量（宽屏/大档位下会不会变）。

四段（⛔ 全是只读 ＋ 页面内临时注入，**一个磁盘文件都不改**）：
  A 现状（未钉）—— 滚到最右 ＋ 下滚，看两行表头各自的 `top`；
  B 临时钉「序号」一列 —— 看表头 / 数据行 / 合计格对不对得上；
  C 临时钉「序号 ＋ 项目名称」两列 —— 看两列有没有缝、合计格是否恰好盖住两列；
  D **扫描**：视口宽 × 界面大小档（`--fscale`）⇒ 量「序号」列的真实宽，与算式 `39px × --fscale` 比对；
  E 给「序号」列**写死宽**（候选 CSS）后再扫一遍 —— 验它能不能把列宽钉在算式上。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_a175_measure.py`
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
REPO = pathlib.Path(__file__).resolve().parents[2]
BIG = 'table[data-sort-key="m07:bigtable"]'
#: 「序号」列在**标准档**下的实测宽（= padding 8×2 ＋ 两个汉字 11.5×2 ＝ 39；随 `--fscale` 线性缩放）
W0_STD = 39


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


#: 量「整张表 ＋ 表头两行 ＋ 首数据行 ＋ 合计行」的盒子（相对**滚动容器**左/上边，便于看吸附）
READ = r"""(sel) => {
  const tb = document.querySelector(sel);
  if (!tb) return {err: '没找到大表'};
  const tw = tb.closest('.tw');
  const box = e => { const b = e.getBoundingClientRect(); return {
    t: Math.round(b.top - tw.getBoundingClientRect().top),
    l: Math.round(b.left - tw.getBoundingClientRect().left),
    w: Math.round(b.width), h: Math.round(b.height) }; };
  const cells = tr => [...tr.children].map(td => Object.assign(
    {txt: (td.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 7), cs: td.colSpan, rs: td.rowSpan},
    box(td)));
  const hrows = [...tb.querySelectorAll('thead tr')];
  const brows = [...tb.querySelectorAll('tbody tr')];
  const sum = brows.find(tr => tr.className.indexOf('sumrow') >= 0);
  return {
    tw: {sw: tw.scrollWidth, cw: tw.clientWidth, sh: tw.scrollHeight, ch: tw.clientHeight,
         sl: Math.round(tw.scrollLeft), st: Math.round(tw.scrollTop)},
    tableW: Math.round(tb.getBoundingClientRect().width),
    head: hrows.map(cells),
    bodyN: brows.length,
    row1: brows[0] ? cells(brows[0]) : null,
    sum: sum ? cells(sum) : null,
  };
}"""

#: 临时给首列（可含第 2 列）挂 `.fl` —— 纯页面内注入，⛔ 不落盘
PIN = r"""([sel, ncol]) => {
  const tb = document.querySelector(sel);
  const th0 = tb.querySelector('thead tr th');           /* 序号（rowspan=2） */
  const w0 = Math.round(th0.getBoundingClientRect().width);
  [...tb.querySelectorAll('thead tr')].forEach(tr => {
    [...tr.children].slice(0, ncol).forEach((c, i) => {
      c.classList.add('fl');
      if (i === 1) c.style.left = w0 + 'px';
    });
  });
  [...tb.querySelectorAll('tbody tr')].forEach(tr => {
    [...tr.children].slice(0, ncol).forEach((c, i) => {
      c.classList.add('fl');
      if (i === 1) c.style.left = w0 + 'px';
    });
  });
  /* 合计行首格（`leadSpan:2` ⇒ colspan=2）—— 一格就占前两列 */
  const sum = [...tb.querySelectorAll('tbody tr')].find(tr => tr.className.indexOf('sumrow') >= 0);
  if (sum && sum.children[0]) sum.children[0].classList.add('fl');
  return {w0: w0, pinned: ncol};
}"""

#: 候选 CSS：给「序号」列**写死宽**（= 第 2 列 `left` 偏移要用的那个算式）
FORCE_W0 = r"""() => {
  const s = document.createElement('style');
  s.id = 'a175probe';
  s.textContent = '.dt[data-sort-key="m07:bigtable"] thead tr:first-child th:first-child'
                + '{width:calc(39px * var(--fscale))}';
  document.head.appendChild(s);
}"""

#: 只量前两列的宽（扫描用）
MEASURE_2 = r"""(sel) => {
  const tb = document.querySelector(sel);
  const tw = tb.closest('.tw');
  const th = tb.querySelectorAll('thead tr:first-child th');
  const f = getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim() || '1';
  return {cw: tw.clientWidth, tw_w: Math.round(tb.getBoundingClientRect().width),
          w0: Math.round(th[0].getBoundingClientRect().width),
          w1: Math.round(th[1].getBoundingClientRect().width), f: f};
}"""


def _dump(tag: str, d: dict) -> None:
    if d.get("err"):
        print(f"{tag} ⛔ {d['err']}")
        return
    tw = d["tw"]
    print(f"{tag} 容器 {tw['cw']}×{tw['ch']} 内容 {tw['sw']}×{tw['sh']} · "
          f"横溢={'是' if tw['sw'] > tw['cw'] + 2 else '否'} · 纵溢={'是' if tw['sh'] > tw['ch'] + 2 else '否'} · "
          f"表宽={d['tableW']} · 行数={d.get('bodyN')} · scrollLeft={tw['sl']} scrollTop={tw['st']}")
    for i, row in enumerate(d["head"]):
        seg = " | ".join(f"{c['txt']}(rs{c['rs']},cs{c['cs']}) t={c['t']} l={c['l']} w={c['w']} h={c['h']}"
                         for c in row)
        print(f"    表头第{i + 1}行：{seg}")
    if d.get("row1"):
        r = d["row1"]
        print("    首数据行：" + " | ".join(f"{c['txt'] or '·'} l={c['l']} w={c['w']}" for c in r[:4]) + " …")
    if d.get("sum"):
        r = d["sum"]
        print("    合计行：" + " | ".join(f"{c['txt'] or '·'}(cs{c['cs']}) l={c['l']} w={c['w']}"
                                        for c in r[:3]) + " …")
    else:
        print("    合计行：（没有 —— 表为空）")


def _scroll_right(pg, dy: int = 120) -> None:
    pg.evaluate("""(a) => { const tw = document.querySelector(a[0]).closest('.tw');
                   tw.scrollLeft = tw.scrollWidth; tw.scrollTop = a[1]; }""", [BIG, dy])
    pg.wait_for_timeout(400)


def main() -> int:
    name, val = _session_cookie()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": name, "value": val, "url": BASE}])
        pg.goto(f"{BASE}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
        pg.click('[data-k="m07"]')
        pg.wait_for_function("() => VIEW === 'm07'", timeout=15000)
        pg.wait_for_timeout(1500)

        print("=" * 100)
        print("A · 现状（未钉）—— 滚到最右 ＋ 向下 120px 时两行表头各自的 top")
        print("=" * 100)
        _scroll_right(pg)
        a = pg.evaluate(READ, BIG)
        _dump("  [未钉]", a)
        if not a.get("err") and len(a["head"]) >= 2:
            r1, r2 = a["head"][0], a["head"][1]
            print(f"  ⇒ 表头两行 top：第1行 {r1[0]['t']} / 第2行 {r2[0]['t']}（第2行首格 h={r2[0]['h']}）"
                  f" ⇒ {'⚠️ 两行都在 top=0 = 第2行会压住第1行' if r2[0]['t'] == 0 else '第2行有自己的 top 偏移（因为容器没纵向滚动）'}")

        print()
        print("=" * 100)
        print("B · 临时钉「首列 = 序号」")
        print("=" * 100)
        pg.evaluate(PIN, [BIG, 1])
        pg.wait_for_timeout(400)
        b1 = pg.evaluate(READ, BIG)
        _dump("  [钉1列]", b1)
        if not b1.get("err"):
            h0, d0 = b1["head"][0][0], (b1["row1"][0] if b1.get("row1") else None)
            s0 = b1["sum"][0] if b1.get("sum") else None
            print(f"  ⇒ 序号表头 l={h0['l']} w={h0['w']} · 首数据格 l={d0['l'] if d0 else '-'} w={d0['w'] if d0 else '-'}"
                  f" · 合计格（colspan={s0['cs'] if s0 else '-'}）l={s0['l'] if s0 else '-'} w={s0['w'] if s0 else '-'}")

        print()
        print("=" * 100)
        print("C · 临时钉「序号 ＋ 项目名称」两列（第 2 列 left = 实测序号宽）")
        print("=" * 100)
        pg.evaluate(PIN, [BIG, 2])
        pg.wait_for_timeout(400)
        c = pg.evaluate(READ, BIG)
        _dump("  [钉2列]", c)
        if not c.get("err"):
            h0, h1 = c["head"][0][0], c["head"][0][1]
            s0 = c["sum"][0] if c.get("sum") else None
            print(f"  ⇒ 序号 l={h0['l']} w={h0['w']} · 项目名称 l={h1['l']} w={h1['w']}（序号右缘={h0['l'] + h0['w']}）"
                  f" · 合计格 l={s0['l'] if s0 else '-'} w={s0['w'] if s0 else '-'}")
            print(f"  ⇒ {'✅ 第2列紧贴第1列右缘（无缝无叠）' if h1['l'] == h0['l'] + h0['w'] else '⚠️ 第2列与第1列错位'}"
                  f" · {'✅ 合计格恰好盖住前两列' if s0 and s0['l'] == h0['l'] and s0['w'] == h0['w'] + h1['w'] else '⚠️ 合计格与前两列宽不等'}")
        pg.evaluate("() => { const s = document.getElementById('a175probe'); if (s) s.remove(); }")

        print()
        print("=" * 100)
        print(f"D · 扫描：序号列的真实宽 vs 算式 `{W0_STD}px × --fscale`（⛔ 决定第2列能不能写死 left）")
        print("=" * 100)
        sweeps = [(1440, "1"), (1920, "1"), (2560, "1"), (1440, "1.4"), (1920, "1.4"), (2560, "1.4")]
        print("     视口  档      容器宽  表宽   序号宽  项目名称宽  算式值  差   判定")
        worst = 0
        for vw, f in sweeps:
            pg.set_viewport_size({"width": vw, "height": 900})
            pg.evaluate("(f) => document.documentElement.style.setProperty('--fscale', f)", f)
            pg.wait_for_timeout(400)
            m = pg.evaluate(MEASURE_2, BIG)
            exp = round(W0_STD * float(f))
            ok = abs(m["w0"] - exp) <= 1
            worst = max(worst, abs(m["w0"] - exp))
            print(f"    {vw:>5}  {f:>4}   {m['cw']:>6}  {m['tw_w']:>5}  {m['w0']:>6}  {m['w1']:>9}  {exp:>6}  "
                  f"{m['w0'] - exp:>3}   {'✅ 对得上' if ok else '⛔ 对不上'}")

        print()
        print("=" * 100)
        print("E · 给序号列**写死宽**（候选 CSS `width:calc(39px * var(--fscale))`）后再扫一遍")
        print("=" * 100)
        pg.evaluate(FORCE_W0)
        print("     视口  档      容器宽  表宽   序号宽  项目名称宽  算式值  差   判定")
        worst2 = 0
        for vw, f in sweeps:
            pg.set_viewport_size({"width": vw, "height": 900})
            pg.evaluate("(f) => document.documentElement.style.setProperty('--fscale', f)", f)
            pg.wait_for_timeout(400)
            m = pg.evaluate(MEASURE_2, BIG)
            exp = round(W0_STD * float(f))
            ok = abs(m["w0"] - exp) <= 1
            worst2 = max(worst2, abs(m["w0"] - exp))
            print(f"    {vw:>5}  {f:>4}   {m['cw']:>6}  {m['tw_w']:>5}  {m['w0']:>6}  {m['w1']:>9}  {exp:>6}  "
                  f"{m['w0'] - exp:>3}   {'✅ 对得上' if ok else '⛔ 对不上'}")

        print()
        print(f"  结论：不写死宽 ⇒ 最大偏差 {worst}px；写死宽 ⇒ 最大偏差 {worst2}px")
        pg.evaluate("() => document.documentElement.style.removeProperty('--fscale')")

    print()
    print("（只读量测 · 一个磁盘文件都没改）")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
