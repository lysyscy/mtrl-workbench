#!/usr/bin/env python
"""`TAIL-64` **P4-a**（2026-09-30）—— 造「筛选栏外壳」出口 `FBAR` ＋ 只改 **1 处试点**（`V.m01`）。

**为什么落成脚本**（⛔ 别在编辑器里手改这三件）：
  ① 本批要**同批同句**改三件（壳 `proj.js` / 壳 `index.html` / 交付面原型），三件的换行全是 **CRLF**；
  ② 交付面原型在**仓外**（WPS 云同步树）⇒ 改前必须先备份到 `.codebuddy/backups/`；
  ③ 本仓血泪：**带 `$` / 引号 / 中文字面**的替换靠手点必错 ⇒ 一律**按 bytes 精确替换 ＋ 断言"恰好命中一次"**。

**本脚本做四件事**（全部带断言，任何一条不成立就 `rc=1` 且**不写**）：
 1. 备份原型（改前那一份）到 `.codebuddy/backups/`；
 2. 在 `shell/proj.js` 与原型里**同一位置**（`TBL` 之后）插入同一段 `FBAR`（注释 ` * ` 缩进 ⇒ 不进 `TBL` 的 `U5` 段）；
 3. 把 `V.m01` 的筛选栏**外壳**换成 `FBAR` 调用（**两侧同改**）—— 栏里的控件**一行不动**；
 4. **自证「渲染字节不变」**：按 `FBAR` 的拼装方式把新写法在 Python 里还原一次，
    必须与**改前那一段**逐字节相等（不是"看着一样"）。

用法：`python tools/oneoff/_p4a_fbar.py`
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
PROTO = FACE / "demo" / "材料报表自动化工作台-交互原型.html"
BACKUPS = ROOT / _run_dir() / "delivery-backups"

NL = "\r\n"


def crlf(s: str) -> bytes:
    """把多行 `str` 变成 **CRLF** 的 `bytes`（三件的换行都是 CRLF）。"""
    return s.replace("\n", NL).encode("utf-8")


# ── ① `FBAR` 出口（两侧**逐字一致**；注释一律 ` * ` 起头 ⇒ 被 `U5` 的段尾削除规则吃掉、
#      ⛔ 不让它挂到前一个件（`TBL`）的段上）。
FBAR_DOC = """/* ⭐ **筛选栏件**（`TAIL-64` P4-a · 2026-09-30）—— 一根筛选栏的**外壳**统一由它渲染（`fbar` 那层）。
 * 契约：`FBAR({cls, sty, body})` ⇒ 返回 `<div class="fbar [cls]"[ style="…"]>body</div>`。
 * ⚠️ 本批（P4-a）**只收外壳**：栏里的控件（`.fi` / 按钮 / 汇总）留在调用点**原地** —— 与 `TBL` 的 P0 同款，
 *    先证明「外壳换写法、控件留在原地」能做到**行数与渲染字节都不变**；⛔ 别顺手把控件也挪进来。
 * `cls` 的合法取值 = `.fbar` 的变体（`pane` / `strip` / `strip mb6` / `plate`），声明见 `index.html` 的样式块。
 * 自证：`tools/mut/_mut_fbar.py`（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */
const FBAR=({cls='',sty='',body=''})=>'<div class="fbar'+(cls?' '+cls:'')+'"'+(sty?' style="'+sty+'"':'')+'>'+body+'</div>';"""

#: 插入锚点 = `TBL` 件本体（两侧逐字一致 · `U5` 正在守它）⇒ 插在它**后面**。
BLOCK_TBL = """const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false})=>{
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody>'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};"""

# ── ② `V.m01` 筛选栏那一段（两侧**逐字相同** —— 已实测：壳 929–934 ⇄ 原型 2749–2755 一字不差）
M01_HEAD, M01_TAIL = '    <div class="fbar">', '    </div>'
M01_MID = """\n      <div class="fi"><label>项目状态（默认在建）</label><select class="inp" id="fPjStatus" data-act="fPjStatus">${optsOf(enumVals('pjStatus').concat(['全部']),fPj.status)}</select></div>
      <div class="fi"><label>项目类型</label><select class="inp" id="fPjType" data-act="fPjType">${optsOf(['全部'].concat(enumVals('pjType').map(v=>enumText('pjType',v))),fPj.type)}</select></div>
      <div class="fi"><label>全名 / 仓库名 / 展示名</label><input class="inp" id="fPjQ" data-act="fPjQ" value="${esc(fPj.q)}" placeholder="模糊搜索"></div>
      <button class="btn" data-act="fPjReset">重置</button>
      <span class="pill" style="margin-left:auto">显示 <b>${rows.length}</b> 行 · 含占位行 ${PJs.filter(p=>p.name.startsWith('未建仓-')).length}</span>
"""
M01_OLD = M01_HEAD + M01_MID + M01_TAIL     # 首行 ＋ 中间控件（一行不动）＋ 收尾行

#: 新写法：**只换首尾两行**（中间控件一行不动）—— 行数 **Δ0**
M01_NEW = "    ${FBAR({body:`" + M01_MID + "    `})}"


def _self_check() -> None:
    """自证「渲染字节不变」：`FBAR` 的输出 = `<div class="fbar">` ＋ body ＋ `</div>`。

    ⛔ 这不是"看着一样"——它把**改前那一段**与**按新写法拼出来的那一段**逐字节比。
    """
    body = M01_MID + "    "                     # 模板字面量里 `${FBAR({body:` 之后到收尾反引号之间的原文
    rendered = '<div class="fbar">' + body + '</div>'
    old = M01_OLD[len("    "):]                  # 去掉模板里 `${` 之前那 4 格缩进
    assert rendered == old, "⛔ 自证失败：新写法拼出来与改前那一段不逐字节相等"
    assert M01_NEW.count("\n") == M01_OLD.count("\n"), "⛔ 行数变了（P4-a 要求 Δ0）"


def main() -> int:
    for p in (PROJ, SHELL, PROTO):
        assert p.exists(), f"⛔ 找不到 {p}"
    _self_check()

    # ── ① 先**干跑校验全部四处**（⛔ 别改一半才发现某处的靶串没命中 ⇒ 留坏态）
    #      ⚠️ 靶串带上 `};` 那一行的换行 —— 新写法自己出「空行 ＋ 注释 ＋ 声明 ＋ 空行」，
    #         否则会与残留的那个空行叠成连续两行空行（对外壳无害，但排版会歪）。
    tbl_old = crlf(BLOCK_TBL + "\n")
    ins = crlf(BLOCK_TBL + "\n\n" + FBAR_DOC + "\n")
    plan: list[tuple[pathlib.Path, bytes, bytes, str]] = [
        (PROJ, tbl_old, ins, "插入 `FBAR` 出口（`proj.js` · `TBL` 之后）"),
        (PROTO, tbl_old, ins, "插入 `FBAR` 出口（原型 · `TBL` 之后）"),
        (SHELL, crlf(M01_OLD), crlf(M01_NEW), "`V.m01` 筛选栏外壳改走 `FBAR`（壳）"),
        (PROTO, crlf(M01_OLD), crlf(M01_NEW), "`V.m01` 筛选栏外壳改走 `FBAR`（原型）"),
    ]
    # 干跑：在内存里**按顺序叠着改**（⚠️ 原型要改两处 ⇒ 第二处的靶串必须在第一处改完之后仍**恰好命中 1 次**）
    sim = {p: p.read_bytes() for p in (PROJ, SHELL, PROTO)}
    for p, old, new, what in plan:
        n = sim[p].count(old)
        assert n == 1, f"⛔ 干跑不过：{what} —— 在 {p.name} 里命中 {n} 次（必须**恰好 1 次**）"
        sim[p] = sim[p].replace(old, new, 1)

    # ── ② 备份原型（交付面是 WPS 云同步树 ⇒ 动它必须先留一份）
    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / "原型-备份-20260930-P4a前.html"
    assert not dst.exists(), f"⛔ 备份已存在（别覆盖）：{dst}"
    shutil.copy2(PROTO, dst)
    print(f"  ✅ 备份原型 ⇒ {dst.relative_to(ROOT)}（{dst.stat().st_size} 字节）")

    # ── ③ 落盘：造出口 ＋ 改试点（壳与原型**同批同句**）
    for p, _old, _new, what in plan:
        p.write_bytes(sim[p])
        print(f"  ✅ {what}")

    # ── ④ 复核：出口在 `proj.js` 与原型各一份（**件本身**），试点调用在 `index.html` 与原型各一处
    CALL = "${FBAR({body:`"
    assert PROJ.read_text(encoding="utf-8").count("const FBAR=") == 1, "⛔ `proj.js` 里 `FBAR` 出口不是恰好 1 份"
    for p in (SHELL, PROTO):
        t = p.read_text(encoding="utf-8")
        assert t.count(CALL) == 1, f"⛔ {p.name} 里试点调用不是恰好 1 处"
    assert PROTO.read_text(encoding="utf-8").count("const FBAR=") == 1, "⛔ 原型里 `FBAR` 出口不是恰好 1 份"
    print("\n✅ `TAIL-64` P4-a 三件已改（壳 `proj.js` ／ 壳 `index.html` ／ 原型）· 两侧同句、行数 Δ0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
