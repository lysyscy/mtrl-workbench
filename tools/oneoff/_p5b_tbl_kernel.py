#!/usr/bin/env python
r"""`TAIL-64` **`P5-b`**：让 `data-vs` 标记**成为默认**（⛔ 不再逐表开关）。

**为什么是"默认"而不是"逐页点名铺一遍"**（本批最关键的一个判断，先量后定）：
真机读数（`artifacts/_smoke_out.txt`）各页行数 = `m01` 20 · `m03` 60 · `m04` 108 · `m05` 若干表 0 ·
`m06` 24 · `m07` 9/9 · `m09` 0 · **`m11` 329** · **`m08` 1373** ⇒ **只有 `m08` 过 400**。
⇒ 若按"逐页点名"铺，**今天一个都不会生效**；而本仓口径早就写着「⛔ 别用名单式：某页涨上去、忘了加
⇒ **永远不生效**」（`TAIL-66` 的原话）⇒ 正确的做法是**让标记无开关**：哪张表哪天涨到阈值，它就自动接管。

⚠️ **`TBL` 是 `U5`（壳 ⇄ 原型**逐字一致**）登记件** ⇒ 两侧**同批同句**改 ＋ 改前备份原型。
⚠️ 注释里 ⛔ **不许出现任何文件名**（交付面注释写了工程仓文件名 ⇒ `demo/_links.js` 判 FAIL）。

用法：`python tools/oneoff/_p5b_tbl_kernel.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
BACKUPS = ROOT / "artifacts" / "delivery-backups"
BAK_NAME = "原型-备份-20260930-P5b前.html"

OLD = """const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false,vs=false})=>{
  /* ⭐ `vs:true` ⇒ 在 `tbody` 上留一个 `data-vs="<key>"` 标记：「这一张表**可以由表级虚拟滚动接管**」。
     ⚠️ **不传就一个字节都不变**（老调用点零影响）· 标记**只说明"可以被接管"**，⛔ 不代表行为变了。 */
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody'+(vs?' data-vs="'+(key||'1')+'"':'')+'>'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};"""

NEW = """const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false})=>{
  /* ⭐ `data-vs` = 「这一张表**可以由表级虚拟滚动接管**」的标记（⚠️ **行数够才真的接管** —— 阈值那一侧说了算）。
     ⚠️ **一律带、⛔ 不设开关**：本仓口径是「**别用名单式**」—— 改成「逐表开关 / 逐页点名」的话，
     哪天某张表涨到阈值而没人记得加，它就**永远不生效、且不报错**（这正是 `TAIL-66` 当年的原话）。 */
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody data-vs="'+(key||'1')+'">'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};"""


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    assert PROTO.exists(), f"⛔ 原型不在预期位置：{PROTO}"
    for name, p in (("壳", PROJ), ("原型", PROTO)):
        txt = read(p)
        assert (txt.count(OLD), txt.count(NEW)) in ((1, 0), (0, 1)), \
            f"⛔ {name}：老内核 {txt.count(OLD)} / 新内核 {txt.count(NEW)}（应恰有一个）"
        print(f"   {name}：{'待改' if txt.count(OLD) else '已是新内核'}")

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / BAK_NAME
    if not dst.exists():
        shutil.copy2(PROTO, dst)
        print(f"  ✅ 备份原型 ⇒ {dst.relative_to(ROOT)}")

    for p in (PROJ, PROTO):
        txt = read(p)
        if txt.count(NEW) == 1:
            print(f"  ⏭ {p.name} 已是新内核（跳过）")
            continue
        out = txt.replace(OLD, NEW, 1)
        nl = "\r\n" if "\r\n" in p.read_text(encoding="utf-8", newline="")[:4000] else "\n"
        p.write_text(out.replace("\n", nl), encoding="utf-8", newline="")
        assert read(p) == out and out.count(NEW) == 1, f"⛔ {p.name} 写回自校验不过"
        print(f"  ✅ {p.name} `TBL` 标记已改为**一律带**（注释同句）")

    a, b = read(PROJ), read(PROTO)
    assert a.count(NEW) == 1 and b.count(NEW) == 1, "⛔ 终检：两侧新内核必须各在位一次"
    assert "vs=false" not in a and "vs=false" not in b, "⛔ 旧开关还在"
    print("  ✅ 终检：两侧逐字一致（`U5` 前提）· 旧开关已消失")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
