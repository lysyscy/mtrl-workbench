#!/usr/bin/env python
r"""`TAIL-64` **`P4-c-a`（试点 1 处）**：口径说明块造出口 `CALIB` ＋ `V.m13` 一处试点。

**为什么试点挑 `m13`**（量测件 `tools/oneoff/_p4ca_survey.py` 的读数，⛔ 不是"我记得"）：
  · 14 块里**最小**的两块是 `m13` / `m14`（各 6 行 · 3 个 `<li>`）；
  · `m14` 旁边那两句被别的判据钉着（`test_ux_colors` / `_mut_a7` 的 M10 盯 `tip wn|dg`）⇒ 绕开；
  · `m13` 的口径说明块**没有任何判据钉它的形态** ⇒ 切换面最小。
  （⚠️ 施工图 §8.10 说 `TAIL-201` 之后「随便挑一页」—— 但"随便"不等于"不看别人钉着谁"。）

**做什么**（两处；⛔ 原型不动 —— `TAIL-201` 起「双边同步」已取消，`U1`/`U5` 都已退场）：
| # | 改哪 | 怎么改 |
|---|---|---|
| ① | `shell/proj.js` | 造出口 `CALIB({items:[…]})`：`<details>` ＋ 标题 ＋ **算出来的条数** ＋ `<ul>` ＋ `<li>` 外壳 |
| ② | `index.html` 的 `V.m13` | 那 6 行块 ⇒ `${CALIB({items:[` ＋ 三行条目 ＋ `]})}`（行数 **-1**：`<ul>` 那行进出口了） |

**自证（本件的命门）**：拿**原文那 6 行**（按它在文件里的**真行尾**取）与**出口真渲染出来的**做
**逐字节比对**（`node` 真跑）—— ⛔ 不靠"看起来一样"。
⭐ 顺带回答一个**必须实测**的问题：**JS 模板字面量里的 `CRLF` 会不会被折成 `LF`**？
（`_p4ca_survey.py` 已量出壳各件**全是 `CRLF`**，而原块就活在模板字面量里）
⇒ 出口那个换行该写 `\r\n` 还是 `\n`：本件把**两种写法各渲一遍**，谁与原文逐字节相同就用谁。

用法：`backend\.venv\Scripts\python.exe -X utf8 tools\oneoff\_p4ca_calib.py`（干跑 ＋ 自证）
     `… --write`（落盘；自证不过不落）
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
INDEX = WEB / "index.html"
PROJ = WEB / "shell" / "proj.js"
#: ⚠️ scratch 的真身是 **`.workbuddy/work/00-scratch/`**（`T14` 的 TTL 管它、`.gitignore` 忽略它）——
#:    ⛔ 别写仓根的 `work/00-scratch`（那是**仓内简写**；第一版就这么写的 ⇒ 仓根多出一个未被忽略的 `work/`）。
SCRATCH = ROOT / ".workbuddy" / "work" / "00-scratch"
NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

PAGE = "m13"
BLOCK_HEAD = '  <details class="tip"><summary>口径说明 · '
BLOCK_END = "</ul></details>"

KERNEL_COMMENT = """/* ⭐ **口径说明块件**（`TAIL-64` P4-c · 2026-09-30）—— 页首那个折叠的「口径说明 · N 条」块
 * 统一由它渲染：`<details>` 外壳 ＋ 标题 ＋ **算出来的条数** ＋ `<ul>` ＋ 条目外壳。
 * 契约：`CALIB({items:[…]})` ⇒ 返回完整块 HTML；**条数 = 条目个数**（本件算出，⛔ 调用点不再手抄那个数）。
 * ⚠️ 为什么必须收：那个数字原先**逐处手抄** —— `m02` 曾写着「6 条」而块里实际 7 条
 *    （用户在屏幕上读到一个**假的条数**，守则 §4.2「状态必须真实」· §2.6「能算的别让人自己数」）
 *    ⇒ 收进本件后「条数 ⇄ 条目」由构造保证，那类漂移**从此不可能**（同族已犯过三次）。
 * ⚠️ 收的只是**外壳**：条目正文（`items` 里每一段）**逐字留在调用点**，本件只负责包外壳与分隔。
 * ⚠️ **换行按壳各件的行尾写**（壳全是 `CRLF`）—— 原调用点那几行是模板字面量里的真换行，
 *    出口拼出来的必须与它**逐字节相同**（本批的硬证据 = 渲染字节不变）。
 * 自证 = 变异脚本（去掉委托 ／ 内核另写死条数 ／ 内核不包条目外壳 ⇒ 对应判据必须红）。 */"""


def kernel_src(nl_js: str) -> str:
    """出口源码。`nl_js` = 写进源码的那个换行的**字面形态**：
    `"\\r\\n"` / `"\\n"`（转义形式，4 或 2 个字符）。"""
    return (
        "const CALIB=({items=[]})=>'<details class=\"tip\"><summary>口径说明 · '+items.length+' 条 "
        "<span class=\"mut sm\">点开查看（默认收起，把空间让给数据）</span></summary>" + nl_js + "'\n"
        "  +'    <ul style=\"margin:calc(6px * var(--fscale)) 0 0;padding-left:calc(17px * var(--fscale));"
        "line-height:1.8\">" + nl_js + "'\n"
        "  +'      <li>'+items.join('</li>" + nl_js + "      <li>')+'</li>" + nl_js + "'\n"
        "  +'    </ul></details>';"
    )


def rd(p: pathlib.Path) -> tuple[str, str]:
    """⇒ `(归一成 \\n 的全文, 它原本的换行风格)`（⚠️ 同 `_p5da_cols.py` 的读法）。"""
    raw = p.read_text(encoding="utf-8", newline="")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def find_block(text: str) -> tuple[int, int, str, list[str]]:
    """在壳全文（`\\n` 归一）里定位 `V.<PAGE>` 的那一块 ⇒ `(起, 止, 块文本, 条目列表)`。"""
    i = text.index("V." + PAGE + "=()=>`")
    a = text.index(BLOCK_HEAD, i)
    b = text.index(BLOCK_END, a) + len(BLOCK_END)
    block = text[a:b]
    assert block.count(BLOCK_HEAD) == 1, "块首不唯一 —— 别按'第一处'改"
    lines = block.split("\n")
    assert lines[0].startswith(BLOCK_HEAD) and lines[-1].endswith(BLOCK_END), "块的形状变了"
    items: list[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("<li>") and s.endswith("</li>"):
            assert s.count("<li>") == 1, f"一格里有多个条目：{s[:40]}"
            items.append(s[4:-5])
    assert len(items) == len(lines) - 3, \
        f"条目数 {len(items)} 与行数 {len(lines)} 对不上（块首 / `<ul>` / 块尾 各 1 行）"
    for it in items:
        assert "`" not in it and "${" not in it and "\\" not in it, \
            f"条目里有模板字面量不认的字符：{it[:40]}"
    return a, b, block, items


def call_site(items: list[str]) -> str:
    """新调用点那一段（`\\n` 归一）：行数 = 原文 - 1（`<ul>` 那行进出口了）。"""
    return "\n".join(["  ${CALIB({items:["]
                      + ["    `" + it + "`," for it in items]
                      + ["  ]})}"])


def run_js(old_region: str, new_region: str, kernel: str, path: pathlib.Path) -> bool:
    """`node` 真跑：`OLD`（原文，真行尾） vs `NEW`（真调用点源码）⇒ 逐字节。"""
    assert "`" not in old_region and "${" not in old_region and "\\" not in old_region, \
        "原文里有模板字面量不认的字符"
    assert "\\" not in new_region, "新调用点里有反斜杠（模板字面量里会被当转义）"
    js = (
        "/* 自动生成（`tools/oneoff/_p4ca_calib.py`）—— P4-c-a 的渲染字节自证 */\n"
        + kernel + "\n\n"
        + "const OLD=`" + old_region + "`;\n"
        + "const NEW=`" + new_region + "`;\n"
        + "let bad=0;\n"
        + "const cmp=(n,a,b)=>{ if(a===b){ console.log('  ✅ '+n+'：**逐字节一致**（'+a.length+' 字）'); }\n"
        + "  else { bad++; console.log('  ❌ '+n+'：**不一致**\\n     旧='+JSON.stringify(a)"
          "+'\\n     新='+JSON.stringify(b)); } };\n"
        + "cmp('原文 vs 出口真渲染',OLD,NEW);\n"
        + "process.exit(bad?1:0);\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(js, encoding="utf-8", newline="")     # ⚠️ 原样写：本件要拿**真 CRLF** 试
    node = shutil.which("node") or NODE_FALLBACK
    r = subprocess.run([node, str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    sys.stderr.write(r.stderr or "")
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell, nl_shell = rd(INDEX)
    proj, nl_proj = rd(PROJ)
    print(f"   换行：index.html={nl_shell!r} · proj.js={nl_proj!r}")

    start, end, block, items = find_block(shell)
    print(f"   定位 `V.{PAGE}` 的口径说明块：第 {shell.count(chr(10), 0, start) + 1} 行起 · "
          f"{len(block.splitlines())} 行 · {len(items)} 条")
    for i, it in enumerate(items, 1):
        print(f"     {i}. {it[:58]}{'…' if len(it) > 58 else ''}")

    old_region = ("  " + block).replace("\n", nl_shell)          # 调用点那 2 格缩进 ＋ 真行尾
    new_region = ("  " + call_site(items)).replace("\n", nl_shell)

    print("\n自证：原文（真行尾） vs 出口真渲染（逐字节）")
    hit: list[str] = []
    for name, nl_js in (("crlf_esc（写 `\\r\\n`）", "\\r\\n"), ("lf_esc（写 `\\n`）", "\\n")):
        print(f"   ── 出口写法 = {name}")
        if run_js(old_region, new_region, kernel_src(nl_js), SCRATCH / "_p4ca_selfcheck.js"):
            hit.append(nl_js)
    if len(hit) != 1:
        print(f"  ⛔ 对得上的写法有 {len(hit)} 种（期望 1）—— 别落盘，先看清楚")
        return 1
    nl_js = hit[0]
    label = "`\\r\\n`（CRLF）" if nl_js == "\\r\\n" else "`\\n`（LF —— ⚠️ JS 把模板字面量里的 CRLF 折成了 LF）"
    print(f"\n   ⇒ 出口里那个换行写 **{label}**（⛔ 不是「看着像」挑的 —— 是渲染出来逐字节相同的那个）")

    nb = call_site(items)
    assert len(nb.split("\n")) == len(block.split("\n")) - 1, "行数不是 -1 —— 块首/块尾算错了"
    new_shell = shell[:start] + nb + shell[end:]
    n_lit = len(re.findall(r'<details class="tip"><summary>口径说明 · \d+ 条', new_shell))
    assert n_lit == 13, f"改动后还剩 {n_lit} 块裸写的 —— 期望 13（14 - 试点 1）"

    # ── 出口插进 `shell/proj.js`（与 `TBL` / `FBAR` / `PJB` 同件），排在 `PJB` 之后
    assert "const CALIB=" not in proj, "`CALIB` 已经在了 —— 先看是不是重复落盘"
    i = proj.index("const PJB=")
    j = proj.index("</button>';", i) + len("</button>';")
    kernel = kernel_src(nl_js)
    new_proj = proj[:j] + "\n\n" + KERNEL_COMMENT + "\n" + kernel + proj[j:]
    assert new_proj.count("const CALIB=") == 1
    assert kernel in new_proj, "⛔ 出口没有逐字进到将写入的文本里"
    print(f"   ✅ 出口落在 `shell/proj.js` 第 {new_proj.count(chr(10), 0, new_proj.index('const CALIB=')) + 1} 行"
          f"（`PJB` 之后）· 共 {len((KERNEL_COMMENT + chr(10) + kernel).splitlines())} 行")

    # ── 二次自证：拿"将要写进去的那两段文本"原样再渲一遍（⛔ 防"算对了、写错了"）
    print("\n二次自证：拿**将写入的文本**再渲一遍")
    if not run_js(old_region, ("  " + nb).replace("\n", nl_shell), kernel, SCRATCH / "_p4ca_selfcheck2.js"):
        print("  ⛔ 落盘版自证不过 —— 拒写")
        return 1

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    wr(INDEX, new_shell, nl_shell)
    wr(PROJ, new_proj, nl_proj)
    back_shell, _ = rd(INDEX)
    back_proj, _ = rd(PROJ)
    assert back_shell == new_shell, "⛔ index.html 写回不一致"
    assert back_proj == new_proj, "⛔ proj.js 写回不一致"
    print("\n✅ 已落盘：`shell/proj.js`（出口 `CALIB`）＋ `index.html`（`V.m13` 试点）")
    print("⚠️ 接着必跑：`syntax_audit` → 全套 pytest → 真机 → 16 把尺子 → `shell_verify --snapshot`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
