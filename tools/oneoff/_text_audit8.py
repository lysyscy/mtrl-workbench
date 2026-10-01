"""只读盘点（第二轮 · 动手前的靶）：① 悬停文案逐条到底有多长；② 行内小字全量；③ 该禁的"内部形态"实测。

⚠️ 只读、不判、不改。判"删/留"按 `D29`（业务常识 / 机制辩解 / 内部编号 / 界面上看得见的 ⇒ 删；
   系统特有行为与后果 ⇒ 留）。
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


PAGES = [(n, strip_comments(t, html=n.endswith(".html"))) for n, t in parts_text()]

# ── ① 悬停文案：全量长度分布 ＋ 逐条列出（≥ 60 字）────────────────────────────
print("══ ① 悬停文案 `title=\"…\"` 长度分布")
rows: list[tuple[int, str, str]] = []
for name, text in PAGES:
    for m in re.finditer(r'title="([^"]{8,})"', text):
        txt = plain(m.group(1))
        if len(txt) >= 8:
            rows.append((len(txt), f"{name}:{text[:m.start()].count(chr(10)) + 1}", txt))
dist = collections.Counter()
for n, _loc, _t in rows:
    dist[200 <= n and "200+" or 150 <= n < 200 and "150-199" or 120 <= n < 150 and "120-149"
         or 80 <= n < 120 and "80-119" or "0-79"] += 1
print(f"   共 {len(rows)} 处 · 合计 {sum(n for n, _, _ in rows)} 字 · 分布 {dict(dist)}")
print("   ── ≥60 字的逐条（供按 `D29` 判）")
for n, loc, t in sorted(rows, reverse=True):
    if n >= 60:
        print(f"   {n:4d} 字 {loc}  {t[:110]}")

# ── ② 行内小字：全量（≥ 25 字）──────────────────────────────────────────
print("\n══ ② 行内小字（`mut sm` / `sm mut`）≥ 25 字逐条")
c = 0
for name, text in PAGES:
    for m in re.finditer(r'class="(?:mut sm|sm mut)(?:"|\s)', text):
        seg = text[m.start():m.start() + 400]
        gt = seg.find(">")
        if gt < 0:
            continue
        body = seg[gt + 1:]
        body = body[:body.find("<") if "<" in body else 140]
        txt = plain(body)
        if len(txt) >= 25:
            c += 1
            print(f"   {len(txt):4d} 字 {name}:{text[:m.start()].count(chr(10)) + 1}  {txt[:110]}")
print(f"   （≥25 字共 {c} 处）")

# ── ③ 该禁的"内部形态"实测（剥注释后，看壳里还剩什么）──────────────────────
print("\n══ ③ 候选形态实测（⛔ 只报命中，判不判由人定）")
SHAPES = {
    "ops 目录名": r"ops[/\\]|见 ops|ops 实测",
    "内部文档/根目录名": r"\.codebuddy|\.md\b|artifacts[/\\]|tools[/\\]",
    "开发术语（黑话）": r"幂等|路由|后端|接口失败|缓存|落库接口",
}
for label, pat in SHAPES.items():
    hits = []
    for name, text in PAGES:
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(pat, line):
                hits.append(f"{name}:{i}  {line.strip()[:100]}")
    print(f"   ── {label}（{len(hits)} 行）")
    for h in hits[:10]:
        print("      ", h)

sys.exit(0)
