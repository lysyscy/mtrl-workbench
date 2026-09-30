#!/usr/bin/env python
r"""`TAIL-64` **P4-d-b**（2026-09-30）：把**余下 11 处**「项目选择按钮」铺进统一出口 `PJB`。

**改法**（同 `FBAR` / `P4-d-a`）：**只把那一整枚按钮**换成 `${PJB({…})}` —— 按钮原本就在**一行里**
（首尾都在同一行）⇒ **行数 Δ0**；渲染字节按 `PJB` 的拼装式**逐字节自证**（⛔ 不是人眼比对）。

**范围怎么定的**（⛔ 不是"我记得有 12 处"）：
- 量测件 = `tools/oneoff/_p4db_survey.py`（**扫全部拆件 ＋ 仓外原型**）⇒ 壳侧共 **12 枚**带 `▼` 的样板按钮；
- 其中 **11 枚**属「项目选择」家族（`pjwrap` 那一层）；第 12 枚 = `ui.js` 的 **`mpToggle`（「选时间」按钮 · `tmBtn`）**
  —— **另一家族**（⛔ 不是项目选择）⇒ 本批**不并**，已在判据里写成**唯一一处例外**（判据只允许它那一行仍是手写）。
- ⚠️ `index.html` 那 **7 枚**在 `V.*` 切片里 ⇒ 只改壳会**让 `U1` 多出漂移登记**（换号）；余下 4 枚
  （`legacy.js` 的 `V.imp` —— 原型没有该页；`pages-a/b.js` 是顶层 `const` 造的条）**在 `U1` 视野外** ⇒ 零登记。
- ⛔ **原型那侧一律不动**（施工图 §8.8 第 1 条）：原型按钮是旧形态（`gap:8px`、无 `--fscale`），
  硬同步会让它的 `gap` 整条失效（`var()` 未定义）⇒ 本批**壳侧单边**，不备份原型（没碰它）。

用法：`python tools/oneoff/_p4d_pjb.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PROJ = WEB / "shell" / "proj.js"
PARTS = ("index.html",) + tuple(f"shell/{p.name}" for p in sorted((WEB / "shell").glob("*.js")))
NL = "\r\n"

#: 手写样板里那串 `style` 的**固定部分**（`w` 是唯一变量）—— 也是判据扫描时的记号
STYLE_TAIL = (";display:inline-flex;align-items:center;justify-content:space-between;"
              "gap:calc(8px * var(--fscale))")
MUT_SPAN = '<span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span>'
MUT_TAIL = MUT_SPAN + '</button>'

#: 一枚样板按钮 = `<button class="…" data-act="…"[其它属性] style="min-width:Npx…">标签 ＋ ▼</button>`（单行）
BTN = re.compile(
    r'<button class="(?P<cls>[^"]*)" data-act="(?P<act>[^"]*)"(?P<attrs>[^>]*)>'
    r'(?P<div>.*?)</button>')

#: ⛔ 本批**不并**的那一枚：**另一家族**（「选时间」· `tmBtn`）—— 判据里也写着这处例外
SKIP = {"mpToggle"}

#: 期望被并的 11 枚（⛔ 写死是为了**发现"多一枚/少一枚"**，不是为了当第二份名单 —— 判据那边是扫描式）
EXPECT = ("plPjToggle", "ledPjToggle", "flPjToggle", "procPjToggle", "invWhToggle",
          "awfPjToggle", "jcPjToggle", "impPjToggle", "ledExpPjToggle", "lgPjToggle", "jcNPjToggle")

PJB_OLD = """const PJB=({act='',w=126,label='',title=''})=>'<button class="btn" data-act="'+act+'" style="min-width:'+w+'px;'
  +'display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"'
  +(title?' title="'+title+'"':'')+'><span>'+label+'</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>';"""

PJB_NEW = """const PJB=({act='',w=126,label='',title='',cls='btn',attrs=''})=>'<button class="'+cls+'" data-act="'+act+'"'+attrs
  +' style="min-width:'+w+'px;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"'
  +(title?' title="'+title+'"':'')+'><span>'+label+'</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>';"""

#: 两处补出来的参（`P4-d-b` 实测**两种形态**逼出来的 · 默认值都保持旧行为）：
PJB_DOC_ADD = """ * ⭐ `P4-d-b` 铺量（2026-09-30）时量出**两种形态**，于是补两个参（**默认值都保持旧行为** ⇒ 老调用点零变化）：
 *    · `cls`（默认 `'btn'`）—— 真例 = 台账那枚 `ledPjToggle` 的**动态 class**
 *      （展开时 `btn on`，用户 2026-09-28 `TAIL-142` 要的"点开必须变样"）。
 *    · `attrs`（默认 `''`）—— **排在 `style` 之前**的额外属性。真例 = 同一枚的 `title`：
 *      它原本就写在 `style` **之前**（而 `title` 那个参是排在 `style` **之后**的，见下）。
 *      ⚠️ 属性顺序在 HTML 里**无语义**，但本仓这一路的验收口径是「**渲染字节逐字节不变**」⇒ 照原样摆。
 * ⚠️ `attrs` / `title` **都是"额外属性"但位置不同**（前者在 `style` 前、后者在后）——
 *    ⛔ 别为某一处随手挑一个：挑错了**渲染字节就变了**（脚本里的自证会当场拦下）。
"""


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse(btn: str) -> dict[str, str]:
    """把一枚手写按钮拆成 `PJB` 的实参（⛔ 解析失败就报出来，别猜）。"""
    m = BTN.fullmatch(btn)
    assert m, f"⛔ 这枚按钮的形状不认识：{btn[:80]}…"
    attrs, div = m.group("attrs"), m.group("div")
    sm = re.search(r'style="min-width:(\d+)px' + re.escape(STYLE_TAIL) + r'"', attrs)
    assert sm, f"⛔ 这枚按钮的 style 不是样板那串（act={m.group('act')}）"
    lm = re.fullmatch(r"<span>(.*?)</span>" + re.escape(MUT_SPAN), div, re.S)
    assert lm, f"⛔ 这枚按钮的标签/收尾不是样板那串（act={m.group('act')}）"
    rest = re.sub(r'\s*style="[^"]*"', "", attrs)       # 去掉 `style` 那一段（含它前面的空白）⇒ 剩下的额外属性
    tm = re.search(r' title="([^"]*)"', rest)
    assert tm or not rest.strip(), f"⛔ 这枚按钮有多余属性我没处理：{rest!r}（act={m.group('act')}）"
    if tm:
        assert rest.strip() == tm.group(0).strip(), \
            f"⛔ 除 `title` 外还有别的属性（本件没处理）：{rest!r}（act={m.group('act')}）"
    #: `title` 在 `style` **之前** ⇒ 走 `attrs`；在**之后** ⇒ 走 `title` 那个参
    before = bool(tm) and attrs.index('title="') < attrs.index('style="')
    return {"act": m.group("act"), "cls": m.group("cls"), "w": sm.group(1),
            "label": lm.group(1),
            "attrs": rest if before else "",
            "title": (tm.group(1) if (tm and not before) else "")}


def render(p: dict[str, str]) -> str:
    """`PJB` 的内核**照抄一遍**（Python 版）—— 用来**逐字节自证**（⛔ 不是人眼比对）。"""
    return ('<button class="' + p["cls"] + '" data-act="' + p["act"] + '"' + p["attrs"]
            + ' style="min-width:' + p["w"] + 'px' + STYLE_TAIL + '"'
            + (' title="' + p["title"] + '"' if p["title"] else "")
            + '><span>' + p["label"] + '</span>' + MUT_TAIL)


def call(p: dict[str, str]) -> str:
    """拼出调用式 `${PJB({…})}`（⚠️ 属性顺序：act / w / label / cls / attrs / title）。"""
    parts = [f"act:'{p['act']}'", f"w:{p['w']}", "label:`" + p["label"] + "`"]
    if p["cls"] != "btn":
        parts.append("cls:`" + p["cls"] + "`")
    if p["attrs"]:
        a = p["attrs"]
        assert "`" not in a and "${" not in a, f"⛔ attrs 里有反引号/`${{`（本件按单引号包）: {a!r}"
        assert "'" not in a, f"⛔ attrs 里有单引号（本件按单引号包）: {a!r}"
        parts.append("attrs:'" + a + "'")
    if p["title"]:
        t = p["title"]
        assert "`" not in t, f"⛔ title 里有反引号: {t!r}"
        parts.append("title:`" + t + "`")
    return "${PJB({" + ",".join(parts) + "})}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell = {n: read(WEB / n) for n in PARTS}
    todo: list[tuple[str, str, str, dict[str, str]]] = []      # (件, 靶串, 替换串, 解析结果)
    for n in PARTS:
        for m in BTN.finditer(shell[n]):
            if not m.group(0).endswith(MUT_TAIL):
                continue
            if f"min-width:" not in m.group("attrs") or STYLE_TAIL not in m.group("attrs"):
                continue
            if m.group("act") in SKIP:      # ⚠️ 先判跳过（那枚的标签格是 `<span class="fc">`，解析器不认）
                print(f"  ⏭ {n:16s} {m.group('act'):16s} —— **另一家族**（不并 · 见判据那处例外）")
                continue
            p = parse(m.group(0))
            assert shell[n].count(m.group(0)) == 1, \
                f"⛔ {n} 里这枚按钮不是唯一的（{p['act']}）⇒ 替换会歧义"
            assert "\n" not in m.group(0), f"⛔ {p['act']} 跨行了 —— 本件按「单行」设计（行数 Δ0）"
            r = render(p)
            assert r == m.group(0), (
                f"⛔ 自证失败：`PJB` 拼出来与原来那一段不逐字节相等（act={p['act']}）\n"
                f"    期望：{m.group(0)}\n    实得：{r}")
            todo.append((n, m.group(0), call(p), p))
            print(f"  ✅ {n:16s} {p['act']:16s} w={p['w']:<4s} cls={p['cls'][:20]:<20s} "
                  f"attrs={'有' if p['attrs'] else '—':<2s} title={'有' if p['title'] else '—'}  自证=逐字节相等")

    acts = [t[3]["act"] for t in todo]
    print(f"⇒ 共 **{len(todo)}** 枚 · act = {acts}")
    assert sorted(acts) == sorted(EXPECT), (
        f"⛔ 命中清单与期望不符（多/少了）—— 期望 {sorted(EXPECT)}，实得 {sorted(acts)}")

    # ── 内核那两行也要一起改（补 `cls` / `attrs`）—— 单独断言，免得"只改了调用点"
    pr = read(PROJ)
    assert pr.count(PJB_OLD) == 1, f"⛔ `PJB` 旧内核在 proj.js 里命中 {pr.count(PJB_OLD)} 次（期望 1）"
    assert pr.count(" * `title` 只在需要时给") == 1, "⛔ `PJB` 注释锚点命中数不对"
    doc_anchor = " * `title` 只在需要时给（真例 = 通用导入面那枚，悬停要带仓库名）。\n"
    assert pr.count(doc_anchor) == 1, "⛔ `PJB` 注释锚点（title 那句）命中数不对"

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    for n, old, new, _p in todo:
        shell[n] = shell[n].replace(old, new, 1)
    for n in PARTS:
        out = shell[n]
        assert len(out.split("\n")) == len(read(WEB / n).split("\n")), f"⛔ {n} 行数变了（应 Δ0）"
        if out == read(WEB / n):
            continue
        (WEB / n).write_text(out.replace("\n", NL), encoding="utf-8", newline="")
        assert read(WEB / n) == out, f"⛔ {n} 写回自校验不过"
        print(f"  ✅ {n:16s} 已写（行数 Δ0）")

    pr2 = pr.replace(PJB_OLD, PJB_NEW, 1).replace(doc_anchor, doc_anchor + PJB_DOC_ADD, 1)
    PROJ.write_text(pr2.replace("\n", NL), encoding="utf-8", newline="")
    assert read(PROJ).count("const PJB=") == 1 and "cls='btn'" in read(PROJ), "⛔ proj.js 复核不过"
    print(f"  ✅ {'shell/proj.js':16s} `PJB` 已补 `cls` / `attrs`（注释同批）")
    print(f"\n✅ `P4-d-b` 已落：{len(todo)} 处调用点 ＋ 出口补两参（⛔ 原型未动）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
