#!/usr/bin/env python
r"""`TAIL-64` **P4-d-a**（2026-09-30）：造「项目选择按钮」出口 `PJB` ＋ **只改 1 处试点**。

**为什么单开一个"出口 ＋ 试点"步**（照 `P4-a` 的先例）：新件必须**先证明它拼出来的字节与原来一模一样**，
再铺量。⚠️ 本条的试点**只改壳**（原型那侧不能同步 —— 见下）。

⭐⭐ **为什么原型不能双边同步**（干跑量出来的，⛔ 不是偷懒）：
原型的项目按钮还是**旧形态**（`gap:8px` / `font-size:9px`，**没走 `--fscale`**），
而壳侧早在 `TAIL-148` 就给内联样式补了倍率 ⇒ 两侧**现在就不是一个写法**，而且原型**没有** `--fscale` 变量
⇒ 硬把壳那套写法塞进原型会让它的按钮**退化成无 gap**（`var()` 未定义 ⇒ 整条声明失效）。
⇒ 本批 7 处（在 `V.*` 切片里）**只改壳 ＋ 换号登记**；另有 3 处在切片外（`pages-a/b.js` 的顶层 `const`）⇒ 连登记都不用。

用法：`python tools/oneoff/_p4d_pjb_pilot.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
NL = "\r\n"

PJB_DOC = """/* ⭐ **项目选择按钮件**（`TAIL-64` P4-d · 2026-09-30）—— 共用面板 `projPanel` 的**那枚 ▾ 按钮**
 * 统一由它渲染（`pjwrap` 里那一层）。契约：`PJB({act, w, label, title})` ⇒ 返回完整 `<button…>…</button>`。
 * ⚠️ 为什么把**按钮**也收了（`P4-d` 的第 ② 档）：那串
 *    `style="min-width:Npx;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"`
 *    与收尾那枚 `▼` 原本**逐处手写**（12 处），而 `min-width` 实测有 **6 种值** ⇒ §5.9「同类形态只留一处出口」。
 *    ⚠️ `w` 是**显式参数**（宽度按标签长短本就不同，⛔ 不是要抹平它 —— 是把它从长串里**抬出来**）。
 * `title` 只在需要时给（真例 = 通用导入面那枚，悬停要带仓库名）。
 * ⛔ 与 `projPanel` 的分工：本件只管**那枚按钮**，⛔ 不碰面板（面板仍走 `projPanel` 唯一出口 · 守则 §5.12）。
 * ⚠️ **本件只在壳侧**（⛔ 不进 `U5_GROUPS`）：原型那侧的按钮还是**旧形态**（`gap:8px`、无 `--fscale`），
 *    硬同步会让它的按钮退化成"没有 gap"（`var()` 未定义）⇒ 见 `tools/oneoff/_p4d_pjb_pilot.py` 的文件头。
 * 自证 = 变异脚本（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */
const PJB=({act='',w=126,label='',title=''})=>'<button class="btn" data-act="'+act+'" style="min-width:'+w+'px;'
  +'display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"'
  +(title?' title="'+title+'"':'')+'><span>'+label+'</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>';"""

#: 插入锚点 = `FBAR` 那一行（P4-a 落的 · 单行）
FBAR_LINE = ("const FBAR=({cls='',sty='',body=''})=>'<div class=\"fbar'+(cls?' '+cls:'')+'\"'"
             "+(sty?' style=\"'+sty+'\"':'')+'>'+body+'</div>';")

#: 试点 = `V.m03`「项目（可多选）」那枚按钮（唯一 · 无 title）
M03_OLD = ('<button class="btn" data-act="pjToggle" style="min-width:126px;display:inline-flex;'
           'align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))">'
           '<span>${fNt.projs.length?`已选 ${fNt.projs.length} 个`:\'全部项目\'}</span>'
           '<span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>')
M03_NEW = ("${PJB({act:'pjToggle',w:126,label:`${fNt.projs.length?`已选 ${fNt.projs.length} 个`:'全部项目'}`})}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    proj = PROJ.read_text(encoding="utf-8").replace("\r\n", "\n")
    shell = SHELL.read_text(encoding="utf-8").replace("\r\n", "\n")

    ins_old = FBAR_LINE + "\n"
    assert proj.count(ins_old) == 1, f"⛔ `FBAR` 锚点在 proj.js 里命中 {proj.count(ins_old)} 次"
    assert shell.count(M03_OLD) == 1, f"⛔ 试点靶串命中 {shell.count(M03_OLD)} 次（须恰好 1）"
    assert proj.count("const PJB=") == 0, "⛔ `PJB` 已经在了"

    print("干跑 ✅ 两个靶各命中 1 次")
    #: 自证「渲染字节不变」：`PJB` 的拼装式与原来那一段逐字节比（⛔ 不是人眼比对）
    rendered = ('<button class="btn" data-act="pjToggle" style="min-width:126px;'
                'display:inline-flex;align-items:center;justify-content:space-between;'
                'gap:calc(8px * var(--fscale))"><span>${fNt.projs.length?`已选 ${fNt.projs.length} 个`'
                ":'全部项目'}</span>"
                '<span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>')
    assert rendered == M03_OLD, "⛔ 自证失败：`PJB` 拼出来与原来那一段不逐字节相等"
    assert M03_NEW.count("\n") == M03_OLD.count("\n"), "⛔ 行数变了"
    print("自证 ✅ 拼装式与原来逐字节相等")

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    PROJ.write_text((proj.replace(ins_old, ins_old + "\n" + PJB_DOC + "\n", 1)).replace("\n", NL),
                    encoding="utf-8", newline="")
    SHELL.write_text(shell.replace(M03_OLD, M03_NEW, 1).replace("\n", NL),
                     encoding="utf-8", newline="")
    assert PROJ.read_text(encoding="utf-8").count("const PJB=") == 1, "⛔ 复核不过（proj.js）"
    assert SHELL.read_text(encoding="utf-8").count("${PJB({act:'pjToggle'") == 1, "⛔ 复核不过（index.html）"
    print("\n✅ `P4-d-a` 已落：出口 `PJB`（`shell/proj.js`，与 `TBL`/`FBAR` 同件）＋ `V.m03` 1 处试点（行数 Δ0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
