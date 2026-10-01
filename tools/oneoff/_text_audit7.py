"""只读盘点（`TAIL-209` 销号后的**第二轮**）：量**还没有机器眼兜住的**那几面文字。

## 为什么要这一件

第一轮（`TAIL-209`）把有机器眼的几面量清并守住上限了：
真机 ㉖ 管**页内 `.tip` ≤ 200 字** · `test_ux_text.py` 管**弹窗说明块 ≤ 200** · `test_ux_brief.py` 管**域自报 ≤ 200** ·
`test_ux_text.py` 管 `**` 与工程代号。
⇒ ⚠️ **剩下"可能多余的字"藏在没人量的面上** —— 本件就是去量它们（⛔ 只量、不判、不改）。

量的五面（都**逐条打印实句**，供人按 `D29` 判"干扰 / 指导"）：
  ① `.mut sm` / `sm mut` **行内小字**（页面上最常见的辅助行）
  ② `title="…"` **悬停文案**
  ③ `modal({title:…})` **弹窗标题**（含内部叫法嫌疑）
  ④ 空态文案（`EMPTYROW` / `EMPTYBOX` 第二三参）
  ⑤ **重复句**（同一句说明出现 ≥2 次 —— "同一件事说两遍"）

⚠️ 口径：字数按**渲染后**算（剥 `${…}` · 剥标签 · 剥 `**` · 空白不计），与 ㉖ 对齐。
⚠️ 本件是**只读量测**：不进收工闸门、不判红。
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.audit.shell_source import parts_text, strip_comments  # noqa: E402

TAG = re.compile(r"<[^>]+>")
JSX = re.compile(r"\$\{[\s\S]{0,600}?\}")


def plain(s: str) -> str:
    return re.sub(r"\s+", "", TAG.sub("", JSX.sub("…", s)).replace("**", ""))


def pages() -> list[tuple[str, str]]:
    return [(n, strip_comments(t, html=n.endswith(".html"))) for n, t in parts_text()]


# ── ① 行内小字（`class="mut sm"` 之类的小号辅助行）──────────────────────────────
print("\n══ ① 行内小字（`mut sm` / `sm mut`）")
c1, tot1 = 0, 0
row1: list[tuple[int, str, str]] = []
for name, text in pages():
    for m in re.finditer(r'class="(?:mut sm|sm mut|mut)(?:"|\s)', text):
        seg = text[m.start():m.start() + 320]
        # 取这一小段里第一个 `>` 之后的文本（到下一个 `<` 或行尾）
        gt = seg.find(">")
        if gt < 0:
            continue
        body = seg[gt + 1:]
        body = body[:body.find("<") if "<" in body else 120]
        txt = plain(body)
        if len(txt) < 10:
            continue
        c1 += 1
        tot1 += len(txt)
        row1.append((len(txt), f"{name}:{text[:m.start()].count(chr(10)) + 1}", txt))
print(f"   共 {c1} 处 · 合计 {tot1} 字")
for n, loc, txt in sorted(row1, reverse=True)[:12]:
    print(f"   {n:4d} 字 {loc}  {txt[:80]}")

# ── ② 悬停文案 `title="…"` ────────────────────────────────────────────────
print("\n══ ② 悬停文案（`title=\"…\"`，只取字面量 —— 带 `${` 的跳过）")
c2, tot2 = 0, 0
row2: list[tuple[int, str, str]] = []
for name, text in pages():
    for m in re.finditer(r'title="([^"$]{12,})"', text):
        txt = plain(m.group(1))
        if len(txt) < 12:
            continue
        c2 += 1
        tot2 += len(txt)
        row2.append((len(txt), f"{name}:{text[:m.start()].count(chr(10)) + 1}", txt))
print(f"   共 {c2} 处 · 合计 {tot2} 字")
for n, loc, txt in sorted(row2, reverse=True)[:12]:
    print(f"   {n:4d} 字 {loc}  {txt[:80]}")

# ── ③ 弹窗标题 ────────────────────────────────────────────────────────────
print("\n══ ③ 弹窗标题（`modal({title:…`）")
c3 = 0
sus: list[str] = []
for name, text in pages():
    for m in re.finditer(r"modal\(\{\s*title:\s*(.{0,120})", text):
        c3 += 1
        head = m.group(1).strip()
        if re.search(r"（|\(|·|\d{4}|[A-Z]{2,}", head):
            sus.append(f"{name}:{text[:m.start()].count(chr(10)) + 1}  {head[:70]}")
print(f"   共 {c3} 处；其中含括号 / 年月 / 大写词（值得人看一眼）{len(sus)} 处：")
for s in sus[:14]:
    print("   ", s)

# ── ④ 空态文案 ────────────────────────────────────────────────────────────
print("\n══ ④ 空态文案（`EMPTYROW` / `EMPTYBOX` 的说明参数）")
c4 = 0
row4: list[str] = []
for name, text in pages():
    for m in re.finditer(r"(EMPTYROW|EMPTYBOX)\(([^)]{0,200})", text):
        args = re.findall(r"'([^']{6,})'", m.group(2))
        if len(args) >= 2:
            c4 += 1
            row4.append(f"{name}:{text[:m.start()].count(chr(10)) + 1}  {plain(args[0])[:26]} / {plain(args[1])[:40]}")
print(f"   共 {c4} 处（第二句多长 = 空态指路多长）")
for s in row4[:14]:
    print("   ", s)

# ── ⑤ 重复句 ─────────────────────────────────────────────────────────────
print("\n══ ⑤ 重复句（同一句 ≥12 字的说明出现 ≥2 次）")
counter: collections.Counter = collections.Counter()
for _name, text in pages():
    for seg in re.findall(r">([^<>]{14,200})<", text):
        t = plain(seg)
        if len(t) >= 12 and "…" not in t:
            counter[t] += 1
dup = [(t, n) for t, n in counter.items() if n >= 2]
print(f"   共 {len(dup)} 句重复；最长的 12 句：")
for t, n in sorted(dup, key=lambda kv: -len(kv[0]))[:12]:
    print(f"   ×{n}  {t[:78]}")

print("\n（⛔ 只量不判：留/删按 `D29` —— 业务常识 · 机制辩解 · 内部编号 · 界面上看得见的 ⇒ 删；"
      "系统特有行为与后果 ⇒ 留）")
sys.exit(0)
