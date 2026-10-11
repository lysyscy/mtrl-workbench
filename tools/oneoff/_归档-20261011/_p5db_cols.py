#!/usr/bin/env python
r"""`TAIL-64` **`P5-d-b`（第一处）**：`modal:ledExp` 那张清单表改**列定义式**（零级联 · 壳独有）。

**为什么是这一处**（`P5-d-a` 试点之后又量了一轮，见 `tools/oneoff/_p5d_survey.py` 新加的"**表头来源**"一栏）：
46 个 `TBL` 调用点里 ——
  · ⛔ **16 处表头来自 `*_THEAD` 常量** ⇒ **不能**改列定义式（`t` 会把表头**抄第二份**；
    而那两个常量还被 `thCount` / `sumRowOf` / `U5` 吃着）⇒ 那是**另一个设计问题**（见施工图 §7.12 的"必读①"）；
  · ✅ **20 处表头是内联的** ⇒ 可转；再筛"**不在 `V.*` 里**（⇒ 零 `U1` 级联）＋ **行模板单行**（⇒ 逐字节自证成立）"：
    `modal:procExp`（`P5-d-a` 已办）与 **`modal:ledExp`（本件）** —— 其余多行模板的站点都撞"**空白差**"那个口径问题（必读②）。
  · ⭐ `modal:ledExp` 还是**壳独有**（原型没有这个弹窗）⇒ **连原型都不用动**（不必动交付面）。

**自证**：拿这一处的**旧写法 vs 新写法**渲染三组数据（0 / 1 / 3 个项目）**逐字节比对**（head ＋ rows 两串）。

用法：`python tools/oneoff/_p5db_cols.py`（干跑 ＋ 自证）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ACT = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

OLD = (
    "        ${TBL({cls:'cond',key:'modal:ledExp',sty:'margin-top:calc(8px * var(--fscale))',"
    "head:'<th>#</th><th>工作簿（每项目一个）</th><th>工作表</th>',\n"
    "        rows:pjs.map((k,i)=>`<tr><td class=\"fc\">${i+1}</td><td>${esc(fnOf(k))}</td>"
    "<td class=\"sm\">辅材欠款 / 机械欠款 / 特殊费用月报表</td></tr>`)})}"
)
NEW = (
    "        ${TBL({cls:'cond',key:'modal:ledExp',sty:'margin-top:calc(8px * var(--fscale))',\n"
    "        cols:[{t:'<th>#</th>', r:(k,i)=>`<td class=\"fc\">${i+1}</td>`},\n"
    "              {t:'<th>工作簿（每项目一个）</th>', r:k=>`<td>${esc(fnOf(k))}</td>`},\n"
    "              {t:'<th>工作表</th>', r:()=>`<td class=\"sm\">辅材欠款 / 机械欠款 / 特殊费用月报表</td>`}], "
    "list:pjs})}"
)

_SELFCHECK_JS = r"""
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const fnOf = k => k + '_欠款台账_2026-08.xlsx';
function oldWay(pjs){ return { head:'<th>#</th><th>工作簿（每项目一个）</th><th>工作表</th>',
  rows:pjs.map((k,i)=>`<tr><td class="fc">${i+1}</td><td>${esc(fnOf(k))}</td><td class="sm">辅材欠款 / 机械欠款 / 特殊费用月报表</td></tr>`) }; }
function newWay(pjs){ const cols=[{t:'<th>#</th>', r:(k,i)=>`<td class="fc">${i+1}</td>`},
  {t:'<th>工作簿（每项目一个）</th>', r:k=>`<td>${esc(fnOf(k))}</td>`},
  {t:'<th>工作表</th>', r:()=>`<td class="sm">辅材欠款 / 机械欠款 / 特殊费用月报表</td>`}]; const list=pjs;
  return { head:cols.map(c=>c.t).join(''),
           rows:list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>') }; }
let bad=0;
for(const pjs of [[], ['晋江污泥项目'], ['A','B','C']]){
  const a=oldWay(pjs), b=newWay(pjs);
  const sa=JSON.stringify([a.head,a.rows]), sb=JSON.stringify([b.head,b.rows]);
  if(sa!==sb){ bad++; console.log('  ⛔ '+pjs.length+' 项目：新旧**不一致**\n   旧='+sa+'\n   新='+sb); }
  else console.log('  ✅ '+pjs.length+' 个项目：逐字节一致（head '+a.head.length+' 字 · rows '+a.rows.join('').length+' 字）');
}
process.exit(bad?1:0);
"""


def node_exe() -> str:
    return shutil.which("node") or NODE_FALLBACK


def rd(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_text(encoding="utf-8", newline="")
    return (raw.replace("\r\n", "\n"), "\r\n" if "\r\n" in raw else "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    act, nl = rd(ACT)
    got = act.count(OLD)
    assert got == 1, f"⛔ 靶命中 {got} 次（期望 1）—— `modal:ledExp` 那处改过？"
    print("   ✅ 靶命中 1 次（`modal:ledExp` 的 `head:` ＋ `rows:`）")

    print("自证：旧写法 vs 新写法（逐字节）")
    r = subprocess.run([node_exe(), "-e", _SELFCHECK_JS], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        print("  ⛔ 自证不过 ⇒ 别写盘")
        return 1

    new = act.replace(OLD, NEW, 1)
    assert new != act, "⛔ 一个字都没改？"
    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    ACT.write_text(new if nl == "\n" else new.replace("\n", nl), encoding="utf-8", newline="")
    assert rd(ACT)[0] == new, "⛔ 写回不一致"
    print("\n✅ 已落盘（壳 1 处：`modal:ledExp` 改列定义式；⚠️ 本处**壳独有** ⇒ 原型不动）")
    print("⚠️ 接着必跑：`syntax_audit` → 全套闸门（`ui_parity` 的 `U1`/`U5` 都不该动）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
