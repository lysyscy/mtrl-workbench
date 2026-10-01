"""只读盘点（`TAIL-210`）：① **技术词上屏**逐行；② **重复句**（这次把模板噪声筛掉）。

⚠️ 只读、不判、不改。判"删/留"按 `D29` ＋ 守则 §2.5（用业务术语）/ §3.3（黑话不入界面）。
⚠️ 剥注释后再扫（壳里这些词**绝大多数只活在注释里**）。
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

# ── ① 技术词逐行 ───────────────────────────────────────────────────────────
#: ⚠️ 只列**用户可见**的落点：排除 `data-act=` / `class=` / `id=` / `style=` 这些属性里的英文与 `apiCode` 之类的**代码取值**
TERMS = ("后端", "接口", "落库", "解析", "幂等", "路由", "缓存", "管线", "字段名", "SQL")
print("══ ① 技术词命中（剥注释 · ⛔ 含属性里的也会列出，请人一眼认掉）")
hit: dict[str, list[str]] = collections.defaultdict(list)
for name, text in PAGES:
    for i, raw in enumerate(text.splitlines(), 1):
        for t in TERMS:
            if t in raw:
                hit[t].append(f"{name}:{i}  {plain(raw)[:118]}")
                break
for t in TERMS:
    if hit[t]:
        print(f"\n   ── 「{t}」（{len(hit[t])} 行）")
        for h in hit[t][:14]:
            print("      ", h)
print(f"\n   合计 {sum(len(v) for v in hit.values())} 行")

# ── ② 重复句（筛掉模板噪声）──────────────────────────────────────────────
print("\n══ ② 重复句（≥14 字 · 已筛掉含 `{…}`／`<…>` 的模板片段）")
counter: collections.Counter = collections.Counter()
where: dict[str, list[str]] = collections.defaultdict(list)
for name, text in PAGES:
    for m in re.finditer(r">([^<>{}]{14,240})<", text):
        t = plain(m.group(1))
        if len(t) < 14 or "…" in t or "${" in t:
            continue
        if not re.search(r"[\u4e00-\u9fff]", t):        # 必须含中文（挡掉纯符号/英文片段）
            continue
        counter[t] += 1
        where[t].append(f"{name}:{text[:m.start()].count(chr(10)) + 1}")
dup = [(t, n) for t, n in counter.items() if n >= 2]
print(f"   共 {len(dup)} 句重复 · 合计多出 {sum(n - 1 for _, n in dup)} 处")
for t, n in sorted(dup, key=lambda kv: (-kv[0].__len__(), -kv[1])):
    print(f"   ×{n}  {t[:76]}")
    if n <= 4:
        print(f"        位置：{' · '.join(where[t])}")
sys.exit(0)
