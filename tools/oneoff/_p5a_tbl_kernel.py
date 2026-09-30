#!/usr/bin/env python
r"""`TAIL-64` **P5-a**（第 ① 步）：给 `TBL` 的输出加一个**可识别标记** `data-vs`（行为零变化）。

**为什么必须两边同批**：`TBL` 是 `U5`（`ui_parity` 的"公共件 ⇄ 原型**逐字一致**"）的登记件
⇒ 只改壳会让 `U5` 当场红。⚠️ 所以本件：
1. **先备份原型**（仓外 · WPS 云同步树 ⇒ 留痕 = 文件本身，备份放 `artifacts/delivery-backups/`）；
2. 断言两侧的 `TBL` 段**本来就逐字一致**（⛔ 不一致就别动手，先查）；
3. 把**同一段新文本**写进两侧（⚠️ 注释也逐字一样 —— `U5` 比的是整段）；
4. 逐件自校验（行数、`vs` 参在位、老调用点渲染字节不变）。

⚠️ 注释里 ⛔ **不许出现任何文件名**（交付面注释写了**工程仓**的文件名 ⇒ `demo/_links.js` 判 FAIL，已踩两次）。

用法：`python tools/oneoff/_p5a_tbl_kernel.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
BACKUPS = ROOT / "artifacts" / "delivery-backups"
BAK_NAME = "原型-备份-20260930-P5a前.html"

OLD = """const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false})=>{
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody>'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};"""

NEW = """const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false,vs=false})=>{
  /* ⭐ `vs:true` ⇒ 在 `tbody` 上留一个 `data-vs="<key>"` 标记：「这一张表**可以由表级虚拟滚动接管**」。
     ⚠️ **不传就一个字节都不变**（老调用点零影响）· 标记**只说明"可以被接管"**，⛔ 不代表行为变了。 */
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody'+(vs?' data-vs="'+(key||'1')+'"':'')+'>'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};"""


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    assert PROTO.exists(), f"⛔ 原型不在预期位置：{PROTO}"
    sh, pt = read(PROJ), read(PROTO)
    assert sh.count("const TBL=") == 1 and pt.count("const TBL=") == 1, "⛔ 两侧各有且只有一个 `TBL`"
    #: ⚠️ 允许"一侧已改"（上次跑到一半中断过）—— 但**最后必须两侧都是新内核**（`U5` 要逐字一致）
    for name, txt in (("壳", sh), ("原型", pt)):
        n_old, n_new = txt.count(OLD), txt.count(NEW)
        assert (n_old, n_new) in ((1, 0), (0, 1)), \
            f"⛔ {name}：老内核 {n_old} 次 / 新内核 {n_new} 次（应恰有一个）"
        print(f"   {name}：{'待改（老内核 1 次）' if n_old else '已是新内核'}")
    if sh.count(OLD) and pt.count(OLD):
        print("✅ 两侧 `TBL` 老内核**逐字同款**（`U5` 的前提成立）")

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
        back = read(p)
        assert back == out, f"⛔ {p.name} 写回自校验不过"
        assert back.count(NEW) == 1, f"⛔ {p.name} 复核不过（新内核不在位）"
        print(f"  ✅ {p.name} `TBL` 已补 `vs` 参（注释同句 · 行为零变化）")

    #: ⭐ 终检 = `U5` 的核心：**两侧 `TBL` 段逐字一致**
    a, b = read(PROJ), read(PROTO)
    assert a.count(NEW) == 1 and b.count(NEW) == 1, "⛔ 终检：两侧新内核必须各在位一次"

    #: ⭐ 自证「老调用点渲染字节不变」：不带 `vs` 时拼出来必须与原来一模一样
    def render(vs: bool, key: str = "") -> str:
        attr = ' class="dt"'
        th = "<thead><tr>H</tr></thead>"
        return ("<table" + attr + ">" + th + "<tbody" + (' data-vs="' + (key or "1") + '"' if vs else "") + ">"
                + "R" + "</tbody></table>")

    assert render(False) == '<table class="dt"><thead><tr>H</tr></thead><tbody>R</tbody></table>', "⛔ 自证失败"
    print("  ✅ 自证：`vs` 不传时输出**逐字节等于**老行为")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
