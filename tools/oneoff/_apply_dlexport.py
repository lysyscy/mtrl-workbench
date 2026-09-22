#!/usr/bin/env python
"""`TAIL-67`（批次 0）· **抽「导出下载」通用件 `dlExport`** ＋ 日期格式化件 —— **机械改写**。

⭐ 为什么落成脚本（本仓纪律 `MEMORY.md` §十七）：行尾工作区 CRLF / 仓库存 LF、编码 UTF-8
   ⇒ 用编辑器改容易把**整份文件的行尾**改掉；脚本可以**只改该改的那几行**、并**先备份**。

改三件事：
  1. `shell/core.js` 里**新增**通用件：`dlExport(url,{name,label,close})` · `ymOf` / `ymdOf`；
  2. `shell/actions.js`（7 处）＋ `shell/print-export.js`（1 处）里那段**逐字重复 8 份**的
     「fetch → 网络错 → JSON 200+ok:false → HTTP 错 → 文件名 → blob 落盘 → 撤 URL」
     ⇒ 换成 `const fn=await dlExport(url,{name:'…'}); if(!fn) return;`；
  3. `index.html` 里 4 处**逐字相同**的日期格式化 ⇒ 换成 `ymOf` / `ymdOf`。

⛔ **契约不变**：`dlExport` 成功返回**文件名**（失败返回 `''`，且**已经弹过 toast**）
   ⇒ 各个导出点原来的「成功提示」一行都不用动（它们有的要用到 `fn`）。
   失败文案统一走通用件（`label` 区分「导出 / 下载」）—— ⭐ 这正是抽它的**真理由**：
   8 份重复的下场就是"改一处的说法，另外 7 处说别的话"。

跑法（先备份、再改、最后打印摘要）：
  backend/.venv/Scripts/python.exe tools/_apply_dlexport.py
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
WEB = ROOT / "backend" / "app" / "web"
BAK = ROOT / ".workbuddy" / "scratch"

COMMON = """
/* ─────────────────────────────────────────────────────────────────────────
   ⭐⭐ **通用件**（`TAIL-67` · 2026-09-21 · 批次 0）—— 本段是**切片外**公共层，
       不参与 `U1` 的逐行比对 ⇒ 新函数一律放这里（`core.js` 头部就是这么说的）。
   ───────────────────────────────────────────────────────────────────────── */

/* ⭐ **导出下载**（原样重复了 **8 份**：`procExpSave` / `expPivot` / `zipSfjc` / 焊材气体 /
   总欠款 / 欠款台账 / 经济活动分析大表 / `m03Download`）。
   ⭐⭐ 抽它的**真理由不是省行数**，而是：**错误分类必须只有一个口径** ——
     8 份重复的下场是"改了一处的说法，另外 7 处还在说别的话"
     （与 2026-09-21「收款账号取错字段」同型：**同一件事 N 个主人**）。
   契约：
     · 成功 ⇒ 返回**文件名**（⛔ 命名规则的**主人是后端**，`name` 只是后端没给时的兜底）；
     · 失败 ⇒ 返回 `''`，且**已经弹过 toast** ⇒ ⛔ 调用方**不要再弹一遍**（会弹两条）。
     · `label` = '导出' / '下载'（只影响失败提示的措辞）；`close` = 成功后关弹窗。
   ⚠️ 顺序照旧：**先看 `content-type`**（后端失败回的是 **JSON 200**），再看 `r.ok`。
      ⛔ 反过来会拿一个"打不开的 xlsx/pdf"当文件存下来（2026-09-20 实测过的坑）。 */
async function dlExport(url, { name = '导出文件', label = '导出', close = false } = {}) {
  let r;
  try { r = await fetch(url); }
  catch (e) { toast(`<b>${label}没能完成</b>：${esc(String((e && e.message) || e))}`, 8000); return ''; }
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    let d = {};
    try { d = await r.json(); } catch (e) { /* 读不出 ⇒ 下面统一报「后端没给原因」 */ }
    /* ⚠️ 两种失败体都认：自己回的 `{message}`（ok:false）· FastAPI 的 `{detail}`（HTTPException）。 */
    toast(`<b>${label}没能完成</b>：${esc(d.message || d.detail || '后端没给原因')}`, 9600);
    return '';
  }
  if (!r.ok) { toast(`<b>${label}没能完成</b>：HTTP ${r.status}`, 8000); return ''; }
  const fn = decodeURIComponent(r.headers.get('x-export-filename') || '') || name;
  const blob = await r.blob(), a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = fn;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);   /* ⚠️ 不 revoke ⇒ 每次导出都漏一份内存 */
  if (close) closeModal();
  return fn;
}

/* ⭐ **日期格式化**（原先 4 处**逐字相同**地各写一份：`bjMonth` 等）
   ⇒ 抽出来是为了让"YYYY-MM / YYYY-MM-DD"这一种写法**只有一个主人**。 */
const ymOf = t => t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0');
const ymdOf = t => ymOf(t) + '-' + String(t.getDate()).padStart(2, '0');
"""


def backup(p: pathlib.Path) -> None:
    BAK.mkdir(parents=True, exist_ok=True)
    dst = BAK / (p.name + ".bak-dlexport")
    shutil.copy2(p, dst)
    print(f"  备份 ⇒ {dst.relative_to(ROOT)}")


def read_lines(p: pathlib.Path) -> tuple[list[str], str]:
    """返回 (行列表, 原换行符) —— ⛔ 原样写回，不改行尾。"""
    t = p.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    return t.replace("\r\n", "\n").split("\n"), nl


def write_lines(p: pathlib.Path, lines: list[str], nl: str) -> None:
    p.write_text(nl.join(lines), encoding="utf-8", newline="")


# ── 1) core.js：插入通用件 ────────────────────────────────────────────────
core = WEB / "shell" / "core.js"
print("[1] core.js · 插入通用件")
backup(core)
lines, nl = read_lines(core)
anchor = next(i for i, l in enumerate(lines) if l.startswith("const API = {"))
lines[anchor:anchor] = COMMON.strip("\n").split("\n") + [""]
write_lines(core, lines, nl)
print(f"  已插到 `const API = {{` 之前（L{anchor + 1}）· 现 {len(lines)} 行")

# ── 2) actions.js / print-export.js：8 处样板 ⇒ dlExport ───────────────────
FN_RE = re.compile(r"^(?P<ind>\s*)const\s+fn\s*=\s*decodeURIComponent\(r\.headers\.get\('x-export-filename'\)"
                   r"\s*\|\|\s*''\)\s*\|\|\s*'(?P<name>[^']*)'")

for rel, label in (("shell/actions.js", "导出"), ("shell/print-export.js", "下载")):
    p = WEB / rel
    print(f"[2] {rel} · 替换导出样板（label={label}）")
    backup(p)
    lines, nl = read_lines(p)
    out, i, n = [], 0, 0
    while i < len(lines):
        m = FN_RE.match(lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        # 向前找样板起点（`let r;`），向后找终点（`revokeObjectURL`）
        s = next(k for k in range(i, max(-1, i - 12), -1) if re.match(r"^\s*let\s+r\s*(=|;)", lines[k]))
        e = next(k for k in range(i, min(len(lines), i + 12)) if "revokeObjectURL" in lines[k])
        ind = m.group("ind")
        close = False
        j = e + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].strip() == "closeModal();":
            close = True
            e = j                                  # `closeModal()` 一并吃掉（通用件里 `close` 做）
        # ⚠️⚠️ 坑（本脚本第一版就踩了）：`s..i-1`（样板的前半段）在**前面的循环里已经 append 进 `out`**
        #    ⇒ 光"跳过 s..e"是**删不掉**它们的（实测：旧 fetch 块原样留在文件里、只把末两行换了）。
        #    ⇒ 必须**回删**已经写进 `out` 的那 (i - s) 行（`lines[i..e]` 本来就没 append 过）。
        del out[len(out) - (i - s):]
        opts = f"{{name:'{m.group('name')}'" + (f",label:'{label}'" if label != "导出" else "") \
               + (",close:true" if close else "") + "}"
        out.append(f"{ind}const fn=await dlExport(url,{opts});")
        out.append(f"{ind}if(!fn) return;")
        n += 1
        print(f"  L{s + 1}–L{e + 1} ⇒ dlExport（{m.group('name')}"
              + (" · 含 closeModal" if close else "") + "）")
        i = e + 1
    write_lines(p, out, nl)
    print(f"  替换 {n} 处 · 现 {len(out)} 行")

# ── 3) index.html：4 处日期格式化 ⇒ ymOf / ymdOf ───────────────────────────
print("[3] index.html · 日期格式化 ⇒ ymOf / ymdOf")
idx = WEB / "index.html"
backup(idx)
lines, nl = read_lines(idx)
YM = re.compile(r"^(\s*)return t\.getFullYear\(\)\+'-'\+String\(t\.getMonth\(\)\+1\)\.padStart\(2,'0'\); \};$")
YMD = re.compile(r"^(\s*)return t\.getFullYear\(\)\+'-'\+String\(t\.getMonth\(\)\+1\)\.padStart\(2,'0'\)"
                 r"\+'-'\+String\(t\.getDate\(\)\)\.padStart\(2,'0'\); \};$")
n = 0
for i, l in enumerate(lines):
    m = YMD.match(l)
    if m:
        lines[i] = f"{m.group(1)}return ymdOf(t); }};"; n += 1; continue
    m = YM.match(l)
    if m:
        lines[i] = f"{m.group(1)}return ymOf(t); }};"; n += 1
write_lines(idx, lines, nl)
print(f"  替换 {n} 处")
