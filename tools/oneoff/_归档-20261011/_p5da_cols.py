#!/usr/bin/env python
r"""`TAIL-64` **`P5-d-a`（试点）**：给表格件加**列定义式**（`cols:[{t,r}]` ＋ `list`）＋ 一处试点调用点。

**为什么试点挑这一处**（施工图 §7.10 的量测结论）：`TBL` 有 **46 个调用点**，其中 **30 个落在 `V.*` 切片里**
（`U1` **逐行对位** ⇒ 每碰一行就是「换号 ＋ 幽灵」）⇒ ⛔ 别一次铺开。试点挑
`actions.js` 的 `modal:procExp`（**2 列 1 行** · **不在 `V.*` 里 ⇒ 零 `U1` 级联**）：

**三处改动**（⚠️ ①② 是 **`U5` 件**（壳 ⇄ 原型**逐段一致**）⇒ **两侧同批同句**；③ 是**壳独有**的调用点）：

| # | 改哪 | 怎么改 |
|---|---|---|
| ① | `TBL` 签名 | 加两个可选参 `cols=null`（列定义）· `list=[]`（数据）—— **默认值保持旧行为** |
| ② | `TBL` 体内 | 给了 `cols` ⇒ `head` / `rows` **由它派生**（`cols` 优先；同时再传 `head`/`rows` 会被**忽略**） |
| ③ | `modal:procExp` 调用点 | 手写的 `head:` ＋ `rows:…map(…)` ⇒ `cols:[{t,r},…]` ＋ `list:pjs` |

**契约**（⭐ 施工图 §7.4 草案写的是 `{t,r,s}`，那个 `s` **暂时没有用武之地** —— 列的可排性写在 `t` 的
`<th class="srt">` 上、格的样式写在 `r` 返回的 `<td>` 上 ⇒ 本件**只收 `{t, r}` 两个**，
⛔ **别为凑第三个发明一个没人读的参**）：
`t` = 表头那一格（**整段 `<th>` HTML**）· `r` = 取值器 `(x,i) =>` 这一格（**整段 `<td>` HTML**）。

**自证（`_self_check`）**：拿试点那两列的**旧写法**与**新写法**各渲染一遍（`pjs` = 空 / 1 个 / 3 个），
**逐字节比对**（`head` 与 `rows` 两串都要相等）—— ⛔ 不靠"看起来一样"。

用法：`python tools/oneoff/_p5da_cols.py`（干跑 ＋ 自证）· `… --write`（⚠️ 改交付面前**先备份**）
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
ACT = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_common import delivery_root  # noqa: E402

BAKDIR = ROOT / "artifacts" / "delivery-backups"
NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

OLD_SIG = "const TBL=({head='',rows=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false})=>{"
NEW_SIG = ("const TBL=({head='',rows=[],cols=null,list=[],empty='',sum='',key='',cls='',sort=true,"
           "sty='',headRows=false})=>{")
#: ⚠️ 这段**两侧逐字相同**（`U5` 会逐段比 `TBL` 的函数体文本）
COLS_BLOCK = (
    "\n"
    "  /* \u2b50 `cols` = **列定义式**（`TAIL-64` P5-d-a \u00b7 2026-09-30）：`cols:[{t,r}]` \uFF0B `list:[\u2026]` \u2014\u2014\n"
    "     `t` = 表头那一格（**整段 `<th>` HTML`）\u00b7 `r` = 取值器 `(x,i)=>` 这一格（**整段 `<td>` HTML`）。\n"
    "     \u7ed9\u4e86 `cols` \u21d2 `head` / `rows` **由它派生**（\u26d4 别同时再传那两个：本件里 `cols` 优先、那两个被忽略）。 */\n"
    "  if(cols){ head=cols.map(c=>c.t).join('');\n"
    "    rows=list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>'); }\n"
)

OLD_SITE = (
    "       ${TBL({cls:'cond',key:'modal:procExp',sty:'margin-top:calc(8px * var(--fscale))',"
    "head:'<th>#</th><th>文件（每项目一份）</th>',\n"
    "       rows:pjs.map((k,i)=>`<tr><td class=\"fc\">${i+1}</td><td>${esc(fnOf(k))}</td></tr>`)})}"
)
NEW_SITE = (
    "       ${TBL({cls:'cond',key:'modal:procExp',sty:'margin-top:calc(8px * var(--fscale))',\n"
    "       cols:[{t:'<th>#</th>', r:(k,i)=>`<td class=\"fc\">${i+1}</td>`},\n"
    "             {t:'<th>文件（每项目一份）</th>', r:k=>`<td>${esc(fnOf(k))}</td>`}], list:pjs})}"
)

#: 自证：旧写法 vs 新写法（⚠️ 两段都要**逐字**取自上面那两个常量，别另抄一份）
_SELFCHECK_JS = r"""
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const fnOf = k => k + '_过程资料_汇总表_2026-09.xlsx';
function oldWay(pjs){ return { head:'<th>#</th><th>文件（每项目一份）</th>',
  rows:pjs.map((k,i)=>`<tr><td class="fc">${i+1}</td><td>${esc(fnOf(k))}</td></tr>`) }; }
function newWay(pjs){ const cols=[{t:'<th>#</th>', r:(k,i)=>`<td class="fc">${i+1}</td>`},
  {t:'<th>文件（每项目一份）</th>', r:k=>`<td>${esc(fnOf(k))}</td>`}]; const list=pjs;
  return { head:cols.map(c=>c.t).join(''),
           rows:list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>') }; }
const cases=[[], ['晋江污泥项目'], ['A','B','C']];
let bad=0;
for(const pjs of cases){
  const a=oldWay(pjs), b=newWay(pjs);
  const sa=JSON.stringify([a.head,a.rows]), sb=JSON.stringify([b.head,b.rows]);
  if(sa!==sb){ bad++; console.log('  ⛔ '+(pjs.length)+' 项目：新旧渲染**不一致**\n   旧='+sa+'\n   新='+sb); }
  else { console.log('  ✅ '+(pjs.length)+' 个项目：逐字节一致（head '+a.head.length+' 字 · rows '+
    a.rows.join('').length+' 字）'); }
}
process.exit(bad?1:0);
"""


def node_exe() -> str:
    return shutil.which("node") or NODE_FALLBACK


def rd(p: pathlib.Path) -> tuple[str, str]:
    """读一件 ⇒ `(归一成 \\n 的全文, 它原本的换行风格)`。

    ⚠️ 本仓各件的换行**不统一**（`.gitattributes` 那边是按扩展名走的）⇒ 锚点串一律**按 `\\n` 写**、
    写回时**还原原风格** —— 否则「命中 0 次」这种哑靶会天天出现（首版就栽在这）。
    """
    raw = p.read_text(encoding="utf-8", newline="")
    return (raw.replace("\r\n", "\n"), "\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def self_check() -> int:
    print("自证：旧写法 vs 新写法（逐字节）")
    r = subprocess.run([node_exe(), "-e", _SELFCHECK_JS], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        print("  ⛔ 自证不过 —— 别写盘")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    proj, nl_proj = rd(PROJ)
    act, nl_act = rd(ACT)
    proto = delivery_root() / "demo" / "材料报表自动化工作台-交互原型.html"
    ptxt, nl_proto = rd(proto)
    print(f"   换行：proj={nl_proj!r} · actions={nl_act!r} · 原型={nl_proto!r}")

    # ── 三处改动的**命中数**先断言（⛔ 宁可不改，也不打偏）
    for name, txt, old, n in (("壳 TBL 签名", proj, OLD_SIG, 1), ("原型 TBL 签名", ptxt, OLD_SIG, 1),
                              ("壳 试点调用点", act, OLD_SITE, 1)):
        got = txt.count(old)
        assert got == n, f"⛔ {name}：命中 {got} 次（期望 {n}）"
        print(f"   ✅ {name}（命中 1 次）")

    if self_check() != 0:
        return 1

    new_proj = proj.replace(OLD_SIG, NEW_SIG + COLS_BLOCK, 1)
    new_ptxt = ptxt.replace(OLD_SIG, NEW_SIG + COLS_BLOCK, 1)
    new_act = act.replace(OLD_SITE, NEW_SITE, 1)
    assert new_proj != proj and new_ptxt != ptxt and new_act != act, "⛔ 一个字都没改？"

    # ── `U5` 自证：两侧那段 `TBL` 的函数体文本必须**逐字相同**
    def seg(text: str) -> str:
        i = text.index("const TBL=")
        j = text.index("\n};", i) + 3
        return text[i:j]
    assert seg(new_proj) == seg(new_ptxt), "⛔ 壳 ⇄ 原型的 `TBL` 段**不再逐字一致**（`U5` 会红）"
    print(f"   ✅ `U5` 自证：壳 ⇄ 原型 `TBL` 段逐字一致（{len(seg(new_proj))} 字）")

    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    BAKDIR.mkdir(parents=True, exist_ok=True)
    bak = BAKDIR / "原型-备份-20260930-P5da前.html"
    if not bak.exists():
        shutil.copy2(proto, bak)
        print(f"   ✅ 原型已备份：{bak.relative_to(ROOT)}")
    else:
        print(f"   ℹ️ 备份已存在（不覆盖）：{bak.name}")
    wr(PROJ, new_proj, nl_proj)
    wr(ACT, new_act, nl_act)
    wr(proto, new_ptxt, nl_proto)
    assert rd(PROJ)[0] == new_proj, "⛔ 壳写回不一致"
    assert rd(ACT)[0] == new_act, "⛔ actions 写回不一致"
    assert rd(proto)[0] == new_ptxt, "⛔ 原型写回不一致"
    print("\n✅ 已落盘（壳 `TBL` ＋ 壳试点调用点 ＋ **原型 `TBL` 同句**）")
    print("⚠️ 接着必跑：`syntax_audit` → `ui_parity`（`U5`）→ 全套闸门 → `doc_audit --ui`（**动过交付面**）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
